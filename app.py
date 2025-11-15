from flask import Flask, request, Response, send_from_directory
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from groq import Groq
from gtts import gTTS
import requests
import os

# ----------------- Load ENV Variables -----------------
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

# ----------------- Setup Flask -----------------
app = Flask(__name__)
AUDIO_DIR = "audio"

# Make sure audio directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)

# ----------------- 1. Twilio Answers the Call -----------------
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


# ----------------- 2. After HR Speaks -----------------
@app.route("/recording", methods=["POST"])
def recording():

    recording_url = request.form.get("RecordingUrl") + ".wav"
    print("Recorded URL:", recording_url)

    # Download the audio
    hr_audio_path = os.path.join(AUDIO_DIR, "hr.wav")
    r = requests.get(recording_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    with open(hr_audio_path, "wb") as f:
        f.write(r.content)

    # STT using Groq Whisper
    with open(hr_audio_path, "rb") as audio_file:
        stt = groq_client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3"
        )
    hr_text = stt.text
    print("HR said:", hr_text)

    # AI Response using Groq Llama 3.1
    prompt = f"""
    You are an AI calling agent. Reply professionally.

    HR said: "{hr_text}"

    Your reply:
    """

    llm = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    ai_reply = llm.choices[0].message.content
    print("AI Reply:", ai_reply)

    # TTS (gTTS)
    reply_file = os.path.join(AUDIO_DIR, "reply.mp3")
    gTTS(text=ai_reply, lang="en").save(reply_file)

    # Public URL for Twilio to play it
    public_audio_url = request.url_root + "audio/reply.mp3"

    resp = VoiceResponse()
    resp.play(public_audio_url)

    # Continue recording to keep conversation going
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
def audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


# ----------------- Root -----------------
@app.route("/", methods=["GET"])
def home():
    return "AI Calling Agent Running on Render!"


# ----------------- Start App -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
