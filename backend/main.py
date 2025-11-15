from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
from langdetect import detect, LangDetectException
import os
import traceback
import uuid
import base64

app = Flask(__name__)
CORS(app)

# ENV'den API KEY oku
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_KEY:
    raise Exception("OPENAI_API_KEY bulunamadı!")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)


@app.route("/")
def home():
    return "MystAI backend is running! 🔮"


def build_system_prompt(reading_type: str, lang: str) -> str:
    """
    Fal / astroloji türüne göre profesyonel sistem mesajı üretir.
    reading_type: 'coffee', 'tarot', 'palm', 'energy', 'astrology', 'general'
    lang: 'tr' ya da 'en'
    """
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, sıcak ve profesyonel bir fal ve astroloji yorumcusun. "
            "Kullanıcıya asla korkutucu veya umutsuz mesajlar verme. "
            "Gerçekçi ama pozitif, yol gösterici ve sakin bir tonda konuş. "
            "Her zaman kullanıcıyı güçlendiren, sorumluluğu eline almasını teşvik eden bir anlatım kullan. "
        )
        types = {
            "coffee": (
                base +
                "Kahve falı uzmanısın. Fincandaki şekilleri, sembolleri ve enerjiyi hissedip "
                "ilişkiler, kariyer, gelecek fırsatlar ve ruhsal mesajlar hakkında detaylı yorumlar yap."
            ),
            "tarot": (
                base +
                "Tarot ustasısın. Kartların arketiplerini, sayıları ve enerjilerini yorumlayarak "
                "kullanıcıya hem spiritüel hem de pratik rehberlik ver."
            ),
            "palm": (
                base +
                "El falı (palmistry) uzmanısın. Yaşam çizgisi, akıl çizgisi, kalp çizgisi ve diğer işaretleri "
                "yorumlayarak karakter, hayat yolu ve potansiyel deneyimler hakkında konuş."
            ),
            "energy": (
                base +
                "Rüyalar ve enerji sembolleri üzerinde çalışan sezgisel bir yorumcusun. "
                "Sembolleri, duyguları ve bilinçdışı mesajları analiz edip, içsel denge ve farkındalık için rehberlik ver."
            ),
            "astrology": (
                base +
                "Profesyonel bir doğum haritası ve transit yorumcusun. "
                "Natal haritayı, gezegenleri, burçları, evleri ve açıları kullanarak; "
                "kişilik, yaşam amacı, aşk ve ilişkiler, kariyer ve para, ruhsal gelişim, karmik temalar ve "
                "önümüzdeki dönem için astrolojik etkiler hakkında detaylı ve anlaşılır bir rapor yazarsın. "
                "Teknik terimleri basit ve günlük dile çevir, kullanıcıyı korkutma; her zorlu göstergeyi bile "
                "\"büyüme fırsatı\" şeklinde yorumla."
            ),
            "general": (
                base +
                "Genel bir mistik fal yorumcususun. Kullanıcının sorusuna göre aşk, kariyer, para, "
                "sağlık, ruhsal yol ve kader hakkında sezgisel yorumlar yap."
            ),
        }
    else:
        base = (
            "You are MystAI, a mystical, warm and professional fortune and astrology interpreter. "
            "Never give scary or hopeless messages. Be realistic but positive, supportive and calm. "
            "Always empower the user and frame challenges as opportunities for growth. "
        )
        types = {
            "coffee": (
                base +
                "You are an expert in coffee cup readings. You interpret shapes, symbols and energy in the cup, "
                "giving insights about relationships, career, future opportunities and spiritual messages."
            ),
            "tarot": (
                base +
                "You are a tarot master. You interpret archetypes, numbers and energies of the cards, "
                "offering both spiritual and practical guidance."
            ),
            "palm": (
                base +
                "You are a palm reading expert. You interpret life line, head line, heart line and other marks "
                "to talk about personality, life path and potential experiences."
            ),
            "energy": (
                base +
                "You are an oracle for dreams and subtle energies. You interpret symbols, emotions and subconscious messages "
                "to help with inner balance and awareness."
            ),
            "astrology": (
                base +
                "You are a professional astrologer. You interpret natal charts, houses, planets, aspects and transits "
                "to describe personality, life purpose, love and relationships, career and money, spiritual lessons "
                "and upcoming trends. Explain any technical terms in simple language."
            ),
            "general": (
                base +
                "You are a general mystical fortune teller. According to the user's question, "
                "you speak about love, career, money, health, spiritual path and destiny."
            ),
        }

    return types.get(reading_type, types["general"])


