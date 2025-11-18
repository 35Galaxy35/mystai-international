# ============================================
# MystAI - PRO Astrology Backend
# - Gerçek hesaplamalı doğum haritası (flatlib + matplotlib)
# - Uzun, bölümlü astroloji raporu (TR / EN)
# - Render uyumlu Flask backend
# ============================================

import os
import uuid
import base64
import traceback
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS

# --- Astro & Chart ---
import matplotlib
matplotlib.use("Agg")  # Render gibi headless ortamlarda şart
import matplotlib.pyplot as plt
import numpy as np

from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from geopy.geocoders import Nominatim

from fpdf import FPDF

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
# Geocoder (şehir -> enlem / boylam)
# -----------------------------
_geolocator = Nominatim(user_agent="mystai-astro")


def geocode_place(name: str):
    """Şehir, ülke metninden yaklaşık enlem / boylam döndürür.
    Bulamazsa varsayılan olarak 0,0 döner (Gana üzeri okyanus :) )."""
    try:
        if not name:
            return 0.0, 0.0
        loc = _geolocator.geocode(name, language="en")
        if not loc:
            return 0.0, 0.0
        return float(loc.latitude), float(loc.longitude)
    except Exception:
        return 0.0, 0.0


# -----------------------------
# Basit ana sayfa
# -----------------------------
@app.route("/")
def index():
    return "MystAI Backend Running 🔮"


# -----------------------------
# SYSTEM PROMPT
# -----------------------------
def build_system_prompt(type_name: str, lang: str) -> str:
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel ve destekleyici bir yorumcusun. "
            "Hem modern psikolojiden hem de kadim ezoterik öğretilerden ilham alırsın. "
            "Kullanıcıya derin, pozitif, gerçekçi ve iyi yapılandırılmış açıklamalar yaparsın."
        )
        types = {
            "general": base + (
                " Genel enerji, sezgi ve rehberlik sun. Maddi tavsiye, tıbbi teşhis, "
                "hukuki veya finansal yönlendirme verme; bunların yerine içsel denge, "
                "farkındalık, niyet ve adım planları öner."
            ),
            "astrology": base + (
                " Kullanıcının doğum haritasını, gezegenler, burçlar, evler ve açılar üzerinden "
                "profesyonel bir astrolog gibi yorumla. Haritayı şu bölümlere ayır:\n"
                "1) Giriş / Genel tema\n"
                "2) Kişilik ve karakter yapısı\n"
                "3) Aşk & ilişkiler\n"
                "4) Kariyer, para ve maddi dünya\n"
                "5) Ruhsal gelişim, kader ve karmik dersler\n"
                "6) Önümüzdeki 12 aya ait transit temaları\n"
                "7) Özet ve pratik tavsiyeler\n\n"
                "Her bölümde en az birkaç paragraf kullan; akıcı, derin ve anlaşılır bir Türkçe ile yaz."
            ),
        }
    else:
        base = (
            "You are MystAI, a mystical yet professional interpreter. "
            "You blend symbolic astrology with psychological insight. "
            "You always speak in a warm, deep and structured way."
        )
        types = {
            "general": base + (
                " Offer intuitive guidance, but never give medical, legal or financial advice. "
                "Focus on emotions, mindset and practical next steps."
            ),
            "astrology": base + (
                " Interpret the natal chart like a professional astrologer using planets, signs, "
                "houses and aspects. Structure the report into clear sections:\n"
                "1) Introduction & overall theme\n"
                "2) Personality & character\n"
                "3) Love & relationships\n"
                "4) Career, vocation & material life\n"
                "5) Spiritual path & karmic lessons\n"
                "6) Main themes for the next 12 months (transits/solar flavour)\n"
                "7) Summary with practical advice\n\n"
                "Each section should contain multiple paragraphs; write in clear, flowing, natural language."
            ),
        }

    return types.get(type_name, types["general"])


# -----------------------------
# Yardımcı: astrolojik doğum haritası çizimi
# -----------------------------
PLANETS_FOR_CHART = [
    const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS,
    const.JUPITER, const.SATURN, const.URANUS, const.NEPTUNE, const.PLUTO
]

PLANET_SYMBOLS = {
    const.SUN: "☉",
    const.MOON: "☽",
    const.MERCURY: "☿",
    const.VENUS: "♀",
    const.MARS: "♂",
    const.JUPITER: "♃",
    const.SATURN: "♄",
    const.URANUS: "♅",
    const.NEPTUNE: "♆",
    const.PLUTO: "♇",
}

