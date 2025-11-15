from flask import Flask, request, Response, send_from_directory
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from groq import Groq
from gtts import gTTS
import requests
import os

app = Flask(__name__)
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# Environment Variables (Render will inject them)
TW_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TW_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

client = Client(TW_SID, TW_TOKEN)
groq = Groq(api_key=GROQ_KEY)


@app.route("/")
def home():
    return "AI Calling Agent is running on Render!"


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


@app.route("/recording", methods=["POST"])
def recording():
    recording_url = request.form["RecordingUrl"] + ".wav"

    audio_path = f"{AUDIO_DIR}/hr.wav"
    r = requests.get(recording_url, auth=(TW_SID, TW_TOKEN))
    open(audio_path, "wb").write(r.content)

    # STT
    with open(audio_path, "rb") as audio:
        stt = groq.audio.transcriptions.create(
            file=audio,
            model="whisper-large-v3"
        ).text

    print("HR Said:", stt)

    # LLM REPLY
    prompt = f"You are an AI calling agent. Reply politely. HR said: {stt}"

    llm = groq.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    ai_reply = llm.choices[0].message.content

    # TTS
    reply_file = f"{AUDIO_DIR}/reply.mp3"
    gTTS(ai_reply).save(reply_file)

    audio_url = request.url_root + f"audio/reply.mp3"

    resp = VoiceResponse()
    resp.play(audio_url)
    resp.record(
        timeout=2,
        maxLength=10,
        playBeep=True,
        action="/recording"
    )

    return Response(str(resp), mimetype="text/xml")


@app.route("/audio/<filename>")
def audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
