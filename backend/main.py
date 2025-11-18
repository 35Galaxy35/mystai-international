# ============================================
# MystAI - Full Stable Backend (ASTRO UZUN RAPOR + KİŞİYE ÖZEL HARİTA)
# Render uyumlu
# ============================================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS
import os
import uuid
import traceback
import base64
import json
from fpdf import FPDF   # PDF için en stabil yöntem (Render uyumlu)


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


@app.route("/")
def index():
    return "MystAI Backend Running 🔮"


# -----------------------------
# SYSTEM PROMPT
# -----------------------------
def build_system_prompt(type_name, lang):
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel ve destekleyici bir yorumcusun. "
            "Kullanıcıya derin, pozitif, empatik ve gerçekçi bir dille açıklama yaparsın. "
            "Cümlelerin akıcı, detaylı ve yapılandırılmıştır."
        )
        types = {
            "general": base + " Genel enerji, sezgi ve rehberlik sun.",
            "astrology": base + (
                " Profesyonel bir astrolog gibi konuş. Doğum haritasını gezegenler, evler ve açılar üzerinden "
                "derinlemesine yorumla. Kişinin hayat dinamiklerini psikolojik ve ruhsal açıdan analiz et."
            ),
        }
    else:
        base = (
            "You are MystAI, a mystical, professional and supportive interpreter. "
            "You speak in a warm, deep and structured way, offering realistic but encouraging insights."
        )
        types = {
            "general": base + " Provide intuitive spiritual guidance.",
            "astrology": base + (
                " Speak as a professional astrologer. Analyse the natal chart using planets, houses and aspects "
                "with psychological and spiritual depth."
            ),
        }

    return types.get(type_name, types["general"])


# =====================================================
# Küçük yardımcı: doğum verisinden tahmini harita bilgisi üret
# (Gezegen konumlarını OpenAI'den JSON formatında alıyoruz.)
# =====================================================
def estimate_chart_positions(birth_date, birth_time, birth_place, lang="en"):
    """
    OpenAI'ye doğum bilgilerini verip
    Güneş, Ay, Merkür, Venüs, Mars, Jüpiter, Satürn, Uranüs, Neptün, Pluto,
    ASC ve MC için burç + derece tahmini alır.
    """
    if lang == "tr":
        sys_msg = (
            "Sen hem astrolog hem astronom olan bir asistansın. "
            "Verilen doğum tarih, saat ve yere göre gezegenlerin zodyaktaki konumlarını tahmini olarak çıkar. "
            "Sonucu mutlaka JSON formatında ver."
        )
        user_msg = f"""
Doğum verileri:
Tarih: {birth_date}
Saat: {birth_time}
Yer: {birth_place}

Lütfen şu formatta JSON üret (başka açıklama yazma):

{{
  "Sun":   {{"sign": "...", "degree": 0-30 arası sayı}},
  "Moon":  {{"sign": "...", "degree": ...}},
  "Mercury": {{...}},
  "Venus":   {{...}},
  "Mars":    {{...}},
  "Jupiter": {{...}},
  "Saturn":  {{...}},
  "Uranus":  {{...}},
  "Neptune": {{...}},
  "Pluto":   {{...}},
  "Ascendant": {{"sign": "...", "degree": ...}},
  "Midheaven": {{"sign": "...", "degree": ...}}
}}
"""
    else:
        sys_msg = (
            "You are both an astrologer and an astronomer. "
            "Given birth date, time and place, estimate the positions of the planets in the zodiac. "
            "Return ONLY valid JSON."
        )
        user_msg = f"""
Birth data:
Date: {birth_date}
Time: {birth_time}
Place: {birth_place}

Return JSON only, no extra text. Example shape:

{{
  "Sun":   {{"sign": "...", "degree": 0-30}},
  "Moon":  {{"sign": "...", "degree": ...}},
  "Mercury": {{...}},
  "Venus":   {{...}},
  "Mars":    {{...}},
  "Jupiter": {{...}},
  "Saturn":  {{...}},
  "Uranus":  {{...}},
  "Neptune": {{...}},
  "Pluto":   {{...}},
  "Ascendant": {{"sign": "...", "degree": ...}},
  "Midheaven": {{"sign": "...", "degree": ...}}
}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        return data
    except Exception:
        traceback.print_exc()
        # Hata olursa boş dict döneriz; backend yine de çalışır
        return {}


# -----------------------------
# NORMAL /predict (ENERGY / ASK MYSTAI)
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


# =====================================================
# ASTROLOJİ – UZUN RAPOR + KİŞİYE ÖZEL HARİTA
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

        # Dil algılama
        try:
            lang = detect(birth_place)
        except Exception:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        # -------------------------
        # 1) TAHMİNİ DOĞUM HARİTASI VERİLERİ
        # -------------------------
        positions = estimate_chart_positions(birth_date, birth_time, birth_place, lang=lang)

        # Gezegen satırlarını metne dök
        planet_lines = []
        for key, value in positions.items():
            try:
                sign = value.get("sign", "?")
                deg = value.get("degree", "?")
                planet_lines.append(f"{key}: {sign} {deg}°")
            except Exception:
                continue

        positions_text = "\n".join(planet_lines) if planet_lines else "No positions calculated."

        # Kullanıcı odak alanlarını daha okunur hale getir
        focus_readable = ", ".join(focus) if focus else ("Genel" if lang == "tr" else "General")

        # -------------------------
        # 2) RAPOR PROMPT'U (ÇOK UZUN METİN)
        # -------------------------
        if lang == "tr":
            user_prompt = f"""
