# ============================================
# MystAI - Full Professional Astrology Backend
# No flatlib, no pyswisseph – fully Render compatible
# Creates professional natal chart with OpenAI Vision Model
# ============================================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
import os
import uuid
import traceback
import base64
from gtts import gTTS
from fpdf import FPDF
from geopy.geocoders import Nominatim

# -----------------------------
# Flask
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# OpenAI Client
# -----------------------------
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

geolocator = Nominatim(user_agent="mystai")


# -----------------------------
# SYSTEM PROMPTS
# -----------------------------
def system_prompt_general(lang):
    if lang == "tr":
        return (
            "Sen MystAI adında sezgisel, mistik ve uzman bir yorumcusun. "
            "Kullanıcıya derin, spiritüel ve pozitif bir dil ile rehberlik edersin."
        )
    else:
        return (
            "You are MystAI, a mystical and deeply intuitive AI. "
            "You speak warmly, professionally, and provide deep spiritual guidance."
        )


def system_prompt_astrology(lang):
    if lang == "tr":
        return (
            "Sen MystAI adında profesyonel bir astroloji uzmanısın. "
            "Natal, solar return ve transit analizini derin, kapsamlı ve uzman bir dille yaz. "
            "Gezegenler, evler, açı kalıpları, karmik etkiler, ruhsal dersler ve 12 ev yorumlarını dahil et."
        )
    else:
        return (
            "You are MystAI, a professional astrology analyst. "
            "Write deep natal + solar return + transit interpretations. "
            "Include planets, houses, aspects, karmic lessons, life mission and 12-house analysis."
        )


# -----------------------------
# BASIC /predict
# -----------------------------
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        text_in = data.get("user_input", "").strip()
        if not text_in:
            return jsonify({"error": "user_input empty"}), 400

        try:
            lang = detect(text_in)
        except:
            lang = "en"

        if lang not in ["tr", "en"]:
            lang = "en"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt_general(lang)},
                {"role": "user", "content": text_in},
            ],
        )

        output = completion.choices[0].message.content.strip()

        # Audio
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=output, lang=lang).save(audio_path)

        return jsonify({"text": output, "audio": f"/audio/{audio_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# HIGH-END ASTROLOGY ENGINE
# -----------------------------
@app.route("/astrology", methods=["POST"])
def astrology():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        focus = data.get("focus_areas", [])
        question = data.get("question", "")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Missing fields"}), 400

        # Language guess
        try:
            lang = detect(birth_place)
        except:
            lang = "en"

        if lang not in ["tr", "en"]:
            lang = "en"

        # -----------------------------
        # Geo Coordinates (optional, nice for realism)
        # -----------------------------
        try:
            loc = geolocator.geocode(birth_place)
            coords = f"Lat: {loc.latitude}, Lon: {loc.longitude}" if loc else ""
        except:
            coords = ""

        # -----------------------------
        # AI Astrology Report
        # -----------------------------
        if lang == "tr":
            user_prompt = (
                f"Doğum bilgileri:\n"
                f"Tarih: {birth_date} - Saat: {birth_time}\n"
                f"Yer: {birth_place}\n{coords}\n"
                f"İsim: {name}\n"
                f"Odak alanları: {', '.join(focus) or 'Genel'}\n"
                f"Soru / niyet: {question}\n\n"
                "Natal + solar return + transit kapsayan DERİN VE PROFESYONEL astroloji raporu yaz. "
                "En az 8 bölüm olsun. Kişilik, kader yolu, aşk, kariyer, bolluk, ruhsal gelişim, karmik dersler, "
                "önümüzdeki 12 ay temaları, 12 ev yorumu ve genel sonuç bölümü olsun."
            )
        else:
            user_prompt = (
                f"Birth data:\n"
                f"Date: {birth_date} - Time: {birth_time}\n"
                f"Place: {birth_place}\n{coords}\n"
                f"Name: {name}\n"
                f"Focus areas: {', '.join(focus) or 'General'}\n"
                f"Question / intention: {question}\n\n"
                "Write a DEEP & PROFESSIONAL natal + solar return + transit astrology report. "
                "At least 8 sections. Include personality, destiny path, love, career, abundance, "
                "spiritual growth, karmic lessons, 12-house analysis, next 12 months outlook and final advice."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt_astrology(lang)},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2500
        )

        report_text = completion.choices[0].message.content.strip()

        # -----------------------------
        # AI Generated Professional Chart
        # -----------------------------
        chart_prompt = (
            "Generate a professional natal astrology chart wheel. "
            "Include zodiac ring, houses, planets, aspects (red & blue lines), "
            "symbols clearly visible, realistic, clean, high-end design. "
            "No labels outside ring. HD quality. "
            f"This chart is for: {birth_date} {birth_time}, {birth_place}."
        )

        img = client.images.generate(
            model="gpt-image-1",
            prompt=chart_prompt,
            size="1024x1024"
        )

        b64 = img.data[0].b64_json
        png = base64.b64decode(b64)

        chart_id = uuid.uuid4().hex
        chart_path = f"/tmp/{chart_id}.png"
        with open(chart_path, "wb") as f:
            f.write(png)

        return jsonify({
            "text": report_text,
            "chart": f"/chart/{chart_id}",
            "language": lang
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PDF Generator
# -----------------------------
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "No text"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)
        pdf.set_font("Arial", size=12)

        for line in text.split("\n"):
            pdf.multi_cell(0, 8, line)

        pdf.output(pdf_path)
        return send_file(pdf_path, download_name="mystai-report.pdf")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# Static Files
# -----------------------------
@app.route("/audio/<id>")
def audio(id):
    path = f"/tmp/{id}.mp3"
    if not os.path.exists(path):
        return jsonify({"error": "Not found"}), 404
    return send_file(path, mimetype="audio/mpeg")


@app.route("/chart/<id>")
def chart(id):
    path = f"/tmp/{id}.png"
    if not os.path.exists(path):
        return jsonify({"error": "Not found"}), 404
    return send_file(path, mimetype="image/png")


# -----------------------------
# Health Check
# -----------------------------
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
