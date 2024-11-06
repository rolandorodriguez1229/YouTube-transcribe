from flask import Flask, render_template, request, send_file
from pytube import YouTube
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_audio():
    url = request.form['url']
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        output_file = audio_stream.download()
        base, ext = os.path.splitext(output_file)
        new_file = base + '.mp3'
        os.rename(output_file, new_file)
        return send_file(new_file, as_attachment=True)
    except Exception as e:
        return f"Error al descargar el audio: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)