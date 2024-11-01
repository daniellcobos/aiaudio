from flask import Flask, render_template,jsonify,request,session
from flask_cors import CORS
import requests,openai,os

from random import randrange
from os import path
import os
#import magic
import urllib.request
from flask import Flask, flash, request, redirect, render_template, jsonify
from werkzeug.utils import secure_filename
from oauth import oauth
from sqla import sqla
from login import login_manager
import whisper
from flask_login import login_required
import auth as auth
import config
import torch

app = Flask(__name__, static_url_path = '/static')
CORS(app)
import openai
app.config.from_object(config.config['development'])

API = app.config['OPENAI_API_KEY']
oauth.init_app(app)
sqla.init_app(app)
login_manager.init_app(app)
app.register_blueprint(auth.bp)

client = openai.OpenAI(api_key=API)

@app.route('/')

def index():

    return render_template('index.html')


@app.route('/uploader', methods = ['GET', 'POST'])

def uploader():
    torch.cuda.init()
    device = "cuda"
    if request.method == 'POST':
        mpath = path.join(app.root_path, 'static', 'uploads',str("temp"))
        if not os.path.exists(mpath):
               os.makedirs(mpath)
        uploaded_files = request.files.getlist("archivo")
        for file in uploaded_files:

            nombre = file.filename.split('.')[0]
            filename = secure_filename(file.filename)
            fpath = path.join(mpath, filename)
            file.save(fpath)
            audio_file = open(fpath, "rb")
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            transfile = path.join(mpath, 'textos', nombre + ".txt")
            with open(transfile, 'w+', encoding="utf-8") as f:
                f.write(transcript)
            formatear_texto(transfile)

            """

            print("Cargando" + file.filename)
            filename = secure_filename(file.filename)
            fpath = path.join(mpath,filename)
            file.save(fpath)

            nombre = file.filename.split('.')[0]
            tipo = file.filename.split('.')[-1]

            sonido = nombre + ".mp3"
            spath = path.join(mpath, sonido)
            tipo = tipo.lower()
            if ( tipo != "mp3" ):

                import moviepy.editor
                #Load the Video
                movie = moviepy.editor.VideoFileClip(fpath)

                #Extract the Audio
                audio = movie.audio

                #Export the Audio
                audio.write_audiofile(spath)




            print("cargando modelo")
            model = whisper.load_model("small").to(device)
            print("transcribiendo")
            result = model.transcribe(spath)

            print(result["text"])
            transfile = path.join(mpath,'textos',nombre +".txt")
            with open(transfile, 'w+', encoding="utf-8") as f:
                f.write(result["text"])
            
            formatear_texto(transfile)

             """

        return 'Files uploaded and proceed successfully'
   
def formatear_texto(transfile):
    # The file is read and its data is stored
    data = open(transfile, 'r',encoding="utf-8").read()
    
    data = data.replace('?', '?\n')
    data = data.replace('.', '.\n')
    
    # Displaying the resultant data
    print(data)    

    fdir = path.dirname(transfile)
    ffile = "Formato_" + path.basename(transfile)
    frpath = path.join(fdir,ffile)
    with open(frpath, 'w+',encoding="utf-8") as f:
        f.write(data)    



if __name__ == '__main__':
    app.run(debug=True)
