from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import logging
from pathlib import Path
import re

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def is_valid_youtube_url(url):
    """Validar URL de YouTube."""
    patterns = [
        r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'^https?://(?:www\.)?youtube\.com/v/[\w-]+',
        r'^https?://youtu\.be/[\w-]+',
        r'^https?://(?:www\.)?youtube\.com/embed/[\w-]+'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

def download_audio(url):
    logger.info(f"Iniciando descarga para URL: {url}")
    
    if not is_valid_youtube_url(url):
        raise ValueError("URL de YouTube inválida")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
        'progress_hooks': [lambda d: logger.debug(f"Progreso: {d.get('status', 'unknown')}")],
        'quiet': False,
        'no_warnings': False,
        'extract_flat': 'in_playlist',
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extraer información primero
            logger.debug("Extrayendo información del video...")
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'audio').replace('/', '_')
            expected_file = f"{title}.mp3"
            
            # Descargar el video
            logger.debug("Iniciando descarga del audio...")
            ydl.download([url])
            
            # Verificar si el archivo existe
            if not os.path.exists(expected_file):
                raise FileNotFoundError(f"No se encontró el archivo: {expected_file}")
            
            return expected_file, title
            
    except Exception as e:
        logger.error(f"Error durante la descarga: {str(e)}")
        # Limpiar archivos parciales
        for file in Path('.').glob('*.mp3'):
            try:
                file.unlink()
            except Exception as e:
                logger.error(f"Error al limpiar archivo {file}: {str(e)}")
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    output_file = None
    try:
        url = request.form.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Por favor, proporciona una URL de YouTube'}), 400
        
        try:
            output_file, title = download_audio(url)
            
            # Enviar archivo
            return send_file(
                output_file,
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=f"{title}.mp3"
            )
            
        except ValueError as ve:
            return jsonify({'error': str(ve)}), 400
        except Exception as e:
            logger.error(f"Error durante la descarga: {str(e)}")
            return jsonify({'error': 'Error al procesar el video. Por favor, intenta con otro video.'}), 500
            
    finally:
        # Limpiar archivos
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
                logger.debug(f"Archivo temporal eliminado: {output_file}")
            except Exception as e:
                logger.error(f"Error al eliminar archivo temporal: {str(e)}")

if __name__ == '__main__':
    app.run(debug=False)