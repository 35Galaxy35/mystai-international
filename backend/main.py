from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect, LangDetectException
from gtts import gTTS
import os
import traceback
import uuid
import base64

app = Flask(__name__)

# ========= CORS =========
CORS(
    app,
    resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

# ========= OpenAI Key =========
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


# ========= Sistem Prompt =========
def build_system_prompt(reading_type: str, lang: str) -> str:
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik ve profesyonel bir yorumcusun. "
            "Kullanıcıya pozitif, destekleyici ve gerçekçi bir dille rehberlik verirsin."
        )
        types = {
            "astrology": (
                base +
                " Doğum haritası, gezegenler, evler ve açılar üzerinden derin ve profesyonel bir astroloji yorumu yap."
            ),
            "general": base + " Genel bir fal ve enerji yorumcusun."
        }
    else:
        base = (
            "You are MystAI, a mystical and professional astrology and fortune interpreter. "
            "You speak warmly, positively and supportively."
        )
        types = {
            "astrology": (
                base +
                " Provide deep and structured natal chart interpretation using planets, houses and aspects."
            ),
            "general": base + " A general oracle and intuitive guide."
        }

    return types.get(reading_type, types["general"])


# ========= NORMAL /predict (kahve, tarot, el, enerji) =========
@app.route("/predict", methods=["POST"])
def predict():
    """
    Kahve, tarot, enerji, el falı, normal sohbet.
    Çalışan eski sistem BOZULMADI.
    """
    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        # Dil tespiti
        try:
            detected = detect(user_input)
        except:
            detected = "en"
        if detected not in ("tr", "en"):
            detected = "en"

        # Sistem mesajı
        system_prompt = build_system_prompt("general", detected)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )
        text = completion.choices[0].message.content.strip()

        # Ses dosyası
        file_id = uuid.uuid4().hex
        audio_path = f"/tmp/{file_id}.mp3"
        tts = gTTS(text=text, lang=detected)
        tts.save(audio_path)

        return jsonify({"text": text, "audio": f"/audio/{file_id}"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= BASİT ASTROLOJİ /astrology (bozulmadı) =========
@app.route("/astrology", methods=["POST"])
def astrology():
    """
    Hızlı çalışan, basit astroloji raporu.
    Ses yok, chart yok.
    (ESKİ SİSTEMİN AYNISI)
    """
    try:
        data = request.get_json() or {}

        birth_date = data.get("birth_date", "").strip()
        birth_time = data.get("birth_time", "").strip()
        birth_place = data.get("birth_place", "").strip()
        name = data.get("name", "").strip()
        focus_areas = data.get("focus_areas", [])
        question = data.get("question", "").strip()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi."}), 400

        try:
            detected = detect(" ".join([birth_place, name, question]))
        except:
            detected = "en"
        if detected not in ("tr", "en"):
            detected = "en"

        system_prompt = build_system_prompt("astrology", detected)

        # Kullanıcı promptu
        if detected == "tr":
            user_prompt = (
                f"Doğum: {birth_date} {birth_time} - {birth_place}\n"
                f"İsim: {name}\n"
                f"Odak: {', '.join(focus_areas) if focus_areas else 'Genel'}\n"
                f"Soru: {question}\n"
                "Kapsamlı bir astroloji raporu yaz."
            )
        else:
            user_prompt = (
                f"Birth: {birth_date} {birth_time} - {birth_place}\n"
                f"Name: {name}\n"
                f"Focus: {', '.join(focus_areas) if focus_areas else 'General'}\n"
                f"Question: {question}\n"
                "Write a detailed astrology reading."
            )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=850,
        )

        report = completion.choices[0].message.content.strip()

        return jsonify({
            "text": report,
            "audio": None,
            "chart": None,
            "language": detected,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= PREMIUM ASTROLOJİ /astrology-premium =========
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    """
    Ultra Premium: Harita PNG + geniş rapor.
    """
    try:
        data = request.get_json() or {}

        birth_date = data.get("birth_date", "").strip()
        birth_time = data.get("birth_time", "").strip()
        birth_place = data.get("birth_place", "").strip()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        # Dil
        try:
            detected = detect(" ".join([birth_place]))
        except:
            detected = "en"
        if detected not in ("tr", "en"):
            detected = "en"

        # ==== 1) PREMIUM METİN ====
        system_prompt = build_system_prompt("astrology", detected)

        user_prompt = (
            f"Premium astroloji raporu hazırla.\n"
            f"Doğum tarihi: {birth_date}\n"
            f"Doğum saati: {birth_time}\n"
            f"Doğum yeri: {birth_place}\n\n"
            "Bölümler:\n"
            "- Kişilik özeti\n"
            "- Yaşam amacı\n"
            "- Aşk & ilişkiler\n"
            "- Kariyer & para\n"
            "- Karmik dersler\n"
            "- 12 ev analizi\n"
            "- Bu yılın yıldızname yorumu (solar return)\n"
        )

        comp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        premium_text = comp.choices[0].message.content.strip()

        # ==== 2) PREMIUM CHART PNG ====
        img_prompt = (
            "High-quality natal astrology chart wheel, 12 houses, planets, aspects, elegant golden lines, "
            "dark blue cosmic background."
        )

        image_resp = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024"
        )

        b64 = image_resp.data[0].b64_json
        img_data = base64.b64decode(b64)

        chart_id = uuid.uuid4().hex
        chart_path = f"/tmp/{chart_id}.png"
        with open(chart_path, "wb") as f:
            f.write(img_data)

        return jsonify({
            "text": premium_text,
            "chart": f"/chart/{chart_id}",
            "audio": None,
            "language": detected
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= FILE SERVERS =========
@app.route("/audio/<file_id>")
def serve_audio(file_id):
    path = f"/tmp/{file_id}.mp3"
    if not os.path.exists(path):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(path, mimetype="audio/mpeg")


@app.route("/chart/<chart_id>")
def serve_chart(chart_id):
    path = f"/tmp/{chart_id}.png"
    if not os.path.exists(path):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(path, mimetype="image/png")


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
