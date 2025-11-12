from flask import Flask, request, jsonify
from flask_cors import CORS
from gtts import gTTS
from openai import OpenAI
import os

app = Flask(__name__)
CORS(app)

# OpenAI anahtarını ortam değişkeninden al
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
print("OPENAI_API_KEY loaded:", bool(os.getenv("OPENAI_API_KEY")))

@app.route("/")
def home():
    return "MystAI backend is running successfully! 🔮"

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        user_input = data.get("user_input", "")
        print("=== Gelen veri:", data)
        print("=== Kullanıcı girişi:", user_input)

        # OpenAI'den yanıt al
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller who speaks with wisdom and insight."},
                {"role": "user", "content": user_input}
            ]
        )

        response_text = completion.choices[0].message.content
        print("=== OpenAI cevabı:", response_text)

        # Ses dosyası oluştur
        tts = gTTS(text=response_text, lang="tr")
        audio_path = "fortune.mp3"
        tts.save(audio_path)

        return jsonify({"text": response_text, "audio": "/" + audio_path})

    except Exception as e:
        import traceback
        print("=== HATA OLUŞTU ===")
        traceback.print_exc()  # 🔴 Hatanın tamamını log'a yazdırır
        return jsonify({"error": str(e)}), 500



# 🔍 Bağlantı testi için ek rota
@app.route("/test_connection")
def test_connection():
    import requests
    try:
        r = requests.get("https://api.openai.com/v1/models", timeout=10)
        return f"Connection OK: {r.status_code}"
    except Exception as e:
        return f"Connection failed: {str(e)}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
