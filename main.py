from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
import openai
from pydub import AudioSegment

# Initialize with environment variables
TOKEN = os.getenv("BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Welcome! Send me a voice message to create your promo script!")

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    voice_file = await update.message.voice.get_file()
    
    # Download and convert voice
    ogg_path = f"{user_id}.ogg"
    mp3_path = f"{user_id}.mp3"
    await voice_file.download_to_drive(ogg_path)
    
    try:
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(mp3_path, format="mp3")
    except Exception as e:
        await update.message.reply_text("❌ Error processing audio. Try again.")
        return

    # Transcribe with Whisper
    await update.message.reply_text("🔍 Processing your voice...")
    try:
        with open(mp3_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        script = transcript['text']
    except Exception as e:
        await update.message.reply_text("❌ Transcription failed. Check your OpenAI key.")
        return

    # Show script with buttons
    keyboard = [
        [InlineKeyboardButton("✏️ Edit", callback_data="edit")],
        [InlineKeyboardButton("✅ Finalize", callback_data="final")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(
        f"📝 Your script:\n\n{script}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Cleanup
    os.remove(ogg_path)
    os.remove(mp3_path)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "edit":
        await query.edit_message_text("Send the corrected text:")
    elif query.data == "final":
        await query.edit_message_text("✅ Done! Video generation coming soon!")
    elif query.data == "cancel":
        await query.edit_message_text("❌ Cancelled. Send /start to begin.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Webhook config
    WEBHOOK_URL = "https://growmo.onrender.com/webhook"  # Your Render URL
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
        url_path=TOKEN,
        drop_pending_updates=True
    )
