# ============================================
# MystAI - Premium Astrology Backend (FINAL)
# - TR & EN iki dilli
# - Premium uzun rapor (20+ sayfa içerik kapasitesi)
# - Kişiye özel AI natal chart görseli
# - Dark Blue Premium PDF tasarımı (kapak + header + footer)
# - Render uyumlu
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
from fpdf import FPDF   # fpdf2 ile uyumlu

# -----------------------------
# Flask App & CORS
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
def home():
    return "MystAI Backend Running 🔮"


# -----------------------------
# SYSTEM PROMPTS
# -----------------------------
def build_system_prompt(type_name: str, lang: str) -> str:
    """
    type_name: "general" | "astrology"
    lang: "tr" | "en"
    """
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, profesyonel ve derin sezgilere sahip bir yorumcusun. "
            "Kullanıcıya güçlü, pozitif, anlaşılır ve gerçekçi açıklamalar yaparsın. "
            "Astroloji bilgisini psikolojik derinlikle birleştirirsin."
        )
        types = {
            "general": base + " Genel rehberlik, sezgisel ve destekleyici yorumlar yap.",
            "astrology": base + " Doğum haritasını gezegenler, evler ve açılar üzerinden derinlemesine yorumla."
        }
    else:
        base = (
            "You are MystAI, a mystical, professional and deeply intuitive interpreter. "
            "You speak with warmth, clarity and psychological depth. "
            "You combine astrology with practical and emotional insight."
        )
        types = {
            "general": base + " Provide general guidance in a supportive tone.",
            "astrology": base + " Provide deep natal chart interpretation using planets, houses and aspects."
        }

    return types.get(type_name, types["general"])


