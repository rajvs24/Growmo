from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
import openai
from pydub import AudioSegment

# Setup (Don't change these - Render will provide the values)
TOKEN = os.getenv("BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Bot Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Send a voice message to create your promo video script!")

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    voice_file = await update.message.voice.get_file()
    
    # 1. Download voice message
    ogg_path = f"{user_id}.ogg"
    await voice_file.download_to_drive(ogg_path)
    
    # 2. Convert to MP3
    try:
        sound = AudioSegment.from_ogg(ogg_path)
        mp3_path = f"{user_id}.mp3"
        sound.export(mp3_path, format="mp3")
    except Exception as e:
        await update.message.reply_text("❌ Error converting audio. Please try again.")
        return

    # 3. Transcribe with OpenAI
    await update.message.reply_text("🧠 Transcribing your voice...")
    try:
        with open(mp3_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        script_text = transcript['text']
    except Exception as e:
        await update.message.reply_text("❌ Transcription failed. Please try again.")
        return

    # 4. Show buttons
    buttons = [
        [InlineKeyboardButton("✏️ Edit Script", callback_data="edit")],
        [InlineKeyboardButton("✅ Finalize", callback_data="final")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(
        f"📝 Your script:\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    # 5. Clean up files
    try:
        os.remove(ogg_path)
        os.remove(mp3_path)
    except:
        pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit":
        await query.edit_message_text("✏️ Send me the corrected text.")
    elif query.data == "final":
        await query.edit_message_text("✅ Script finalized! (Video coming soon!)")
    elif query.data == "cancel":
        await query.edit_message_text("❌ Cancelled. Send /start to try again.")

# Webhook Setup (Critical for Render)
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Webhook config (Replace YOUR_SERVICE_NAME with your Render service name)
    WEBHOOK_URL = "https://growmo.onrender.com/webhook"
    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        webhook_url=WEBHOOK_URL,
    )