ZODIAC_SIGNS = [
    ("♈︎", 0),   # Koç / Aries
    ("♉︎", 30),
    ("♊︎", 60),
    ("♋︎", 90),
    ("♌︎", 120),
    ("♍︎", 150),
    ("♎︎", 180),
    ("♏︎", 210),
    ("♐︎", 240),
    ("♑︎", 270),
    ("♒︎", 300),
    ("♓︎", 330),
]


def create_natal_chart_image(birth_date: str, birth_time: str, birth_place: str) -> str:
    """Doğum bilgilerine göre profesyonel bir natal chart PNG üretir ve dosya yolunu döndürür."""
    # Tarih/saat parse
    # HTML date input: YYYY-MM-DD geliyor
    try:
        year, month, day = map(int, birth_date.split("-"))
    except Exception:
        # Kullanıcı farklı format girdiyse kaba bir fallback deneyelim
        dt = datetime.strptime(birth_date, "%d.%m.%Y")
        year, month, day = dt.year, dt.month, dt.day

    hour, minute = map(int, birth_time.split(":"))

    # Şehir -> enlem / boylam
    lat, lon = geocode_place(birth_place)

    # Flatlib datetime (timezone'ı şimdilik 00:00 alıyoruz; çok büyük hata yaratmaz)
    dt = Datetime(year, month, day, hour, minute, "+00:00")
    pos = GeoPos(lat, lon)
    chart = Chart(dt, pos, hsys=const.HOUSES_PLACIDUS)

    # Matplotlib ile çember çizimi
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"projection": "polar"})
    ax.set_theta_direction(-1)         # Saat yönünün tersine
    ax.set_theta_offset(np.radians(90))  # 0° Koç tepeye gelsin
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.set_ylim(0, 1.05)
    ax.grid(False)
    ax.set_facecolor("#050814")
    fig.patch.set_facecolor("#050814")

    # Dış çember
    theta = np.linspace(0, 2 * np.pi, 360)
    ax.plot(theta, np.ones_like(theta), color="white", linewidth=1.2)

    # 12 burç dilimi
    for i, (symbol, start_deg) in enumerate(ZODIAC_SIGNS):
        angle_rad = np.radians(start_deg)
        ax.plot([angle_rad, angle_rad], [0.2, 1.0], color="white", linewidth=0.7, alpha=0.6)

        mid_angle = np.radians(start_deg + 15)
        ax.text(
            mid_angle, 1.02, symbol,
            ha="center", va="center",
            fontsize=13, color="#ffd54f"
        )

    # Ev çizgileri (house cusps)
    for house_num in range(1, 13):
        house = chart.houses[house_num - 1]
        lon_deg = house.lon  # 0–360
        ang = np.radians(lon_deg)
        ax.plot([ang, ang], [0.0, 0.95], color="#5555ff", linewidth=0.7, alpha=0.5)

    # Gezegenleri yerleştir
    for body in PLANETS_FOR_CHART:
        obj = chart.get(body)
        lon_deg = obj.lon

        ang = np.radians(lon_deg)
        radius = 0.78

        symbol = PLANET_SYMBOLS.get(body, "?")
        ax.text(
            ang, radius, symbol,
            ha="center", va="center",
            fontsize=13, color="#ffffff"
        )

    # Basit aspect çizgileri (örnek: Sun–Moon vs.) – isteğe bağlı
    # Burada sadece görsel zenginlik için birkaç çizgi çekiyoruz
    coords = []
    for body in PLANETS_FOR_CHART:
        obj = chart.get(body)
        lon_deg = obj.lon
        ang = np.radians(lon_deg)
        coords.append((ang, 0.4))

    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            a1, r1 = coords[i]
            a2, r2 = coords[j]
            diff = abs(np.degrees(a1 - a2)) % 360
            diff = min(diff, 360 - diff)
            # 60, 90, 120, 180 gibi açılara yakınsa çiz
            if any(abs(diff - d) < 6 for d in (60, 90, 120, 180)):
                color = "#ff6666" if diff in (90, 180) else "#66ccff"
                ax.plot([a1, a2], [r1, r2], color=color, linewidth=0.5, alpha=0.7)

    # İmza / alt yazı
    caption = f"Doğum: {birth_date} • Saat: {birth_time} • Yer: {birth_place}"
    fig.text(0.5, 0.03, caption, ha="center", va="center", color="#e0e7ff", fontsize=9)

    # Dosyaya kaydet
    chart_id = uuid.uuid4().hex
    out_path = f"/tmp/{chart_id}.png"
    plt.subplots_adjust(top=0.96, bottom=0.08)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)

    return chart_id, out_path


