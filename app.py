# app.py
from flask import Flask, render_template, request, send_file
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = Flask(__name__)

def get_video_id(url):
    # Extrae el ID del video de la URL de YouTube
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en'])
        return '\n'.join([entry['text'] for entry in transcript_list])
    except Exception as e:
        return f"Error al obtener la transcripción: {str(e)}"

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    url = request.form['url']
    video_id = get_video_id(url)
    
    if not video_id:
        return "URL de YouTube inválida", 400
        
    transcript = get_transcript(video_id)
    
    # Guardar la transcripción en un archivo temporal
    with open('transcript.txt', 'w', encoding='utf-8') as f:
        f.write(transcript)
    
    return send_file('transcript.txt',
                     mimetype='text/plain',
                     as_attachment=True,
                     download_name='transcripcion.txt')

if __name__ == '__main__':
    app.run(debug=True)
    
if __name__ == '__main__':
    # Development
    app.run(debug=False)
else:
    # Production
    app.run(host='0.0.0.0', port=10000)
