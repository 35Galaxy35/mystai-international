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
# SYSTEM PROMPT (GENEL)
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
# NORMAL /predict (Ask MystAI)
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


# =========================================================
# GELİŞMİŞ ASTROLOJİ  (UZUN RAPOR + PROFESYONEL HARİTA)
# Frontend: astrology.html bu endpoint'i kullanıyor
# =========================================================
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

        # Dili tespit et (TR / EN)
        raw_text_for_lang = " ".join([
            birth_place or "",
            question or "",
            " ".join(focus) if focus else "",
        ]).strip()

        try:
            lang = detect(raw_text_for_lang) if raw_text_for_lang else "tr"
        except Exception:
            lang = "tr"

        if lang not in ("tr", "en"):
            lang = "tr"

        # Odak alanları string
        if focus:
            focus_text = ", ".join(focus)
        else:
            focus_text = "Genel" if lang == "tr" else "General"

        # Kullanıcı bilgilerini özetle (LLM'e gidecek metin)
        if lang == "tr":
            user_summary = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim: {name or 'Belirtilmemiş'}\n"
                f"Odak alanları: {focus_text}\n"
                f"Kullanıcının sorusu/niyeti: {question or 'Belirtilmemiş'}\n"
            )
        else:
            user_summary = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not specified'}\n"
                f"Focus areas: {focus_text}\n"
                f"User question / intention: {question or 'Not specified'}\n"
            )

        # ---- SYSTEM PROMPT: PROFESYONEL ASTROLOG MODU ----
        if lang == "tr":
            system_prompt = (
                "Sen, dünya çapında bilinen çok deneyimli bir profesyonel astrologsun. "
                "Modern psikolojik astroloji, klasik astroloji ve spiritüel yaklaşımı birleştiriyorsun. "
                "Tarzın: derin, profesyonel, dürüst ama her zaman umut verici ve güçlendirici.\n\n"
                "Kullanıcıya, natal + solar return + transit mantığında, EN AZ 8 BÖLÜMLÜ, çok kapsamlı bir astroloji raporu yaz. "
                "Metin akıcı Türkçe olsun. Gerektiğinde başlıklar kullan.\n\n"
                "Raporda özellikle şu bölümler olmalı (başlıkları benzer ama anlamlı şekilde sen koyabilirsin):\n"
                "1) Giriş ve genel enerji\n"
                "2) Kişilik, yükselen ve temel karakter\n"
                "3) Aşk, ilişkiler ve duygusal dünya\n"
                "4) Kariyer, meslek, para ve maddi alanlar\n"
                "5) Ruhsal gelişim, karmik temalar ve içsel yolculuk\n"
                "6) Önümüzdeki 12 aya yayılmış ana transit/temalar (fırsatlar, dikkat edilmesi gereken dönemler)\n"
                "7) İlişkiler ve sosyal çevre ile ilgili özet mesajlar\n"
                "8) Son bölüm: sevgi dolu, motive edici, toparlayıcı bir kapanış\n\n"
                "Odak alanları ve kullanıcının sorusu varsa mutlaka yorumların içinde bunlara özel paragraflar ayır. "
                "Genel fal gibi yüzeysel kalma; sanki karşında oturan danışanına uzun seans yapıyormuşsun gibi yaz. "
                "Net öneriler, farkındalık cümleleri ve yapıcı tavsiyeler ver."
            )
        else:
            system_prompt = (
                "You are a highly experienced professional astrologer with a worldwide reputation. "
                "You blend modern psychological astrology, traditional techniques and a spiritual approach. "
                "Your tone is deep, professional, honest yet always empowering and hopeful.\n\n"
                "Write a VERY DETAILED astrology report in English, in the style of natal + solar return + transits, "
                "with AT LEAST 8 CLEAR SECTIONS. Use headings where appropriate.\n\n"
                "Suggested sections (you can rename them in a meaningful way):\n"
                "1) Introduction & overall energy\n"
                "2) Personality, Ascendant and core character\n"
                "3) Love, relationships and emotional world\n"
                "4) Career, vocation, money and material life\n"
                "5) Spiritual growth, karmic themes and inner journey\n"
                "6) Main themes for the next 12 months (opportunities, challenging periods, key lessons)\n"
                "7) Social life, friends and networks\n"
                "8) Final section: a warm, motivating and integrating conclusion\n\n"
                "If the user has specific focus areas or a question, weave those into the interpretation explicitly. "
                "Do not be shallow or generic – write as if this is a full professional consultation."
            )

        # ---- USER PROMPT: BİLGİ + İSTEK ----
        if lang == "tr":
            user_prompt = (
                "Aşağıda kullanıcının doğum bilgileri ve odak alanları yer alıyor.\n\n"
                f"{user_summary}\n"
                "Bu bilgilere göre, talep edilen bölümlere uygun olacak şekilde, kapsamlı ve profesyonel bir astroloji raporu yaz."
            )
        else:
            user_prompt = (
                "Below you can see the user's birth data and focus areas.\n\n"
                f"{user_summary}\n"
                "Based on this, write a comprehensive professional astrology report matching the requested sections."
            )

        # ---- METİN RAPORU OLUŞTUR ----
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2200,
            temperature=0.9,
        )

        text = completion.choices[0].message.content.strip()

        # ---- HARİTA GÖRSELİ (PROFESYONEL STİL) ----
        if lang == "tr":
            img_prompt = (
                "Profesyonel astroloji yazılımı görünümünde, yüksek kaliteli bir doğum haritası çarkı: "
                "12 ev, burç sembolleri, gezegen sembolleri, merkezde kırmızı ve mavi açısal çizgiler, "
                "krem dış halka, koyu lacivert kozmik arka plan, yüksek çözünürlük, yazısız, sadece semboller."
            )
        else:
            img_prompt = (
                "High-quality professional natal astrology chart wheel: "
                "12 houses, zodiac glyphs around the circle, planet glyphs in correct style, "
                "red and blue aspect lines in the center, cream outer ring, deep navy cosmic background, "
                "no text labels, only symbols, HD, 4k."
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
            "audio": None,
            "language": lang,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# OPSİYONEL: PREMIUM ASTROLOJİ
# (Şu an frontend bunu kullanmıyor, ileride kullanabiliriz)
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
                "- 12 evin kısa analizi\n- Önümüzdeki 1 yıla dair önemli transit temaları\n"
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
            ]
        )

        text = completion.choices[0].message.content.strip()

        img_prompt = (
            "High-quality natal astrology chart wheel, circular chart, zodiac signs around the wheel, "
            "elegant fine lines, mystical deep blue cosmic background, golden accents, HD, 4k, no text labels."
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
            "audio": None,
            "language": lang
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
# RUN (Render uyumlu)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
