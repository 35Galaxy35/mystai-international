from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
import os
import traceback
import base64
import uuid

app = Flask(__name__)
CORS(app)

# =========================== 
# OpenAI API Key
# ===========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)


# ===========================
# Root Test Route
# ===========================
@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


# ===========================
# Ask MystAI — TEXT + TTS
# ===========================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        user_input = data.get("user_input", "")

        print("=== Kullanıcı Sordu:", user_input)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller."},
                {"role": "user", "content": user_input}
            ]
        )

        response_text = completion.choices[0].message.content
        print("=== Cevap:", response_text)

        # ========== TTS (Google gTTS) ==========
        audio_filename = f"voice_{uuid.uuid4().hex}.mp3"
        audio_path = f"static/{audio_filename}"

        os.makedirs("static", exist_ok=True)

        tts = gTTS(text=response_text, lang="tr")
        tts.save(audio_path)

        return jsonify({
            "text": response_text,
            "audio": f"/static/{audio_filename}"
        })

    except Exception as e:
        print("=== HATA /predict ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ===========================
# NEW: Kahve Falı — Image + Question
# ===========================
@app.route("/coffee_fortune", methods=["POST"])
def coffee_fortune():
    """
    Beklenen JSON:
    {
      "image_url": "data:image/jpeg;base64,...",
      "question": "Aşk hayatım?",
      "lang": "tr"
    }
    """
    try:
        data = request.get_json() or {}
        image_url = data.get("image_url", "")
        question = data.get("question", "")
        lang = data.get("lang", "tr")

        if not image_url:
            return jsonify({"error": "image_url eksik"}), 400

        print("=== Kahve Fincanı Geldi ===")
        print("Soru:", question)

        # Sistem prompt'u
        system_prompt_tr = (
            "Sen mistik bir Türk kahve falcısısın. "
            "Telve şekillerini, sembolleri ve enerjiyi spiritüel bir dille yorumlarsın. "
            "Korkutucu veya medikal şeyler söyleme. Duygusal, pozitif ama gerçekçi konuş."
        )

        system_prompt_en = (
            "You are a mystical Turkish coffee fortune teller. "
            "Interpret the shapes in the coffee grounds with spiritual symbolism."
        )

        system_prompt = system_prompt_tr if lang == "tr" else system_prompt_en

        # Görsel + metin birlikte gönderiyoruz
        user_content = [
            {"type": "text", "text": question or (
                "Genel bir kahve falı yorumu yap." if lang == "tr"
                else "Give a general coffee fortune reading."
            )},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )

        response_text = completion.choices[0].message.content
        print("=== Kahve Yorum:", response_text)

        # ========== TTS ==========
        audio_filename = f"coffee_{uuid.uuid4().hex}.mp3"
        audio_path = f"static/{audio_filename}"

        tts = gTTS(text=response_text, lang="tr")
        tts.save(audio_path)

        return jsonify({
            "text": response_text,
            "audio": f"/static/{audio_filename}"
        })

    except Exception as e:
        print("=== HATA /coffee_fortune ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ===========================
# OpenAI Test
# ===========================
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


# ===========================
# Run — Render uses Gunicorn
# ===========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
