from flask import Flask, render_template, request, jsonify, send_file
import os
from pydub import AudioSegment
from dotenv import load_dotenv
import tempfile
from werkzeug.utils import secure_filename
import io
from openai import OpenAI
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'temp_files'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Verificar API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    logger.error("No se encontró OPENAI_API_KEY en las variables de entorno")
else:
    logger.info("OPENAI_API_KEY encontrada")

# Inicializar cliente de OpenAI con manejo de errores
try:
    client = OpenAI(api_key=api_key)
    logger.info("Cliente OpenAI inicializado correctamente")
except Exception as e:
    logger.error(f"Error al inicializar cliente OpenAI: {str(e)}")
    client = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check')
def check_config():
    """Ruta para verificar la configuración"""
    return jsonify({
        'api_key_exists': bool(api_key),
        'api_key_length': len(api_key) if api_key else 0,
        'client_initialized': client is not None,
        'upload_folder': os.path.exists(app.config['UPLOAD_FOLDER']),
        'current_directory': os.getcwd(),
        'files_in_temp': os.listdir(app.config['UPLOAD_FOLDER'])
    })

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    logger.info("Iniciando solicitud de transcripción")
    
    if not client:
        logger.error("Cliente OpenAI no inicializado")
        return jsonify({'error': 'OpenAI client not initialized'}), 500

    if 'file' not in request.files:
        logger.error("No se encontró archivo en la solicitud")
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.error("Nombre de archivo vacío")
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.mp3'):
        logger.error("Archivo no es MP3")
        return jsonify({'error': 'Only MP3 files are supported'}), 400

    try:
        filename = secure_filename(file.filename)
        base_filename = os.path.splitext(filename)[0]
        
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"Guardando archivo en: {temp_path}")
        file.save(temp_path)
        
        logger.info("Iniciando transcripción con OpenAI")
        with open(temp_path, 'rb') as audio_file:
            try:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es"
                )
                logger.info("Transcripción completada exitosamente")
            except Exception as e:
                logger.error(f"Error en la transcripción de OpenAI: {str(e)}")
                raise
        
        transcription = transcript.text
        txt_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_filename}.txt")
        
        logger.info(f"Guardando transcripción en: {txt_path}")
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(transcription)
        
        logger.info("Limpiando archivo temporal de audio")
        os.unlink(temp_path)
        
        return jsonify({
            'transcription': transcription,
            'filename': f"{base_filename}.txt"
        })
    
    except Exception as e:
        logger.error(f"Error durante el proceso: {str(e)}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        logger.info(f"Intentando descargar: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Archivo no encontrado: {file_path}")
            return jsonify({'error': 'File not found'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        mem_file = io.BytesIO()
        mem_file.write(content.encode('utf-8'))
        mem_file.seek(0)
        
        os.unlink(file_path)
        logger.info(f"Archivo descargado y eliminado: {file_path}")
        
        return send_file(
            mem_file,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    except Exception as e:
        logger.error(f"Error en la descarga: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)