# -----------------------------
# PDF CLASS (Dark Blue Premium)
# -----------------------------
class MystAIPDF(FPDF):
    def __init__(self, language="tr", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        # Dark blue banner
        self.set_fill_color(10, 18, 40)  # koyu lacivert
        self.rect(0, 0, self.w, 18, "F")

        # Gold text
        self.set_text_color(255, 215, 0)  # altın sarısı
        self.set_font("Arial", "B", 12)
        title = (
            "MystAI Premium Astroloji Raporu"
            if self.language == "tr"
            else "MystAI Premium Astrology Report"
        )
        self.set_y(5)
        self.cell(0, 8, title, align="C")
        self.ln(10)

        # Normal metin rengine dön
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_text_color(120, 120, 120)
        self.set_font("Arial", "I", 8)
        if self.language == "tr":
            page_str = f"Sayfa {self.page_no()}"
        else:
            page_str = f"Page {self.page_no()}"
        self.cell(0, 10, page_str, align="C")


# -----------------------------
# /predict – Genel fal / yorum
# -----------------------------
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        user_input = data.get("user_input", "").strip()
        language = (data.get("language") or "").lower().strip()

        if not user_input:
            return jsonify({"error": "user_input boş olamaz"}), 400

        # Dil seçimi: öncelik kullanıcı seçimi, yoksa otomatik tespit
        if language not in ("tr", "en"):
            try:
                detected = detect(user_input)
                language = "tr" if detected == "tr" else "en"
            except Exception:
                language = "en"

        system_prompt = build_system_prompt("general", language)

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
        gTTS(text=text, lang="tr" if language == "tr" else "en").save(audio_path)

        return jsonify({
            "text": text,
            "audio": f"/audio/{audio_id}",
            "language": language
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# /astrology – basit versiyon
# -----------------------------
@app.route("/astrology", methods=["POST"])
def astrology():
    """
    Basit astroloji endpoint'i – istersen daha sonra detaylandırırsın.
    Premium için /astrology-premium kullanılıyor.
    """
    try:
        data = request.json or {}
        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        text = f"Temel astroloji endpoint'i aktif.\nDoğum: {birth_date} {birth_time} - {birth_place}"
        return jsonify({"text": text, "chart": None})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# /astrology-premium – Kişiye özel harita + uzun rapor
# =====================================================
@app.route("/astrology-premium", methods=["POST"])
def astrology_premium():
    try:
        data = request.json or {}

        birth_date = data.get("birth_date")
        birth_time = data.get("birth_time")
        birth_place = data.get("birth_place")
        name = data.get("name", "")
        language = (data.get("language") or "").lower().strip()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "Eksik bilgi"}), 400

        # Dil: kullanıcı seçimi yoksa tahmin et, en kötü en'e düş
        if language not in ("tr", "en"):
            try:
                detected = detect(birth_place)
                language = "tr" if detected == "tr" else "en"
            except Exception:
                language = "en"

        system_prompt = build_system_prompt("astrology", language)

        # ---------------- PREMIUM PROMPT (TR / EN) ----------------
        if language == "tr":
            user_prompt = f"""
Aşağıdaki doğum bilgilerine göre, ücretli bir danışmanlıkta verilebilecek kalitede,
çok uzun ve detaylı bir Premium Astroloji Raporu yaz.

Doğum Bilgileri:
- İsim: {name}
- Doğum Tarihi: {birth_date}
- Doğum Saati: {birth_time}
- Doğum Yeri: {birth_place}

Raporun profesyonel bir astrolog tarafından yazılmış gibi olması gerekiyor.
Aşağıdaki bölümleri mutlaka ve net başlıklarla işle:

1. Giriş ve Genel Enerji
2. Güneş Burcu (kişilik, egonun yapısı, hayata bakış)
3. Ay Burcu (duygular, iç dünya, çocukluk izleri)
4. Yükselen Burç (hayata yaklaşım, dış imaj, ilk izlenim)
5. Merkür, Venüs, Mars, Jüpiter, Satürn, Uranüs, Neptün ve Pluto'nun burçlardaki konumları
6. 1'den 12'ye kadar evlerin temaları ve bu evlerdeki gezegenlerin olası etkileri
7. En az 10 önemli açı (konjonksiyon, kare, karşıt, üçgen, sekstil) ve bunların psikolojik anlamları
8. Aşk ve İlişkiler (romantik ilişkiler, bağlanma tarzı, partner seçimleri)
9. Kariyer, İş Hayatı ve Yaşam Amacı
10. Para, bolluk ve maddi potansiyel
11. Karmik dersler, tekrar eden temalar ve ruhsal gelişim
12. Sonuç ve danışana özel motive edici kapanış mesajı

Dili:
- Sıcakkanlı, anlaşılır ama profesyonel olsun.
- Cümleler çok yüzeysel olmasın; derinlikli ve açıklayıcı olsun.
- Gerektiğinde paragraf içinde örnekler ver.
- Bölümler arasında akıcı geçişler kullan.
"""
        else:
            user_prompt = f"""
Based on the birth data below, write a very long, in-depth and professional
Premium Natal Astrology Report, as if written by an experienced astrologer.

Birth Data:
- Name: {name}
- Date of birth: {birth_date}
- Time of birth: {birth_time}
- Place of birth: {birth_place}

The report should be structured and detailed. Please include at least the following sections
with clear headings:

1. Introduction and overall life energy
2. Sun sign (core personality, ego, life force)
3. Moon sign (emotional nature, inner world, childhood imprints)
4. Rising sign / Ascendant (approach to life, outer persona, first impression)
5. Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune and Pluto in signs
6. Houses 1 to 12 and the main themes of planets in those houses
7. At least 10 important aspects (conjunctions, squares, oppositions, trines, sextiles)
   and their psychological meaning
8. Love & Relationships (romantic style, attachment, what they seek in a partner)
9. Career, Vocation and Life Purpose
10. Money, abundance and material potential
11. Karmic lessons, repeating themes and soul growth
12. Final conclusion and an empowering closing message directly to the client

Tone:
- Warm, empathetic, but professional.
- Avoid being too generic; make it feel personal and specific.
- Use clear, flowing paragraphs, with rich explanations and examples.
"""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3000,
        )

        text = completion.choices[0].message.content.strip()

        # ---------------- KİŞİYE ÖZEL HARİTA GÖRSELİ ----------------
        if language == "tr":
            img_prompt = (
                "Koyu lacivert arka plan üzerinde, altın detaylı, profesyonel bir doğum haritası çarkı. "
                "Gezegen sembolleri, burç sembolleri ve 12 ev çizgisi net şekilde görünüyor. "
                "Lüks, mistik ve premium bir görünüm."
            )
        else:
            img_prompt = (
                "High-end professional natal astrology chart wheel on a dark navy background, "
                "with golden lines, clear planet symbols, zodiac signs and 12 house divisions. "
                "Luxurious, mystical and premium look."
            )

        img = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024"
        )

        b64 = img.data[0].b64_json
        img_bytes = base64.b64decode(b64)

        chart_id = uuid.uuid4().hex
        chart_path = f"/tmp/{chart_id}.png"
        with open(chart_path, "wb") as f:
            f.write(img_bytes)

        return jsonify({
            "text": text,
            "chart_id": chart_id,
            "chart": f"/chart/{chart_id}",
            "language": language
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================
# /generate_pdf – Haritalı, Dark Blue Premium PDF
# =====================================================
@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()
        chart_id = data.get("chart_id")
        language = (data.get("language") or "tr").lower().strip()

        if not text:
            return jsonify({"error": "Metin yok"}), 400

        if language not in ("tr", "en"):
            language = "tr"

        pdf_id = uuid.uuid4().hex
        pdf_path = f"/tmp/{pdf_id}.pdf"

        pdf = MystAIPDF(language=language)
        pdf.alias_nb_pages()
        pdf.add_page()

        # ---------- KAPAK SAYFASI: HARİTA + BAŞLIKLAR ----------
        # Header zaten çizildi (Dark blue bar)
        # Haritayı ortaya yerleştir
        if chart_id:
            chart_path = f"/tmp/{chart_id}.png"
            if os.path.exists(chart_path):
                # sayfanın ortasına yakın konumlandır
                chart_width = 120
                x = (pdf.w - chart_width) / 2
                y = 25
                pdf.image(chart_path, x=x, y=y, w=chart_width)
                pdf.set_y(y + chart_width + 10)
            else:
                pdf.ln(40)
        else:
            pdf.ln(40)

        # Kapak metinleri
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(10, 18, 40)  # koyu lacivert

        if language == "tr":
            main_title = "Kişiye Özel Doğum Haritası Analizi"
            sub_title = "MystAI Premium Astroloji Raporu"
        else:
            main_title = "Personal Natal Chart Analysis"
            sub_title = "MystAI Premium Astrology Report"

        pdf.cell(0, 10, main_title, ln=True, align="C")
        pdf.set_font("Arial", "", 14)
        pdf.set_text_color(60, 60, 60)
        pdf.ln(3)
        pdf.cell(0, 8, sub_title, ln=True, align="C")

        # Biraz boşluk bırak
        pdf.ln(10)

        # Kapak sayfasını burada bırak, yeni sayfada içerik
        pdf.add_page()
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", size=12)

        # ---------- METNİ SAYFALARA YAY ----------
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue

            # Basit başlık algısı: satır çok kısa ve sonunda ":" varsa bold yap
            if len(line) < 80 and (line.endswith(":") or line.isupper()):
                pdf.set_font("Arial", "B", 12)
                pdf.multi_cell(0, 8, line)
                pdf.ln(1)
                pdf.set_font("Arial", "", 12)
            else:
                pdf.multi_cell(0, 8, line)
                pdf.ln(1)

        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True, download_name="mystai_premium_report.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# Static File Endpoints
# -----------------------------
@app.route("/chart/<id>")
def serve_chart(id):
    path = f"/tmp/{id}.png"
    if not os.path.exists(path):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(path, mimetype="image/png")


@app.route("/audio/<id>")
def serve_audio(id):
    path = f"/tmp/{id}.mp3"
    if not os.path.exists(path):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(path, mimetype="audio/mpeg")


# -----------------------------
# Health Check
# -----------------------------
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


# -----------------------------
# Run (Render Uyumlu)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
