from flask import Flask, request, jsonify
from flask_cors import CORS
from gtts import gTTS
from openai import OpenAI
import os
import traceback

app = Flask(__name__)
CORS(app)

# OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
print("OPENAI_API_KEY loaded:", "YES" if api_key else "NO")
client = OpenAI(api_key=api_key)

@app.route("/")
def home():
    return "MystAI backend is running! 🔮"

# OpenAI bağlantısını test etmek için
@app.route("/test_openai")
def test_openai():
    try:
        resp = client.models.list()
        return f"OpenAI OK, model count = {len(resp.data)}"
    except Exception as e:
        traceback.print_exc()
        return f"OpenAI ERROR: {type(e).__name__}: {e}", 500

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(force=True) or {}
        # frontend bazen "user_input", bazen "text" yollayabilir, ikisini de dene
        user_input = data.get("user_input") or data.get("text") or ""
        print("=== Kullanıcı girişi:", user_input)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller."},
                {"role": "user", "content": user_input},
            ],
            timeout=20,  # 20 sn timeout
        )

        response_text = completion.choices[0].message.content

        # Ses dosyası oluştur
        audio_filename = "fortune.mp3"
        tts = gTTS(text=response_text, lang="tr")
        tts.save(audio_filename)

        return jsonify({
            "text": response_text,
            "audio": f"/{audio_filename}",
        })

    except Exception as e:
        print("=== HATA OLUŞTU ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
