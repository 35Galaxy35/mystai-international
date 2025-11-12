from flask import Flask, request, jsonify, send_from_directory
from langdetect import detect
from flask_cors import CORS
import openai
from gtts import gTTS
import os

app = Flask(__name__)
CORS(app)  # frontend bağlantısı için

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_fortune(user_input, lang):
    """OpenAI'den yanıt alır ve fortune.mp3 dosyasını oluşturur."""
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a mystical fortune teller named MystAI."},
            {"role": "user", "content": user_input}
        ]
    )

    prediction = completion.choices[0].message.content.strip()

    audio_dir = "static"
    os.makedirs(audio_dir, exist_ok=True)
    audio_file = os.path.join(audio_dir, "fortune.mp3")

    tts = gTTS(text=prediction, lang=lang)
    tts.save(audio_file)

    return prediction

# ---- Ana API (frontend buraya istek atıyor) ----
@app.route("/api/fortune", methods=["POST"])
def api_fortune():
    try:
        data = request.get_json()
        user_input = data.get("type", "Your fortune")
        lang = data.get("lang", "en")

        prediction = generate_fortune(user_input, lang)

        return jsonify({
            "fortune": prediction,
            "audio": "/static/fortune.mp3"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- Eski predict endpoint’i de çalışsın ----
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "No input text provided."}), 400
        lang = detect(text)
        prediction = generate_fortune(text, lang)
        return jsonify({"text": prediction, "audio": "/static/fortune.mp3"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/static/<path:filename>")
def serve_audio(filename):
    return send_from_directory("static", filename)

@app.route("/")
def home():
    return "🔮 MystAI backend is running successfully! 🔮"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
