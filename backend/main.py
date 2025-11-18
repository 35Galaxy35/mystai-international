# ============================================
# MystAI - Full Stable Backend (FINAL VERSION)
# Tüm özellikler çalışan, Render uyumlu
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
            "Kullanıcıya derin, pozitif ve gerçekçi bir dille açıklama yaparsın."
        )
        types = {
            "general": base + " Genel enerji, sezgi ve rehberlik sun.",
            "astrology": base + " Doğum haritasını gezegenler, evler ve açılar üzerinden profesyonel şekilde yorumla."
        }
    else:
        base = (
            "You are MystAI, a mystical and professional interpreter. "
            "You speak warmly, deeply and offer supportive insights."
        )
        types = {
            "general": base + " Provide intuitive guidance.",
            "astrology": base + " Provide structured natal chart analysis using planets, houses and aspects."
        }

    return types.get(type_name, types["general"])


# -----------------------------
# NORMAL /predict
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
            ]
        )

        text = completion.choices[0].message.content.strip()

        # Ses oluştur
        audio_id = uuid.uuid4().hex
        audio_path = f"/tmp/{audio_id}.mp3"
        gTTS(text=text, lang=lang).save(audio_path)

        return jsonify({
            "text": text,
            "audio": f"/audio/{audio_id}"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# BASIC ASTROLOGY
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
                "Kapsamlı bir astroloji raporu yaz."
            )
        else:
            user_prompt = (
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\nFocus: {', '.join(focus) or 'General'}\n"
                f"Question: {question}\n"
                "Write a detailed natal chart interpretation."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900
        )

        text = completion.choices[0].message.content.strip()

        return jsonify({"text": text, "chart": None, "audio": None, "language": lang})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PREMIUM ASTROLOGY (GÜNCEL)
# -----------------------------
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        # Dil algılama
        try:
            lang = detect(birth_place)
        except:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        # ----------- PREMIUM RAPOR PROMPTU ------------
        if lang == "tr":
            user_prompt = f"""
Premium, en az 20 sayfalık çok uzun ve detaylı bir astroloji raporu oluştur.

Doğum Bilgileri:
- Tarih: {birth_date}
- Saat: {birth_time}
- Yer: {birth_place}
- İsim: {name}

Raporun Yapısı:

1. Kapak Bölümü (kısa özet)
2. Kişiye Özel Giriş (1–2 sayfa)
3. Güneş Burcu, Ay Burcu ve Yükselen Burç (her biri ayrı başlık ve en az 1 sayfa)
4. Diğer Gezegenler Burçlarda (Merkür, Venüs, Mars, Jüpiter, Satürn, Uranüs, Neptün, Pluto)
5. Evlerde Gezegenler (1–12. Ev, özellikle 1., 2., 5., 7., 10. ve 12. evleri detaylı anlat)
6. Aspektler (En az 10 önemli açı; her bir açı 2–3 paragraf olacak şekilde derin yorumla)
7. Aşk & İlişkiler Analizi
8. Kariyer & Yaşam Amacı
9. Para & Maddi Potansiyel
10. Karmik Dersler ve Geçmiş Hayat Temaları (kader, düğümler, tekrar eden dersler)
11. Ruhsal Yolculuk ve Spiritüel Potansiyel
12. Sonuç ve Kapanış Mesajı (danışana özel güçlü, motive edici bir final)

Her bölümü net başlıklarla ayır, mistik ama profesyonel bir dille yaz.
Akıcı paragraf yapısı kullan, madde madde ve paragrafları karıştırarak zengin bir anlatım oluştur.
"""
        else:
            user_prompt = f"""
Create a premium, very long (at least the equivalent of 20 pages) natal astrology report.

Birth data:
- Date: {birth_date}
- Time: {birth_time}
- Place: {birth_place}
- Name: {name}

Structure of the report:

1. Cover-style short overview
2. Personalized introduction (1–2 pages)
3. Sun, Moon and Rising sign (each with its own section, at least 1 page each)
4. Planets in signs (Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto)
5. Planets in houses (1–12, with special focus on 1st, 2nd, 5th, 7th, 10th and 12th houses)
6. Aspects (At least 10 major aspects, each explained with 2–3 paragraphs in depth)
7. Love & Relationships analysis
8. Career & Life Purpose
9. Money & Material Potential
10. Karmic lessons and past-life themes
11. Spiritual path and soul growth
12. Final message and conclusion (strong, motivating, personal)

Use clear headings, a mystical yet professional tone and long, rich paragraphs.
"""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3000,
            temperature=0.9
        )

        text = completion.choices[0].message.content.strip()

        # ---------- AI HARİTA GÖRSELİ ----------
        # Şimdilik gerçek hesap yerine, profesyonel bir görsel üretiyoruz.
        img_prompt = (
            "Elegant professional natal astrology chart wheel, "
            "thin lines, high-quality, realistic planet symbols, "
            "dark navy background, golden highlights."
        )

        img = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024"
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
            "chart_id": chart_id,
            "audio": None,
            "language": lang
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PDF GENERATOR (GÜNCEL – HARİTALI)
# -----------------------------
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()
        chart_id = data.get("chart_id")

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # İstersen Türkçe karakter desteği için TTF font ekleyebilirsin:
        # pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        # pdf.set_font("DejaVu", size=12)
        pdf.set_font("Arial", size=12)

        # ---------- 1. SAYFA: HARİTA + BAŞLANGIÇ ----------
        pdf.add_page()

        if chart_id:
            chart_path = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_path):
                # Haritayı kapağa büyükçe yerleştir
                pdf.image(chart_path, x=20, y=20, w=170)
                pdf.ln(115)
        else:
            pdf.ln(10)

        # Kapak altına kısa başlık istersen buraya yazabilirsin:
        # pdf.set_font("Arial", "B", 16)
        # pdf.cell(0, 10, "MystAI Premium Astroloji Raporu", ln=True, align="C")
        # pdf.ln(10)
        # pdf.set_font("Arial", size=12)

        # ---------- METNİ SAYFALARA YAY ----------
        lines = text.split("\n")
        for line in lines:
            # Çok uzun satırları da böler
            pdf.multi_cell(0, 8, line)
            pdf.ln(1)

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
# RUN (Render uyumlu)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
