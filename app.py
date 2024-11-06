from flask import Flask, render_template, request, send_file, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import logging
import time
import requests
from urllib.parse import parse_qs, urlparse

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Ejecutar en modo headless
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return chrome_options

def download_audio(url):
    logger.debug(f"Iniciando proceso para URL: {url}")
    
    try:
        driver = webdriver.Chrome(options=get_chrome_options())
        wait = WebDriverWait(driver, 20)
        
        try:
            # Cargar la página
            logger.debug("Accediendo a YouTube...")
            driver.get(url)
            
            # Esperar a que el título esté disponible
            title_element = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1.style-scope.ytd-video-primary-info-renderer"))
            )
            video_title = title_element.text
            
            # Obtener la URL del audio
            logger.debug("Extrayendo información del video...")
            time.sleep(3)  # Esperar a que se cargue el reproductor
            
            # Encontrar el elemento de audio
            audio_element = driver.execute_script("""
                var video = document.querySelector('video');
                return video.src;
            """)
            
            if not audio_element:
                raise Exception("No se pudo encontrar el elemento de audio")
            
            # Descargar el audio
            logger.debug("Descargando audio...")
            response = requests.get(audio_element, stream=True)
            response.raise_for_status()
            
            # Guardar temporalmente
            output_file = f"temp_audio_{int(time.time())}.mp3"
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.debug(f"Audio descargado exitosamente: {output_file}")
            return output_file, video_title
            
        finally:
            driver.quit()
            
    except Exception as e:
        logger.error(f"Error en download_audio: {str(e)}")
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
            if os.path.exists(output_file):
                os.remove(output_file)
                logger.debug(f"Archivo temporal eliminado: {output_file}")
                
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error en /download: {error_message}")
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    app.run(debug=True)