import os
import sys
import uuid
import traceback
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS
from geopy.geocoders import Nominatim
from fpdf import FPDF

# chart_generator.py aynı klasörde
sys.path.append(os.path.dirname(__file__))
from chart_generator import generate_natal_chart

# -----------------------------
# Flask
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# OpenAI API
# -----------------------------
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)

# -----------------------------
# Yol sabitleri (font + logo)
# -----------------------------
BACKEND_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))

FONT_PATH_TTF = os.path.join(BACKEND_DIR, "fonts", "DejaVuSans.ttf")
LOGO_PATH = os.path.join(ROOT_DIR, "images", "mystai-logo.png")

# -----------------------------
# Geocoder
# -----------------------------
geolocator = Nominatim(user_agent="mystai-astrology")

def geocode_place(place: str):
    try:
        loc = geolocator.geocode(place, timeout=10)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except:
        pass
    return 0.0, 0.0


# -----------------------------
# SYSTEM PROMPT BUILDER
# -----------------------------
def build_system_prompt(kind: str, lang: str):

    base_tr = (
        "Sen MystAI adında profesyonel, mistik ve destekleyici bir yorumcusun. "
        "Kullanıcıya güçlü, pozitif ve derin bir dille yorum yap."
    )
    base_en = (
        "You are MystAI, a mystical and professional interpreter. "
        "Speak warmly, clearly and with empowering insights."
    )

    mapping_tr = {
        "general": base_tr,
        "astrology": base_tr + " Doğum haritasını gezegenler, evler ve açılarla profesyonelce yorumla.",
        "solar_return": base_tr + " Solar return (güneş dönüşü) temasını yıllık olarak yorumla.",
        "transit": base_tr + " Transitlerin danışan üzerindeki etkilerini detaylandır.",
    }

    mapping_en = {
        "general": base_en,
        "astrology": base_en + " Interpret the natal chart with planets, houses, and aspects.",
        "solar_return": base_en + " Interpret the solar return theme for the year ahead.",
        "transit": base_en + " Explain how the current transits affect the natal chart.",
    }

    if lang == "tr":
        return mapping_tr.get(kind, mapping_tr["general"])
    return mapping_en.get(kind, mapping_en["general"])


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def index():
    return "MystAI Backend Running 🔮"


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# =====================================================
#  NORMAL /predict
# =====================================================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = (data.get("user_input") or "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        try:
            lang = detect(user_input)
        except:
            lang = "en"

        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("general", lang)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )

        text = completion.choices[0].message.content.strip()

        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=text, lang=lang).save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{audio_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# =====================================================
#  NATAL PREMIUM
# =====================================================
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        focus = data.get("focus_areas", [])
        question = data.get("question", "")
        lang = data.get("language", "en")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        if lang not in ("tr", "en"):
            lang = "en"

        lat, lon = geocode_place(birth_place)

        # NATAL CHART
        chart_id, chart_file = generate_natal_chart(
            birth_date=birth_date,
            birth_time=birth_time,
            latitude=lat,
            longitude=lon,
            out_dir="/tmp",
        )

        # AI TEXT
        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"Premium NATAL astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\n"
                f"Odak alanları: {', '.join(focus) or 'Genel'}\n"
                f"Soru: {question}\n\n"
                "- Kişilik & ruhsal yapı\n"
                "- Yaşam amacı\n"
                "- Aşk & ilişkiler\n"
                "- Kariyer & para\n"
                "- 12 Ev analizi\n"
                "- Önümüzdeki 3–6 ay"
            )
        else:
            user_prompt = (
                f"Create a premium NATAL astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Focus: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n\n"
                "- Personality\n"
                "- Life purpose\n"
                "- Love & relationships\n"
                "- Career & finances\n"
                "- 12-house analysis\n"
                "- Next 3–6 months"
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({
            "text": text,
            "chart": f"/chart/{chart_id}",
            "chart_id": chart_id,
            "language": lang,
            "mode": "natal",
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# =====================================================
#  SOLAR RETURN
# =====================================================
@app.route("/solar-return", methods=["POST"])
def solar_return():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        lang = data.get("language", "en")
        year = int(data.get("year") or datetime.utcnow().year)

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        if lang not in ("tr", "en"):
            lang = "en"

        y, m, d = map(int, birth_date.split("-"))
        sr_date = f"{year}-{m:02d}-{d:02d}"

        lat, lon = geocode_place(birth_place)

        chart_id, _ = generate_natal_chart(
            birth_date=sr_date,
            birth_time=birth_time,
            latitude=lat,
            longitude=lon,
            out_dir="/tmp",
        )

        system_prompt = build_system_prompt("solar_return", lang)

        if lang == "tr":
            user_prompt = (
                f"Solar return raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"Yıl: {year}"
            )
        else:
            user_prompt = (
                f"Create a solar return astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Year: {year}"
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900,
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({
            "text": text,
            "chart": f"/chart/{chart_id}",
            "chart_id": chart_id,
            "language": lang,
            "mode": "solar",
            "solar_year": year,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# =====================================================
#  TRANSITS
# =====================================================
@app.route("/transits", methods=["POST"])
def transits():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        lang = data.get("language", "en")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        today = datetime.utcnow().strftime("%Y-%m-%d")

        system_prompt = build_system_prompt("transit", lang)

        if lang == "tr":
            user_prompt = (
                f"Transit odaklı astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"Danışan: {name}\n"
                f"Bugün: {today}"
            )
        else:
            user_prompt = (
                f"Create a transit-focused astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Today: {today}"
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({"text": text, "language": lang, "mode": "transits"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# =====================================================
#  PDF
# =====================================================
class MystPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists(FONT_PATH_TTF):
            self.add_font("DejaVu", "", FONT_PATH_TTF, uni=True)
            self.add_font("DejaVu", "B", FONT_PATH_TTF, uni=True)

    def header(self):
        # LOGO SOL ÜSTTE - ORTA BOY
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, x=10, y=6, w=38)  # burası sol üst + orta boy
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"MystAI.ai • Page {self.page_no()}", align="C")


@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}

        text = (data.get("text") or "").strip()
        chart_id = data.get("chart_id")
        lang = data.get("language", "en")
        report_type = data.get("report_type", "natal")

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        # PDF
        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = MystPDF()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        # -------------------------------------------
        # BAŞLIK (Logo alta yazı)
        # -------------------------------------------
        pdf.set_font("DejaVu", "B", 18)
        pdf.set_text_color(30, 28, 60)

        if lang == "tr":
            titles = {
                "natal": "MystAI Natal Doğum Haritası Raporu",
                "solar": "MystAI Solar Return Astroloji Raporu",
                "transits": "MystAI Transit Astroloji Raporu"
            }
        else:
            titles = {
                "natal": "MystAI Natal Astrology Report",
                "solar": "MystAI Solar Return Report",
                "transits": "MystAI Transit Report"
            }

        pdf.multi_cell(0, 10, titles.get(report_type, "MystAI Report"))
        pdf.ln(4)

        # -------------------------------------------
        # CHART (sadece natal & solar)
        # -------------------------------------------
        if chart_id and report_type in ("natal", "solar"):
            chart_path = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_path):
                pdf.image(chart_path, x=25, w=160)
                pdf.ln(8)
                pdf.add_page()

        # -------------------------------------------
        # METİN
        # -------------------------------------------
        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(25, 25, 40)

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(3)
                continue
            pdf.multi_cell(0, 6, line)
            pdf.ln(1)

        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True, download_name="mystai-report.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




# =====================================================
#  STATIC FILES
# =====================================================
@app.route("/audio/<id>")
def serve_audio(id):
    path = f"/tmp/{id}.mp3"
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    return send_file(path, mimetype="audio/mpeg")


@app.route("/chart/<id>")
def serve_chart(id):
    path = f"/tmp/{id}.png"
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    return send_file(path, mimetype="image/png")


# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
