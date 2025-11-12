from flask import Flask, request, jsonify
from langdetect import detect
import openai
from gtts import gTTS
import os

app = Flask(__name__)

# OpenAI API anahtarını ortam değişkeninden al
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        user_input = data.get("text", "")

        if not user_input:
            return jsonify({"error": "No input text provided."}), 400

        # Dil tespiti
        lang = detect(user_input)

        # OpenAI cevabı oluştur
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller named MystAI."},
                {"role": "user", "content": user_input}
            ]
        )

        prediction = completion.choices[0].message.content.strip()

        # Sesli çıktı oluştur (gTTS)
        tts = gTTS(text=prediction, lang=lang)
        audio_file = "fortune.mp3"
        tts.save(audio_file)

        return jsonify({
            "text": prediction,
            "audio": f"/{audio_file}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fortune.mp3")
def serve_audio():
    return app.send_static_file("fortune.mp3")

# Ana sayfa – kontrol için
@app.route("/")
def home():
    return "🔮 MystAI backend is running successfully! 🔮"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
