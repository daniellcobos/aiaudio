from flask import Flask, render_template,jsonify,request
from flask_cors import CORS
import requests,openai,os
from dotenv.main import load_dotenv
from random import randrange

import os
#import magic
import urllib.request
from flask import Flask, flash, request, redirect, render_template, jsonify
from werkzeug.utils import secure_filename
from os import path
import whisper


app = Flask(__name__, static_url_path = '/static')
CORS(app)

load_dotenv()

API = os.environ.get('OPENAI_API_KEY')

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/uploader', methods = ['GET', 'POST'])
def uploader():
    fpath = path.join(app.root_path, 'static', 'uploads')
    if not os.path.exists(fpath):
        os.makedirs(fpath)
    if request.method == 'POST':
        file = request.files['archivo']
        filename = secure_filename(file.filename)
        print(filename)
        fpath = path.join(app.root_path, 'static', 'uploads',filename)
        file.save(fpath)

        nombre = file.filename.split('.')[0]
        tipo = file.filename.split('.')[1]
        sonido = nombre + ".mp3"
        spath = path.join(app.root_path, 'static', 'uploads',sonido)



        if ( tipo != "mp3" ):

            import moviepy.editor
            #Load the Video
            movie = moviepy.editor.VideoFileClip(fpath)

            #Extract the Audio
            audio = movie.audio

            #Export the Audio
            print(spath)
            audio.write_audiofile(spath)





        model = whisper.load_model("large")
        print(spath)
        result = model.transcribe(spath)
        print(result["text"])

        with open('Transcripcion.txt', 'w') as f:
            f.write(result["text"])

        formatear_texto()


        return 'File uploaded and proceed successfully'
   
def formatear_texto():
    # The file is read and its data is stored
    data = open('Transcripcion.txt', 'r').read()
    
    data = data.replace('?', '?\n')
    data = data.replace('.', '.\n')
    
    # Displaying the resultant data
    print(data)    


    with open('_Transcripcion.txt', 'w') as f:
        f.write(data)    



if __name__ == '__main__':
    app.run(debug=True)
