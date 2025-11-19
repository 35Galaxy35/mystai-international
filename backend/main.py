# ============================================
# MystAI - Full Premium Backend (FINAL)
# --------------------------------------------
# Özellikler:
# - /predict           : Normal fal / sohbet + TTS
# - /astrology         : Kısa, text-only astroloji
# - /astrology-premium : Uzun premium natal rapor + gerçek natal harita
# - /solar-return      : Solar return raporu + harita (basit)
# - /transits          : Transit odaklı yorum
# - /generate_pdf      : Profesyonel PDF (kapak + harita sayfası + metin)
# - /audio/<id>        : TTS dosyası
# - /chart/<id>        : Harita PNG dosyası
# - /health, /version  : Durum kontrolü
#
# Render uyumlu, tüm görseller /tmp altında oluşturulur.
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
from datetime import datetime, timedelta

# ---------------------------------
# Yol ayarları
# ---------------------------------
BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
IMAGES_DIR = os.path.join(ROOT_DIR, "images")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

LOGO_PATH = os.path.join(IMAGES_DIR, "mystai-logo.png")
DEJAVU_PATH = os.path.join(FONTS_DIR, "DejaVuSans.ttf")  # Unicode destekli font

# chart_generator.py aynı klasörde olduğu için:
sys.path.append(BASE_DIR)
from chart_generator import generate_natal_chart  # doğum haritası çizer

# Versiyon
BACKEND_VERSION = "1.0.0-premium"


# -----------------------------
# Flask & CORS
# -----------------------------
app = Flask(__name__)

# Güvenli CORS (gerekirse localhost'u da bıraktım)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "https://mystai.ai",
                "https://mystai-international.onrender.com",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        }
    },
)


# -----------------------------
# OpenAI Client + Helper
# -----------------------------
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)


def safe_chat_completion(messages, max_tokens=900, temperature=0.9):
    """
    OpenAI modeli için güvenli çağrı:
    - Önce gpt-4o
    - Sonra gpt-4o-mini
    - Gerekirse gpt-3.5-turbo
    """
    models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

    last_error = None
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"[OpenAI] Model {model} error:", e)
            last_error = e

    # Hepsi çökerse
    raise last_error or Exception("OpenAI completion failed")


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
# /tmp temizlik
# -----------------------------
def clean_tmp_files(max_age_hours: int = 24):
    """24 saatten eski geçici dosyaları siler."""
    tmp_dir = "/tmp"
    try:
        now = datetime.utcnow()
        limit = now - timedelta(hours=max_age_hours)

        for filename in os.listdir(tmp_dir):
            full_path = os.path.join(tmp_dir, filename)
            if not os.path.isfile(full_path):
                continue

            try:
                mtime = datetime.utcfromtimestamp(os.path.getmtime(full_path))
                if mtime < limit:
                    os.remove(full_path)
            except Exception as e:
                print("clean_tmp_files error:", e)
    except Exception as e:
        print("clean_tmp_files TOP error:", e)


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
# HEALTH / VERSION
# -----------------------------
@app.route("/")
def index():
    return "MystAI Backend Running 🔮"


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "version": BACKEND_VERSION,
            "time": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.route("/version")
def version():
    return jsonify({"version": BACKEND_VERSION})


