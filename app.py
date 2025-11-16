from flask import Flask, request, Response, send_from_directory, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from groq import Groq
from gtts import gTTS
import os, requests

app = Flask(__name__)
AUDIO_DIR = "audio"

os.makedirs(AUDIO_DIR, exist_ok=True)

# ------------------ Load Environment Variables ------------------
TW_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TW_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
TARGET_NUMBER = os.environ.get("TARGET_PHONE_NUMBER")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

twilio_client = Client(TW_SID, TW_TOKEN)
groq_client = Groq(api_key=GROQ_KEY)


# ------------------ Home Page ------------------
@app.route("/")
def home():
    return "AI Calling Agent is LIVE 🔥"


# ------------------ Make Outgoing Call ------------------
@app.route("/call", methods=["GET"])
def make_call():
    PUBLIC_URL = os.environ.get("PUBLIC_URL")  # you must add this inside Render env
    if not PUBLIC_URL:
        return "Missing PUBLIC_URL in environment", 500

    call = twilio_client.calls.create(
        to=TARGET_NUMBER,
        from_=TW_NUMBER,
        url=f"{PUBLIC_URL}/voice"
    )
    return jsonify({"message": "Call started", "call_sid": call.sid})


# ------------------ Twilio hits /voice when call starts ------------------
@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    resp.say(
        "Hello, this is your AI calling agent from AiKing Solutions. May I know if there are any job openings available?",
        voice="alice"
    )
    resp.record(
        timeout=2,
        maxLength=10,
        playBeep=True,
        action="/recording",
        method="POST"
    )
    return Response(str(resp), mimetype="text/xml")


# ------------------ Twilio sends recording to /recording ------------------
@app.route("/recording", methods=["POST"])
def recording():
    recording_url = request.form.get("RecordingUrl") + ".wav"
    print("Recording URL:", recording_url)

    hr_file = os.path.join(AUDIO_DIR, "hr.wav")
    ai_file = os.path.join(AUDIO_DIR, "ai.mp3")

    # download recording
    audio_data = requests.get(recording_url, auth=(TW_SID, TW_TOKEN)).content
    with open(hr_file, "wb") as f:
        f.write(audio_data)

    # STT (Whisper)
    with open(hr_file, "rb") as f:
        stt = groq_client.audio.transcriptions.create(
            file=f, model="whisper-large-v3"
        ).text

    print("HR said:", stt)

    # AI Reply (Groq)
    prompt = f"You are an AI HR assistant. Reply politely.\nHR said: {stt}\nAI Reply:"
    ai_reply = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content

    print("AI:", ai_reply)

    # TTS
    gTTS(text=ai_reply, lang="en").save(ai_file)

    PUBLIC_URL = os.environ.get("PUBLIC_URL")

    resp = VoiceResponse()
    resp.play(f"{PUBLIC_URL}/audio/ai.mp3")
    resp.record(
        timeout=2,
        maxLength=10,
        playBeep=True,
        action="/recording",
        method="POST"
    )
    return Response(str(resp), mimetype="text/xml")


# ------------------ Serve audio files ------------------
@app.route("/audio/<path:filename>")
def audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


# ------------------ Required by Render ------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
