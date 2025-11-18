# ============================================
# MystAI - Full Premium Backend (FINAL)
# --------------------------------------------
# Özellikler:
# - /predict           : Normal fal / sohbet + TTS
# - /astrology         : Kısa, text-only astroloji
# - /astrology-premium : Uzun premium rapor + gerçek natal harita PNG
# - /solar-return      : Basit Solar Return raporu + harita (yaklaşık)
# - /transits          : Transit odaklı yorum
# - /generate_pdf      : Profesyonel PDF çıktısı (harita + uzun rapor)
# - /audio/<id>        : TTS dosyası
# - /chart/<id>        : Harita PNG dosyası
#
# Render uyumlu, haritalar /tmp altında saklanır.
# ============================================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS
from fpdf import FPDF
from geopy.geocoders import Nominatim

import os
import sys
import uuid
import traceback
import base64
from datetime import datetime

# chart_generator.py aynı klasörde olduğu için:
sys.path.append(os.path.dirname(__file__))
from chart_generator import generate_natal_chart  # doğum haritası çizer


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
    """Şehir/ülke bilgisinden enlem-boylam bulur. Hata olursa (0,0) döner."""
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
def build_system_prompt(type_name: str, lang: str) -> str:
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel ve destekleyici bir yorumcusun. "
            "Kullanıcıya derin, pozitif ve gerçekçi bir dille açıklama yaparsın."
        )
        types = {
            "general": base + " Genel enerji, sezgi ve rehberlik sun.",
            "astrology": base
            + " Doğum haritasını gezegenler, evler ve açılar üzerinden profesyonel şekilde yorumla. "
            + "Teknik astroloji bilgin yüksek, fakat dili sade ve güçlendirici kullan. "
            + "Korkutucu, kesin kaderci ifadelerden uzak dur.",
            "transit": base
            + " Transit gezegenlerin danışanın doğum haritası üzerindeki etkilerini açıkla. "
            + "Önümüzdeki birkaç hafta/ay için ana temaları özetle; günlük fal gibi yüzeysel olma.",
            "solar_return": base
            + " Solar return (güneş dönüşü) haritasını yıllık tema olarak yorumla. "
            + "Bu yılın ana derslerini ve fırsatlarını, özellikle aşk, kariyer ve ruhsal gelişim açısından açıkla.",
        }
    else:
        base = (
            "You are MystAI, a mystical and professional interpreter. "
            "You speak warmly, deeply and offer supportive insights."
        )
        types = {
            "general": base + " Provide intuitive guidance.",
            "astrology": base
            + " Provide a structured natal chart analysis using planets, houses and aspects. "
            + "Use a clear and empowering tone, avoid fatalistic language.",
            "transit": base
            + " Explain how the current transiting planets interact with the natal chart. "
            + "Summarise the main themes for the coming weeks and months.",
            "solar_return": base
            + " Interpret the solar return chart as a theme for the year ahead. "
            + "Highlight love, career, personal growth and karmic lessons.",
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


# -----------------------------
# NORMAL /predict (fal + TTS)
# -----------------------------
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

        # Ses dosyası oluştur
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=text, lang=lang).save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{audio_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# BASIC ASTROLOGY (kısa)
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
        lang = data.get("language")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        if not lang:
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
                f"İsim: {name}\nOdak: {', '.join(focus) or 'Genel'}\n"
                f"Soru: {question}\n"
                "Natal haritaya dayalı, kısa ama anlamlı bir astroloji raporu yaz. "
                "En önemli 3-4 temaya odaklan."
            )
        else:
            user_prompt = (
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\nFocus: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n"
                "Write a concise but meaningful astrology report based on the natal chart. "
                "Focus on the 3–4 most important themes."
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

        return jsonify({"text": text, "chart": None, "audio": None, "language": lang})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PREMIUM ASTROLOGY (natal)
# -----------------------------
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    """
    Uzun premium astroloji raporu + gerçek doğum haritası PNG üretir.
    Frontend astrology.html bu endpoint'i kullanabilir.
    """
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        focus = data.get("focus_areas", [])
        question = data.get("question", "")
        lang = data.get("language")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        # Dil
        if not lang:
            try:
                lang = detect(birth_place)
            except Exception:
                lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"Premium astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\n"
                f"Odak alanları: {', '.join(focus) or 'Genel'}\n"
                f"Özel soru/niyet: {question}\n\n"
                "- Kişilik ve ruhsal yapı\n"
                "- Yaşam amacı\n"
                "- Aşk & İlişkiler\n"
                "- Kariyer & Para\n"
                "- Karmik dersler\n"
                "- 12 Ev analizi (ev ev, başlıklarla)\n"
                "- Önümüzdeki 3-6 aya dair genel temalar\n"
                "Pozitif, destekleyici ve gerçekçi bir dil kullan. "
                "Korkutucu, kesin kaderci ifadelerden kaçın."
            )
        else:
            user_prompt = (
                f"Create a premium astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Focus areas: {', '.join(focus) or 'General'}\n"
                f"Specific question/intention: {question}\n\n"
                "- Personality & psyche\n"
                "- Life purpose\n"
                "- Love & relationships\n"
                "- Career & finances\n"
                "- Karmic lessons\n"
                "- Detailed 12-house analysis (with headings)\n"
                "- General future themes for the next 3-6 months\n"
                "Use a positive, empowering tone and avoid fatalistic statements."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = completion.choices[0].message.content.strip()

        # ------- GERÇEK DOĞUM HARİTASI OLUŞTUR -------
        lat, lon = geocode_place(birth_place)
        chart_id = None
        chart_public_path = None

        try:
            chart_id, chart_file_path = generate_natal_chart(
                birth_date=birth_date,
                birth_time=birth_time,
                latitude=lat,
                longitude=lon,
                out_dir="/tmp",
            )
            chart_public_path = f"/chart/{chart_id}"
        except Exception as e:
            print("Chart generation error:", e)

        return jsonify(
            {
                "text": text,
                "chart": chart_public_path,  # frontend burayı kullanıyor
                "chart_id": chart_id,        # PDF için gerekli
                "audio": None,
                "language": lang,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# SOLAR RETURN (basit versiyon)
# -----------------------------
@app.route("/solar-return", methods=["POST"])
def solar_return():
    """
    Basit Solar Return:
    - Aynı doğum günü ve saati kullanarak, seçilen yıl için harita çıkarır.
    - Astronomik olarak %100 hassas değil ama yorum için yeterli.
    """
    try:
        data = request.json or {}
        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        year = data.get("year")  # opsiyonel, yoksa şu yıl
        lang = data.get("language")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        if not year:
            year = datetime.utcnow().year
        year = int(year)

        # Doğum tarihindeki ay-gün, ama yıl = seçilen yıl
        y0, m0, d0 = map(int, birth_date.split("-"))
        sr_date = f"{year:04d}-{m0:02d}-{d0:02d}"

        if not lang:
            try:
                lang = detect(birth_place)
            except Exception:
                lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        # Harita
        lat, lon = geocode_place(birth_place)
        chart_id = None
        chart_public_path = None
        try:
            chart_id, chart_file_path = generate_natal_chart(
                birth_date=sr_date,
                birth_time=birth_time,
                latitude=lat,
                longitude=lon,
                out_dir="/tmp",
            )
            chart_public_path = f"/chart/{chart_id}"
        except Exception as e:
            print("Solar return chart error:", e)

        # Yorum
        system_prompt = build_system_prompt("solar_return", lang)

        if lang == "tr":
            user_prompt = (
                f"Solar return (güneş dönüşü) astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"Solar return yılı: {year}\n\n"
                "- Bu yılın ana temaları\n"
                "- Aşk ve ilişkiler\n"
                "- Kariyer, para ve fırsatlar\n"
                "- Ruhsal gelişim ve karmik dersler\n"
                "Yaklaşık bir yıllık dönemi genel hatlarıyla yorumla."
            )
        else:
            user_prompt = (
                f"Create a solar return astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Solar return year: {year}\n\n"
                "- Main themes of this year\n"
                "- Love and relationships\n"
                "- Career, money and opportunities\n"
                "- Spiritual growth and karmic lessons\n"
                "Describe roughly the upcoming year."
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

        return jsonify(
            {
                "text": text,
                "chart": chart_public_path,
                "chart_id": chart_id,
                "language": lang,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# TRANSIT ETKİLERİ
# -----------------------------
@app.route("/transits", methods=["POST"])
def transits():
    """
    Transit odaklı yorum (şu anki/çok yakın gelecek enerji).
    Grafik çizdirmiyoruz; sadece profesyonel metin.
    """
    try:
        data = request.json or {}
        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        lang = data.get("language")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        if not lang:
            try:
                lang = detect(birth_place)
            except Exception:
                lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        today = datetime.utcnow().strftime("%Y-%m-%d")

        system_prompt = build_system_prompt("transit", lang)

        if lang == "tr":
            user_prompt = (
                f"Transit odaklı astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"Danışan: {name}\n"
                f"Bugün: {today}\n\n"
                "- Yakın geçmiş ve şu anki enerji\n"
                "- Önümüzdeki haftalar için ana temalar\n"
                "- Aşk, kariyer, finans ve ruhsal gelişim için ayrı paragraflar\n"
                "- Satürn, Uranüs, Neptün ve Plüton transitlerinin önemli etkileri\n"
                "Somut tavsiyeler ver; korkutucu olmayıp güçlendirici bir dil kullan."
            )
        else:
            user_prompt = (
                f"Create a transit-focused astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Today: {today}\n\n"
                "- Recent past and current energy\n"
                "- Key themes for the next weeks\n"
                "- Separate paragraphs for love, career, finances and spiritual growth\n"
                "- Focus on important Saturn, Uranus, Neptune and Pluto transits\n"
                "Give concrete advice, use an empowering tone and avoid fear-based language."
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
        return jsonify({"text": text, "language": lang})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PROFESYONEL PDF GENERATOR
# -----------------------------
class MystPDF(FPDF):
    def header(self):
        # üst şerit
        self.set_fill_color(12, 20, 45)  # koyu lacivert
        self.rect(0, 0, 210, 25, "F")
        self.set_xy(10, 7)
        self.set_text_color(255, 215, 120)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 6, "MystAI Astrology Report", ln=1)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(220, 230, 255)
        self.cell(0, 4, "mystai.ai • AI-powered divination & astrology", ln=1)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 155, 180)
        self.cell(0, 10, f"MystAI.ai • Page {self.page_no()}", align="C")


@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    """
    Frontend, text + chart_id + language ile çağırır.
    Profesyonel görünümlü bir PDF üretir:
    - Kapak başlığı, alt başlık
    - Varsa harita görseli
    - Uzun rapor metni
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
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        pdf.ln(20)  # header'dan sonra boşluk

        if lang == "tr":
            title = "Yapay Zekâ Astroloji Raporun"
            sub = (
                "MystAI, sembolik astrolojiyi yapay zekâ ile birleştirerek doğum haritan "
                "ve gökyüzü hareketleri üzerinden kişisel ve derinlemesine bir yorum sunar."
            )
            intro = "Detaylı astroloji raporun aşağıdadır:\n"
        else:
            title = "Your AI Astrology Report"
            sub = (
                "MystAI blends symbolic astrology with advanced AI to offer a deep, "
                "personalised interpretation of your chart and current sky."
            )
            intro = "Your detailed astrology report is below:\n"

        # Başlık
        pdf.set_text_color(30, 35, 60)
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 8, title)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(80, 86, 120)
        pdf.multi_cell(0, 6, sub)
        pdf.ln(6)

        # Harita görseli (varsa) – önce RGB'ye çevir
        if chart_id:
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                try:
                    from PIL import Image

                    img = Image.open(chart_file).convert("RGB")
                    rgb_fixed = f"/tmp/{chart_id}_rgb.jpg"
                    img.save(rgb_fixed, "JPEG", quality=95)

                    img_width = 130
                    x = (210 - img_width) / 2
                    y = pdf.get_y()
                    pdf.image(rgb_fixed, x=x, y=y, w=img_width)
                    pdf.ln(90)
                except Exception as e:
                    print("PDF image error:", e)
                    pdf.ln(10)

        # Gövde
        pdf.set_text_color(40, 40, 60)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 6, intro)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(25, 25, 40)

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
            pdf.multi_cell(0, 5.5, line)
            pdf.ln(0.5)

        pdf.output(pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name="mystai-report.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# STATIC FILE SERVERS
# -----------------------------
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


# -----------------------------
# RUN (Render uyumlu)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
