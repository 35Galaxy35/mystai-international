# ============================================
# MystAI - Full Stable Backend (PREMIUM)
# - /predict           : Normal fal / sohbet
# - /astrology         : Kısa astroloji raporu (text)
# - /astrology-premium : Uzun rapor + gerçek harita PNG
# - /generate_pdf      : Profesyonel PDF çıktısı
# Render uyumlu
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
import sys

# chart_generator.py'yi bulabilmek için
sys.path.append(os.path.dirname(__file__))

from chart_generator import generate_natal_chart


# -----------------------------
# Flask & CORS
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# OpenAI Client
# -----------------------------
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)

# -----------------------------
# Geocoder (doğum yeri → lat/lon)
# -----------------------------
geolocator = Nominatim(user_agent="mystai-astrology")


def geocode_place(place: str):
    """
    Şehir/ülke bilgisinden enlem-boylam bulur.
    Hata veya rate limit durumunda (0.0, 0.0) döner ki backend ÇÖKMEZ.
    """
    try:
        loc = geolocator.geocode(place, timeout=10)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception as e:
        print("Geocode error:", e)
    return 0.0, 0.0


# -----------------------------
# SYSTEM PROMPT
# -----------------------------
def build_system_prompt(type_name, lang):
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel ve destekleyici bir yorumcusun. "
            "Kullanıcıya derin, pozitif ve gerçekçi bir dille açıklama yaparsın."
        )
        types = {
            "general": base + " Genel enerji, sezgi ve rehberlik sun.",
            "astrology": base
            + " Doğum haritasını gezegenler, evler ve açılar üzerinden profesyonel şekilde yorumla. "
            + "Teknik astroloji terimlerini sade ve güçlendirici bir dille açıkla."
        }
    else:
        base = (
            "You are MystAI, a mystical and professional interpreter. "
            "You speak warmly, deeply and offer supportive insights."
        )
        types = {
            "general": base + " Provide intuitive, practical guidance.",
            "astrology": base
            + " Provide a structured natal chart analysis using planets, houses and aspects "
            + "in a clear, empowering tone (no fatalism)."
        }

    return types.get(type_name, types["general"])


# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/")
def index():
    return "MystAI Backend Running 🔮"


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# =====================================================
# /predict  — Normal sohbet / fal
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
        except Exception:
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

        # Ses
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=text, lang=lang).save(audio_path)

        return jsonify({
            "text": text,
            "audio": f"/audio/{audio_id}",
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# /astrology — KISA rapor, HARİTASIZ
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
        except Exception:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\nOdak alanları: {', '.join(focus) or 'Genel'}\n"
                f"Soru: {question}\n\n"
                "Kısa ama net bir astroloji raporu yaz. En önemli temalara odaklan."
            )
        else:
            user_prompt = (
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\nFocus areas: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n\n"
                "Write a concise but meaningful astrology report focusing on key themes."
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

        # chart: None → bu endpoint harita yapmıyor
        return jsonify({
            "text": text,
            "chart": None,
            "audio": None,
            "language": lang,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# /astrology-premium — UZUN RAPOR + GERÇEK HARİTA PNG
# =====================================================
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    """
    Uzun premium astroloji raporu + gerçek doğum haritası PNG üretir.
    Frontend astroloji sayfasını buna bağlarsan:
      - data.text  → uzun rapor
      - data.chart → /chart/<chart_id> (PNG URL)
      - data.chart_id → PDF endpoint'ine göndermek için
    """
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

        # Dil
        try:
            lang = detect(birth_place)
        except Exception:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"PREMIUM astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\n"
                f"Odak alanları: {', '.join(focus) or 'Genel'}\n"
                f"Özel soru/niyet: {question}\n\n"
                "- Kişilik ve ruhsal yapı\n"
                "- Yaşam amacı\n"
                "- Aşk & ilişkiler\n"
                "- Kariyer & maddi alanlar\n"
                "- Karmik dersler\n"
                "- 12 ev analizi (ev ev başlıklarla)\n"
                "- Önümüzdeki 3-6 ay için genel temalar\n\n"
                "Pozitif, destekleyici ve gerçekçi bir dil kullan. Korkutucu, kesin kaderci cümlelerden kaçın."
            )
        else:
            user_prompt = (
                f"Create a PREMIUM astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Focus areas: {', '.join(focus) or 'General'}\n"
                f"Specific question/intention: {question}\n\n"
                "- Personality & psyche\n"
                "- Life purpose\n"
                "- Love & relationships\n"
                "- Career & finances\n"
                "- Karmic lessons\n"
                "- 12-house analysis (each house as a section)\n"
                "- General themes for next 3–6 months\n\n"
                "Use a positive, empowering and non-fatalistic tone."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = completion.choices[0].message.content.strip()

        # --- GERÇEK HARİTA ---
        lat, lon = geocode_place(birth_place)

        chart_id, chart_file = generate_natal_chart(
            birth_date=birth_date,
            birth_time=birth_time,
            latitude=lat,
            longitude=lon,
            out_dir="/tmp",
        )

        return jsonify({
            "text": text,
            "chart": f"/chart/{chart_id}",  # frontend için PNG URL
            "chart_id": chart_id,           # PDF için lazım
            "audio": None,
            "language": lang,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# PROFESYONEL PDF GENERATOR (/generate_pdf)
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
    """
    Beklenen JSON:
    {
      "text": "...uzun rapor...",
      "chart_id": "abcd1234",   # /astrology-premium döndürür
      "language": "tr" veya "en"
    }
    """
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
        pdf.ln(20)

        # Başlık
        if lang == "tr":
            title = "Yapay Zekâ Astroloji Raporun"
            sub = (
                "MystAI, sembolik astrolojiyi yapay zekâ ile birleştirerek doğum haritan "
                "üzerinden kişisel ve derin bir analiz sunar."
            )
        else:
            title = "Your AI Astrology Report"
            sub = (
                "MystAI blends symbolic astrology with AI to offer a deep, personalised "
                "interpretation of your natal chart."
            )

        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 8, title)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, sub)
        pdf.ln(4)

        # Harita görseli
        if chart_id:
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                try:
                    img_w = 130  # mm
                    x = (210 - img_w) / 2
                    y = pdf.get_y() + 5
                    pdf.image(chart_file, x=x, y=y, w=img_w)
                    pdf.ln(95)
                except Exception as e:
                    print("PDF image error:", e)
                    pdf.ln(10)

        # Metin
        if lang == "tr":
            intro = "Detaylı astroloji raporun aşağıdadır:\n"
        else:
            intro = "Your detailed astrology report is below:\n"

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
