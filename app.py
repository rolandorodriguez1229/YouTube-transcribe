from flask import Flask, request, render_template, send_file, redirect, url_for
import openai
import os

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'audio' not in request.files:
        return redirect(url_for('index'))
    
    audio = request.files['audio']
    if audio.filename == '':
        return redirect(url_for('index'))

    file_path = os.path.join(UPLOAD_FOLDER, audio.filename)
    audio.save(file_path)

    with open(file_path, 'rb') as audio_file:
        response = openai.Audio.transcribe("whisper-1", audio_file)
        transcript = response.get("text", "")
    
    txt_filename = f"{os.path.splitext(audio.filename)[0]}.txt"
    txt_path = os.path.join(UPLOAD_FOLDER, txt_filename)
    
    with open(txt_path, "w") as txt_file:
        txt_file.write(transcript)
    
    return send_file(txt_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)