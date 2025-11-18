# ============================================
# MystAI - Full Stable Backend (PREMIUM VERSION)
# ============================================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS
from fpdf import FPDF
from geopy.geocoders import Nominatim

import os
import uuid
import traceback
import base64
import sys

# Modül yolu düzeltme
sys.path.append(os.path.dirname(__file__))

# Chart generator import
from chart_generator import generate_natal_chart


# -----------------------------
# FLASK
# -----------------------------
app = Flask(__name__)
CORS(app)


# -----------------------------
# OPENAI CLIENT
# -----------------------------
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)


# -----------------------------
# GEOCODER
# -----------------------------
geolocator = Nominatim(user_agent="mystai-astrology")


def geocode_place(place: str):
    """Şehir/ülke bilgisi → enlem-boylam"""
    try:
        loc = geolocator.geocode(place, timeout=10)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception as e:
        print("Geocode error:", e)
    return 0.0, 0.0


# -----------------------------
# SYSTEM PROMPT BUILDER
# -----------------------------
def build_system_prompt(type_name, lang):
    if lang == "tr":
        base = "Sen MystAI adlı profesyonel ve mistik bir yorumcusun. Derin, pozitif ve destekleyici konuşursun."
        types = {
            "general": base + " Genel rehberlik sun.",
            "astrology": base + " Doğum haritasını profesyonel bir astroloji uzmanı gibi yorumla."
        }
    else:
        base = "You are MystAI, a mystical and professional interpreter. You speak warmly and deeply."
        types = {
            "general": base + " Provide intuitive guidance.",
            "astrology": base + " Provide a structured astrology report using planets and houses."
        }

    return types.get(type_name, types["general"])


# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/")
def index():
    return "MystAI Backend Running ✔"


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# =====================================================
# NORMAL /predict
# =====================================================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = data.get("user_input", "").strip()

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
# BASIC ASTROLOGY
# =====================================================
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
            return jsonify({"error": "Eksik bilgi"}), 400

        try:
            lang = detect(birth_place)
        except:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\nOdak: {', '.join(focus) or 'Genel'}\n"
                f"Soru: {question}\n"
                "Kısa ama anlamlı bir astroloji analizi yaz."
            )
        else:
            user_prompt = (
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\nFocus: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n"
                "Write a meaningful but short astrology report."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=700,
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({"text": text, "chart": None, "audio": None, "language": lang})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# PREMIUM ASTROLOGY (HARİTA + RAPOR)
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

        if not all([birth_date, birth_time, birth_place]):
            return jsonify({"error": "Eksik bilgi"}), 400

        try:
            lang = detect(birth_place)
        except:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        # User prompt
        if lang == "tr":
            user_prompt = (
                f"Premium astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\n"
                f"Odak: {', '.join(focus) or 'Genel'}\n"
                f"Soru: {question}\n\n"
                "12 ev analizi, kişilik, ilişkiler, kariyer ve geleceğe dair temaları yaz."
            )
        else:
            user_prompt = (
                f"Create a premium astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Focus: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n\n"
                "Include 12 houses, personality, love, career and future themes."
            )

        # LLM raporu
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = completion.choices[0].message.content.strip()

        # HARİTA
        lat, lon = geocode_place(birth_place)

        chart_id, chart_path = generate_natal_chart(
            birth_date,
            birth_time,
            lat,
            lon,
            out_dir="/tmp"
        )

        return jsonify(
            {
                "text": text,
                "chart": f"/chart/{chart_id}",
                "chart_id": chart_id,
                "language": lang
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# PDF GENERATOR
# =====================================================
class MystPDF(FPDF):
    def header(self):
        self.set_auto_page_break(auto=True, margin=18)
        self.set_fill_color(12, 20, 45)
        self.rect(0, 0, 210, 25, "F")
        self.set_xy(10, 7)
        self.set_text_color(255, 215, 100)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 6, "MystAI Astrology Report", ln=1)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(230, 235, 255)
        self.cell(0, 4, "Powered by MystAI.ai", ln=1)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 155, 180)
        self.cell(0, 10, f"MystAI.ai • {self.page_no()}", align="C")


@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()
        chart_id = data.get("chart_id")
        lang = data.get("language", "en")

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = MystPDF()
        pdf.add_page()

        # Başlık
        pdf.ln(20)

        if lang == "tr":
            title = "Yapay Zekâ Astroloji Raporun"
            sub = (
                "MystAI, sembolik astrolojiyi yapay zekâ ile birleştirerek sana özel bir rapor sunar."
            )
        else:
            title = "Your AI Astrology Report"
            sub = (
                "MystAI blends symbolic astrology with AI to deliver a personalised report."
            )

        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 8, title)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, sub)
        pdf.ln(4)

        # Harita ekle
        if chart_id:
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                try:
                    pdf.image(chart_file, x=40, y=pdf.get_y() + 5, w=130)
                    pdf.ln(95)
                except Exception:
                    pdf.ln(10)

        # İçerik
        if lang == "tr":
            intro = "Detaylı astroloji raporun:\n"
        else:
            intro = "Your detailed astrology report:\n"

        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 6, intro)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 11)

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
            pdf.multi_cell(0, 5.5, line)

        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True, download_name="mystai-report.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# STATIC FILE SERVERS
# =====================================================
@app.route("/audio/<id>")
def serve_audio(id):
    path = f"/tmp/{id}.mp3"
    if not os.path.exists(path):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(path, mimetype="audio/mpeg")


@app.route("/chart/<id>")
def serve_chart(id):
    path = f"/tmp/{id}.png"
    if not os.path.exists(path):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(path, mimetype="image/png")


# =====================================================
# RUN (Render uyumlu)
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

