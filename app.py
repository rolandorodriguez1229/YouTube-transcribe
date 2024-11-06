from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from google.cloud import speech_v1
from google.oauth2 import service_account
import yt_dlp
import os
import json
import logging
import tempfile
from datetime import datetime

# Configurar logging más detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Diccionario para almacenar el estado de las transcripciones
transcription_status = {}

def update_status(task_id, status, message):
    transcription_status[task_id] = {
        'status': status,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    logger.debug(f"Status actualizado - ID: {task_id}, Status: {status}, Message: {message}")

def download_audio(url, task_id):
    update_status(task_id, 'downloading', 'Iniciando descarga del audio...')
    logger.debug(f"Intentando descargar audio de: {url}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'outtmpl': f'temp_{task_id}_%(id)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
        'progress_hooks': [lambda d: logger.debug(f"Progreso descarga: {d.get('status', 'unknown')}")],
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
            update_status(task_id, 'downloading', 'Obteniendo información del video...')
            info = ydl.extract_info(url, download=True)
            output_file = f"temp_{task_id}_{info['id']}.wav"
            
            if not os.path.exists(output_file):
                raise Exception(f"El archivo {output_file} no se creó correctamente")
            
            update_status(task_id, 'processing', 'Leyendo archivo de audio...')
            with open(output_file, 'rb') as f:
                audio_content = f.read()
            
            os.remove(output_file)
            update_status(task_id, 'downloaded', 'Audio descargado exitosamente')
            return audio_content
            
    except Exception as e:
        error_msg = f"Error en download_audio: {str(e)}"
        logger.error(error_msg)
        update_status(task_id, 'error', error_msg)
        cleanup_temp_files(task_id)
        raise Exception(error_msg)

def cleanup_temp_files(task_id):
    try:
        for f in os.listdir('.'):
            if f.startswith(f'temp_{task_id}'):
                os.remove(f)
    except Exception as e:
        logger.error(f"Error limpiando archivos temporales: {str(e)}")

def transcribe_audio(audio_content, task_id):
    update_status(task_id, 'transcribing', 'Iniciando transcripción...')
    logger.debug("Cargando credenciales...")
    
    credentials = get_credentials()
    if not credentials:
        error_msg = "No se pudieron cargar las credenciales"
        update_status(task_id, 'error', error_msg)
        raise Exception(error_msg)
    
    client = speech_v1.SpeechClient(credentials=credentials)
    
    config = speech_v1.RecognitionConfig(
        language_code="es-ES",
        enable_automatic_punctuation=True,
        audio_channel_count=1,
        enable_word_time_offsets=True,
    )

    update_status(task_id, 'transcribing', 'Enviando audio a Google Speech-to-Text...')
    audio = speech_v1.RecognitionAudio(content=audio_content)

    try:
        operation = client.long_running_recognize(config=config, audio=audio)
        update_status(task_id, 'transcribing', 'Procesando audio...')
        
        # Monitorear el progreso
        while not operation.done():
            update_status(task_id, 'transcribing', 'Transcripción en proceso...')
            operation.result(timeout=10)
        
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
        
        update_status(task_id, 'completed', 'Transcripción completada exitosamente')
        return transcript

    except Exception as e:
        error_msg = f"Error en transcribe_audio: {str(e)}"
        logger.error(error_msg)
        update_status(task_id, 'error', error_msg)
        raise Exception(error_msg)

@app.route('/status/<task_id>')
def get_status(task_id):
    status = transcription_status.get(task_id, {
        'status': 'unknown',
        'message': 'Tarea no encontrada'
    })
    return jsonify(status)

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({
                'status': 'error',
                'message': 'Por favor, proporciona una URL de YouTube válida.'
            })

        logger.info(f"Procesando URL: {url}")
        update_status(task_id, 'started', 'Iniciando proceso...')
        
        try:
            audio_content = download_audio(url, task_id)
            if not audio_content:
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo descargar el audio del video.'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error al descargar el audio: {str(e)}'
            })
        
        try:
            transcript = transcribe_audio(audio_content, task_id)
            if not transcript:
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo generar la transcripción.'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error en la transcripción: {str(e)}'
            })
        
        temp_file_name = None
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
            return jsonify({
                'status': 'error',
                'message': f'Error al guardar la transcripción: {str(e)}'
            })
                        
    except Exception as e:
        error_msg = f"Error general: {str(e)}"
        logger.error(error_msg)
        update_status(task_id, 'error', error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        })
    finally:
        cleanup_temp_files(task_id)
        if 'temp_file_name' in locals() and temp_file_name:
            try:
                os.remove(temp_file_name)
            except:
                pass

if __name__ == '__main__':
    app.run(debug=False)
