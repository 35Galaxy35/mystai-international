from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from langdetect import detect, LangDetectException
from gtts import gTTS
import os
import traceback
import uuid

app = Flask(__name__)

# ========= CORS AYARLARI =========
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

# ENV'den API KEY oku
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


# === Sistem prompt oluşturucu ===
def build_system_prompt(reading_type: str, lang: str) -> str:
    """
    reading_type:
      - 'general' : Ask MystAI, kahve/tarot vb. genel yorumlar
      - 'astrology': Astroloji raporu için
    """
    if lang == "tr":
        base_general = (
            "Sen MystAI adında mistik, sıcak ve profesyonel bir fal yorumcusun. "
            "Kullanıcıya asla korkutucu veya umutsuz mesajlar verme. "
            "Gerçekçi ama pozitif, yol gösterici ve sakin bir tonda konuş. "
            "Kullanıcının kendi iradesini ve özgür seçimlerini her zaman onurlandır."
        )
        base_astro = (
            "Sen MystAI adında çok deneyimli, mistik ama aynı zamanda profesyonel bir astroloji yorumcusun. "
            "Astrolojiyi KESİNLİK gibi değil, sembolik bir dil ve rehberlik aracı olarak anlatırsın. "
            "Kullanıcıyı asla korkutmaz, kaderini eline almasını teşvik eder, zor etkileri bile "
            "büyüme fırsatı olarak yorumlarsın. "
        )

        if reading_type == "astrology":
            return (
                base_astro
                + "Doğum haritasını (natal chart) analiz ederken şu başlıkları mutlaka kullan:\n\n"
                "1) Genel Astrolojik Profil ve Enerji Teması\n"
                "2) Yaşam Amacı & Ruhsal Yol (Güneş, Ay, Yükselen ve önemli açılar üzerinden)\n"
                "3) Aşk, İlişkiler ve Evlilik Potansiyeli\n"
                "4) Para, İş ve Kariyer Dinamikleri\n"
                "5) Karmik Dersler, Şifalanma Alanları ve Ruhsal Gelişim\n"
                "6) 12 Ev Üzerinden Kısa Bir Akış (her evi tek tek değil, tema tema, okunaklı bir şekilde)\n"
                "7) Önümüzdeki Yaklaşık 12 Ay İçin Genel Gökyüzü Etkileri (solar return ve transit temaları, "
                "tahmin değil, eğilim ve atmosfer olarak anlat)\n\n"
                "Dil tarzın: anlaşılır, akıcı, samimi ama profesyonel. Maddeler ve paragraflar halinde yaz, "
                "çok uzun cümleler kurma. Astrolojik terimleri kullansan bile mutlaka günlük dile çevir."
            )
        else:
            return base_general

    else:
        base_general = (
            "You are MystAI, a mystical, warm and professional oracle. "
            "You never give scary, fatalistic or hopeless messages. "
            "You are realistic but positive, soothing and empowering."
        )
        base_astro = (
            "You are MystAI, a very experienced, mystical yet professional astrologer. "
            "You present astrology not as rigid fate but as a symbolic language and a tool for reflection. "
            "You always empower the user and frame difficult indicators as opportunities for growth."
        )

        if reading_type == "astrology":
            return (
                base_astro
                + "When interpreting the natal chart, always structure your reading with these sections:\n\n"
                "1) Overall Astrological Profile & Main Energy\n"
                "2) Life Purpose & Soul Path (via Sun, Moon, Ascendant and key aspects)\n"
                "3) Love, Relationships & Partnership Potential\n"
                "4) Money, Work & Career Dynamics\n"
                "5) Karmic Lessons, Healing Themes & Spiritual Growth\n"
                "6) A Short Walk Through the 12 Houses (grouped in themes, not dry technical listing)\n"
                "7) A Gentle Forecast for the Next ~12 Months (solar return & transits as trends, not fixed events)\n\n"
                "Write in clear, human-friendly language with paragraphs and some bullet-like sections. "
                "Avoid doom, fear or rigid predictions; speak in terms of tendencies, potentials and advice."
            )
        else:
            return base_general


