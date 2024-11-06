from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from google.cloud import speech_v1
from google.oauth2 import service_account
from pytube import YouTube
import os
import json
from pydub import AudioSegment
import io
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

def get_credentials():
    logger.debug("Intentando obtener credenciales...")
    creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_json:
        logger.error("No se encontraron credenciales en las variables de entorno")
        return None
    
    try:
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        logger.debug("Credenciales cargadas exitosamente")
        return credentials
    except Exception as e:
        logger.error(f"Error al cargar credenciales: {str(e)}")
        return None

def download_audio(url):
    logger.debug(f"Intentando descargar audio de: {url}")
    try:
        yt = YouTube(url)
        logger.debug(f"Título del video: {yt.title}")
        
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            logger.error("No se encontró stream de audio")
            return None
            
        buffer = io.BytesIO()
        audio_stream.stream_to_buffer(buffer)
        buffer.seek(0)
        
        logger.debug("Convirtiendo audio...")
        audio = AudioSegment.from_file(buffer, format="mp4")
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
        
        wav_io = io.BytesIO()
        audio.export(wav_io, format='wav')
        wav_io.seek(0)
        
        logger.debug("Audio descargado y convertido exitosamente")
        return wav_io
    except Exception as e:
        logger.error(f"Error en download_audio: {str(e)}")
        raise Exception(f"Error al descargar el audio: {str(e)}")

def transcribe_audio(audio_content):
    logger.debug("Iniciando transcripción...")
    credentials = get_credentials()
    if not credentials:
        raise Exception("No se pudieron cargar las credenciales")
    
    client = speech_v1.SpeechClient(credentials=credentials)
    
    config = speech_v1.RecognitionConfig(
        language_code="es-ES",
        enable_automatic_punctuation=True,
        audio_channel_count=1,
        sample_rate_hertz=16000,
    )

    audio = speech_v1.RecognitionAudio(content=audio_content.getvalue())

    try:
        logger.debug("Enviando audio a Google Speech-to-Text...")
        operation = client.long_running_recognize(config=config, audio=audio)
        logger.debug("Esperando respuesta...")
        response = operation.result()

        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + "\n"
        
        logger.debug("Transcripción completada exitosamente")
        return transcript
    except Exception as e:
        logger.error(f"Error en transcribe_audio: {str(e)}")
        raise Exception(f"Error en la transcripción: {str(e)}")

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        url = request.form.get('url')
        if not url:
            logger.error("No se proporcionó URL")
            flash('Por favor, proporciona una URL de YouTube válida.', 'error')
            return redirect(url_for('home'))

        logger.info(f"Procesando URL: {url}")
        
        # Descargar audio
        audio_content = download_audio(url)
        if not audio_content:
            flash('No se pudo descargar el audio del video.', 'error')
            return redirect(url_for('home'))
        
        # Transcribir
        transcript = transcribe_audio(audio_content)
        if not transcript:
            flash('No se pudo generar la transcripción.', 'error')
            return redirect(url_for('home'))
        
        # Guardar la transcripción
        with open('transcript.txt', 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        return send_file('transcript.txt',
                        mimetype='text/plain',
                        as_attachment=True,
                        download_name='transcripcion.txt')
                        
    except Exception as e:
        logger.error(f"Error en /transcribe: {str(e)}")
        flash(str(e), 'error')
        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=False)
