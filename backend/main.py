from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect, LangDetectException
import uuid
import os
import traceback

app = Flask(__name__)

# CORS
CORS(
    app,
    resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

# OpenAI Key
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)


# ========== ROOT ==========
@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


# ========== /predict ==========
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        try:
            detected = detect(user_input)
        except:
            detected = "en"

        if detected not in ("tr", "en"):
            detected = "en"

        if detected == "tr":
            system_prompt = (
                "Sen MystAI adında sezgisel ve mistik bir fal yorumcusun. "
                "Pozitif, umut veren, sakin bir tonda konuş. "
                "Korkutucu şeyler söyleme."
            )
        else:
            system_prompt = (
                "You are MystAI, an intuitive spiritual oracle. "
                "Stay positive, calming, mystical and non-fearful."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",        # ← hız artırıldı
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            max_tokens=300,        # ← stabil fal boyutu
        )

        text = completion.choices[0].message.content.strip()

        # Ses üret
        from gtts import gTTS
        file_id = uuid.uuid4().hex
        audio_path = f"/tmp/{file_id}.mp3"

        tts = gTTS(text=text, lang=detected)
        tts.save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{file_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========== /astrology ==========
@app.route("/astrology", methods=["POST"])
def astrology():
    try:
        data = request.get_json() or {}

        birth_date = (data.get("birth_date") or "").strip()
        birth_time = (data.get("birth_time") or "").strip()
        birth_place = (data.get("birth_place") or "").strip()
        name = (data.get("name") or "").strip()
        focus_areas = data.get("focus_areas") or []
        question = (data.get("question") or "").strip()
        language = (data.get("language") or "tr").strip()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi: birth_date, birth_time, birth_place zorunlu."}), 400

        sample_text = " ".join([birth_place, name, question]).strip() or "test"
        try:
            detected = detect(sample_text)
        except LangDetectException:
            detected = language

        if detected not in ("tr", "en"):
            detected = "en"

        if detected == "tr":
            system_prompt = (
                "Sen MystAI isimli profesyonel bir astrologsun. "
                "Üslubun bilge, sakin, derin ve spiritüel."
            )
        else:
            system_prompt = (
                "You are MystAI, a professional astrologer. "
                "Your tone is wise, calm, deep and spiritual."
            )

        focus_text = ", ".join(focus_areas) if focus_areas else "general themes"

        if detected == "tr":
            user_prompt = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim: {name or 'Belirtilmedi'}\n"
                f"Odak alanları: {focus_text}\n"
                f"Soru: {question or 'Belirtilmedi'}\n\n"
                "Lütfen detaylı ve profesyonel bir astroloji raporu yaz."
            )
        else:
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not provided'}\n"
                f"Focus areas: {focus_text}\n"
                f"Question: {question or 'Not provided'}\n\n"
                "Please write a detailed, professional astrology report."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",         # ← büyük model (timeout çözümü)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=6000,        # ← timeout engelleyen ideal değer
            temperature=0.9,
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({
            "text": text,
            "audio": None,
            "chart": None,
            "language": detected
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========== Audio ==========
@app.route("/audio/<file_id>")
def serve_audio(file_id):
    f = f"/tmp/{file_id}.mp3"
    if not os.path.exists(f):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(f, mimetype="audio/mpeg")


# ========== Ping ==========
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# ========== Run (RENDER-COMPATIBLE) ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
