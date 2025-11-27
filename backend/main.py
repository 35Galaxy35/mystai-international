# ============================================
# MystAI - Full Premium Backend (Commercial Ready)
# --------------------------------------------
# Özellikler:
# - /predict           : Normal fal / sohbet + TTS (OpenAI TTS PRO)
# - /astrology-premium : Natal (uzun rapor + gerçek doğum haritası PNG)
# - /solar-return      : Solar return raporu + solar harita PNG
# - /transits          : Transit odaklı uzun rapor (haritasız)
# - /generate_pdf      : Profesyonel PDF (logo + kapak + harita + uzun rapor)
# - /audio/<id>        : TTS dosyası
# - /chart/<id>        : Harita PNG dosyası
#
# Notlar:
# - Haritalar Swiss Ephemeris + gerçek timezone ile hesaplanır (Astro.com uyumlu).
# - Ev sistemi: chart_generator içindeki sisteme göre (Placidus).
# - PDF: DejaVuSans.ttf ile tam Unicode (TR/EN) desteği.
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
from fpdf import FPDF
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from PIL import Image

# chart_generator.py aynı klasörde
sys.path.append(os.path.dirname(__file__))
from chart_generator import generate_natal_chart  # Swiss Ephemeris tabanlı

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

# TimezoneFinder instance
tf = TimezoneFinder()


def geocode_place(place: str):
    """Şehir/ülke bilgisinden enlem-boylam bulur. Hata olursa (0,0) döner."""
    try:
        loc = geolocator.geocode(place, timeout=10)
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception as e:
        print("Geocode error:", e)
    return 0.0, 0.0


def get_timezone_from_latlon(lat: float, lon: float) -> str:
    """
    Enlem-boylamdan IANA timezone ismini bulur.
    Örn: Europe/Istanbul, America/New_York, Europe/London, Asia/Tokyo
    Hata durumunda UTC döner.
    """
    try:
        if lat == 0.0 and lon == 0.0:
            return "UTC"
        tz = tf.timezone_at(lat=lat, lng=lon)
        if tz is None:
            return "UTC"
        return tz
    except Exception as e:
        print("Timezone error:", e)
        return "UTC"