Aşağıdaki doğum haritasına dayalı olarak profesyonel, DERİN ve UZUN bir astroloji raporu yaz.

Doğum bilgileri:
- Tarih: {birth_date}
- Saat: {birth_time}
- Yer: {birth_place}
- İsim: {name or 'Belirtilmemiş'}
- Odak alanları: {focus_readable}
- Soru / niyet: {question or 'Genel rehberlik isteği'}

Tahmini gezegen yerleşimleri ve noktalar:
{positions_text}

İSTENEN RAPOR YAPISI (en az 1500–3000 kelime):

1) Giriş:
   - Kişinin genel enerji atmosferi
   - Haritanın ilk bakışta verdiği izlenim

2) Natal harita analizi:
   - Güneş, Ay, ASC ve MC'nin önemi
   - Tüm gezegenlerin burç ve ev konumları üzerinden karakter analizi
   - Element (ateş, toprak, hava, su) ve nitelik (öncü, sabit, değişken) dengesi

3) Aşk & ilişkiler:
   - Venüs, Mars, Ay ve 5./7. evlerle bağlantılı yorum
   - Bağlanma biçimi, ilişki dinamikleri, çekim alanları
   - Varsa öğrenilmesi gereken ilişki dersleri

4) Kariyer, para ve yaşam amacı:
   - MC, 2., 6. ve 10. ev temaları
   - Kişinin yetenekleri, mesleki potansiyeli ve bolluk alanları
   - Kariyerle ilgili geleceğe dönük tavsiyeler

5) Psikolojik ve ruhsal derinlik:
   - Karmik dersler, tekrar eden kalıplar
   - Güçlü ve zayıf yönler
   - Ruhsal gelişim, şifa ve dönüşüm fırsatları

6) Önümüzdeki 12 ayın transiti / solar return havası:
   - Yaklaşan önemli temalar (aşk, kariyer, para, içsel yolculuk)
   - Kişiyi bekleyen fırsatlar ve dikkat edilmesi gereken noktalar

7) Son bölüm:
   - Kısa bir özet
   - Sevgi dolu, cesaretlendirici kapanış cümleleri
   - Kişinin kendi iradesini ve seçim özgürlüğünü hatırlatan bir not

Dili akıcı, samimi ama profesyonel tut. Gereksiz astro-teknik kavramları sade bir dille açıkla.
            """
        else:
            user_prompt = f"""
Based on the birth chart below, write a PROFESSIONAL, DEEP and LONG astrology report.

Birth data:
- Date: {birth_date}
- Time: {birth_time}
- Place: {birth_place}
- Name: {name or 'Not given'}
- Focus areas: {focus_readable}
- Question / intention: {question or 'General guidance'}

Estimated natal positions:
{positions_text}

REQUESTED STRUCTURE (at least 1500–3000 words):

1) Introduction:
   - Overall energetic tone of the chart
   - First impression of the person's life themes

