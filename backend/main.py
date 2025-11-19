# ============================================
# MystAI - Full Premium Backend (Commercial Ready)
# --------------------------------------------
# Özellikler:
# - /predict           : Normal fal / sohbet + TTS
# - /astrology-premium : Natal (uzun rapor + gerçek doğum haritası PNG)
# - /solar-return      : Solar return raporu + solar harita PNG
# - /transits          : Transit odaklı rapor (haritasız)
# - /generate_pdf      : Profesyonel PDF (logo + kapak + harita + uzun rapor)
# - /audio/<id>        : TTS dosyası
# - /chart/<id>        : Harita PNG dosyası
#
# Render uyumlu, haritalar ve PDF'ler /tmp altında saklanır.
# ============================================

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
from fpdf import FPDF
from geopy.geocoders import Nominatim

# chart_generator.py aynı klasörde
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
# Yol sabitleri (logo, font)
# -----------------------------
BACKEND_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))

FONT_PATH_TTF = os.path.join(BACKEND_DIR, "fonts", "DejaVuSans.ttf")
LOGO_PATH = os.path.join(ROOT_DIR, "images", "mystai-logo.png")


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
def build_system_prompt(kind: str, lang: str) -> str:
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel ve destekleyici bir yorumcusun. "
            "Kullanıcıya derin, pozitif ve gerçekçi bir dille açıklama yaparsın."
        )
        mapping = {
            "general": base + " Genel enerji, sezgi ve rehberlik sun.",
            "astrology": base
            + " Doğum haritasını gezegenler, evler ve açılar üzerinden profesyonel şekilde yorumla. "
            + "Teknik astroloji bilgin yüksek, fakat dili sade ve güçlendirici kullan. "
            + "Korkutucu, kesin kaderci ifadelerden uzak dur.",
            "solar_return": base
            + " Solar return (güneş dönüşü) haritasını yıllık tema olarak yorumla. "
            + "Bu yılın ana derslerini ve fırsatlarını, özellikle aşk, kariyer ve ruhsal gelişim açısından açıkla.",
            "transit": base
            + " Transit gezegenlerin danışanın doğum haritası üzerindeki etkilerini açıkla. "
            + "Önümüzdeki birkaç hafta/ay için ana temaları özetle; günlük fal gibi yüzeysel olma.",
        }
    else:
        base = (
            "You are MystAI, a mystical and professional interpreter. "
            "You speak warmly, deeply and offer supportive insights."
        )
        mapping = {
            "general": base + " Provide intuitive guidance.",
            "astrology": base
            + " Provide a structured natal chart analysis using planets, houses and aspects. "
            + "Use a clear and empowering tone, avoid fatalistic language.",
            "solar_return": base
            + " Interpret the solar return chart as a theme for the year ahead. "
            + "Highlight love, career, personal growth and karmic lessons.",
            "transit": base
            + " Explain how the current transiting planets interact with the natal chart. "
            + "Summarise the main themes for the coming weeks and months.",
        }
    return mapping.get(kind, mapping["general"])


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
#  NORMAL /predict (fal + TTS)
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

        # Ses dosyası (TTS)
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=text, lang=lang).save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{audio_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
#  NATAL ASTROLOGY (PREMIUM)
# =====================================================
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    """
    Uzun premium NATAL astroloji raporu + gerçek doğum haritası PNG.
    Frontend: NATAL modu bu endpoint'i kullanır.
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
                f"Premium NATAL astroloji raporu oluştur.\n"
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
                f"Create a premium NATAL astrology report.\n"
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
                "- General future themes for the next 3–6 months\n"
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

        # ---- NATAL HARİTASI ----
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
            print("Natal chart generation error:", e)

        return jsonify(
            {
                "text": text,
                "chart": chart_public_path,
                "chart_id": chart_id,
                "language": lang,
                "mode": "natal",
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
#  SOLAR RETURN
# =====================================================
@app.route("/solar-return", methods=["POST"])
def solar_return():
    """
    Basit, fakat profesyonel Solar Return raporu + harita.
    Frontend: SOLAR RETURN modu bu endpoint'i kullanır.
    """
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        year = data.get("year")  # opsiyonel
        lang = data.get("language")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        if not year:
            year = datetime.utcnow().year
        year = int(year)

        # Solar return tarih: aynı ay/gün, farklı yıl
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
                f"Create a SOLAR RETURN astrology report.\n"
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
                "mode": "solar",
                "solar_year": year,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
#  TRANSITLER
# =====================================================
@app.route("/transits", methods=["POST"])
def transits():
    """
    Transit odaklı uzun rapor (grafik yok).
    Frontend: TRANSITLER modu bu endpoint'i kullanır.
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
                f"Create a TRANSIT-focused astrology report.\n"
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

        return jsonify({"text": text, "language": lang, "mode": "transits"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
#  PDF SINIFI (UNICODE + LOGO + KAPAK)
# =====================================================
class MystPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # fonts, header'da kullanabilmek için add_page'den ÖNCE ekleniyor
        if os.path.exists(FONT_PATH_TTF):
            # Normal & Bold aynı TTF (fpdf2 böyle destekliyor)
            self.add_font("DejaVu", "", FONT_PATH_TTF, uni=True)
            self.add_font("DejaVu", "B", FONT_PATH_TTF, uni=True)

    def header(self):
        # Küçük logo sol üstte
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            # x=10, y=8, genişlik=14mm
            self.image(LOGO_PATH, 10, 7, 14)
        # Marka başlığı
        self.set_xy(28, 8)
        self.set_font("DejaVu", "B", 11)
        self.set_text_color(25, 30, 55)
        self.cell(0, 5, "MystAI Astrology", ln=1)

        self.set_xy(28, 14)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(110, 115, 150)
        self.cell(0, 4, "mystai.ai  •  AI-powered divination & astrology", ln=1)

        self.ln(4)
        self.set_text_color(25, 25, 40)

    def footer(self):
        self.set_y(-13)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(130, 130, 160)
        self.cell(0, 8, f"MystAI.ai • Page {self.page_no()}", align="C")


# =====================================================
#  PROFESYONEL PDF OLUŞTURUCU
# =====================================================
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    """
    Frontend, text + chart_id + language + report_type (+ doğum bilgileri) ile çağırır.
    report_type: 'natal' | 'solar' | 'transits'
    """
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()
        chart_id = data.get("chart_id")
        lang = data.get("language", "en")
        report_type = (data.get("report_type") or "natal").lower()

        # meta (opsiyonel)
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
        pdf.alias_nb_pages()
        pdf.add_page()

        # ----- Kapak başlığı & alt başlık -----
        if lang == "tr":
            if report_type == "solar":
                title = "MystAI Güneş Dönüşü Astroloji Raporu"
                sub = (
                    "Bu rapor, doğum haritan ile güneş dönüşü haritanı bir araya getirerek "
                    "önümüzdeki yaklaşık bir yılın ana temalarını yorumlar."
                )
            elif report_type == "transits":
                title = "MystAI Transit Astroloji Raporu"
                sub = (
                    "Bu rapor, güncel gökyüzü hareketlerini doğum haritanla ilişkilendirerek "
                    "yakın gelecekte öne çıkan enerjileri açıklar."
                )
            else:
                title = "MystAI Natal Doğum Haritası Raporu"
                sub = (
                    "Bu rapor, doğum haritanın sembollerini yorumlayarak kişilik, yaşam amacı, "
                    "ilişkiler ve kader potansiyelin hakkında derinlemesine içgörüler sunar."
                )
            intro_heading = "Detaylı astroloji raporun aşağıdadır:"
        else:
            if report_type == "solar":
                title = "MystAI Solar Return Astrology Report"
                sub = (
                    "This report combines your natal chart with your solar return chart "
                    "to describe the main themes of the year ahead."
                )
            elif report_type == "transits":
                title = "MystAI Transit Astrology Report"
                sub = (
                    "This report relates current planetary transits to your natal chart, "
                    "highlighting the key energies around you now and in the near future."
                )
            else:
                title = "MystAI Natal Astrology Report"
                sub = (
                    "This report interprets the symbols of your natal chart to explore your "
                    "personality, life purpose, relationships and destiny potential."
                )
            intro_heading = "Your detailed astrology report is below:"

        # Başlık
        pdf.set_font("DejaVu", "B", 17)
        pdf.set_text_color(30, 32, 60)
        pdf.multi_cell(0, 8, title)
        pdf.ln(2)

        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(85, 90, 125)
        pdf.multi_cell(0, 6, sub)
        pdf.ln(6)

        # Meta satırı
        meta_lines = []
        if birth_date and birth_time and birth_place:
            if lang == "tr":
                meta_lines.append(
                    f"Doğum: {birth_date} • {birth_time} • {birth_place}"
                )
            else:
                meta_lines.append(
                    f"Birth: {birth_date} • {birth_time} • {birth_place}"
                )
        if name:
            if lang == "tr":
                meta_lines.append(f"Danışan: {name}")
            else:
                meta_lines.append(f"Client: {name}")

        if meta_lines:
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(105, 110, 140)
            pdf.multi_cell(0, 4.5, "  •  ".join(meta_lines))
            pdf.ln(5)

        # ----- Harita görseli (NATAL / SOLAR için) -----
        has_chart_page = False
        if chart_id and report_type in ("natal", "solar"):
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                try:
                    from PIL import Image

                    img = Image.open(chart_file).convert("RGB")
                    rgb_fixed = f"/tmp/{chart_id}_rgb.jpg"
                    img.save(rgb_fixed, "JPEG", quality=95)

                    img_width = 140  # mm
                    x = (210 - img_width) / 2
                    y = pdf.get_y() + 2

                    pdf.image(rgb_fixed, x=x, y=y, w=img_width)
                    has_chart_page = True
                except Exception as e:
                    print("PDF image error:", e)

        # Eğer harita çizildiyse, detaylı metni 2. sayfadan başlat
        if has_chart_page:
            pdf.add_page()

        # ----- Gövde / detaylı metin -----
        pdf.set_text_color(35, 35, 55)
        pdf.set_font("DejaVu", "B", 13)
        pdf.multi_cell(0, 7, intro_heading)
        pdf.ln(3)

        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(25, 25, 40)

        for raw_line in text.split("\n"):
            line = raw_line.strip()
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


# =====================================================
#  STATIC FILE SERVERS
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
#  RUN (Render uyumlu)
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
