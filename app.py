from flask import Flask, render_template, request, send_file, jsonify
import pafy
import os
import logging
from urllib.parse import urlparse, parse_qs
import tempfile
import shutil

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_video_id(url):
    """Extraer el ID del video de una URL de YouTube."""
    if 'youtu.be' in url:
        return url.split('/')[-1]
    query = urlparse(url)
    if query.hostname == 'www.youtube.com' or query.hostname == 'youtube.com':
        if query.path == '/watch':
            return parse_qs(query.query)['v'][0]
    return None

def download_audio(url):
    """Descargar el audio usando pafy."""
    logger.debug(f"Iniciando descarga de: {url}")
    
    # Crear directorio temporal
    temp_dir = tempfile.mkdtemp()
    try:
        # Obtener video
        video = pafy.new(url)
        logger.debug(f"Título del video: {video.title}")
        
        # Obtener el mejor stream de audio
        audio = video.getbestaudio()
        logger.debug(f"Stream de audio seleccionado: {audio.extension}, {audio.bitrate}")
        
        # Nombre de archivo seguro
        safe_title = "".join(x for x in video.title if x.isalnum() or x in (' ', '-', '_')).rstrip()
        filename = os.path.join(temp_dir, f"{safe_title}.{audio.extension}")
        
        # Descargar audio
        logger.debug(f"Descargando a: {filename}")
        audio.download(filepath=filename, quiet=False)
        
        return filename, safe_title
        
    except Exception as e:
        logger.error(f"Error en la descarga: {str(e)}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise Exception(f"Error al descargar el audio: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    temp_dir = None
    try:
        url = request.form.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Por favor, proporciona una URL de YouTube'}), 400
            
        # Validar URL
        video_id = get_video_id(url)
        if not video_id:
            return jsonify({'error': 'URL de YouTube inválida'}), 400

        try:
            output_file, title = download_audio(url)
            
            return send_file(
                output_file,
                as_attachment=True,
                download_name=f"{title}.mp3",
                mimetype='audio/mp3'
            )
            
        except Exception as e:
            logger.error(f"Error durante la descarga: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    finally:
        # Limpiar archivos temporales
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Error limpiando directorio temporal: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)