from flask import Flask, request, Response, send_from_directory
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from groq import Groq
from gtts import gTTS
import requests
import os

app = Flask(__name__)

# ----------------- Load Environment Variables -----------------
TW_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TW_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
TARGET_NUMBER = os.environ.get("TARGET_PHONE_NUMBER")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

client = Client(TW_SID, TW_TOKEN)
groq = Groq(api_key=GROQ_KEY)

SERVER_URL = os.environ.get("SERVER_URL")   # example: https://ai-calling-agent.onrender.com
AUDIO_DIR = "audio"

# Create audio folder if not exists
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)


# ----------------- Home Route -----------------
@app.route("/")
def home():
    return "AI Calling Agent is running on Render!"


# ----------------- Twilio Starts Call Here -----------------
@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()

    resp.say(
        "Hello, this is your AI calling agent from AiKing Solutions. "
        "May I know if there are any job openings available?",
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


# ----------------- Handle HR Recording -----------------
@app.route("/recording", methods=["POST"])
def recording():
    recording_url = request.form.get("RecordingUrl") + ".wav"
    print("\n🎧 Recording URL:", recording_url)

    hr_audio = f"{AUDIO_DIR}/hr.wav"
    r = requests.get(recording_url, auth=(TW_SID, TW_TOKEN))

    with open(hr_audio, "wb") as f:
        f.write(r.content)

    # STT
    with open(hr_audio, "rb") as audio:
        stt = groq.audio.transcriptions.create(
            file=audio,
            model="whisper-large-v3"
        ).text

    print("HR said:", stt)

    # LLM
    prompt = f"You are an AI calling agent. HR said: '{stt}'. Reply professionally."

    reply = groq.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content

    print("AI Reply:", reply)

    # TTS
    tts_file = f"{AUDIO_DIR}/reply.mp3"
    gTTS(reply, lang="en").save(tts_file)

    audio_url = f"{SERVER_URL}/audio/reply.mp3"

    resp = VoiceResponse()
    resp.play(audio_url)
    resp.record(
        timeout=2,
        maxLength=10,
        playBeep=True,
        action="/recording",
        method="POST"
    )

    return Response(str(resp), mimetype="text/xml")


# ----------------- Serve Audio Files -----------------
@app.route("/audio/<filename>")
def audio_file(filename):
    return send_from_directory(AUDIO_DIR, filename)


# ----------------- Trigger Call Manually -----------------
@app.route("/call", methods=["GET"])
def call():
    call = client.calls.create(
        to=TARGET_NUMBER,
        from_=TW_NUMBER,
        url=f"{SERVER_URL}/voice"
    )
    return f"Call started! SID: {call.sid}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