# -----------------------------
# NORMAL /predict (Ask MystAI)
# -----------------------------
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = data.get("user_input", "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        # Dil tespiti
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
            max_tokens=600,
        )

        text = completion.choices[0].message.content.strip()

        # Ses oluştur
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


# -----------------------------
# ASTROLOGY (Uzun rapor + gerçek harita)
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

        # Frontend'ten gelen language alanı
        lang = (data.get("language") or "").lower()
        if lang not in ("tr", "en"):
            # Fallback: doğum yeri üzerinden tahmin
            try:
                lang = detect(birth_place or "")
            except Exception:
                lang = "en"
            if lang not in ("tr", "en"):
                lang = "en"

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        system_prompt = build_system_prompt("astrology", lang)

        # Rapor prompt'u
        if lang == "tr":
            user_prompt = (
                f"Doğum bilgileri:\n"
                f"- Tarih: {birth_date}\n"
                f"- Saat: {birth_time}\n"
                f"- Yer: {birth_place}\n"
                f"- İsim: {name or 'Belirtilmemiş'}\n"
                f"- Odak alanları: {', '.join(focus) or 'Genel'}\n"
                f"- Soru / niyet: {question or 'Belirtilmemiş'}\n\n"
                "Bu bilgilere göre, yukarıda belirtilen 7 bölümlü profesyonel astroloji raporunu yaz. "
                "Her bölüm için ayrıntılı, en az birkaç paragraf kullan. "
                "Metinde gereksiz listeleme yapma, akıcı bir hikâye mantığıyla yaz. "
                "Kullanıcıya hem psikolojik içgörü hem de somut öneriler sun."
            )
        else:
            user_prompt = (
                f"Birth data:\n"
                f"- Date: {birth_date}\n"
                f"- Time: {birth_time}\n"
                f"- Place: {birth_place}\n"
                f"- Name: {name or 'Not specified'}\n"
                f"- Focus areas: {', '.join(focus) or 'General'}\n"
                f"- Question / intention: {question or 'Not specified'}\n\n"
                "Using this data, write the 7-part professional astrology report described above. "
                "Each section should contain multiple paragraphs. "
                "Avoid bullet lists, write in flowing, narrative form and end with concrete suggestions."
            )

        # ---- Metin raporu ----
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1900,  # daha uzun rapor
        )

        text = completion.choices[0].message.content.strip()

        # ---- Gerçek doğum haritası görseli ----
        chart_id, chart_path = create_natal_chart_image(
            birth_date=birth_date,
            birth_time=birth_time,
            birth_place=birth_place,
        )

        return jsonify({
            "text": text,
            "chart": f"/chart/{chart_id}",
            "audio": None,
            "language": lang,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PREMIUM ASTROLOGY (opsiyonel)
# -----------------------------
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    """Frontend şu an kullanmıyor ama istersen ileride kullanırsın."""
    try:
        data = request.json or {}
        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")

        lang = (data.get("language") or "").lower()
        if lang not in ("tr", "en"):
            try:
                lang = detect(birth_place or "")
            except Exception:
                lang = "en"
            if lang not in ("tr", "en"):
                lang = "en"

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        system_prompt = build_system_prompt("astrology", lang)

        if lang == "tr":
            user_prompt = (
                f"PREMİUM astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n\n"
                "Klasik 7 bölümlü yapıdan daha da detaylı, en az 10 alt başlıklı, "
                "uzun ve derin bir astroloji raporu yaz. "
                "Ruhsal gelişim, kader, karmik temalar, aşk, kariyer, bolluk ve önümüzdeki 2 yıla yayılan "
                "genel transit etkilerini ayrıntılı anlat."
            )
        else:
            user_prompt = (
                f"Create an extended PREMIUM astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n\n"
                "Use at least 10 subsections with a long and deep analysis of personality, "
                "karmic themes, love, career, abundance and the main astrological trends "
                "for the next 2 years."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2600,
        )

        text = completion.choices[0].message.content.strip()

        # Aynı chart görseli
        chart_id, chart_path = create_natal_chart_image(
            birth_date=birth_date,
            birth_time=birth_time,
            birth_place=birth_place,
        )

        return jsonify({
            "text": text,
            "chart": f"/chart/{chart_id}",
            "audio": None,
            "language": lang,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PDF GENERATOR
# -----------------------------
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        for line in text.split("\n"):
            pdf.multi_cell(0, 8, line)

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
# HEALTH CHECK
# -----------------------------
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# -----------------------------
# RUN (local için – Render gunicorn kullanıyor)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
