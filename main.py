import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from pydub import AudioSegment
import openai

# Logging for Render debug
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment vars
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://growmo.onrender.com/webhook"
PORT = int(os.getenv("PORT", 10000))
openai.api_key = os.getenv("OPENAI_API_KEY")


# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/start triggered by user %s", update.effective_user.id)
    await update.message.reply_text("🎤 Send a voice message to get your video script!")


# Voice message handler
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    logger.info("Voice received from user %s", user_id)

    file = await update.message.voice.get_file()
    ogg_path = f"{user_id}.ogg"
    wav_path = f"{user_id}.wav"
    await file.download_to_drive(ogg_path)

    # Convert OGG to WAV
    try:
        audio = AudioSegment.from_file(ogg_path, format="ogg")
        audio.export(wav_path, format="wav")
    except Exception as e:
        await update.message.reply_text(f"❌ Error converting audio: {str(e)}")
        return

    await update.message.reply_text("🧠 Transcribing your voice...")

    # Transcribe with OpenAI Whisper
    try:
        with open(wav_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        script_text = transcript['text']
    except Exception as e:
        await update.message.reply_text(f"❌ Transcription error: {str(e)}")
        return

    # Create buttons
    buttons = [
        [InlineKeyboardButton("✏️ Edit Script", callback_data="edit")],
        [InlineKeyboardButton("✅ Finalize", callback_data="final")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]

    await update.message.reply_text(
        f"📝 Here's your script:\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    # Cleanup
    try:
        os.remove(ogg_path)
        os.remove(wav_path)
    except:
        pass


# Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"🔘 You selected: {query.data}")


# Error logger
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Update %s caused error %s", update, context.error)


# Bot launcher
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Set webhook
    async def on_startup():
        await app.bot.set_webhook(WEBHOOK_URL)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
        on_startup=on_startup,
        drop_pending_updates=True
    )
