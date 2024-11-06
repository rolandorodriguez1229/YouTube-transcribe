from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from google.cloud import speech_v1
from google.oauth2 import service_account
import yt_dlp
import os
import json
import logging
import tempfile

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
    
    # Configuración actualizada para yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'outtmpl': 'temp_%(id)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
        # Configuración anti-bot
        'extract_flat': False,
        'writesubtitles': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
                'player_skip': ['webpage', 'config', 'js'],
            }
        },
        # Configuración de red
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
            
            with open(output_file, 'rb') as f:
                audio_content = f.read()
            
            os.remove(output_file)
            logger.debug("Audio descargado exitosamente")
            return audio_content
            
    except Exception as e:
        logger.error(f"Error detallado en download_audio: {str(e)}")
        # Intentar limpiar archivos temporales si existen
        try:
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
        enable_word_time_offsets=True,  # Para obtener timestamps
    )

    # Convertir el contenido de bytes a objeto RecognitionAudio
    audio = speech_v1.RecognitionAudio(content=audio_content)

    try:
        logger.debug("Enviando audio a Google Speech-to-Text...")
        operation = client.long_running_recognize(config=config, audio=audio)
        logger.debug("Esperando respuesta...")
        response = operation.result()

        # Formato de transcripción con timestamps
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

@app.route('/test_ffmpeg')
def test_ffmpeg():
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return f"FFmpeg está instalado correctamente:\n{result.stdout}"
    except Exception as e:
        return f"Error al verificar FFmpeg: {str(e)}"

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
        try:
            audio_content = download_audio(url)
            if not audio_content:
                flash('No se pudo descargar el audio del video.', 'error')
                return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error al descargar el audio: {str(e)}', 'error')
            return redirect(url_for('home'))
        
        # Transcribir
        try:
            transcript = transcribe_audio(audio_content)
            if not transcript:
                flash('No se pudo generar la transcripción.', 'error')
                return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error en la transcripción: {str(e)}', 'error')
            return redirect(url_for('home'))
        
        # Guardar la transcripción en un archivo temporal
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                f.write(transcript)
                temp_file_name = f.name
            
            return send_file(
                temp_file_name,
                mimetype='text/plain',
                as_attachment=True,
                download_name='transcripcion.txt'
            )
        except Exception as e:
            flash(f'Error al guardar la transcripción: {str(e)}', 'error')
            return redirect(url_for('home'))
                        
    except Exception as e:
        logger.error(f"Error general en /transcribe: {str(e)}")
        flash(f'Error inesperado: {str(e)}', 'error')
        return redirect(url_for('home'))
    finally:
        # Limpiar archivos temporales
        if 'temp_file_name' in locals():
            try:
                os.remove(temp_file_name)
            except:
                pass

if __name__ == '__main__':
    app.run(debug=False)
