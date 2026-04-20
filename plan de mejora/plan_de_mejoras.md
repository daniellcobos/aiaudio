# Plan de Mejoras — FocusIA
**Fecha:** 15 de abril de 2026  
**Autor:** Plan generado por análisis del codebase actual  
**Versión actual:** MVP funcional (transcripción de audio/video con IA)

---

## Contexto general

FocusIA es una plataforma para analizar sesiones de focus groups mediante IA. Actualmente permite subir archivos de audio/video y transcribirlos usando el modelo `gpt-4o-transcribe` de OpenAI. La app tiene autenticación por usuario/contraseña y OAuth con Google.

Es una herramienta de uso personal, por lo que no se requiere persistencia en base de datos ni historial multi-usuario para las transcripciones.

---

## FASE 1 — Seguridad y estabilidad crítica
> **Prioridad: URGENTE** — antes de cualquier nueva funcionalidad

### 1.1 Mover credenciales a variables de entorno ✅
- Credenciales movidas a `.env`: `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `DATABASE_URL`, `OPENAI_API_KEY`.
- `config.py` actualizado para leer con `os.getenv()` vía `python-dotenv`.
- `.gitignore` creado en la raíz con `.env` incluido.

### 1.2 Validación y seguridad en subida de archivos — No aplica
- Herramienta de uso personal. `secure_filename()` ya cubre el único riesgo relevante.

### 1.3 Manejo de errores en llamadas a la API ✅
- `transcribir_chunk` maneja: `RateLimitError`, `APIConnectionError`, `BadRequestError`, `APIStatusError` con mensajes claros.
- `transcribir` usa `try/finally` para garantizar limpieza de temporales incluso si hay error.
- `uploader` captura errores y devuelve JSON con descripción en lugar de romper la app.

### 1.4 Desactivar modo debug en producción ✅
- `config.py` tiene `DevelopmentConfig` (DEBUG=True) y `ProductionConfig` (DEBUG=False).
- `main.py` lee `FLASK_ENV` del `.env` para elegir la config. Por defecto usa `production` si no está definido.
- Para pasar a producción basta con cambiar `FLASK_ENV=production` en el `.env`.

---

## FASE 2 — Procesamiento de audio ✅ COMPLETADO
> Automatización del corte y transcripción de archivos largos

### 2.1 Corte automático de audio ✅
- **Problema:** OpenAI tiene un límite de 1400 segundos por archivo. Antes el corte se hacía manualmente en Audacity.
- **Solución implementada:** `split_audio_chunks()` detecta la duración con `ffmpeg.probe()` y divide automáticamente en fragmentos de 1200s si supera el límite.

### 2.2 Extracción de audio de video ✅
- **Problema:** Archivos MP4 de hasta 1.4GB se enviaban completos, haciendo el proceso muy lento.
- **Solución implementada:** `extraer_audio_mp3()` extrae solo el audio como MP3 mono a 64k antes de procesar, reduciendo el tamaño hasta 4x.

### 2.3 Transcripción paralela de fragmentos ✅
- **Problema:** Los fragmentos se enviaban a OpenAI uno por uno, multiplicando el tiempo de espera.
- **Solución implementada:** `ThreadPoolExecutor` envía todos los fragmentos a OpenAI simultáneamente. Para un archivo de ~90 min (5 fragmentos), el tiempo de transcripción bajó de ~9 min a ~2 min.

### 2.4 Un solo archivo de salida ✅
- **Problema:** El programa generaba dos archivos `.txt` (crudo y formateado).
- **Solución implementada:** El texto se formatea en memoria antes de escribir, generando un único archivo con saltos de línea por oraciones.

### 2.5 Limpieza automática de archivos temporales ✅
- **Solución implementada:** El video original y los chunks MP3 intermedios se eliminan automáticamente al finalizar la transcripción. La carpeta `temp` solo conserva el `.txt` final.

---

## FASE 3 — Experiencia de usuario (UX)
> **Prioridad: ALTA** — actualmente no hay feedback ni resultados visibles en la UI

### 3.1 Indicador de progreso durante la transcripción ✅
- Overlay oscuro con spinner y mensaje "Transcribiendo... esto puede demorar varios minutos" mientras se procesa.

### 3.2 Visualización del resultado en pantalla ✅
- El texto transcripto aparece directamente en la página al finalizar, en un área scrolleable.
- Botón "Copiar" al portapapeles y botón "Descargar .txt".
- Backend devuelve JSON con `transcripcion` y `nombre` en lugar de texto plano.

### 3.3 Notificaciones claras de éxito y error ✅
- SweetAlert2 integrado en index.html para confirmar éxito y mostrar errores con descripción.
- El AJAX fue corregido para usar FormData correctamente (antes enviaba un FileList vacío).

---

## FASE 4 — Análisis con IA (core del producto)
> **Prioridad: MEDIA-ALTA** — diferenciador clave de FocusIA

### 4.1 Resumen automático ✅
- `generar_resumen()`: GPT-4o genera 3 párrafos (contexto, hallazgos, conclusiones).

### 4.2 Extracción de temas clave ✅
- `extraer_temas()`: GPT-4o identifica 5-8 temas con descripción breve en formato de lista.

### 4.3 Análisis de sentimiento ✅
- `analizar_sentimiento()`: GPT-4o clasifica el tono general e identifica momentos de acuerdo y tensión.

### 4.4 Identificación de participantes ✅
- `identificar_participantes()`: GPT-4o reformatea la transcripción etiquetando turnos de voz ([Participante 1], [Participante 2], etc.) por cambios de perspectiva o tono.

### 4.5 Generación de reportes en PDF
- Pendiente.

**Implementación:** Los 4 análisis se ejecutan en paralelo con `ThreadPoolExecutor` después de la transcripción. La UI muestra los resultados en 5 pestañas: Transcripción, Resumen, Temas clave, Sentimiento y Participantes.

---

## FASE 5 — Calidad de código ✅ COMPLETADO

### 5.1 Manejo de errores robusto ✅
- El pipeline ya tenía `try/except/finally` en `transcribir()` y `uploader()`.
- **Bug corregido:** la carpeta `textos/` ahora se crea con `os.makedirs(..., exist_ok=True)` antes de escribir el `.txt` (antes fallaba si no existía).
- `logger.error(..., exc_info=True)` en errores inesperados para incluir el traceback completo en los logs.

### 5.2 Logging estructurado ✅
- Reemplazados todos los `print()` por `logging` con formato `HH:MM:SS [LEVEL] mensaje`.
- Mensajes INFO para el progreso del pipeline, ERROR para fallos.

---

## Roadmap resumido

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Seguridad y estabilidad crítica | ✅ Completado |
| 2 | Procesamiento de audio | ✅ Completado |
| 3 | Experiencia de usuario (UX) | ✅ Completado |
| 4 | Análisis con IA | En progreso (4/5) |
| 5 | Calidad de código | ✅ Completado |
