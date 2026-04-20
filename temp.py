"""
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