# ========= /predict =========
# (Kahve, tarot vb. için genel uç nokta – SESLİ cevap devam ediyor!)
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "").strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        try:
            detected = detect(user_input)
        except LangDetectException:
            detected = "en"

        if detected not in ("tr", "en"):
            detected = "en"

        system_prompt = build_system_prompt("general", detected)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            max_tokens=600,
        )

        response_text = completion.choices[0].message.content.strip()

        # Ses oluştur (DİĞER FALAR İÇİN)
        file_id = uuid.uuid4().hex
        audio_path = f"/tmp/{file_id}.mp3"
        try:
            tts = gTTS(text=response_text, lang=detected)
            tts.save(audio_path)
            audio_url = f"/audio/{file_id}"
        except Exception as tts_err:
            print("gTTS hata:", tts_err)
            audio_url = None

        return jsonify(
            {
                "text": response_text,
                "audio": audio_url,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= /astrology =========
# (SADECE METİN – SES YOK, CHART ŞİMDİLİK YOK, UZUN PRO RAPOR)
@app.route("/astrology", methods=["POST"])
def astrology():
    """
    Astroloji raporu – uzun ve profesyonel yorum.
    Sadece METİN döner (audio yok, chart yok).
    """
    try:
        data = request.get_json() or {}

        birth_date = (data.get("birth_date") or "").strip()
        birth_time = (data.get("birth_time") or "").strip()
        birth_place = (data.get("birth_place") or "").strip()
        name = (data.get("name") or "").strip()
        focus_areas = data.get("focus_areas") or []
        question = (data.get("question") or "").strip()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi: birth_date, birth_time, birth_place zorunlu."}), 400

        # Dil tespiti
        sample_text = " ".join([birth_place, name, question]).strip() or "test"
        try:
            detected = detect(sample_text)
        except LangDetectException:
            detected = "en"

        if detected not in ("tr", "en"):
            detected = "en"

        print("=== /astrology dil:", detected)

        # Sistem prompt
        system_prompt = build_system_prompt("astrology", detected)

        # Kullanıcı prompt – daha detaylı / yönlendirmeli
        if detected == "tr":
            focus_text = ", ".join(focus_areas) if focus_areas else "genel yaşam temaları"
            user_prompt = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim: {name or 'Belirtilmedi'}\n"
                f"Odaklanmak istediği alanlar: {focus_text}\n"
                f"Kullanıcının sorusu / niyeti: {question or 'Belirtilmedi'}\n\n"
                "Yukarıdaki bilgilere göre kapsamlı ama okunaklı bir astroloji raporu yaz. "
                "Mutlaka şu başlıklar olsun ve başlıkları belirgin yap:\n"
                "1) Genel Astrolojik Profil ve Enerji Teması\n"
                "2) Yaşam Amacı & Ruhsal Yol\n"
                "3) Aşk, İlişkiler ve Evlilik\n"
                "4) Para, İş ve Kariyer Dinamikleri\n"
                "5) Karmik Dersler ve Ruhsal Gelişim\n"
                "6) 12 Ev Üzerinden Temalar\n"
                "7) Önümüzdeki 12 Ay İçin Genel Gökyüzü Eğilimleri\n\n"
                "Cümlelerin akıcı olsun, teknik terimleri açıklamayı unutma. "
                "Kesin tahminler verme, olasılıklar ve eğilimler üzerinden konuş."
            )
        else:
            focus_text = ", ".join(focus_areas) if focus_areas else "general life themes"
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name: {name or 'Not provided'}\n"
                f"Focus areas requested: {focus_text}\n"
                f"User's question / intention: {question or 'Not provided'}\n\n"
                "Write a detailed but readable astrology report using these sections:\n"
                "1) Overall Astrological Profile & Energy\n"
                "2) Life Purpose & Soul Path\n"
                "3) Love, Relationships & Marriage\n"
                "4) Money, Work & Career\n"
                "5) Karmic Lessons & Spiritual Growth\n"
                "6) Themes through the 12 Houses\n"
                "7) General Sky Trends for the Next 12 Months\n\n"
                "Use warm, empowering language. Explain any technical terms briefly."
            )

        # OpenAI – daha uzun, ama timeout yemesin diye makul
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1800,
            temperature=0.9,
        )

        report_text = completion.choices[0].message.content.strip()
        print("Astroloji rapor uzunluğu:", len(report_text))

        # SADECE METİN – audio ve chart yok
        return jsonify(
            {
                "text": report_text,
                "audio": None,
                "chart": None,
                "language": detected,
            }
        )

    except Exception as e:
        print("=== /astrology HATA ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ========= Ses dosyası =========
@app.route("/audio/<file_id>")
def serve_audio(file_id):
    filename = f"/tmp/{file_id}.mp3"
    if not os.path.exists(filename):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(filename, mimetype="audio/mpeg")


# ========= Chart dosyası (şimdilik kullanılmıyor ama kalsın) =========
@app.route("/chart/<chart_id>")
def serve_chart(chart_id):
    filename = f"/tmp/{chart_id}.png"
    if not os.path.exists(filename):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(filename, mimetype="image/png")


# ========= Ping testi =========
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# ========= OpenAI bağlantı testi =========
@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )
        return "OK -> " + r.choices[0].message.content
    except Exception as e:
        return "OpenAI ERROR: " + str(e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
