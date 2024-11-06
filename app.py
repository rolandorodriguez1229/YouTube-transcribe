from flask import Flask, render_template, request, send_file, jsonify
import youtube_dl
import os
import logging
import tempfile
from urllib.parse import parse_qs, urlparse

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class MyLogger:
    def debug(self, msg):
        logger.debug(msg)
    def warning(self, msg):
        logger.warning(msg)
    def error(self, msg):
        logger.error(msg)

def my_hook(d):
    if d['status'] == 'downloading':
        logger.info(f'Descargando... {d.get("_percent_str", "0%")}')
    elif d['status'] == 'finished':
        logger.info('Descarga completada, convirtiendo...')

def download_audio(url):
    logger.debug(f"Intentando descargar audio de: {url}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'temp_%(id)s.%(ext)s',
        'logger': MyLogger(),
        'progress_hooks': [my_hook],
        'verbose': True,
        # Headers personalizados
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        },
        # Configuraciones adicionales
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': False,
        'no_warnings': False,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            logger.debug("Obteniendo información del video...")
            # Primero obtener metadatos
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'audio')
            video_id = info.get('id', 'unknown')
            
            # Luego descargar
            logger.debug("Iniciando descarga...")
            ydl.download([url])
            
            # El archivo será temp_ID.mp3 después de la conversión
            output_file = f"temp_{video_id}.mp3"
            
            if not os.path.exists(output_file):
                raise Exception("No se pudo crear el archivo de audio")
            
            logger.debug(f"Audio descargado exitosamente: {output_file}")
            return output_file, video_title
            
    except Exception as e:
        logger.error(f"Error detallado en download_audio: {str(e)}")
        # Limpiar archivos temporales en caso de error
        try:
            for f in os.listdir('.'):
                if f.startswith('temp_'):
                    os.remove(f)
        except:
            pass
        raise Exception(f"Error al descargar el audio: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({'error': 'URL no proporcionada'}), 400

        logger.info(f"Procesando URL: {url}")
        output_file, title = download_audio(url)
        
        try:
            return send_file(
                output_file,
                as_attachment=True,
                download_name=f"{title}.mp3",
                mimetype='audio/mp3'
            )
        finally:
            # Limpiar archivo después de enviarlo
            if os.path.exists(output_file):
                os.remove(output_file)
                logger.debug(f"Archivo temporal eliminado: {output_file}")
                
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error en /download: {error_message}")
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    app.run(debug=True)