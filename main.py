import os
import logging
import requests
from gtts import gTTS
from pydub import AudioSegment
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from moviepy.editor import *

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tokens and Keys
TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLY_API = os.getenv("ASSEMBLYAI_API_KEY")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Send a voice message to get your promo video!")

# Generate Promo Video Function
def generate_promo_video(script_text: str, user_id: int) -> str:
    tts = gTTS(script_text)
    audio_path = f"{user_id}_voice.mp3"
    tts.save(audio_path)

    # Load background image or video
    if os.path.exists("assets/background.mp4"):
        clip = VideoFileClip("assets/background.mp4").subclip(0, 10)
    else:
        clip = ImageClip("assets/background.jpg", duration=10)

    clip = clip.resize(height=720)

    # Add text overlay
    txt = TextClip(script_text, fontsize=40, color='white', font='Arial-Bold',
                   method='caption', size=(clip.w * 0.9, None))
    txt = txt.set_position('center').set_duration(clip.duration)

    # Set audio
    audio = AudioFileClip(audio_path)
    final = CompositeVideoClip([clip, txt.set_start(0)]).set_audio(audio)

    # Output
    output_path = f"{user_id}_promo.mp4"
    final.write_videofile(output_path, fps=24, verbose=False, logger=None)

    os.remove(audio_path)
    return output_path

# Voice message handler
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    file = await update.message.voice.get_file()
    ogg_path = f"{user_id}.ogg"
    mp3_path = f"{user_id}.mp3"
    await file.download_to_drive(ogg_path)

    # Convert OGG to MP3
    sound = AudioSegment.from_ogg(ogg_path)
    sound.export(mp3_path, format="mp3")
    await update.message.reply_text("🧠 Transcribing your voice...")

    # Upload to AssemblyAI
    with open(mp3_path, "rb") as f:
        headers = {'authorization': ASSEMBLY_API}
        response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})
    upload_url = response.json()["upload_url"]

    # Start transcription
    transcript_response = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={'authorization': ASSEMBLY_API, "content-type": "application/json"},
        json={"audio_url": upload_url}
    )
    transcript_id = transcript_response.json()["id"]

    # Wait for transcription
    status = "processing"
    while status != "completed":
        result = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers={'authorization': ASSEMBLY_API})
        status = result.json()["status"]

    script_text = result.json()["text"]
    await update.message.reply_text("🎬 Creating your promo video...")

    video_path = generate_promo_video(script_text, user_id)

    # Send video
    with open(video_path, "rb") as video:
        await update.message.reply_video(video)

    # Clean up
    os.remove(ogg_path)
    os.remove(mp3_path)
    os.remove(video_path)

# Button handler (optional)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Button clicked: " + query.data)

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main App
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Render deployment
    WEBHOOK_URL = "https://growmo.onrender.com/webhook"
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
        url_path=TOKEN,
        drop_pending_updates=True
    )
