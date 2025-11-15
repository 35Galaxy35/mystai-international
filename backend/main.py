from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
from langdetect import detect, LangDetectException
import os
import traceback
import uuid

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
    Fal türüne göre profesyonel sistem mesajı üretir.
    reading_type: 'coffee', 'tarot', 'palm', 'energy', 'general' vb.
    lang: 'tr' ya da 'en'
    """
    # Türkçe / İngilizce başlıklar
    if lang == "tr":
        base = (
            "Sen MystAI adında mistik, sıcak ve profesyonel bir fal yorumcusun. "
            "Kullanıcıya asla korkutucu veya umutsuz mesajlar verme. "
            "Gerçekçi ama pozitif, yol gösterici ve sakin bir tonda konuş. "
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
            "general": (
                base +
                "Genel bir mistik fal yorumcususun. Kullanıcının sorusuna göre aşk, kariyer, para, "
                "sağlık, ruhsal yol ve kader hakkında sezgisel yorumlar yap."
            ),
        }
    else:
        base = (
            "You are MystAI, a mystical, warm and professional fortune teller. "
            "Never give scary or hopeless messages. Be realistic but positive, "
            "supportive and calm. "
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
            "general": (
                base +
                "You are a general mystical fortune teller. According to the user's question, "
                "you speak about love, career, money, health, spiritual path and destiny."
            ),
        }

    return types.get(reading_type, types["general"])


@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json() or {}
        user_input = data.get("user_input", "") or ""
        reading_type = (data.get("reading_type") or "general").lower()

        if not user_input.strip():
            return jsonify({"error": "user_input boş olamaz"}), 400

        print("=== Kullanıcı girişi:", user_input)
        print("=== Fal türü:", reading_type)

        # Dil tespiti
        try:
            detected = detect(user_input)
            print("=== Tespit edilen dil:", detected)
        except LangDetectException:
            detected = "en"

        if detected not in ("en", "tr"):
            detected = "en"

        # Eğer front-end reading_type göndermediyse / garip bir şeyse:
        valid_types = {"coffee", "tarot", "palm", "energy", "general"}
        if reading_type not in valid_types:
            reading_type = "general"

        system_prompt = build_system_prompt(reading_type, detected)

        # OpenAI'den fal metni al
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )

        response_text = completion.choices[0].message.content.strip()

        # gTTS ile ses dosyası üret
        file_id = uuid.uuid4().hex
        filename = f"{file_id}.mp3"
        filepath = os.path.join("/tmp", filename)  # Render'da yazılabilir dizin

        tts = gTTS(text=response_text, lang=detected)
        tts.save(filepath)

        return jsonify(
            {
                "text": response_text,
                # Frontend için /audio/<id> şeklinde path dönüyoruz
                "audio": f"/audio/{file_id}",
                "reading_type": reading_type,
                "language": detected,
            }
        )

    except Exception as e:
        print("=== HATA OLUŞTU ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/audio/<file_id>")
def serve_audio(file_id):
    """
    /audio/<file_id> → /tmp/<file_id>.mp3 dosyasını döner.
    """
    filename = f"{file_id}.mp3"
    filepath = os.path.join("/tmp", filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(filepath, mimetype="audio/mpeg")

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
        return "OpenAI OK → " + r.choices[0].message.content

    except Exception as e:
        return "OpenAI ERROR → " + str(e)


if __name__ == "__main__":
    # Lokal çalıştırma için
    app.run(host="0.0.0.0", port=10000)
