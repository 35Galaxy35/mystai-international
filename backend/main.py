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


# -----------------------------
# BASIC ASTROLOGY  (RAPOR + CHART)
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
        except Exception:
            lang = "en"
        if lang not in ("tr", "en"):
            lang = "en"

        system_prompt = build_system_prompt("astrology", lang)

        # ---- Astroloji metin prompt'u ----
        if lang == "tr":
            user_prompt = (
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\nOdak alanları: {', '.join(focus) or 'Genel'}\n"
                f"Soru / niyet: {question}\n\n"
                "Natal + solar return + transit tarzında kapsamlı, bölümlere ayrılmış bir astroloji raporu yaz. "
                "Kişilik, yaşam amacı, aşk & ilişkiler, kariyer, maddi konular, ruhsal gelişim ve önümüzdeki 12 ayın "
                "ana temalarını detaylı şekilde açıkla."
            )
        else:
            user_prompt = (
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\nFocus areas: {', '.join(focus) or 'General'}\n"
                f"Question / intention: {question}\n\n"
                "Write a structured astrology report in the style of natal + solar return + transits. "
                "Explain personality, life purpose, love & relationships, career, money, spiritual growth "
                "and the key themes for the next 12 months."
            )

        # ---- Metin raporu ----
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900
        )

        text = completion.choices[0].message.content.strip()

        # ---- Harita görseli ----
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
# (İstersen kalsın) PREMIUM ASTROLOGY
# Aynı mantık, biraz daha spiritüel / uzun yorum için kullanılabilir.
# Frontend şu an bunu KULLANMIYOR, sadece /astrology kullanıyor.
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

        # Aynı chart üretimi
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