@app.route("/predict", methods=["POST"])
def predict():
    """
    Kahve / tarot / el falı / enerji & rüyalar için genel uç nokta.
    Frontend 'reading_type' gönderiyorsa ona göre sistem prompt seçilir.
    """
    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "") or ""
        reading_type = (data.get("reading_type") or "general").lower()

        if not user_input.strip():
            return jsonify({"error": "user_input boş olamaz"}), 400

        print("=== /predict Kullanıcı girişi:", user_input)
        print("=== Fal türü:", reading_type)

        # Dil tespiti
        try:
            detected = detect(user_input)
            print("=== Tespit edilen dil:", detected)
        except LangDetectException:
            detected = "en"

        if detected not in ("en", "tr"):
            detected = "en"

        valid_types = {"coffee", "tarot", "palm", "energy", "astrology", "general"}
        if reading_type not in valid_types:
            reading_type = "general"

        system_prompt = build_system_prompt(reading_type, detected)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )

        response_text = completion.choices[0].message.content.strip()

        # gTTS ile ses
        file_id = uuid.uuid4().hex
        audio_filename = f"{file_id}.mp3"
        audio_path = os.path.join("/tmp", audio_filename)

        tts = gTTS(text=response_text, lang=detected)
        tts.save(audio_path)

        return jsonify(
            {
                "text": response_text,
                "audio": f"/audio/{file_id}",
                "reading_type": reading_type,
                "language": detected,
            }
        )

    except Exception as e:
        print("=== /predict HATA ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/astrology", methods=["POST"])