# -----------------------------
# SYSTEM PROMPT
# -----------------------------
def build_system_prompt(kind: str, lang: str) -> str:
    """
    kind: "general" | "astrology" | "solar_return" | "transit"
    """
    if lang == "tr":
        # ==== TÜRKÇE SİSTEM PROMPTLARI ====
        base_general = (
            "Sen MystAI adında mistik, profesyonel ve çok içten bir fal ve enerji yorumcusun. "
            "Kahve falı, tarot, el falı, enerji ve rüya yorumları yaparsın. "
            "Kullanıcıya derin, pozitif, gerçekçi ve güçlendirici bir dille hitap edersin. "
            "Onu gerçekten dinleyen bir insan gibi, sıcak ve samimi konuşursun. "
            "Gerektiğinde psikolojik içgörüler verirsin ama asla yargılayıcı olmazsın. "
            "Korkutucu, tehditkâr, lanet gibi görülebilecek veya kesin kaderci cümleler kullanmazsın; "
            "her zaman özgür iradeyi, kişinin seçimlerini ve iç gücünü vurgularsın. "
            "Cevaplarını paragraflara böl, hikâye anlatır gibi akıcı yaz. "
            "Özellikle girişte enerjiyi ve şu anki durumu anlat, ortada duyguları ve süreci derinleştir, "
            "sonda ise net, umut veren tavsiyeler ve yakın geleceğe dair olasılıkları paylaş. "
        )

        base_astro = (
            "Sen MystAI adında mistik, profesyonel ve destekleyici bir astroloji yorumcusun. "
            "Kullanıcıya derin, pozitif, gerçekçi ve güçlendirici bir dille açıklama yaparsın. "
            "Korkutucu, tehditkâr, kesin kaderci ifadeler kullanmazsın; özgür iradeyi ve bilinçli seçimleri vurgularsın. "
        )

        mapping = {
            "general": (
                base_general
                + "Genel enerji, sezgi ve rehberlik sun. Fal, enerji ve sembolik dil kullanabilirsin; "
                  "kullanıcının aşk, ilişkiler, kariyer, para ve kişisel dönüşüm alanlarına dokunan, "
                  "kalbine işleyen bir yorum yap."
            ),
            "astrology": (
                base_astro
                + "Teknik astroloji bilgin çok yüksek. Doğum haritasını gezegenler, burçlar, evler ve açılar üzerinden "
                  "profesyonel şekilde yorumla. Güneş, Ay, ASC, MC, kişisel ve dışsal gezegenleri ayrı ayrı ele al. "
                  "Metni mutlaka başlıklar ve paragraflarla düzenli yaz."
            ),
            "solar_return": (
                base_astro
                + "Solar return (güneş dönüşü) haritasını yıllık tema olarak yorumla. "
                  "Bu yılın ana derslerini ve fırsatlarını; aşk, kariyer, para, ruhsal gelişim ve kişisel dönüşüm "
                  "başlıkları altında detaylıca açıkla."
            ),
            "transit": (
                base_astro
                + "Güncel transit gezegenlerin danışanın doğum haritası üzerindeki etkilerini yorumla. "
                  "Özellikle Satürn, Uranüs, Neptün, Plüton transitlerinin önemli süreçlerini, aynı zamanda Jüpiter ve Mars "
                  "gibi daha hızlı gezegenlerin etkilerini de ele al. Somut öneriler ver."
            ),
        }
    else:
        # ==== ENGLISH SYSTEM PROMPT ====
        base_general = (
            "You are MystAI, a mystical, professional and very warm fortune & energy reader. "
            "You read coffee cups, tarot, palm, energy and dreams. "
            "You speak in a deep, comforting, realistic and empowering tone, like a close friend who truly listens. "
            "You may offer psychological insight, but you are never judgmental. "
            "You avoid fear-based, threatening or fatalistic language; instead you highlight free will, choice and inner strength. "
            "Write in clear paragraphs, like telling a flowing story. "
            "Begin with the current energy, then explore emotions and the situation in depth, "
            "and finally give hopeful, practical advice and possibilities for the near future. "
        )

        base_astro = (
            "You are MystAI, a mystical, professional and supportive astrologer. "
            "You speak in a deep, empowering and realistic tone. "
            "You avoid fear-based or fatalistic language and always emphasise free will and conscious choices. "
        )

        mapping = {
            "general": (
                base_general
                + "Offer intuitive guidance and symbolic insight. "
                  "Touch on love, relationships, career, money and personal transformation in a heartfelt, inspiring way."
            ),
            "astrology": (
                base_astro
                + "You are highly skilled in technical astrology. Interpret the natal chart using planets, signs, houses "
                  "and aspects in a professional way. Highlight Sun, Moon, ASC, MC, personal and outer planets. "
                  "Organise the text with headings and clear paragraphs."
            ),
            "solar_return": (
                base_astro
                + "Interpret the solar return chart as the main theme for the year ahead. "
                  "Describe love, career, money, spiritual growth and personal transformation as yearly topics."
            ),
            "transit": (
                base_astro
                + "Explain how the current planetary transits affect the natal chart. "
                  "Pay special attention to Saturn, Uranus, Neptune, and Pluto processes, as well as Jupiter and Mars. "
                  "Give concrete, practical advice."
            ),
        }

    return mapping.get(kind, mapping["general"])


