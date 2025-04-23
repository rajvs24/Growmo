from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
import openai
from pydub import AudioSegment
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Send voice to get your video script!")



openai.api_key = os.getenv("OPENAI_API_KEY")

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.id
    file = await update.message.voice.get_file()
    ogg_path = f"{user}.ogg"
    mp3_path = f"{user}.mp3"
    await file.download_to_drive(ogg_path)

    # Convert .ogg to .mp3
    sound = AudioSegment.from_ogg(ogg_path)
    sound.export(mp3_path, format="mp3")

    await update.message.reply_text("🧠 Transcribing your voice...")

    # Transcribe using Whisper
    with open(mp3_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

    script_text = transcript['text']

    # Add buttons
    buttons = [
        [InlineKeyboardButton("✏️ Edit Script", callback_data="edit")],
        [InlineKeyboardButton("✅ Finalize", callback_data="final")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(
        f"📝 Here's your promo script:\n\n{script_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Button clicked: " + query.data)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