2) Natal chart analysis:
   - Role of the Sun, Moon, Ascendant and Midheaven
   - Character analysis through all planets by sign and house
   - Balance of elements (fire, earth, air, water) and modes (cardinal, fixed, mutable)

3) Love & relationships:
   - Venus, Mars, Moon and 5th/7th house themes
   - Attachment style, relationship patterns, what the person attracts
   - Lessons to be learned in love

4) Career, money and life purpose:
   - MC, 2nd, 6th and 10th house themes
   - Talents, professional potential and abundance channels
   - Forward-looking advice on career direction

5) Psychological & spiritual depth:
   - Karmic lessons and repeating patterns
   - Strengths and vulnerabilities
   - Spiritual growth, healing and transformation opportunities

6) Next 12 months (transits / solar return style):
   - Key themes in love, career, money and inner life
   - Main opportunities and potential challenges

7) Closing:
   - Short summary
   - Encouraging closing words
   - A reminder of free will and the power of conscious choice

Keep the tone warm, mystical and empowering, while remaining grounded and realistic.
            """

        # -------------------------
        # 3) RAPOR OLUŞTUR
        # -------------------------
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": build_system_prompt("astrology", lang)},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3500,
        )

        text = completion.choices[0].message.content.strip()

        # -------------------------
        # 4) KİŞİYE ÖZEL HARİTA GÖRSELİ
        # -------------------------
        if lang == "tr":
            img_prompt = f"""
Yüksek kaliteli, dairesel bir doğum haritası çarkı çiz.
Aşağıdaki gezegen yerleşimlerini temel al:

{positions_text}

Klasik astroloji doğum haritası görünümü:
- Burçlar çemberi
- Ev çizgileri
- Merkezde kırmızı ve mavi açı çizgileri
- Mistifik koyu lacivert kozmik arka plan
- Altın tonlarda detaylar
- 4K, HD kalitede, yazı etiketleri çok minimal olsun.
            """
        else:
            img_prompt = f"""
Draw a high-quality circular natal astrology chart wheel
based on the following positions:

{positions_text}

Classic natal chart style:
- Zodiac ring with signs
- House cusps
- Red and blue aspect lines in the center
- Deep midnight blue cosmic background with golden accents
- HD / 4K quality, minimal text labels.
            """

        img = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024",
        )

        b64 = img.data[0].b64_json
        img_data = base64.b64decode(b64)

        chart_id = uuid.uuid4().hex
        chart_path = f"/tmp/{chart_id}.png"
        with open(chart_path, "wb") as f:
            f.write(img_data)

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
# (İstersen kalsın) PREMIUM ASTROLOGY
# Frontend şu an bunu kullanmıyor; dokunmadık.
# -----------------------------
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")

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
                f"PREMİUM astroloji raporu oluştur.\n"
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n\n"
                "- Derin kişilik analizi\n- Yaşam amacı ve kader yolu\n"
                "- Aşk & ilişkiler\n- Kariyer ve bolluk\n"
                "- Karmik dersler ve ruhsal gelişim\n"
                "- 12 evin kısa analizi\n"
                "- Önümüzdeki 1 yıla dair önemli transit temaları\n"
            )
        else:
            user_prompt = (
                f"Create a PREMIUM astrology report.\n"
                f"Birth: {birth_date} {birth_time} - {birth_place}\n\n"
                "- Deep personality analysis\n- Life purpose & destiny\n"
                "- Love & relationships\n- Career & abundance\n"
                "- Karmic lessons & spiritual growth\n"
                "- Short analysis of the 12 houses\n"
                "- Key transits and themes for the coming year\n"
            )

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = completion.choices[0].message.content.strip()

        # Basit chart (istersen burada da positions_text kullanacak şekilde geliştirebiliriz)
        img_prompt = (
            "High-quality natal astrology chart wheel, circular chart, zodiac signs around the wheel, "
            "elegant fine lines, mystical deep blue cosmic background, golden accents, HD, 4k, no text labels."
        )

        img = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024",
        )

        b64 = img.data[0].b64_json
        img_data = base64.b64decode(b64)

        chart_id = uuid.uuid4().hex
        chart_path = f"/tmp/{chart_id}.png"
        with open(chart_path, "wb") as f:
            f.write(img_data)

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
# PDF GENERATOR (FINAL – STABLE)
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
# RUN (Render uyumlu – lokal için)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