def astrology():
    """
    Otomatik astroloji raporu + OpenAI ile çizilmiş doğum haritası PNG.
    Frontend JSON gönderir:
    {
      "birth_date": "1978-11-06",
      "birth_time": "13:40",
      "birth_place": "Izmir, Turkey",
      "name": "Mystic Soul",
      "focus_areas": ["love", "career"],
      "question": "Bu yıl aşk ve kariyerim nasıl etkilenir?",
      "language": "tr"  # opsiyonel: "tr" veya "en"
    }
    """
    try:
        data = request.get_json() or {}

        birth_date = (data.get("birth_date") or "").strip()
        birth_time = (data.get("birth_time") or "").strip()
        birth_place = (data.get("birth_place") or "").strip()
        name = (data.get("name") or "").strip()
        focus_areas = data.get("focus_areas") or []
        question = (data.get("question") or "").strip()
        forced_lang = (data.get("language") or "").lower()

        if not birth_date or not birth_time or not birth_place:
            return jsonify({"error": "birth_date, birth_time ve birth_place zorunludur."}), 400

        # Dil tespiti: önce parametre, yoksa sorudan / isimden
        if forced_lang in ("tr", "en"):
            detected = forced_lang
        else:
            sample_text = " ".join([question, name, birth_place]).strip() or question or "test"
            try:
                detected = detect(sample_text)
            except LangDetectException:
                detected = "en"
        if detected not in ("tr", "en"):
            detected = "en"

        print("=== /astrology dil:", detected)

        system_prompt = build_system_prompt("astrology", detected)

        # Kullanıcıya özel metin (model için)
        if detected == "tr":
            focus_text = ", ".join(focus_areas) if focus_areas else "genel yaşam temaları"
            user_prompt = (
                f"Doğum tarihi: {birth_date}\n"
                f"Doğum saati: {birth_time}\n"
                f"Doğum yeri: {birth_place}\n"
                f"İsim (opsiyonel): {name or 'Belirtilmedi'}\n"
                f"Odaklanmak istediği alanlar: {focus_text}\n"
                f"Özel soru / niyet: {question or 'Belirtilmedi'}\n\n"
                "Lütfen kullanıcının natal haritasını, yaşam temasını, aşk/ilişkiler, kariyer/para, "
                "ruhsal gelişim ve karmik dersler başlıklarıyla detaylı ama okunaklı bir şekilde yorumla. "
                "Son bölümde bu yılki genel gökyüzü etkilerini (solar return + transit temaları gibi) "
                "yumuşak bir dille özetle."
            )
        else:
            focus_text = ", ".join(focus_areas) if focus_areas else "general life themes"
            user_prompt = (
                f"Birth date: {birth_date}\n"
                f"Birth time: {birth_time}\n"
                f"Birth place: {birth_place}\n"
                f"Name (optional): {name or 'Not provided'}\n"
                f"Focus areas: {focus_text}\n"
                f"Question / intention: {question or 'Not provided'}\n\n"
                "Please interpret the natal chart with sections for personality, life purpose, "
                "love & relationships, career & money, spiritual growth and karmic lessons. "
                "At the end, add a short forecast for the coming year based on symbolic solar return "
                "and transits, in a gentle, encouraging tone."
            )

        # Metin yorumu
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        report_text = completion.choices[0].message.content.strip()

        # Ses dosyası
        audio_id = uuid.uuid4().hex
        audio_filename = f"{audio_id}.mp3"
        audio_path = os.path.join("/tmp", audio_filename)
        tts = gTTS(text=report_text, lang=detected)
        tts.save(audio_path)

        # Doğum haritası görseli (OpenAI image)
        # Not: Bu sembolik, artistik bir natal chart çizimidir; gerçek astronomik hesap yapmaz.
        if detected == "tr":
            img_prompt = (
                "Profesyonel, yüksek çözünürlüklü bir astroloji doğum haritası çiz. "
                "Koyu lacivert uzay arka planı, altın detaylar, dairesel natal chart, "
                "12 ev, burç sembolleri, gezegen ikonları, ince çizgilerle açılar. "
                "MystAI markasına uygun, modern ve mistik bir tasarım."
            )
        else:
            img_prompt = (
                "A professional high-resolution natal astrology chart wheel. "
                "Dark blue cosmic background, golden details, circular chart with 12 houses, "
                "zodiac signs and planet symbols, elegant aspect lines. "
                "Modern, mystical design that fits a premium fortune-telling website."
            )

        image_resp = client.images.generate(
            model="gpt-image-1",
            prompt=img_prompt,
            size="1024x1024"
        )
        image_b64 = image_resp.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        chart_id = uuid.uuid4().hex
        chart_filename = f"{chart_id}.png"
        chart_path = os.path.join("/tmp", chart_filename)
        with open(chart_path, "wb") as f:
            f.write(image_bytes)

        return jsonify(
            {
                "text": report_text,
                "audio": f"/audio/{audio_id}",
                "chart": f"/chart/{chart_id}",
                "language": detected,
            }
        )

    except Exception as e:
        print("=== /astrology HATA ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/audio/<file_id>")
def serve_audio(file_id):
    """
    /audio/<file_id> -> /tmp/<file_id>.mp3 dosyasını döner.
    """
    filename = f"{file_id}.mp3"
    filepath = os.path.join("/tmp", filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(filepath, mimetype="audio/mpeg")


@app.route("/chart/<chart_id>")
def serve_chart(chart_id):
    """
    /chart/<chart_id> -> /tmp/<chart_id>.png dosyasını döner.
    """
    filename = f"{chart_id}.png"
    filepath = os.path.join("/tmp", filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Chart not found"}), 404
    return send_file(filepath, mimetype="image/png")


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test message"}],
        )
        return "OpenAI OK -> " + r.choices[0].message.content
    except Exception as e:
        return "OpenAI ERROR -> " + str(e)


if __name__ == "__main__":
    # Lokal çalıştırma için
    app.run(host="0.0.0.0", port=10000)
