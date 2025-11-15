from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
from langdetect import detect, LangDetectException
import os
import traceback
import uuid
import base64

app = Flask(__name__)

# ======== CORS AYARLARI =========
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://mystai.ai",
            "https://www.mystai.ai",
            "https://mystaiai.vercel.app"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# ENV'den API KEY oku
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


def build_system_prompt(reading_type: str, lang: str) -> str:
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, sıcak ve profesyonel bir fal ve astroloji yorumcusun. "
            "Kullanıcıya asla korkutucu veya umutsuz mesajlar verme. "
            "Gerçekçi ama pozitif, yol gösterici ve sakin bir tonda konuş. "
        )
        types = {
            "coffee": base + "Kahve falı uzmanısın...",
            "tarot": base + "Tarot ustasısın...",
            "palm": base + "El falı uzmanısın...",
            "energy": base + "Rüya ve enerji yorumcusun...",
            "astrology": (
                base +
                "Profesyonel bir doğum haritası yorumcusun. "
                "Gezegenleri, burçları, evleri ve açıları yorumlayarak detaylı rapor yaz."
            ),
            "general": base + "Genel mistik bir yorumcusun."
        }
    else:
        base = (
            "You are MystAI, a warm mystical interpreter. "
            "Never give scary messages. Be realistic and supportive."
        )
        types = {
            "coffee": base + "You read coffee cups...",
            "tarot": base + "You are a tarot master...",
            "palm": base + "You read palm lines...",
            "energy": base + "You interpret dreams and energy...",
            "astrology": (
                base +
                "You interpret natal charts, planets, houses and aspects clearly and gently."
            ),
            "general": base + "You give general mystical readings."
        }

    return types.get(reading_type, types["general"])


# =============================
#    FAL / PREDICT ENDPOINT
# =============================
@app.route("/predict", methods=["POST", "OPTIONS"])
def predict():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "") or ""
        reading_type = (data.get("reading_type") or "general").lower()

        if not user_input.strip():
            return jsonify({"error": "user_input boş olamaz"}), 400

        try:
            detected = detect(user_input)
        except LangDetectException:
            detected = "en"

        if detected not in ("en", "tr"):
            detected = "en"

        valid_types = {"coffee", "tarot", "palm", "energy", "astrology", "general"}
        if reading_type not in valid_types:
            reading_type = "general"

        system_prompt = build_system_prompt(reading_type, detected)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )

        response_text = completion.choices[0].message.content.strip()

        file_id = uuid.uuid4().hex
        audio_path = os.path.join("/tmp", f"{file_id}.mp3")
        gTTS(text=response_text, lang=detected).save(audio_path)

        return jsonify(
            {
                "text": response_text,
                "audio": f"/audio/{file_id}",
                "reading_type": reading_type,
                "language": detected,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =============================
#     ASTROLOJİ ENDPOINT
# =============================
@app.route("/astrology", methods=["POST", "OPTIONS"])
def astrology():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json() or {}

        birth_date = (data.get("birth_date") or "").strip()
        birth_time = (data.get("birth_time") or "").strip()
        birth_place = (data.get("birth_place") or "").strip()
        name = (data.get("name") or "").strip()
        focus_areas = data.get("focus_areas") or []
        question = (data.get("question") or "").strip()
        forced_lang = (data.get("language") or "").lower()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "birth_date, birth_time, birth_place zorunludur"}), 400

        if forced_lang in ("tr", "en"):
            detected = forced_lang
        else:
            try:
                detected = detect(question or name or birth_place)
            except:
                detected = "en"

        if detected not in ("tr", "en"):
            detected = "en"

        system_prompt = build_system_prompt("astrology", detected)

        if detected == "tr":
            user_prompt = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim: {name or 'Belirtilmedi'}\n"
                f"Alanlar: {', '.join(focus_areas) or 'Genel'}\n"
                f"Soru: {question or 'Belirtilmedi'}\n\n"
                "Detaylı bir astroloji raporu yaz."
            )
        else:
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not provided'}\n"
                f"Focus areas: {', '.join(focus_areas) or 'General'}\n"
                f"Question: {question or 'Not provided'}\n\n"
                "Write a detailed astrology report."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        report_text = completion.choices[0].message.content.strip()

        audio_id = uuid.uuid4().hex
        audio_path = os.path.join("/tmp", f"{audio_id}.mp3")
        gTTS(text=report_text, lang=detected).save(audio_path)

        # --- IMAGE ---
        img_prompt = (
            "A high-quality mystical natal chart in dark blue-gold theme."
        )

        img = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024"
        )

        img_bytes = base64.b64decode(img.data[0].b64_json)
        chart_id = uuid.uuid4().hex
        chart_path = os.path.join("/tmp", f"{chart_id}.png")

        with open(chart_path, "wb") as f:
            f.write(img_bytes)

        return jsonify(
            {
                "text": report_text,
                "audio": f"/audio/{audio_id}",
                "chart": f"/chart/{chart_id}",
                "language": detected,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ================================
#     STATIC FILE ROUTES
# ================================
@app.route("/audio/<file_id>")
def serve_audio(file_id):
    path = os.path.join("/tmp", f"{file_id}.mp3")
    if not os.path.exists(path):
        return jsonify({"error": "audio bulunamadı"}), 404
    return send_file(path, mimetype="audio/mpeg")


@app.route("/chart/<chart_id>")
def serve_chart(chart_id):
    path = os.path.join("/tmp", f"{chart_id}.png")
    if not os.path.exists(path):
        return jsonify({"error": "chart bulunamadı"}), 404
    return send_file(path, mimetype="image/png")


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )
        return "OK -> " + r.choices[0].message.content
    except Exception as e:
        return "ERR -> " + str(e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
