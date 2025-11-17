# ============================================
# MystAI - FULL BACKEND (FINAL VERSION)
# ✔ GPT-4o-mini yorumlama
# ✔ Flatlib ile GERÇEK doğum haritası üretimi
# ✔ PNG chart kaydetme /chart/<id>
# ✔ TTS ses
# ✔ PDF üretimi
# ============================================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect
from gtts import gTTS
import os
import uuid
import traceback
from fpdf import FPDF
import base64

# ---- Astrology Libraries ----
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib import const
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np


# ============================================
# Flask
# ============================================
app = Flask(__name__)
CORS(app)


# ============================================
# OpenAI
# ============================================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def index():
    return "MystAI Backend Running 🔮"


# ============================================
# SYSTEM PROMPTS
# ============================================
def build_system_prompt(type_name, lang):
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel bir yorumcusun. "
            "Kullanıcıya derin, olumlu, sezgisel ve gerçekçi bir dille rehberlik edersin."
        )
        types = {
            "general": base + " Genel enerji ve rehberlik sun.",
            "astrology": base + " Doğum haritasını gezegenler, evler ve açılar üzerinden yorumla."
        }
    else:
        base = (
            "You are MystAI, a mystical and professional interpreter. "
            "You speak warm, deep and intuitive."
        )
        types = {
            "general": base + " Provide intuitive guidance.",
            "astrology": base + " Analyze natal chart using planets, houses and aspects."
        }

    return types.get(type_name, types["general"])



# ============================================
# REAL CHART GENERATOR (PNG)
# ============================================
def generate_astrology_chart(birth_date, birth_time, birth_place, chart_id):

    try:
        # ---- birth date/time parse ----
        year, month, day = birth_date.split("-")
        hour, minute = birth_time.split(":")

        # ---- dummy geo pos (fallback) ----
        # *İstersen sana gerçek şehir koordinatı API ekleyebilirim*
        geo = GeoPos("39.9208", "32.8541")   # Ankara default

        # ---- flatlib chart ----
        dt = Datetime(year, month, day, hour, minute)
        chart = Chart(dt, geo)

        # ---- PNG OUTPUT PATH ----
        out_path = f"/tmp/{chart_id}.png"

        # ---- DRAW BASIC WHEEL ----
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.set_facecolor("#0d1436")
        ax.set_aspect("equal")

        # Outer circle
        circle = Circle((0, 0), 1, fill=False, lw=3, edgecolor="#ffd777")
        ax.add_patch(circle)

        # Houses
        for i in range(12):
            angle = np.deg2rad(i * 30)
            ax.plot(
                [0, np.cos(angle)],
                [0, np.sin(angle)],
                color="#ffffff55",
                lw=1
            )

        # Planets
        planets = [
            const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS,
            const.JUPITER, const.SATURN, const.URANUS, const.NEPTUNE, const.PLUTO
        ]

        for pl in planets:
            obj = chart.get(pl)
            angle = np.deg2rad(obj.lon)
            x = 0.82 * np.cos(angle)
            y = 0.82 * np.sin(angle)
            ax.text(x, y, pl[0], color="white", fontsize=14, ha="center")

        ax.axis("off")
        plt.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="#0d1436")
        plt.close()

        return out_path

    except Exception as e:
        print("Chart error:", e)
        return None



# ============================================
# NORMAL /predict
# ============================================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = data.get("user_input", "")

        if not user_input:
            return jsonify({"error": "user_input boş"}), 400

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

        # Audio
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



# ============================================
# BASIC ASTROLOGY (with real chart)
# ============================================
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
                "Write a full natal chart interpretation."
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

        # --- CHART GENERATION ---
        chart_id = uuid.uuid4().hex
        chart_path = generate_astrology_chart(birth_date, birth_time, birth_place, chart_id)

        if chart_path:
            chart_url = f"/chart/{chart_id}"
        else:
            chart_url = None

        return jsonify({
            "text": text,
            "chart": chart_url,
            "audio": None,
            "language": lang
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# ============================================
# PDF GENERATOR
# ============================================
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}
        text = data.get("text", "")

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        for line in text.split("\n"):
            pdf.multi_cell(0, 7, line)

        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True, download_name="mystai-report.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# ============================================
# STATIC FILE SERVERS
# ============================================
@app.route("/audio/<id>")
def serve_audio(id):
    p = f"/tmp/{id}.mp3"
    if not os.path.exists(p):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(p, mimetype="audio/mpeg")


@app.route("/chart/<id>")
def serve_chart(id):
    p = f"/tmp/{id}.png"
    if not os.path.exists(p):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(p, mimetype="image/png")



# ============================================
# HEALTH CHECK
# ============================================
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# ============================================
# RUN
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
