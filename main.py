from flask_cors import CORS
from os import path
import os
import math
import logging
import ffmpeg
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, flash, request, redirect, render_template, jsonify
from werkzeug.utils import secure_filename
from oauth import oauth
from sqla import sqla
from login import login_manager
import auth as auth
import config

app = Flask(__name__, static_url_path = '/static')
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
import openai
env = os.getenv('FLASK_ENV', 'production')
app.config.from_object(config.config[env])

API = app.config['OPENAI_API_KEY']
oauth.init_app(app)
sqla.init_app(app)
login_manager.init_app(app)
app.register_blueprint(auth.bp)

client = openai.OpenAI(api_key=API)

CHUNK_DURATION = 1200  # 20 minutos por fragmento, por debajo del límite de 1400s de OpenAI

def get_duration(filepath):
    probe = ffmpeg.probe(filepath)
    return float(probe['format']['duration'])

def extraer_audio_mp3(filepath):
    """Si el archivo es video, extrae el audio como MP3 mono 64k (más liviano).
    Devuelve (ruta_mp3, es_video). Si ya es audio, devuelve (filepath, False)."""
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg'}
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return filepath, False

    mp3_path = os.path.splitext(filepath)[0] + '_audio.mp3'
    logger.info("[1/3] Extrayendo audio (%.1f MB)...", os.path.getsize(filepath) / 1024 / 1024)
    """los parentesis aqui son para continuar la cadena de comandos de ffmpeg sin necesidad de usar '\' al final de cada linea, 
    lo que mejora la legibilidad y evita errores de sintaxis. 
    Es una forma común en Python de escribir comandos largos o encadenados de manera clara."""
    (
        ffmpeg
        .input(filepath) # toma el archivo de video como entrada con ffmpeg
        .output(mp3_path, acodec='libmp3lame', audio_bitrate='64k', ac=1, vn=None) #Lo convierte a MP3 con codec libmp3lame, bitrate de 64k, mono (ac=1), sin video (vn=None)
        .overwrite_output() # sobreescribe el archivo de salida si ya existe
        .run(quiet=True) # ejecuta el comando en silencio
    )
    logger.info("      Audio extraido: %.1f MB", os.path.getsize(mp3_path) / 1024 / 1024)
    return mp3_path, True

def split_audio_chunks(filepath):
    """Divide el archivo en fragmentos de CHUNK_DURATION segundos si supera el límite.
    Devuelve lista de rutas: [filepath] si no hace falta dividir, o [chunk1, chunk2, ...] si sí."""
    try:
        duration = get_duration(filepath)
    except ffmpeg.Error:
        return [filepath]

    logger.info("[2/3] Duracion: %.0fs (%.1f min)", duration, duration / 60)

    if duration <= 1300:
        logger.info("      Sin necesidad de dividir.")
        return [filepath]

    base = os.path.splitext(filepath)[0]
    num_chunks = math.ceil(duration / CHUNK_DURATION)
    logger.info("      Dividiendo en %d fragmentos...", num_chunks)
    chunks = []

    """ este bloque divide el audio en fragmentos (chunks)"""
    for i in range(num_chunks):
        chunk_path = f"{base}_chunk{i + 1}.mp3"
        (
            ffmpeg
            .input(filepath, ss=i * CHUNK_DURATION, t=CHUNK_DURATION)
            .output(chunk_path, acodec='libmp3lame', audio_bitrate='64k', ac=1)
            .overwrite_output()
            .run(quiet=True)
        )
        chunks.append(chunk_path)

    return chunks

def transcribir_chunk(chunk, indice, total):
    """Transcribe un único fragmento. Diseñado para ejecutarse en paralelo."""
    logger.info("      Transcribiendo fragmento %d/%d...", indice + 1, total)
    try:
        with open(chunk, 'rb') as f:
            resultado = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=f,
                response_format="text"
            )
        return indice, resultado
    except openai.RateLimitError:
        raise RuntimeError(f"Fragmento {indice + 1}: límite de uso de OpenAI alcanzado. Intentá más tarde.")
    except openai.APIConnectionError:
        raise RuntimeError(f"Fragmento {indice + 1}: no se pudo conectar con OpenAI. Verificá tu conexión.")
    except openai.BadRequestError as e:
        raise RuntimeError(f"Fragmento {indice + 1}: archivo rechazado por OpenAI — {e}")
    except openai.APIStatusError as e:
        raise RuntimeError(f"Fragmento {indice + 1}: error de OpenAI ({e.status_code}) — {e.message}")

