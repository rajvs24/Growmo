import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from pydub import AudioSegment

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tokens
TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLY_API = os.getenv("ASSEMBLYAI_API_KEY")

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Send a voice message to get your video script!")

# Voice Handler
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

    # Polling until done
    status = "processing"
    while status != "completed":
        result = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers={'authorization': ASSEMBLY_API})
        status = result.json()["status"]

    script_text = result.json()["text"]

    # Buttons
    buttons = [
        [InlineKeyboardButton("✏️ Edit Script", callback_data="edit")],
        [InlineKeyboardButton("✅ Finalize", callback_data="final")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]

    await update.message.reply_text(
        f"📝 Here's your promo script:\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Button Callback
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Button clicked: " + query.data)

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main App
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Run Webhook (for Render.com)
    WEBHOOK_URL = "https://growmo.onrender.com/webhook"
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
        url_path=TOKEN,
        drop_pending_updates=True
    )
