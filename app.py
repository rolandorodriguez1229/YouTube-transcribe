from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import logging
import tempfile

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def download_audio(url):
    logger.debug(f"Intentando descargar audio de: {url}")
    
    # Configuración actualizada para evitar detección de bot
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'temp_%(id)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
        # Configuración anti-bot
        'extract_flat': False,
        'writesubtitles': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'config', 'js'],
                'max_comments': [0],
            }
        },
        # Configuración de red
        'socket_timeout': 30,
        'retries': 3,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug("Obteniendo información del video...")
            # Primero extraer la información sin descargar
            info = ydl.extract_info(url, download=False)
            video_id = info['id']
            video_title = info['title']
            
            logger.debug(f"Descargando audio para video: {video_title}")
            # Luego descargar
            ydl.download([url])
            
            output_file = f"temp_{video_id}.mp3"
            
            if not os.path.exists(output_file):
                raise Exception("No se pudo descargar el audio")
            
            return output_file, video_title
            
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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({'error': 'URL no proporcionada'}), 400

        output_file, title = download_audio(url)
        
        try:
            return send_file(
                output_file,
                as_attachment=True,
                download_name=f"{title}.mp3",
                mimetype='audio/mp3'
            )
        finally:
            # Limpiar el archivo después de enviarlo
            if os.path.exists(output_file):
                os.remove(output_file)
                
    except Exception as e:
        logger.error(f"Error en /download: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)