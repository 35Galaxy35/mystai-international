from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
import os

app = Flask(__name__)
CORS(app)

# Yeni OpenAI istemcisi
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return "MystAI backend is running successfully! 🔮"

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        user_input = data.get("user_input", "")
        lang = data.get("lang", "tr")

        # OpenAI'den yanıt al
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller who answers in a magical and wise tone."},
                {"role": "user", "content": user_input}
            ]
        )

        reply = completion.choices[0].message.content

        # Sesli yanıt oluştur
        tts = gTTS(reply, lang=lang)
        tts.save("fortune.mp3")

        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
