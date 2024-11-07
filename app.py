from flask import Flask, render_template, request, jsonify, send_file
from google.cloud import speech
from google.oauth2 import service_account
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

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def get_speech_client():
    """Crear cliente de Speech-to-Text usando credenciales directamente"""
    try:
        credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_json:
            raise Exception("No se encontraron las credenciales")
            
        # Convertir string a diccionario
        credentials_info = json.loads(credentials_json)
        
        # Crear credenciales directamente del JSON
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        
        # Crear y retornar el cliente
        return speech.SpeechClient(credentials=credentials)
    except Exception as e:
        print(f"Error al crear el cliente: {str(e)}")
        raise

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
        client = get_speech_client()
        
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
        print(f"Error durante la transcripción: {str(e)}")
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

if __name__ == '__main__':
    app.run(debug=True)