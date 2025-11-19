# ============================================
# MystAI - Full Premium Backend (Commercial Ready)
# VER: v4.2 (Full Fix Pack)
# --------------------------------------------
# - /predict : sohbet + TTS
# - /astrology-premium (NATAL)
# - /solar-return        (SOLAR)
# - /transits            (TRANSIT)
# - /generate_pdf        (Doğru başlık + kesintisiz metin + PNG render)
# - /chart/<id>, /audio/<id>
# ============================================

import os
import uuid
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS
from fpdf import FPDF
from geopy.geocoders import Nominatim

import sys
sys.path.append(os.path.dirname(__file__))
from chart_generator import generate_natal_chart


app = Flask(__name__)
CORS(app)

# -----------------------------
# OpenAI
# -----------------------------
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)

# -----------------------------
# Yol sabitleri
# -----------------------------
BACKEND_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))

FONT_PATH_TTF = os.path.join(BACKEND_DIR, "fonts", "DejaVuSans.ttf")
LOGO_PATH = os.path.join(ROOT_DIR, "images", "mystai-logo.png")

# -----------------------------
# Geocoder
# -----------------------------
geolocator = Nominatim(user_agent="mystai-astrology")


def geocode_place(place):
    try:
        loc = geolocator.geocode(place, timeout=10)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except:
        pass
    return 0.0, 0.0


# -----------------------------
# System Prompts
# -----------------------------
def build_system_prompt(kind, lang):
    if lang == "tr":
        base = (
            "Sen MystAI'sin. Profesyonel, destekleyici, sakin ve derin bir üslup kullan. "
            "Kaderci veya korkutucu ifadeler kullanma."
        )
        mapping = {
            "general": base + " Genel sezgisel rehberlik sun.",
            "astrology": base + " Natal haritayı gezegenler, evler ve açılarla profesyonelce yorumla.",
            "solar_return": base + " Solar return haritasını yıllık tema olarak yorumla.",
            "transit": base + " Transit gezegen etkilerini danışanın doğum haritası üzerinden açıkla."
        }
    else:
        base = (
            "You are MystAI. You speak professionally, warmly and with supportive clarity. "
            "Avoid fear-based or fatalistic statements."
        )
        mapping = {
            "general": base + " Provide intuitive guidance.",
            "astrology": base + " Interpret the natal chart using planets, houses and aspects.",
            "solar_return": base + " Explain the yearly themes via the solar return chart.",
            "transit": base + " Explain how current transits interact with the natal chart."
        }

    return mapping.get(kind, mapping["general"])


