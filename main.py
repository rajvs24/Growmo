import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)
from pydub import AudioSegment

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tokens
TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLY_API = os.getenv("ASSEMBLYAI_API_KEY")
TOGETHER_API = os.getenv("TOGETHER_API_KEY")

# In-memory storage for user transcriptions
user_transcriptions = {}

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Send a voice message or type text to create your promotional script!")

# Expand text into promotional script
async def expand_text_into_script(text):
    headers = {
        "Authorization": f"Bearer {TOGETHER_API}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistralai/Mixtral-8x7b-instruct-v0.1",
        "prompt": f"Expand this into a detailed, catchy, emotional, energetic 30-second promotional video script: {text}",
        "max_tokens": 300,
        "temperature": 0.7
    }
    response = requests.post("https://api.together.xyz/inference", headers=headers, json=data)
    result = response.json()
    return result['output'].strip()

# Handle text messages
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("🧠 Creating your promotional script...")

    promo_script = await expand_text_into_script(user_text)

    await update.message.reply_text(f"🎬 Here’s your promo video script:\n\n{promo_script}")

# Handle voice messages
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

    # Poll until done
    status = "processing"
    while status != "completed":
        result = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers={'authorization': ASSEMBLY_API})
        status = result.json()["status"]

    script_text = result.json()["text"]

    # Save transcription for user
    user_transcriptions[user_id] = script_text

    # Send text and buttons
    buttons = [
        [InlineKeyboardButton("✅ Proceed to Script", callback_data="proceed")],
        [InlineKeyboardButton("🔁 Re-speak", callback_data="respeak")]
    ]

    await update.message.reply_text(
        f"🗣️ You said:\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Button Callbacks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "proceed":
        if user_id in user_transcriptions:
            text_to_expand = user_transcriptions[user_id]
            await query.edit_message_text("🧠 Creating your promotional script...")
            promo_script = await expand_text_into_script(text_to_expand)
            await query.message.reply_text(f"🎬 Here’s your promo video script:\n\n{promo_script}")
        else:
            await query.edit_message_text("❌ No transcription found. Please send a new voice message.")

    elif query.data == "respeak":
        await query.edit_message_text("🔁 Please send a new voice message.")

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main App
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Run Webhook (for Render.com)
    WEBHOOK_URL = "https://growmo.onrender.com/webhook"
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
        url_path="webhook",
        drop_pending_updates=True
    )
