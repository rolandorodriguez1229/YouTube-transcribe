from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from google.cloud import speech_v1
from google.oauth2 import service_account
import yt_dlp
import os
import json
import logging
import tempfile

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'outtmpl': 'temp_%(id)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'writesubtitles': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
                'player_skip': ['webpage', 'config', 'js'],
            }
        },
        'socket_timeout': 30,
        'retries': 3,
        'nocheckcertificate': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug("Obteniendo información del video...")
            info = ydl.extract_info(url, download=True)
            output_file = f"temp_{info['id']}.wav"
            
            if not os.path.exists(output_file):
                raise Exception(f"El archivo {output_file} no se creó correctamente")
            
            logger.debug("Leyendo archivo de audio...")
            with open(output_file, 'rb') as f:
                audio_content = f.read()
            
            os.remove(output_file)
            logger.debug("Audio descargado exitosamente")
            return audio_content
            
    except Exception as e:
        logger.error(f"Error en download_audio: {str(e)}")
        try:
            # Limpiar archivos temporales
            for f in os.listdir('.'):
                if f.startswith('temp_'):
                    os.remove(f)
        except:
            pass
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
        enable_word_time_offsets=True,
    )

    logger.debug("Enviando audio a Google Speech-to-Text...")
    audio = speech_v1.RecognitionAudio(content=audio_content)

    try:
        operation = client.long_running_recognize(config=config, audio=audio)
        logger.debug("Esperando respuesta...")
        response = operation.result()

        transcript = ""
        for result in response.results:
            alternative = result.alternatives[0]
            for word_info in alternative.words:
                word = word_info.word
                start_time = word_info.start_time.total_seconds()
                end_time = word_info.end_time.total_seconds()
                transcript += f"[{start_time:.2f}-{end_time:.2f}] {word} "
            transcript += "\n"
        
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
            return jsonify({
                'status': 'error',
                'message': 'Por favor, proporciona una URL de YouTube válida.'
            }), 400

        logger.info(f"Iniciando transcripción para URL: {url}")
        
        try:
            # Intentar descargar el audio
            logger.debug("Iniciando descarga de audio...")
            audio_content = download_audio(url)
            if not audio_content:
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo descargar el audio del video.'
                }), 400

            # Intentar transcribir
            logger.debug("Iniciando transcripción...")
            transcript = transcribe_audio(audio_content)
            if not transcript:
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo generar la transcripción.'
                }), 400

            # Crear archivo temporal
            logger.debug("Guardando transcripción...")
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                f.write(transcript)
                temp_file_name = f.name

            # Enviar archivo
            return send_file(
                temp_file_name,
                mimetype='text/plain',
                as_attachment=True,
                download_name='transcripcion.txt'
            )

        except Exception as e:
            logger.error(f"Error en el proceso: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    finally:
        # Limpiar archivos temporales
        if 'temp_file_name' in locals():
            try:
                os.remove(temp_file_name)
            except:
                pass

if __name__ == '__main__':
    app.run(debug=False)
