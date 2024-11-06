# app.py
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from google.cloud import speech_v1
from google.cloud import storage
from pytube import YouTube
import os
from pydub import AudioSegment
import io

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuración de Google Cloud
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/your/credentials.json"

def download_audio(url):
    try:
        # Descarga el audio del video de YouTube
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        # Descarga el archivo de audio
        audio_file = audio_stream.download(filename="temp_audio")
        
        # Convertir a formato compatible con Google Speech-to-Text
        audio = AudioSegment.from_file(audio_file)
        audio = audio.set_channels(1)  # Mono
        audio = audio.set_frame_rate(16000)  # 16kHz
        
        # Guardar como WAV
        wav_io = io.BytesIO()
        audio.export(wav_io, format='wav')
        
        os.remove(audio_file)  # Limpieza
        return wav_io
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None

def transcribe_audio(audio_content):
    client = speech_v1.SpeechClient()
    
    # Configuración para el reconocimiento
    config = speech_v1.RecognitionConfig(
        language_code="es-ES",  # Puedes cambiar el idioma según necesites
        enable_automatic_punctuation=True,
        audio_channel_count=1,
        sample_rate_hertz=16000,
    )

    # Crear el objeto audio
    audio = speech_v1.RecognitionAudio(content=audio_content.getvalue())

    try:
        # Para archivos largos, usar reconocimiento asíncrono
        operation = client.long_running_recognize(config=config, audio=audio)
        response = operation.result()

        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + "\n"
        
        return transcript
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        return None

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        url = request.form['url']
        
        # Descargar audio
        audio_content = download_audio(url)
        if not audio_content:
            flash('Error al descargar el audio del video.', 'error')
            return redirect(url_for('home'))
        
        # Transcribir
        transcript = transcribe_audio(audio_content)
        if not transcript:
            flash('Error durante la transcripción.', 'error')
            return redirect(url_for('home'))
        
        # Guardar la transcripción
        with open('transcript.txt', 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        return send_file('transcript.txt',
                        mimetype='text/plain',
                        as_attachment=True,
                        download_name='transcripcion.txt')
                        
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
