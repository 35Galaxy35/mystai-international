from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
import traceback

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


@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        user_input = data.get("user_input", "")

        print("=== Kullanıcı girişi:", user_input)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a mystical fortune teller."},
                {"role": "user", "content": user_input}
            ]
        )

        response_text = completion.choices[0].message.content

        return jsonify({
            "text": response_text
        })

    except Exception as e:
        print("=== HATA OLUŞTU ===")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/test_openai")
def test_openai():
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test message"}]
        )
        return "OpenAI OK → " + r.choices[0].message.content

    except Exception as e:
        return "OpenAI ERROR → " + str(e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
