from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
from langdetect import detect, LangDetectException
import os
import traceback
import uuid

app = Flask(__name__)
CORS(app)

# ENV'den API KEY okunur
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        print("=== Kullanıcı girişi:", user_input)

        # Dil tespiti
        try:
            detected = detect(user_input)
        except LangDetectException:
            detected = "en"

        if detected not in ("en", "tr"):
            detected = "en"

        # OpenAI fal cevabı
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a mystical fortune teller named MystAI. "
                        "If the user writes Turkish, respond in Turkish. "
                        "If the user writes English, respond in English."
                    ),
                },
                {"role": "user", "content": user_input},
            ],
        )

        response_text = completion.choices[0].message.content.strip()

        # Ses dosyası oluşturma
        file_id = uuid.uuid4().hex
        filename = f"{file_id}.mp3"
        filepath = os.path.join("/tmp", filename)  # Render'da yazılabilir dizin

        tts = gTTS(text=response_text, lang=detected)
        tts.save(filepath)

        return jsonify({
            "text": response_text,
            "audio": f"/audio/{file_id}"
        })

    except Exception as e:
        print("=== HATA OLUŞTU ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/audio/<file_id>")
def serve_audio(file_id):
    """GTTs tarafından üretilen MP3 dosyasını döner."""
    filepath = os.path.join("/tmp", f"{file_id}.mp3")

    if not os.path.exists(filepath):
        return jsonify({"error": "Audio not found"}), 404

    return send_file(filepath, mimetype="audio/mpeg")


@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test message"}]
        )
        return "OpenAI OK → " + r.choices[0].message.content

    except Exception as e:
        return "OpenAI ERROR → " + str(e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
