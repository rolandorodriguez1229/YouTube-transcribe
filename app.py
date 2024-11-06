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
    
    # Configuración para yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'temp_%(id)s.%(ext)s',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Obtener información del video
            info = ydl.extract_info(url, download=True)
            # El archivo se guardará como temp_ID.mp3
            output_file = f"temp_{info['id']}.mp3"
            
            if not os.path.exists(output_file):
                raise Exception("No se pudo descargar el audio")
            
            return output_file, info.get('title', 'audio')
            
    except Exception as e:
        logger.error(f"Error en download_audio: {str(e)}")
        raise

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
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)