def degree_to_sign(deg: float) -> str:
    """0–360 dereceyi burç adına çevirir."""
    signs = [
        "Koç", "Boğa", "İkizler", "Yengeç",
        "Aslan", "Başak", "Terazi", "Akrep",
        "Yay", "Oğlak", "Kova", "Balık",
    ]
    if deg is None:
        return ""
    deg = float(deg) % 360.0
    index = int(deg // 30) % 12
    return signs[index]


def build_chart_summary(chart_meta: dict, lang: str) -> str:
    """AI'ya gönderilecek gerçek harita özetini üretir."""
    if not chart_meta:
        return ""

    planets = chart_meta.get("planets", [])

    # --- ASC & MC: dict veya float gelebilir ---
    asc_raw = chart_meta.get("asc")
    mc_raw = chart_meta.get("mc")

    def extract_sign_and_degree(val):
        """
        ASC/MC için:
        - Eğer dict ise: {'sign': 'Kova', 'lon': 304.0, 'degree_in_sign': 4.0}
        - Eğer float ise: 0–360 global derece
        """
        if isinstance(val, dict):
            sign = val.get("sign")
            lon = val.get("lon")
            if not sign and lon is not None:
                sign = degree_to_sign(lon)
            deg = lon
            if deg is None:
                deg = val.get("degree") or val.get("degree_in_sign")
            return sign, deg
        elif isinstance(val, (int, float)):
            return degree_to_sign(val), float(val)
        else:
            return None, None

    asc_sign, asc_deg = extract_sign_and_degree(asc_raw)
    mc_sign, mc_deg = extract_sign_and_degree(mc_raw)

    # --- Gezegenler ---
    fixed = []
    for p in planets:
        p_name = p.get("name")
        p_sign = p.get("sign")
        lon = p.get("lon")

        if lon is not None:
            if not p_sign:
                p_sign = degree_to_sign(lon)
            degree_val = float(lon)
        else:
            degree_val = p.get("degree") or p.get("degree_in_sign")
            if not p_sign and degree_val is not None:
                p_sign = ""

        fixed.append(
            {
                "name": p_name,
                "degree": degree_val,
                "sign": p_sign,
            }
        )

    lines = []

    if lang == "tr":
        lines.append("Gerçek doğum haritası yerleşimleri (Swiss Ephemeris):")
        if asc_sign:
            lines.append(f"• Yükselen (ASC): {asc_sign} ({asc_deg:.2f}°)")
        if mc_sign:
            lines.append(f"• MC: {mc_sign} ({mc_deg:.2f}°)")

        for p in fixed:
            if p["sign"]:
                lines.append(
                    f"• {p['name']}: {p['sign']} ({p['degree']:.2f}°)"
                )
    else:
        en_signs = {
            "Koç": "Aries",
            "Boğa": "Taurus",
            "İkizler": "Gemini",
            "Yengeç": "Cancer",
            "Aslan": "Leo",
            "Başak": "Virgo",
            "Terazi": "Libra",
            "Akrep": "Scorpio",
            "Yay": "Sagittarius",
            "Oğlak": "Capricorn",
            "Kova": "Aquarius",
            "Balık": "Pisces",
        }

        lines.append("True natal chart placements:")
        if asc_sign:
            lines.append(
                f"• Ascendant: {en_signs.get(asc_sign, asc_sign)} ({asc_deg:.2f}°)"
            )
        if mc_sign:
            lines.append(
                f"• MC: {en_signs.get(mc_sign, mc_sign)} ({mc_deg:.2f}°)"
            )

        for p in fixed:
            if p["sign"]:
                en_name = en_signs.get(p["sign"], p["sign"])
                lines.append(
                    f"• {p['name']}: {en_name} ({p['degree']:.2f}°)"
                )

    return "\n".join(lines)


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
#  /predict (fal + sohbet + OpenAI TTS PRO)
# =====================================================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = (data.get("user_input") or "").strip()

        # İstersen ileride front-end'den yollayabilirsin:
        # reading_type: "coffee" | "tarot" | "palm" | "energy" | "dream" | "soul" ...
        reading_type = (data.get("reading_type") or "").lower().strip()

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

        # --- Stil ipucu: kategoriye göre hafif yönlendirme (opsiyonel) ---
        style_hint = ""
        if lang == "tr":
            if reading_type == "coffee":
                style_hint = (
                    "Bu bir KAHVE FALI yorumudur. Fincan sembollerinden bahsedebilirsin; "
                    "örneğin 'fincanında şunu görüyorum' gibi, ama abartmadan doğal kullan."
                )
            elif reading_type == "tarot":
                style_hint = (
                    "Bu bir TAROT yorumudur. Kartlar, kupalar, kılıçlar, değnekler ve büyük arkana dilini kullan."
                )
            elif reading_type == "palm":
                style_hint = (
                    "Bu bir EL FALI yorumudur. Avuç içi çizgileri, yaşam çizgisi, kalp çizgisi gibi sembolleri kullan."
                )
            elif reading_type in ("energy", "dream"):
                style_hint = (
                    "Bu bir ENERJİ / RÜYA yorumudur. Fincandan söz ETME; daha çok ruh hali, semboller ve bilinçaltı üzerinden konuş."
                )
            elif reading_type == "soul":
                style_hint = (
                    "Bu bir RUH BAĞLANTISI yorumudur. İki ruh arasındaki enerji, bağlantı, çekim ve karmik bağlardan bahset."
                )
            else:
                style_hint = (
                    "Kategori belirtilmedi, genel mistik bir fal ve enerji yorumu yap. "
                    "Kahve, tarot gibi spesifik kelimeleri çok vurgulama, daha nötr sembolik bir dil kullan."
                )

            user_prompt = f"""
Kullanıcının sorusu / niyeti:

\"\"\"{user_input}\"\"\"

{style_hint}

Yukarıdaki soruya ve enerjiye göre tek parça, akıcı bir fal ve enerji yorumu yaz.
Kahve falı, tarot, el falı, enerji ya da rüya yorumu yapıyor olabilirsin; semboller üzerinden konuşup
kişinin ruh halini, iç dünyasını ve yakın geleceğini yorumla.

Lütfen şuna dikkat et:
- Etkileyici ve mistik bir giriş yap; enerjisini ve şu anki halini anlat.
- Ortada, yaşadığı sürecin duygusal ve psikolojik tarafını sıcak ve anlayışlı bir dille anlat.
- Aşk, ilişkiler, kariyer, para ve kişisel dönüşüm alanlarında görebildiğin fırsatları ve olasılıkları paylaş.
- Yakın gelecek (önümüzdeki haftalar/aylar) için net ama korkutmayan, umut veren cümlelerle olası gelişmeleri anlat.
- Sonda, kalbine dokunan, destekleyici bir kapanış paragrafı yaz; kişinin değerini ve iç gücünü hatırlat.

Cevabı SORU-CEVAP biçiminde değil, tek bir uzun fal metni olarak yaz.
"""
        else:
            if reading_type == "coffee":
                style_hint = (
                    "This is a COFFEE READING. You may gently mention symbols in the cup, "
                    "like “in your cup I see…”, but keep it natural, not exaggerated."
                )
            elif reading_type == "tarot":
                style_hint = (
                    "This is a TAROT reading. Use the language of tarot: suits, major arcana, spreads."
                )
            elif reading_type == "palm":
                style_hint = (
                    "This is a PALM reading. Talk about palm lines, life line, heart line, and general hand symbolism."
                )
            elif reading_type in ("energy", "dream"):
                style_hint = (
                    "This is an ENERGY / DREAM reading. Do NOT mention coffee cups; focus on feelings, symbols and the subconscious."
                )
            elif reading_type == "soul":
                style_hint = (
                    "This is a SOUL CONNECTION reading. Talk about the energetic bond, attraction, lessons and growth between two souls."
                )
            else:
                style_hint = (
                    "No specific category is given. Give a general mystical fortune & energy reading "
                    "without overusing coffee or tarot specific words."
                )

            user_prompt = f"""
User's question / intention:

\"\"\"{user_input}\"\"\"

{style_hint}

Based on the question and energy above, write ONE complete, flowing fortune & energy reading.
It may feel like a coffee, tarot, palm, energy or dream reading; use symbols and intuition
to describe the person's emotional state, inner world and near future.

Please:
- Start with a mystical, impactful introduction describing the current energy.
- Then explore their emotional and psychological process in a warm, understanding tone.
- Touch on love, relationships, career, money and personal growth, sharing possible opportunities and lessons.
- For the near future (next weeks/months), describe likely developments in a hopeful but realistic way.
- End with a heartfelt closing paragraph that reminds them of their worth and inner strength.

Do NOT answer in Q&A format; write a single, coherent fortune-style text.
"""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1600,
        )

        text = completion.choices[0].message.content.strip()

        # ============================
        #  PRO TTS (OpenAI Audio)
        # ============================
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        audio_url = None

        try:
            # OpenAI TTS – daha doğal, insan benzeri ses
            with client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice="alloy",  # istersen sonra voice'i değiştirebiliriz
                input=text,
            ) as response:
                response.stream_to_file(audio_path)
            audio_url = f"/audio/{audio_id}"
        except Exception as e:
            traceback.print_exc()
            # Ses hata verirse fallback: sadece metin döneriz
            audio_url = None

        return jsonify({"text": text, "audio": audio_url})

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

        if not lang:
            try:
                lang = detect(birth_place)
            except Exception:
                lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)
        focus_str = ", ".join(focus) if focus else ("Genel" if lang == "tr" else "General")

        # ---- NATAL HARİTASI (GERÇEK HESAP) ----
        lat, lon = geocode_place(birth_place)
        chart_id = None
        chart_public_path = None
        chart_meta = None

        try:
            timezone_str = get_timezone_from_latlon(lat, lon)
            chart_id, chart_file_path, chart_meta = generate_natal_chart(
                birth_date=birth_date,
                birth_time=birth_time,
                latitude=lat,
                longitude=lon,
                out_dir="/tmp",
                timezone_str=timezone_str,
            )
            chart_public_path = f"/chart/{chart_id}"
        except Exception as e:
            print("Natal chart generation error:", e)

        chart_summary = build_chart_summary(chart_meta, lang)

        if lang == "tr":
            user_prompt = (
                f"Premium NATAL astroloji raporu oluştur.\n"
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"Danışan ismi: {name}\n"
                f"Odak alanları: {focus_str}\n"
                f"Özel soru veya niyet: {question}\n\n"
                "Aşağıda Swiss Ephemeris ile hesaplanmış gerçek doğum haritası yerleşimleri verilmiştir. "
                "Lütfen yorumlarını bu yerleşimlere sadık kalarak yap:\n\n"
                f"{chart_summary}\n\n"
                "Lütfen raporu şu başlıklarla ve detaylı şekilde yaz:\n"
                "1) Giriş ve genel enerji\n"
                "2) Kişilik, ego ve ruhsal yapı (Güneş, Ay, ASC)\n"
                "3) Zihinsel yapı ve iletişim (Merkür)\n"
                "4) Aşk, ilişkiler ve çekim alanı (Venüs, 5. ve 7. evler)\n"
                "5) Enerji, motivasyon ve mücadele (Mars)\n"
                "6) Kariyer, para ve yaşam amacı (MC, 10. ev, Jüpiter, Satürn)\n"
                "7) Dışsal gezegenler ve karmik dersler (Uranüs, Neptün, Plüton)\n"
                "8) 12 ev üzerinden kısa ama anlamlı bir geçiş (her ev için 1-2 cümle)\n"
                "9) Önümüzdeki 3-6 aya dair genel temalar ve öneriler\n\n"
                "Dili sıcak, anlaşılır, profesyonel ve motive edici kullan. "
                "Danışanın kendini suçlu hissetmesine değil, bilinçlenmesine yardımcı ol."
            )
        else:
            user_prompt = (
                f"Create a premium NATAL astrology report.\n"
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Client name: {name}\n"
                f"Focus areas: {focus_str}\n"
                f"Specific question or intention: {question}\n\n"
                "Below are the actual natal chart placements calculated with Swiss Ephemeris. "
                "Please base your interpretation strictly on these placements:\n\n"
                f"{chart_summary}\n\n"
                "Please structure the report with clear headings:\n"
                "1) Introduction and overall energy\n"
                "2) Personality, ego and soul structure (Sun, Moon, ASC)\n"
                "3) Mind and communication (Mercury)\n"
                "4) Love, relationships and attraction (Venus, 5th and 7th houses)\n"
                "5) Drive, desire and action (Mars)\n"
                "6) Career, money and life direction (MC, 10th house, Jupiter, Saturn)\n"
                "7) Outer planets and karmic lessons (Uranus, Neptune, Pluto)\n"
                "8) Short but meaningful overview of the 12 houses (1–2 sentences each)\n"
                "9) General themes and advice for the next 3–6 months\n\n"
                "Use a warm, clear and empowering tone. Focus on awareness and growth rather than fear."
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2300,
        )
        text = completion.choices[0].message.content.strip()

        return jsonify(
            {
                "text": text,
                "chart": chart_public_path,
                "chart_id": chart_id,
                "chart_data": chart_meta,
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
    Solar return raporu + harita.
    Not: Solar return tarihi, doğum günü + aynı saat üzerinden yaklaşık alınır.
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

        y0, m0, d0 = map(int, birth_date.split("-"))
        sr_date = f"{year:04d}-{m0:02d}-{d0:02d}"

        if not lang:
            try:
                lang = detect(birth_place)
            except Exception:
                lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        lat, lon = geocode_place(birth_place)
        chart_id = None
        chart_public_path = None
        try:
            timezone_str = get_timezone_from_latlon(lat, lon)
            chart_id, chart_file_path, _ = generate_natal_chart(
                birth_date=sr_date,
                birth_time=birth_time,
                latitude=lat,
                longitude=lon,
                out_dir="/tmp",
                timezone_str=timezone_str,
            )
            chart_public_path = f"/chart/{chart_id}"
        except Exception as e:
            print("Solar return chart error:", e)

        system_prompt = build_system_prompt("solar_return", lang)

        if lang == "tr":
            user_prompt = (
                f"Solar return (güneş dönüşü) astroloji raporu oluştur.\n"
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"Solar return yılı: {year}\n\n"
                "Raporda şu başlıkları kullan:\n"
                "1) Bu yılın genel atmosferi ve ana dersleri\n"
                "2) Aşk, ilişkiler ve sosyal çevre\n"
                "3) Kariyer, para, iş ve fırsatlar\n"
                "4) Ruhsal gelişim, şifa ve içsel dönüşüm\n"
                "5) Bu yıl dikkat edilmesi gereken gölgeler / uyarılar\n"
                "6) Danışan için bilinçli seçimler ve öneriler\n"
                "Dili sıcak, gerçekçi ve umut verici kullan."
            )
        else:
            user_prompt = (
                f"Create a SOLAR RETURN astrology report.\n"
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Solar return year: {year}\n\n"
                "Please structure the report with headings:\n"
                "1) Overall atmosphere and main lessons of the year\n"
                "2) Love, relationships and social life\n"
                "3) Career, money, work and opportunities\n"
                "4) Spiritual growth, healing and inner transformation\n"
                "5) Potential challenges and what to be mindful about\n"
                "6) Practical advice and conscious choices for the year\n"
                "Keep the tone warm, realistic and encouraging."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1600,
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
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"Danışan ismi: {name}\n"
                f"Bugün: {today}\n\n"
                "Lütfen raporu şu başlıklarla yaz:\n"
                "1) Son dönem ve şu anki genel enerji\n"
                "2) Önümüzdeki 1-3 ay için ana temalar\n"
                "3) Aşk ve ilişkiler üzerindeki transit etkileri\n"
                "4) Kariyer, para ve iş alanındaki transit etkileri\n"
                "5) Ruhsal gelişim, şifa ve içsel süreçler\n"
                "6) Özellikle Satürn, Uranüs, Neptün, Plüton transitleri ve ana dersler\n"
                "7) Danışana özel tavsiyeler ve odaklanması gereken noktalar\n"
                "Korkutucu değil, bilinçlendirici ve motive edici bir dil kullan."
            )
        else:
            user_prompt = (
                f"Create a TRANSIT-focused astrology report.\n"
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Client name: {name}\n"
                f"Today: {today}\n\n"
                "Please structure the report with headings:\n"
                "1) Recent past and current overall energy\n"
                "2) Main themes for the next 1–3 months\n"
                "3) Transits affecting love and relationships\n"
                "4) Transits affecting career, money and work\n"
                "5) Spiritual growth, healing and inner processes\n"
                "6) Key long-term transits (Saturn, Uranus, Neptune, Pluto) and their lessons\n"
                "7) Practical advice and focus points for the client\n"
                "Keep the tone empowering and supportive, not fear-based."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1600,
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
        if os.path.exists(FONT_PATH_TTF):
            self.add_font("DejaVu", "", FONT_PATH_TTF, uni=True)
            self.add_font("DejaVu", "B", FONT_PATH_TTF, uni=True)

    def header(self):
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 10, 7, 16)

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
    Frontend, text + chart_id + language + (opsiyonel) report_type + meta ile çağırır.
    report_type: 'natal' | 'solar' | 'transits'
    """
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()
        chart_id = data.get("chart_id")
        lang = data.get("language", "en")
        report_type = (data.get("report_type") or "natal").lower()

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name")
        solar_year = data.get("solar_year")

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = MystPDF()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.alias_nb_pages()
        pdf.add_page()

        if lang == "tr":
            if report_type == "solar":
                title = "MystAI Güneş Dönüşü (Solar Return) Astroloji Raporu"
                sub = (
                    "Bu rapor, doğum haritan ile güneş dönüşü haritanı bir araya getirerek "
                    "önümüzdeki yaklaşık bir yılın ana temalarını yorumlar."
                )
            elif report_type == "transits":
                title = "MystAI Transit Astroloji Raporu"
                sub = (
                    "Bu rapor, güncel gökyüzü hareketlerini (transitleri) doğum haritanla ilişkilendirerek "
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

        pdf.set_font("DejaVu", "B", 17)
        pdf.set_text_color(30, 32, 60)
        pdf.multi_cell(0, 8, title)
        pdf.ln(2)

        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(85, 90, 125)
        pdf.multi_cell(0, 6, sub)
        pdf.ln(6)

        meta_lines = []
        if birth_date and birth_time and birth_place:
            if lang == "tr":
                meta_lines.append(f"Doğum: {birth_date} • {birth_time} • {birth_place}")
            else:
                meta_lines.append(f"Birth: {birth_date} • {birth_time} • {birth_place}")
        if solar_year and report_type == "solar":
            if lang == "tr":
                meta_lines.append(f"Güneş dönüşü yılı: {solar_year}")
            else:
                meta_lines.append(f"Solar return year: {solar_year}")
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

        has_chart_page = False
        if chart_id and report_type in ("natal", "solar"):
            chart_file = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_file):
                try:
                    img = Image.open(chart_file).convert("RGB")
                    rgb_fixed = f"/tmp/{chart_id}_rgb.jpg"
                    img.save(rgb_fixed, "JPEG", quality=95)

                    img_width = 140
                    x = (210 - img_width) / 2
                    y = pdf.get_y() + 2

                    pdf.image(rgb_fixed, x=x, y=y, w=img_width)
                    has_chart_page = True
                except Exception as e:
                    print("PDF image error:", e)

        if has_chart_page:
            pdf.add_page()

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
