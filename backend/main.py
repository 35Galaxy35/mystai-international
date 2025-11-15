from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect, LangDetectException
from gtts import gTTS
import os
import traceback
import uuid

app = Flask(__name__)

# ========= CORS AYARLARI =========
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

# ENV'den API KEY oku
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


# === Sistem prompt oluşturucu ===
def build_system_prompt(reading_type: str, lang: str) -> str:
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, sıcak ve profesyonel bir fal ve astroloji yorumcusun. "
            "Kullanıcıya asla korkutucu veya umutsuz mesajlar verme. "
            "Gerçekçi ama pozitif, yol gösterici ve sakin bir tonda konuş."
        )
        types = {
            "astrology": (
                base
                + " Doğum haritasını, gezegenleri, burçları, evleri ve açıları kullanarak; "
                "kişilik, yaşam amacı, aşk, kariyer, para ve ruhsal gelişim hakkında geniş bir rapor yaz."
            ),
            "general": base + " Genel bir mistik fal yorumcususun.",
        }
    else:
        base = (
            "You are MystAI, a mystical, warm and professional astrology interpreter. "
            "Never give scary or hopeless messages. Be positive, realistic and calm."
        )
        types = {
            "astrology": (
                base
                + " Interpret the natal chart: planets, houses, aspects. Provide kind and deep insights."
            ),
            "general": base + " A general oracle giving intuitive guidance.",
        }

    return types.get(reading_type, types["general"])


# ========= /predict =========
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

        system_prompt = build_system_prompt("general", detected)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )

        response_text = completion.choices[0].message.content.strip()

        # Ses oluştur
        file_id = uuid.uuid4().hex
        audio_path = f"/tmp/{file_id}.mp3"
        tts = gTTS(text=response_text, lang=detected)
        tts.save(audio_path)

        return jsonify(
            {
                "text": response_text,
                "audio": f"/audio/{file_id}",
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= /astrology (sorunsuz – sadece metin) =========
@app.route("/astrology", methods=["POST"])
def astrology():
    """
    Astroloji raporu – hızlı çalışır, timeout yemez.
    Sadece METİN döner (audio yok, chart yok).
    """
    try:
        data = request.get_json() or {}

        birth_date = data.get("birth_date", "").strip()
        birth_time = data.get("birth_time", "").strip()
        birth_place = data.get("birth_place", "").strip()
        name = data.get("name", "").strip()
        focus_areas = data.get("focus_areas", [])
        question = data.get("question", "").strip()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi: birth_date, birth_time, birth_place zorunlu."}), 400

        # Dil tespiti
        sample_text = " ".join([birth_place, name, question]).strip() or "test"
        try:
            detected = detect(sample_text)
        except:
            detected = "en"

        if detected not in ("tr", "en"):
            detected = "en"

        print("=== astrology dil:", detected)

        # Sistem prompt
        system_prompt = build_system_prompt("astrology", detected)

        # Kullanıcı prompt
        if detected == "tr":
            focus_text = ", ".join(focus_areas) if focus_areas else "genel yaşam temaları"
            user_prompt = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim: {name or 'Belirtilmedi'}\n"
                f"Odak: {focus_text}\n"
                f"Soru: {question or 'Belirtilmedi'}\n\n"
                "Kapsamlı bir astroloji raporu hazırla."
            )
        else:
            focus_text = ", ".join(focus_areas) if focus_areas else "general life themes"
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not provided'}\n"
                f"Focus areas: {focus_text}\n"
                f"Question: {question or 'Not provided'}\n\n"
                "Write a detailed astrology reading."
            )

        # OpenAI – hızlı olsun diye max_tokens sınırlı
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900,
        )

        report_text = completion.choices[0].message.content.strip()
        print("Rapor uzunluğu:", len(report_text))

        # Sadece METİN döner
        return jsonify(
            {
                "text": report_text,
                "audio": None,
                "chart": None,
                "language": detected,
            }
        )

    except Exception as e:
        print("=== astrology HATA ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= Ses dosyası =========
@app.route("/audio/<file_id>")
def serve_audio(file_id):
    filename = f"/tmp/{file_id}.mp3"
    if not os.path.exists(filename):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(filename, mimetype="audio/mpeg")


# ========= Chart dosyası =========
@app.route("/chart/<chart_id>")
def serve_chart(chart_id):
    filename = f"/tmp/{chart_id}.png"
    if not os.path.exists(filename):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(filename, mimetype="image/png")


# ========= Ping testi =========
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# ========= OpenAI bağlantı testi =========
@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )
        return "OK -> " + r.choices[0].message.content
    except Exception as e:
        return "OpenAI ERROR: " + str(e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