# -----------------------------
# NORMAL /predict (fal + TTS)
# -----------------------------
@app.route("/predict", methods=["POST"])
def predict():
    clean_tmp_files()
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

        text = safe_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            max_tokens=700,
        )

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
    clean_tmp_files()
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

        text = safe_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900,
        )

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
    clean_tmp_files()
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

        text = safe_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1800,
        )

        # ------- GERÇEK DOĞUM HARİTASI OLUŞTUR -------
        lat, lon = geocode_place(birth_place)
        chart_id = None
        chart_public_path = None

        try:
            chart_id, _ = generate_natal_chart(
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
                "chart_id": chart_id,  # PDF için gerekli
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
    clean_tmp_files()
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
            chart_id, _ = generate_natal_chart(
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

        text = safe_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
        )

        return jsonify(
            {
                "text": text,
                "chart": chart_public_path,
                "chart_id": chart_id,
                "language": lang,
                "year": year,
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
    clean_tmp_files()
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

        text = safe_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
        )
        return jsonify({"text": text, "language": lang})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PROFESYONEL PDF GENERATOR
# -----------------------------
class MystPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Unicode font ekle (DejaVu)
        try:
            if os.path.exists(DEJAVU_PATH):
                self.add_font("DejaVu", "", DEJAVU_PATH, uni=True)
                self.add_font("DejaVu", "B", DEJAVU_PATH, uni=True)
        except Exception as e:
            print("Font load error:", e)

    def header(self):
        # Tüm sayfalarda üst bant
        self.set_fill_color(12, 20, 45)  # koyu lacivert
        self.rect(0, 0, 210, 20, "F")
        self.set_xy(10, 5)

        # Logo (varsa)
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, x=10, y=2, w=16)
                self.set_xy(28, 6)
            except Exception as e:
                print("Header logo error:", e)
                self.set_xy(10, 6)

        self.set_text_color(255, 215, 120)
        try:
            self.set_font("DejaVu", "B", 11)
        except Exception:
            self.set_font("Helvetica", "B", 11)
        self.cell(0, 5, "MystAI Astrology Report", ln=1)

        self.set_text_color(220, 230, 255)
        try:
            self.set_font("DejaVu", "", 8)
        except Exception:
            self.set_font("Helvetica", "", 8)
        self.cell(0, 4, "mystai.ai • AI-powered divination & astrology", ln=1)

        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_text_color(160, 165, 190)
        try:
            self.set_font("DejaVu", "I", 8)
        except Exception:
            self.set_font("Helvetica", "I", 8)
        page_text = f"MystAI.ai • Page {self.page_no()}"
        self.cell(0, 8, page_text, align="C")


@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    """
    Frontend, text + chart_id + language (+ opsiyonel solar/transit metinleri) ile çağırır.
    Profesyonel görünümlü bir PDF üretir:
    1. Kapak sayfası (logo + başlık)
    2. Natal harita sayfası (harita büyük ve ortada)
    3. Rapor sayfaları:
       - Natal rapor (text)
       - Opsiyonel: Solar return raporu
       - Opsiyonel: Transit raporu
    """
    clean_tmp_files()
    try:
        data = request.json or {}
        text = data.get("text", "").strip()  # ana natal rapor
        chart_id = data.get("chart_id")
        lang = data.get("language", "en")

        # Opsiyonel ek bölümler
        solar_text = (data.get("solar_text") or "").strip()
        transit_text = (data.get("transit_text") or "").strip()

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = MystPDF()
        pdf.set_auto_page_break(auto=True, margin=18)

        # 1) KAPAK SAYFASI
        pdf.add_page()

        # Kapakta header zaten var; biraz aşağı in
        pdf.ln(20)

        if lang == "tr":
            title = "Yapay Zekâ Astroloji Raporun"
            sub = (
                "MystAI, sembolik astrolojiyi yapay zekâ ile birleştirerek doğum haritan "
                "ve gökyüzü hareketleri üzerinden kişisel ve derinlemesine bir yorum sunar."
            )
        else:
            title = "Your AI Astrology Report"
            sub = (
                "MystAI blends symbolic astrology with advanced AI to offer a deep, "
                "personalised interpretation of your chart and the current sky."
            )

        # Kapak başlık
        pdf.set_text_color(30, 35, 60)
        try:
            pdf.set_font("DejaVu", "B", 18)
        except Exception:
            pdf.set_font("Helvetica", "B", 18)
        pdf.multi_cell(0, 10, title, align="L")
        pdf.ln(4)

        try:
            pdf.set_font("DejaVu", "", 11)
        except Exception:
            pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(80, 86, 120)
        pdf.multi_cell(0, 6, sub)
        pdf.ln(10)

        if lang == "tr":
            cover_note = (
                "Bu rapor, doğum haritanın sembolik dilini ve güncel gökyüzü enerjilerini "
                "bir araya getirerek seni güçlendirmeyi amaçlayan, mistik ama ayakları yere basan "
                "bir rehberdir. Aşağıdaki sayfalarda natal haritan, olası yıllık temaların ve "
                "önümüzdeki süreçteki transit etkilerin hakkında derinlemesine yorumlar bulacaksın."
            )
        else:
            cover_note = (
                "This report weaves together the symbolic language of your natal chart and the "
                "current movements in the sky. Its purpose is to support and empower you with "
                "grounded yet mystical guidance for the path ahead."
            )

        pdf.multi_cell(0, 6, cover_note)

        # 2) NATAL CHART SAYFASI
        if chart_id:
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                try:
                    from PIL import Image

                    # PNG → RGB JPEG (bazı PDF kütüphaneleri için daha stabil)
                    img = Image.open(chart_file).convert("RGB")
                    rgb_fixed = f"/tmp/{chart_id}_rgb.jpg"
                    img.save(rgb_fixed, "JPEG", quality=95)

                    pdf.add_page()

                    # Başlık
                    pdf.ln(18)
                    pdf.set_text_color(40, 45, 70)
                    try:
                        pdf.set_font("DejaVu", "B", 14)
                    except Exception:
                        pdf.set_font("Helvetica", "B", 14)

                    if lang == "tr":
                        chart_title = "Natal Chart (Doğum Haritası)"
                    else:
                        chart_title = "Natal Chart"

                    pdf.multi_cell(0, 8, chart_title, align="C")
                    pdf.ln(6)

                    # Haritayı ortalı yerleştir
                    img_width = 150  # mm
                    x = (210 - img_width) / 2
                    y = pdf.get_y()
                    pdf.image(rgb_fixed, x=x, y=y, w=img_width)
                    pdf.ln(160)
                except Exception as e:
                    print("PDF image error:", e)

        # 3) RAPOR SAYFALARI
        pdf.add_page()

        # Giriş başlığı
        pdf.ln(10)
        pdf.set_text_color(40, 40, 60)
        try:
            pdf.set_font("DejaVu", "B", 13)
        except Exception:
            pdf.set_font("Helvetica", "B", 13)

        if lang == "tr":
            intro = "Detaylı Astroloji Raporun"
        else:
            intro = "Your Detailed Astrology Report"

        pdf.multi_cell(0, 7, intro)
        pdf.ln(4)

        # Gövde metni ayarı
        try:
            pdf.set_font("DejaVu", "", 11)
        except Exception:
            pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(25, 25, 40)

        def write_section(header, body):
            if not body:
                return
            pdf.ln(4)
            try:
                pdf.set_font("DejaVu", "B", 12)
            except Exception:
                pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 6, header)
            pdf.ln(1)
            try:
                pdf.set_font("DejaVu", "", 11)
            except Exception:
                pdf.set_font("Helvetica", "", 11)
            for line in body.split("\n"):
                line = line.strip()
                if not line:
                    pdf.ln(2)
                    continue
                pdf.multi_cell(0, 5.5, line)
                pdf.ln(0.5)

        # Ana natal rapor
        if lang == "tr":
            natal_header = "1) Natal Harita Analizi"
        else:
            natal_header = "1) Natal Chart Analysis"

        write_section(natal_header, text)

        # Solar return bölümü (opsiyonel)
        if solar_text:
            if lang == "tr":
                sr_header = "2) Solar Return (Yıllık Tema)"
            else:
                sr_header = "2) Solar Return (Yearly Themes)"
            write_section(sr_header, solar_text)

        # Transit bölümü (opsiyonel)
        if transit_text:
            if lang == "tr":
                tr_header = "3) Transit Etkileri"
            else:
                tr_header = "3) Transit Influences"
            write_section(tr_header, transit_text)

        # PDF'i kaydet
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
