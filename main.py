import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from pydub import AudioSegment
from openai import OpenAI

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ENV variables
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = "https://growmo.onrender.com/webhook"

client = OpenAI(api_key=OPENAI_KEY)

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
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

    # Transcribe with Whisper
    with open(mp3_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    script_text = transcript.text

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

# Main entry
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        url_path=TOKEN,
        drop_pending_updates=True
    )
