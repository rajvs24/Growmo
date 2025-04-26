import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from pydub import AudioSegment

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLY_API = os.getenv("ASSEMBLYAI_API_KEY")
TOGETHER_API = os.getenv("TOGETHER_API_KEY")

# Global storage (consider using database in production)
user_transcriptions = {}

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 Welcome to PromoScript Bot!\n\n"
        "Send me a voice message or text, and I'll create "
        "an engaging promotional video script for you!"
    )

# Improved script generation with robust error handling
async def expand_text_into_script(text):
    headers = {
        "Authorization": f"Bearer {TOGETHER_API}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"Create a compelling 30-second promotional video script based on this input:\n\n"
        f"{text}\n\n"
        "The script should be:\n"
        "- Engaging and attention-grabbing\n"
        "- Emotionally resonant\n"
        "- Clear call-to-action\n"
        "- Suitable for voiceover with visual cues\n"
        "- Approximately 60-80 words"
    )
    
    data = {
        "model": "mistralai/Mixtral-8x7b-instruct-v0.1",
        "prompt": prompt,
        "max_tokens": 350,
        "temperature": 0.7,
        "top_p": 0.9
    }
    
    try:
        response = requests.post(
            "https://api.together.xyz/inference",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Handle different API response formats
        if 'output' in result:
            return result['output'].strip()
        elif 'choices' in result and result['choices']:
            return result['choices'][0]['text'].strip()
        elif isinstance(result, str):
            return result.strip()
        else:
            logger.error(f"Unexpected API response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return None

# Text message handler
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text.strip():
        await update.message.reply_text("Please provide some text to generate a script.")
        return
        
    await update.message.reply_text("🧠 Crafting your promotional script...")
    
    script = await expand_text_into_script(user_text)
    if not script:
        await update.message.reply_text(
            "❌ Sorry, I couldn't generate a script right now. "
            "Please try again later or with different text."
        )
        return
    
    await update.message.reply_text(
        f"🎬 Here's your promotional script:\n\n{script}\n\n"
        "Would you like me to refine or expand any part of it?"
    )

# Voice message handler with file cleanup
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    try:
        file = await update.message.voice.get_file()
        ogg_path = f"{user.id}.ogg"
        mp3_path = f"{user.id}.mp3"
        
        await file.download_to_drive(ogg_path)
        
        # Convert and cleanup
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(mp3_path, format="mp3")
        os.remove(ogg_path)
        
        await update.message.reply_text("🔍 Processing your voice message...")
        
        # Upload to AssemblyAI
        with open(mp3_path, "rb") as f:
            headers = {'authorization': ASSEMBLY_API}
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f},
                timeout=30
            )
            upload_response.raise_for_status()
        
        upload_url = upload_response.json()["upload_url"]
        
        # Start transcription
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={
                'authorization': ASSEMBLY_API,
                "content-type": "application/json"
            },
            json={"audio_url": upload_url},
            timeout=30
        )
        transcript_response.raise_for_status()
        
        transcript_id = transcript_response.json()["id"]
        
        # Poll for completion
        status = "processing"
        while status != "completed":
            result = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers={'authorization': ASSEMBLY_API},
                timeout=30
            )
            result.raise_for_status()
            status = result.json()["status"]
            if status == "error":
                raise Exception("Transcription failed")
        
        transcript_text = result.json()["text"]
        os.remove(mp3_path)  # Clean up MP3 file
        
        if not transcript_text.strip():
            raise Exception("Empty transcription")
        
        # Store and show options
        user_transcriptions[user.id] = transcript_text
        buttons = [
            [InlineKeyboardButton("✅ Generate Script", callback_data="proceed")],
            [InlineKeyboardButton("🔄 Try Again", callback_data="respeak")]
        ]
        
        await update.message.reply_text(
            f"🗣️ I heard:\n\n{transcript_text}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Voice processing failed: {str(e)}")
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        await update.message.reply_text(
            "❌ Sorry, I couldn't process your voice message. "
            "Please try again or send text instead."
        )

# Button callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    try:
        if query.data == "proceed":
            if user.id not in user_transcriptions:
                await query.edit_message_text("❌ No transcription found. Please send a new voice message.")
                return
                
            await query.edit_message_text("🧠 Creating your promotional script...")
            script = await expand_text_into_script(user_transcriptions[user.id])
            
            if not script:
                await query.message.reply_text(
                    "❌ Sorry, I couldn't generate a script. "
                    "Please try again with different text."
                )
                return
                
            await query.message.reply_text(
                f"🎬 Here's your promotional script:\n\n{script}\n\n"
                "Would you like me to refine or expand any part of it?"
            )
            
        elif query.data == "respeak":
            await query.edit_message_text(
                "🔄 Please record your message again or send text instead."
            )
            
    except Exception as e:
        logger.error(f"Button handler error: {str(e)}")
        await query.message.reply_text(
            "❌ An error occurred. Please try again."
        )

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}", exc_info=True)
    if update and hasattr(update, 'message'):
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again later."
        )

# Application setup
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    # Webhook configuration for Render
    webhook_url = os.getenv("WEBHOOK_URL", "https://your-render-url.onrender.com/webhook")
    port = int(os.getenv("PORT", 10000))
    
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
        url_path="webhook",
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
