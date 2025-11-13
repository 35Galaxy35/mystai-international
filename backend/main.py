from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
import os
import traceback

app = Flask(__name__)
CORS(app)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        user_input = data.get("user_input", "")

        print("=== Kullanıcı girişi:", user_input)

        # OpenAI response (Yeni API formatı)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller."},
                {"role": "user", "content": user_input}
            ]
        )

        response_text = completion.choices[0].message.content

        # Ses dosyası oluştur
        audio_filename = "fortune.mp3"
        tts = gTTS(text=response_text, lang="tr")
        tts.save(audio_filename)

        return jsonify({
            "text": response_text,
            "audio": f"/{audio_filename}"
        })

    except Exception as e:
        print("=== HATA OLUŞTU ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
