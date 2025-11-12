# MystAI Backend - AI Fortune System (EN/TR Bilingual)
# Developed for MystAI.ai by ChatGPT

from flask import Flask, request, jsonify
import openai
import os
from gtts import gTTS
from io import BytesIO
import base64
import langdetect

app = Flask(__name__)

# ✅ OpenAI API anahtarını GitHub Secrets'ta OPENAI_API_KEY olarak kaydetmelisin
openai.api_key = os.getenv("OPENAI_API_KEY")

def detect_language(text):
    """Kullanıcının yazdığı dilin Türkçe mi İngilizce mi olduğunu algılar"""
    try:
        lang = langdetect.detect(text)
        return "tr" if lang == "tr" else "en"
    except:
        return "en"

def generate_prompt(category, input_text, lang):
    """Dil ve fal türüne göre uygun prompt oluşturur"""
    if lang == "tr":
        prompts = {
            "coffee": f"Sen MystAI adında yapay zekâ destekli bir fal yorumcususun. Kahve falı bakıyorsun. Fincandaki sembolleri, şekilleri ve duygusal enerjileri mistik bir dille açıkla. Kullanıcının girdisi: {input_text}",
            "tarot": f"Sen MystAI adında mistik bir yapay zekâsın. Tarot kartlarını ruhsal, arketipsel ve zamansal bir şekilde yorumla. Kullanıcının girdiği bilgi: {input_text}",
            "palm": f"Sen MystAI adında bir el falı uzmanısın. Kullanıcının avuç içi çizgilerini karakter, kader ve enerji yönlerinden analiz et. Girdi: {input_text}",
            "dream": f"Sen MystAI adında bir rüya yorumcususun. Rüyadaki sembolleri, bilinçaltı temaları ve enerjileri çözümle. Girdi: {input_text}"
        }
    else:
        prompts = {
            "coffee": f"You are MystAI, an advanced AI fortune teller. Interpret the coffee cup’s symbols, shapes, and emotional energy with mystical depth. User input: {input_text}",
            "tarot": f"You are MystAI, a mystical AI tarot reader. Interpret the drawn tarot cards in terms of archetypes, guidance, and destiny. User input: {input_text}",
            "palm": f"You are MystAI, a spiritual AI palm reader. Analyze palm lines and patterns for life energy, destiny, and traits. User input: {input_text}",
            "dream": f"You are MystAI, an AI dream interpreter. Decode symbols and emotions hidden in dreams. User input: {input_text}"
        }
    return prompts.get(category, prompts["coffee"])

def generate_fortune_text(category, input_text, lang):
    """Yapay zekâdan fal yorumunu üretir"""
    prompt = generate_prompt(category, input_text, lang)
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message["content"]

def generate_audio(text, lang):
    """Fal yorumunun sesli halini oluşturur"""
    tts = gTTS(text=text, lang=lang)
    mp3_buffer = BytesIO()
    tts.write_to_fp(mp3_buffer)
    mp3_data = base64.b64encode(mp3_buffer.getvalue()).decode('utf-8')
    return mp3_data

@app.route("/api/fortune", methods=["POST"])
def fortune():
    data = request.get_json()
    category = data.get("category", "coffee").lower()
    user_input = data.get("input", "")

    lang = detect_language(user_input)
    fortune_text = generate_fortune_text(category, user_input, lang)
    audio_data = generate_audio(fortune_text, lang)

    return jsonify({
        "fortune_text": fortune_text,
        "audio_base64": audio_data,
        "language": lang
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