def transcribir(filepath):
    """Transcribe un archivo de audio/video con extracción y procesamiento paralelo."""
    audio_path, es_video = None, False
    chunks = []

    try:
        # Paso 1: extraer audio si es video
        audio_path, es_video = extraer_audio_mp3(filepath)

        # Paso 2: dividir si supera el límite
        chunks = split_audio_chunks(audio_path)

        # Paso 3: transcribir todos los fragmentos en paralelo
        logger.info("[3/3] Transcribiendo %d fragmento(s) en paralelo...", len(chunks))
        resultados = [None] * len(chunks)

        with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            futuros = {
                executor.submit(transcribir_chunk, chunk, i, len(chunks)): i
                for i, chunk in enumerate(chunks)
            }
            for futuro in as_completed(futuros):
                indice, texto = futuro.result()
                resultados[indice] = texto

        logger.info("      Transcripcion completada.")
        return ' '.join(resultados)

    finally:
        # Limpiar siempre los archivos temporales, incluso si hubo un error
        for chunk in chunks:
            if chunk != audio_path and os.path.exists(chunk):
                os.remove(chunk)
        if es_video and audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


def analizar_transcripcion(texto):
    """Ejecuta resumen, temas, sentimiento e identificación de participantes en paralelo con GPT-4o."""

    system = "Eres un analista experto en focus groups. Responde siempre en español."

    def generar_resumen():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    "Genera un resumen ejecutivo de esta transcripción de focus group en exactamente 3 párrafos:\n"
                    "1. Contexto general de la sesión.\n"
                    "2. Principales hallazgos y opiniones expresadas.\n"
                    "3. Conclusiones clave.\n\n"
                    f"Transcripción:\n{texto}"
                )}
            ]
        )
        return resp.choices[0].message.content

    def extraer_temas():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    "Extrae los 5 a 8 temas principales discutidos en esta transcripción de focus group.\n"
                    "Para cada tema indicá: nombre del tema y una descripción breve de lo que se dijo.\n"
                    "Formato: lista con viñetas (•).\n\n"
                    f"Transcripción:\n{texto}"
                )}
            ]
        )
        return resp.choices[0].message.content

    def analizar_sentimiento():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    "Analiza el sentimiento de esta transcripción de focus group e indicá:\n"
                    "1. Clasificación general: positivo, negativo, neutro o mixto.\n"
                    "2. Momentos o temas de mayor acuerdo entre los participantes.\n"
                    "3. Momentos o temas de mayor tensión o desacuerdo.\n\n"
                    f"Transcripción:\n{texto}"
                )}
            ]
        )
        return resp.choices[0].message.content

    def identificar_participantes():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    "Analiza esta transcripción e identificá los distintos participantes o cambios de hablante.\n"
                    "Reformatea el texto etiquetando cada turno de voz con [Participante 1], [Participante 2], etc.\n"
                    "Basate en cambios de perspectiva, tema o tono para detectar los cambios de hablante.\n\n"
                    f"Transcripción:\n{texto}"
                )}
            ]
        )
        return resp.choices[0].message.content

    tareas = {
        "resumen": generar_resumen,
        "temas": extraer_temas,
        "sentimiento": analizar_sentimiento,
        "participantes": identificar_participantes,
    }

    logger.info("[4/4] Analizando transcripcion con IA (en paralelo)...")
    resultados = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futuros = {executor.submit(fn): nombre for nombre, fn in tareas.items()}
        for futuro in as_completed(futuros):
            nombre = futuros[futuro]
            try:
                resultados[nombre] = futuro.result()
            except Exception as e:
                logger.error("ERROR en analisis '%s': %s", nombre, e)
                resultados[nombre] = f"No se pudo generar este análisis: {e}"

    logger.info("      Analisis completado.")
    return resultados


@app.route('/')

def index():

    return render_template('index.html')


@app.route('/uploader', methods = ['GET', 'POST'])

def uploader():
    logger.info("Solicitud de transcripcion recibida")
    if request.method == 'POST':
        mpath = path.join(app.root_path, 'static', 'uploads', 'temp')
        os.makedirs(path.join(mpath, 'textos'), exist_ok=True)
        uploaded_files = request.files.getlist("archivo")
        for file in uploaded_files:
            nombre = file.filename.split('.')[0]
            filename = secure_filename(file.filename)
            fpath = path.join(mpath, filename)
            file.save(fpath)
            try:
                transcript = transcribir(fpath)
                texto_formateado = transcript.replace('?', '?\n').replace('.', '.\n')
                transfile = path.join(mpath, 'textos', nombre + ".txt")
                with open(transfile, 'w+', encoding="utf-8") as f:
                    f.write(texto_formateado)
                analisis = analizar_transcripcion(transcript)
            except RuntimeError as e:
                logger.error("ERROR en transcripcion: %s", e)
                return jsonify({"error": str(e)}), 500
            except Exception as e:
                logger.error("ERROR inesperado: %s", e, exc_info=True)
                return jsonify({"error": "Ocurrió un error inesperado durante la transcripción."}), 500
            finally:
                if os.path.exists(fpath):
                    os.remove(fpath)

        return jsonify({
            "transcripcion": texto_formateado,
            "nombre": nombre,
            "resumen": analisis.get("resumen", ""),
            "temas": analisis.get("temas", ""),
            "sentimiento": analisis.get("sentimiento", ""),
            "participantes": analisis.get("participantes", ""),
        })    



if __name__ == '__main__':
    app.run(debug=True)
