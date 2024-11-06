from flask import Flask, render_template, request, send_file, jsonify
from pytube import YouTube
import os
import logging
import tempfile
from urllib.parse import parse_qs, urlparse

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_video_id(url):
    """Extraer el ID del video de la URL de YouTube."""
    query = urlparse(url)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch':
            return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/embed/':
            return query.path.split('/')[2]
        if query.path[:3] == '/v/':
            return query.path.split('/')[2]
    return None

def download_audio(url):
    logger.debug(f"Intentando descargar audio de: {url}")
    
    try:
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp()
        
        # Inicializar YouTube
        yt = YouTube(url)
        
        # Obtener el stream de audio
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            raise Exception("No se encontró stream de audio")

        # Descargar el audio
        logger.debug("Descargando audio...")
        output_file = audio_stream.download(output_path=temp_dir)
        
        if not os.path.exists(output_file):
            raise Exception("No se pudo descargar el audio")
        
        logger.debug(f"Audio descargado exitosamente: {output_file}")
        return output_file, yt.title
            
    except Exception as e:
        logger.error(f"Error detallado en download_audio: {str(e)}")
        raise Exception(f"Error al descargar el audio: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    temp_file = None
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({'error': 'URL no proporcionada'}), 400

        # Validar URL
        video_id = get_video_id(url)
        if not video_id:
            return jsonify({'error': 'URL de YouTube inválida'}), 400

        logger.debug(f"Iniciando descarga para video ID: {video_id}")
        output_file, title = download_audio(url)
        
        try:
            return send_file(
                output_file,
                as_attachment=True,
                download_name=f"{title}.mp3",
                mimetype='audio/mp3'
            )
        finally:
            # Limpiar archivos
            if output_file and os.path.exists(output_file):
                try:
                    os.remove(output_file)
                    logger.debug(f"Archivo temporal eliminado: {output_file}")
                except:
                    pass
                
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error en /download: {error_message}")
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    app.run(debug=True)