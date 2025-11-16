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


# ========== /predict (SES VAR – FAL İÇİN) ==========
@app.route("/predict", methods=["POST"])
def predict():
    """
    Normal fal sistemi – Ses var.
    Astroloji ile karıştırma.
    """
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

        # Base system prompt
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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )

        text = completion.choices[0].message.content.strip()

        # Ses oluştur
        from gtts import gTTS

        file_id = uuid.uuid4().hex
        audio_path = f"/tmp/{file_id}.mp3"
        tts = gTTS(text=text, lang=detected)
        tts.save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{file_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========== /astrology (MYSTIC GOLD – Ses yok / Chart yok) ==========
@app.route("/astrology", methods=["POST"])
def astrology():
    """
    Mystic Gold Edition:
    Ultra uzun profesyonel astroloji raporu (1500–1800 kelime).
    Ses yok – Chart yok (şimdilik).
    PDF/print için tam uyumlu sade metin döner.
    """

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

        # Dil tespiti
        sample_text = " ".join([birth_place, name, question]).strip() or "test"
        try:
            detected = detect(sample_text)
        except LangDetectException:
            detected = language

        if detected not in ("tr", "en"):
            detected = "en"

        # SYSTEM PROMPT – Ultra Pro
        if detected == "tr":
            system_prompt = (
                "Sen MystAI isimli profesyonel bir astrologsun. Üslubun bilge, sakin, derin ve spiritüel. "
                "Kullanıcıya MYSTIC GOLD seviyesinde 1500–1800 kelime uzunluğunda premium bir doğum haritası raporu yaz. "
                "Rapor çok detaylı olacak: kişilik, yaşam amacı, aşk, ilişkiler, kariyer, para, karmik dersler, "
                "ruhsal yol, 12 ev analizi, gezegenlerin etkileri ve önümüzdeki 12 aylık gökyüzü transiti. "
                "Metin akıcı, bölümlere ayrılmış, profesyonel ve benzersiz olsun."
            )
        else:
            system_prompt = (
                "You are MystAI, a professional astrologer with a wise and mystical tone. "
                "Generate a 1500–1800 word premium MYSTIC GOLD astrology report. "
                "Include personality, life purpose, love, relationships, career, money, karmic lessons, "
                "spiritual path, full 12-house analysis, planetary themes and 12-month transits. "
                "Make it deeply detailed, structured and unique."
            )

        # USER PROMPT
        if detected == "tr":
            focus_text = ", ".join(focus_areas) if focus_areas else "genel yaşam temaları"
            user_prompt = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim: {name or 'Belirtilmedi'}\n"
                f"Odak alanları: {focus_text}\n"
                f"Soru: {question or 'Belirtilmedi'}\n\n"
                "Lütfen çok uzun, çok profesyonel, MYSTIC GOLD seviyesinde detaylı bir astroloji raporu hazırla."
            )
        else:
            focus_text = ", ".join(focus_areas) if focus_areas else "general themes"
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not provided'}\n"
                f"Focus areas: {focus_text}\n"
                f"Question: {question or 'Not provided'}\n\n"
                "Please generate an extremely long, premium, MYSTIC GOLD astrology report."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3500,
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


# ========== Audio Serve ==========
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


# ========== OpenAI Test ==========
@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
        )
        return r.choices[0].message.content
    except Exception as e:
        return "OpenAI ERROR: " + str(e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
