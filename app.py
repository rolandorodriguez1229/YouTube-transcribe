from flask import Flask, render_template, request, jsonify, send_file
from google.cloud import speech
import os
from pydub import AudioSegment
from dotenv import load_dotenv
import tempfile
from werkzeug.utils import secure_filename
import io
import json

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'temp_files'

# Asegurarse de que existe el directorio temporal
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Crear archivo de credenciales desde la variable de entorno
def setup_credentials():
    credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if credentials_json and credentials_json.startswith('{'):
        # Si es un JSON, crear un archivo temporal
        fd, temp_path = tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd, 'w') as temp:
            temp.write(credentials_json)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
        return temp_path
    return None

# Configurar credenciales al inicio
creds_path = setup_credentials()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.mp3'):
        return jsonify({'error': 'Only MP3 files are supported'}), 400

    try:
        filename = secure_filename(file.filename)
        base_filename = os.path.splitext(filename)[0]
        
        # Create temporary files for audio processing
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_mp3:
            file.save(temp_mp3.name)
            
        # Convert MP3 to WAV
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            audio = AudioSegment.from_mp3(temp_mp3.name)
            audio.export(temp_wav.name, format="wav")
        
        # Initialize Google Cloud client
        client = speech.SpeechClient()
        
        # Read the audio file
        with open(temp_wav.name, 'rb') as audio_file:
            content = audio_file.read()
        
        # Configure the recognition
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code="es-ES",
            enable_automatic_punctuation=True,
        )
        
        # Perform the transcription
        response = client.recognize(config=config, audio=audio)
        
        # Extract the transcribed text
        transcription = ""
        for result in response.results:
            transcription += result.alternatives[0].transcript + "\n"
        
        # Save transcription to a temporary file
        txt_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_filename}.txt")
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(transcription)
        
        # Clean up audio temporary files
        os.unlink(temp_mp3.name)
        os.unlink(temp_wav.name)
        
        return jsonify({
            'transcription': transcription,
            'filename': f"{base_filename}.txt"
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        mem_file = io.BytesIO()
        mem_file.write(content.encode('utf-8'))
        mem_file.seek(0)
        
        os.unlink(file_path)
        
        return send_file(
            mem_file,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Limpiar archivo de credenciales al cerrar
@app.teardown_appcontext
def cleanup_credentials(exception=None):
    if creds_path and os.path.exists(creds_path):
        try:
            os.unlink(creds_path)
        except:
            pass

if __name__ == '__main__':
    app.run(debug=True)