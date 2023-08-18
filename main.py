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


app.config.from_object(config.config['development'])


oauth.init_app(app)
sqla.init_app(app)
login_manager.init_app(app)
app.register_blueprint(auth.bp)


@app.route('/')
@login_required
def index():

    return render_template('index.html')


@app.route('/uploader', methods = ['GET', 'POST'])
@login_required
def uploader():
    torch.cuda.init()
    device = "cpu"
    if request.method == 'POST':
        mpath = path.join(app.root_path, 'static', 'uploads',str(session['Cliente']))
        if not os.path.exists(mpath):
               os.makedirs(mpath)
        file = request.files['archivo']
        filename = secure_filename(file.filename)
        fpath = path.join(mpath,filename)
        file.save(fpath)

        nombre = file.filename.split('.')[0]
        tipo = file.filename.split('.')[-1]
        print(tipo)
        sonido = nombre + ".mp3"
        spath = path.join(mpath, sonido)


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
        transfile = path.join(mpath,nombre +".txt")
        with open(transfile, 'w+', encoding="utf-8") as f:
            f.write(result["text"])

        formatear_texto(transfile)


        return 'File uploaded and proceed successfully'
   
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
