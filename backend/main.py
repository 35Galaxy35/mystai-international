from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect, LangDetectException
import uuid
import os
import traceback

app = Flask(__name__)

# ========= CORS =========
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

# ========= OpenAI & Model Ayarları =========
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# Modelleri ve token limitlerini env'den okuyalım ki sonra kod değiştirmeden
# Render panelinden değiştirebilesin.
CHAT_MODEL = os.environ.get("MYST_CHAT_MODEL", "gpt-4o-mini")
ASTROLOGY_MODEL = os.environ.get("MYST_ASTROLOGY_MODEL", "gpt-4o")

MAX_CHAT_TOKENS = int(os.environ.get("MYST_CHAT_MAX_TOKENS", "400"))
MAX_ASTROLOGY_TOKENS = int(os.environ.get("MYST_ASTROLOGY_MAX_TOKENS", "2200"))


def safe_detect_lang(text: str, fallback: str = "en") -> str:
    """
    langdetect kütüphanesi bazen hata atabiliyor.
    Bu yardımcı fonksiyon, her durumda 'tr' veya 'en' döner.
    """
    try:
        if text and text.strip():
            lang = detect(text)
        else:
            return fallback
        return lang if lang in ("tr", "en") else fallback
    except LangDetectException:
        return fallback
    except Exception:
        return fallback


# ========= ROOT =========
@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


# ========= /predict =========
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(silent=True) or {}
        user_input = (data.get("user_input") or "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        detected = safe_detect_lang(user_input, fallback="en")

        if detected == "tr":
            system_prompt = (
                "Sen MystAI adında sezgisel ve mistik bir fal yorumcusun. "
                "Pozitif, umut veren, sakin bir tonda konuş. "
                "Korkutucu veya karanlık şeyler söyleme."
            )
        else:
            system_prompt = (
                "You are MystAI, an intuitive spiritual oracle. "
                "Stay positive, calming, mystical and non-fearful."
            )

        completion = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            max_tokens=MAX_CHAT_TOKENS,
            temperature=0.9,
        )

        text = completion.choices[0].message.content.strip()

        # Ses üret (gTTS burada import, böylece predict hiç çağrılmazsa yüklenmiyor)
        from gtts import gTTS

        file_id = uuid.uuid4().hex
        audio_path = f"/tmp/{file_id}.mp3"

        tts = gTTS(text=text, lang="tr" if detected == "tr" else "en")
        tts.save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{file_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= /astrology =========
@app.route("/astrology", methods=["POST"])
def astrology():
    try:
        data = request.get_json(silent=True) or {}

        birth_date = (data.get("birth_date") or "").strip()
        birth_time = (data.get("birth_time") or "").strip()
        birth_place = (data.get("birth_place") or "").strip()
        name = (data.get("name") or "").strip()
        focus_areas = data.get("focus_areas") or []
        question = (data.get("question") or "").strip()
        language = (data.get("language") or "tr").strip()

        if not birth_date or not birth_time or not birth_place:
            return (
                jsonify(
                    {
                        "error": "Eksik bilgi: birth_date, birth_time, birth_place zorunlu."
                    }
                ),
                400,
            )

        # Dil tespiti için küçük bir örnek metin
        sample_text = " ".join([birth_place, name, question]).strip() or "test"
        detected = safe_detect_lang(sample_text, fallback=language or "tr")

        if detected == "tr":
            system_prompt = (
                "Sen MystAI isimli profesyonel bir astrologsun. "
                "Üslubun bilge, sakin, derin ve spiritüel. "
                "Kişiyi güçlendiren, umut veren bir dille yaz; "
                "korkutucu, deterministik ve karanlık söylemlerden kaçın. "
                "Doğum haritası, solar return ve transitleri harmanlayan "
                "uzun, derinlikli bir premium astroloji raporu üret."
            )
        else:
            system_prompt = (
                "You are MystAI, a professional astrologer. "
                "Your tone is wise, calm, empowering and spiritual. "
                "Avoid fear-based or fatalistic language. "
                "Blend natal chart, solar return and transits into one long, "
                "premium-style astrology report."
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
                "Lütfen yaklaşık 1500 kelimelik, çok uzun, detaylı ve profesyonel "
                "bir astroloji raporu yaz. Başlıklar ve paragraflar kullan."
            )
        else:
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not provided'}\n"
                f"Focus areas: {focus_text}\n"
                f"Question: {question or 'Not provided'}\n\n"
                "Please write a ~1500-word, long and professional astrology report "
                "with clear sections and paragraphs."
            )

        completion = client.chat.completions.create(
            model=ASTROLOGY_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=MAX_ASTROLOGY_TOKENS,
            temperature=0.9,
        )

        text = completion.choices[0].message.content.strip()

        return jsonify(
            {
                "text": text,
                "audio": None,   # İleride seslendirme eklemek istersen burayı kullanırız
                "chart": None,   # Şimdilik grafik yok, frontend bu alanı idare ediyor
                "language": detected,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= /audio/<id> =========
@app.route("/audio/<file_id>")
def serve_audio(file_id):
    path = f"/tmp/{file_id}.mp3"
    if not os.path.exists(path):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(path, mimetype="audio/mpeg")
# ---------- PDF OLUŞTURMA ENDPOINTİ ----------
from flask import send_file
from weasyprint import HTML
import uuid

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    data = request.json
    text = data.get("text", "")

    # HTML formatına dönüştür
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 25px;
                line-height: 1.5;
                font-size: 14px;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        {text}
    </body>
    </html>
    """

    # PDF oluştur
    file_id = str(uuid.uuid4())
    pdf_path = f"/tmp/{file_id}.pdf"

    HTML(string=html_content).write_pdf(pdf_path)

    return send_file(pdf_path, as_attachment=True, download_name="mystai-report.pdf")


# ========= /ping =========
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# ========= Render uyumlu run =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
