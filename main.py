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
    await update.message.reply_text("🎤 Send a voice message or text to get your video script!")

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

    # Show the transcribed text
    await update.message.reply_text(f"📝 Here's what I transcribed:\n\n{script_text}")

    # Buttons to proceed or resubmit voice
    buttons = [
        [InlineKeyboardButton("✅ Proceed to Script", callback_data="generate_script")],
        [InlineKeyboardButton("🔄 Re-speak", callback_data="respeak")]
    ]

    await update.message.reply_text(
        f"Would you like to proceed with the following script or re-speak your message?\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Text Handler (for users who send text directly)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    script_text = f"✨ Promotional Script for: {user_text}\n\n"
    script_text += f"🎉 Grab amazing offers at your favorite store! 🎉\n"
    script_text += f"🛍️ {user_text} - 20% off on all products!\n"
    script_text += "Visit us today for unbeatable deals! Don't miss out. 🎯"
    
    # Buttons to proceed with script
    buttons = [
        [InlineKeyboardButton("✅ Proceed to Script", callback_data="generate_script")]
    ]

    await update.message.reply_text(
        f"📝 Here's your promotional script:\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Button Callback Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "generate_script":
        # Generate a detailed script
        await query.edit_message_text("🎬 Creating your detailed promotional video script...")

        # Here you could add any additional logic for creating a detailed script
        detailed_script = "🎥 Promotional Video Script (30 seconds):\n\n"
        detailed_script += "✨ Start with an introduction:\n"
        detailed_script += "🎤 'Welcome to Patel General Store, where we bring you the best offers on groceries and essentials!'\n\n"
        detailed_script += "✨ Highlight the offer:\n"
        detailed_script += "🎉 'This week, everything is 20% off! Don't miss these unbeatable prices.'\n\n"
        detailed_script += "✨ Add a call to action:\n"
        detailed_script += "🚀 'Visit us today and grab your favorites before the sale ends!'\n\n"
        detailed_script += "🎯 'Patel General Store – your one-stop shop for all things essential!'"

        await query.edit_message_text(f"📜 Here is your detailed promotional script:\n\n{detailed_script}")

    elif query.data == "respeak":
        await query.edit_message_text("🎤 Please send a new voice message to re-record your script.")

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main App
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))  # Added text handler
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Run Webhook (for Render.com)
    WEBHOOK_URL = "https://your-app-name.onrender.com/webhook"  # Make sure this URL is correct
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
        url_path="webhook",
        drop_pending_updates=True
    )