# =====================================================
# Normal /predict
# =====================================================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = (data.get("user_input") or "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş"}), 400

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

        # TTS
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=text, lang=lang).save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{audio_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# NATAL
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
        lang = data.get("language")

        if not (birth_date and birth_time and birth_place):
            return jsonify({"error": "Eksik bilgi"}), 400

        if not lang:
            try:
                lang = detect(birth_place)
            except:
                lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"NATAL astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\n"
                f"Odak: {', '.join(focus) or 'Genel'}\n"
                f"Soru: {question}\n\n"
                "- Kişilik, ruhsal yapı\n"
                "- Yaşam amacı\n"
                "- Aşk / İlişkiler\n"
                "- Kariyer ve maddi alan\n"
                "- Karmik temalar\n"
                "- 12 evin detaylı analizi\n"
                "- Önümüzdeki 3-6 aylık genel temalar\n"
            )
        else:
            user_prompt = (
                f"Create a NATAL astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Focus: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n\n"
                "- Personality\n"
                "- Life purpose\n"
                "- Love & relationships\n"
                "- Career & money\n"
                "- Karmic themes\n"
                "- Full house-by-house analysis\n"
                "- Themes for next 3–6 months\n"
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = completion.choices[0].message.content.strip()

        # Harita
        lat, lon = geocode_place(birth_place)
        cid = None
        path = None
        try:
            cid, fpath = generate_natal_chart(
                birth_date=birth_date,
                birth_time=birth_time,
                latitude=lat,
                longitude=lon,
                out_dir="/tmp"
            )
            path = f"/chart/{cid}"
        except Exception as e:
            print("Natal chart error:", e)

        return jsonify({
            "text": text,
            "chart": path,
            "chart_id": cid,
            "mode": "natal",
            "language": lang
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# SOLAR RETURN
# =====================================================
@app.route("/solar-return", methods=["POST"])
def solar_return():
    try:
        data = request.json or {}
        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        year = data.get("year")
        lang = data.get("language")

        if not (birth_date and birth_time and birth_place):
            return jsonify({"error": "Eksik bilgi"}), 400

        if not year:
            year = datetime.utcnow().year
        year = int(year)

        if not lang:
            lang = "tr"
        if lang not in ("tr", "en"):
            lang = "en"

        # SR tarih
        y0, m0, d0 = map(int, birth_date.split("-"))
        sr_date = f"{year}-{m0:02d}-{d0:02d}"

        # Harita
        lat, lon = geocode_place(birth_place)
        cid = None
        path = None
        try:
            cid, fpath = generate_natal_chart(
                birth_date=sr_date,
                birth_time=birth_time,
                latitude=lat,
                longitude=lon,
                out_dir="/tmp"
            )
            path = f"/chart/{cid}"
        except Exception as e:
            print("Solar chart error:", e)

        system_prompt = build_system_prompt("solar_return", lang)

        if lang == "tr":
            user_prompt = (
                f"Solar return yılı: {year}\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n\n"
                "- Bu yılın ana temaları\n"
                "- Aşk & ilişkiler\n"
                "- Kariyer & maddi fırsatlar\n"
                "- Ruhsal gelişim ve karmik dersler\n"
            )
        else:
            user_prompt = (
                f"Solar return year: {year}\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n\n"
                "- Main themes\n"
                "- Love & relationships\n"
                "- Career & opportunities\n"
                "- Spiritual & karmic lessons\n"
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({
            "text": text,
            "chart": path,
            "chart_id": cid,
            "mode": "solar",
            "solar_year": year,
            "language": lang
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# TRANSITS
# =====================================================
@app.route("/transits", methods=["POST"])
def transits():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        lang = data.get("language")

        if not (birth_date and birth_time and birth_place):
            return jsonify({"error": "Eksik bilgi"}), 400

        if not lang:
            lang = "tr"
        if lang not in ("tr", "en"):
            lang = "en"

        today = datetime.utcnow().strftime("%Y-%m-%d")

        system_prompt = build_system_prompt("transit", lang)

        if lang == "tr":
            user_prompt = (
                f"Transit raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"Danışan: {name}\n"
                f"Bugün: {today}\n\n"
                "- Şu anki ana enerji\n"
                "- Yakın gelecek temaları\n"
                "- Aşk, kariyer, para, ruhsal gelişim\n"
                "- Satürn, Uranüs, Neptün, Plüton transit etkileri\n"
            )
        else:
            user_prompt = (
                f"Create a transit report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Today: {today}\n\n"
                "- Current energy\n"
                "- Themes for coming weeks\n"
                "- Love, career, finances, spiritual growth\n"
                "- Saturn / Uranus / Neptune / Pluto effects\n"
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({
            "text": text,
            "language": lang,
            "mode": "transits"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# PDF TEMPLATE
# =====================================================
class MystPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists(FONT_PATH_TTF):
            self.add_font("DejaVu", "", FONT_PATH_TTF, uni=True)
            self.add_font("DejaVu", "B", FONT_PATH_TTF, uni=True)

    def header(self):
        # Logo sol üst
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 10, 7, 15)

        self.set_xy(30, 8)
        self.set_font("DejaVu", "B", 11)
        self.set_text_color(25, 30, 55)
        self.cell(0, 5, "MystAI Astrology", ln=1)

        self.set_xy(30, 14)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(110, 115, 150)
        self.cell(0, 4, "mystai.ai  •  AI-powered divination & astrology", ln=1)

        self.ln(4)

    def footer(self):
        self.set_y(-13)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(130, 130, 160)
        self.cell(0, 8, f"Page {self.page_no()} • MystAI.ai", align="C")


# =====================================================
# GENERATE PDF (Fix Pack)
# =====================================================
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}

        text = (data.get("text") or "").strip()
        chart_id = data.get("chart_id")
        lang = data.get("language", "en")
        report_type = data.get("report_type", "natal").lower()

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name")

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = MystPDF()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        # Başlıklar
        if lang == "tr":
            titles = {
                "natal": ("MystAI Natal Doğum Haritası Raporu",
                          "Bu rapor doğum haritanın derinlemesine yorumlanmış halidir."),
                "solar": ("MystAI Solar Return Astroloji Raporu",
                          "Bu rapor önümüzdeki yılın ana temalarını solar return üzerinden açıklar."),
                "transits": ("MystAI Transit Astroloji Raporu",
                             "Bu rapor güncel gezegen transitlerini senin doğum haritan ile ilişkilendirir.")
            }
            intro_heading = "Detaylı astroloji raporun aşağıdadır:"
        else:
            titles = {
                "natal": ("MystAI Natal Astrology Report",
                          "A deep interpretation of your natal chart."),
                "solar": ("MystAI Solar Return Report",
                          "This report reveals the main themes of your year ahead."),
                "transits": ("MystAI Transit Astrology Report",
                             "This report explains how current transits interact with your chart.")
            }
            intro_heading = "Your detailed astrology report is below:"

        title, subtitle = titles.get(report_type, titles["natal"])

        pdf.set_font("DejaVu", "B", 17)
        pdf.set_text_color(30, 32, 60)
        pdf.multi_cell(0, 8, title)
        pdf.ln(2)

        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(85, 90, 125)
        pdf.multi_cell(0, 6, subtitle)
        pdf.ln(5)

        # Meta
        meta = []
        if birth_date and birth_time and birth_place:
            if lang == "tr":
                meta.append(f"Doğum: {birth_date} • {birth_time} • {birth_place}")
            else:
                meta.append(f"Birth: {birth_date} • {birth_time} • {birth_place}")

        if name:
            if lang == "tr":
                meta.append(f"Danışan: {name}")
            else:
                meta.append(f"Client: {name}")

        if meta:
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(105, 110, 140)
            pdf.multi_cell(0, 5, "  •  ".join(meta))
            pdf.ln(5)

        # Harita (PNG direkt!)
        if chart_id and report_type in ("natal", "solar"):
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                img_w = 140
                x = (210 - img_w) / 2
                y = pdf.get_y()
                pdf.image(chart_file, x=x, y=y, w=img_w)
                pdf.add_page()

        # Metin
        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(25, 25, 40)

        pdf.set_font("DejaVu", "B", 13)
        pdf.multi_cell(0, 7, intro_heading)
        pdf.ln(3)

        pdf.set_font("DejaVu", "", 11)

        paragraphs = text.split("\n")
        for p in paragraphs:
            p = p.strip()
            if not p:
                pdf.ln(3)
                continue
            pdf.multi_cell(0, 6, p)
            pdf.ln(1)

        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True, download_name="mystai-report.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# SERVERS
# =====================================================
@app.route("/audio/<id>")
def serve_audio(id):
    f = f"/tmp/{id}.mp3"
    if not os.path.exists(f):
        return jsonify({"error": "Ses yok"}), 404
    return send_file(f, mimetype="audio/mpeg")


@app.route("/chart/<id>")
def serve_chart(id):
    f = f"/tmp/{id}.png"
    if not os.path.exists(f):
        return jsonify({"error": "Harita yok"}), 404
    return send_file(f, mimetype="image/png")


# =====================================================
# Run
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

