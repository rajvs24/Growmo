import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from pydub import AudioSegment

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLY_API = os.getenv("ASSEMBLYAI_API_KEY")
TOGETHER_API = os.getenv("TOGETHER_API_KEY")

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🎤 Welcome to PromoScript Pro!\n\n"
            "Send me text about your business or a voice message, "
            "and I'll generate a professional promotional script for you."
        )
        # Clear any existing user data
        context.user_data.clear()
    except Exception as e:
        logger.error(f"Start command error: {e}")

# Generate script using Together AI
async def generate_script(prompt_text):
    headers = {
        "Authorization": f"Bearer {TOGETHER_API}",
        "Content-Type": "application/json"
    }
    
    enhanced_prompt = (
        f"Create a compelling 30-second promotional video script for: {prompt_text}\n\n"
        "The script should include:\n"
        "1. Attention-grabbing opening\n"
        "2. Key benefits/features\n"
        "3. Emotional appeal\n"
        "4. Clear call-to-action\n"
        "5. Natural pacing for voiceover\n"
        "Format: 4-5 short paragraphs, 60-80 words total"
    )
    
    data = {
        "model": "mistralai/Mixtral-8x7b-instruct-v0.1",
        "prompt": enhanced_prompt,
        "max_tokens": 400,
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
        
        # Parse different possible response formats
        if 'output' in result:
            return result['output'].strip()
        elif 'choices' in result and result['choices']:
            return result['choices'][0]['text'].strip()
        else:
            logger.error(f"Unexpected API response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return None

# Helper function for audio transcription
async def transcribe_audio(mp3_path):
    try:
        with open(mp3_path, "rb") as f:
            headers = {'authorization': ASSEMBLY_API}
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f},
                timeout=30
            )
            response.raise_for_status()
        
        upload_url = response.json()["upload_url"]
        
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
        
        while True:
            result = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers={'authorization': ASSEMBLY_API},
                timeout=30
            )
            result.raise_for_status()
            status = result.json()["status"]
            
            if status == "completed":
                return result.json()["text"]
            elif status == "error":
                raise Exception("Transcription failed")
            
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise

# Text message handler with edit support
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_text = update.message.text
        if not user_text.strip():
            await update.message.reply_text("Please provide some text to generate a script.")
            return
            
        # Check if we're in edit mode
        if context.user_data.get('edit_mode'):
            original_script = context.user_data.get('current_script', "")
            
            combined_prompt = (
                f"Original script: {original_script}\n\n"
                f"User requested changes: {user_text}\n\n"
                "Please modify the script according to these requests, "
                "keeping the same format and length."
            )
            
            await update.message.reply_text("🔄 Updating your script...")
            updated_script = await generate_script(combined_prompt)
            
            if not updated_script:
                await update.message.reply_text("❌ Failed to update script. Please try again.")
                return
                
            context.user_data['current_script'] = updated_script
            context.user_data['edit_mode'] = False
            
            # Show updated script with action buttons
            keyboard = [
                [InlineKeyboardButton("✏️ Edit Script", callback_data="edit_script")],
                [InlineKeyboardButton("✅ Finalize Script", callback_data="finalize_script")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎬 Updated Script:\n\n{updated_script}\n\n"
                "What would you like to do next?",
                reply_markup=reply_markup
            )
            
        else:
            # New script generation flow
            await update.message.reply_text("🧠 Crafting your professional script...")
            script = await generate_script(user_text)
            
            if not script:
                await update.message.reply_text(
                    "❌ Couldn't generate a script right now. "
                    "Please try again later or contact support."
                )
                return
                
            context.user_data['current_script'] = script
            
            # Add action buttons
            keyboard = [
                [InlineKeyboardButton("✏️ Edit Script", callback_data="edit_script")],
                [InlineKeyboardButton("✅ Finalize Script", callback_data="finalize_script")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎬 Here's your promotional script:\n\n{script}\n\n"
                "What would you like to do next?",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await update.message.reply_text("❌ Error processing your request. Please try again.")

# Voice message handler with edit support
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        ogg_path = f"{user.id}.ogg"
        mp3_path = f"{user.id}.mp3"
        
        file = await update.message.voice.get_file()
        await file.download_to_drive(ogg_path)
        
        # Convert to MP3
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(mp3_path, format="mp3")
        os.remove(ogg_path)
        
        # Check if we're in edit mode
        if context.user_data.get('edit_mode'):
            await update.message.reply_text("🔍 Processing your edits...")
            original_script = context.user_data.get('current_script', "")
            
            transcript_text = await transcribe_audio(mp3_path)
            os.remove(mp3_path)
            
            if not transcript_text.strip():
                raise Exception("Empty transcription")
            
            combined_prompt = (
                f"Original script: {original_script}\n\n"
                f"User requested changes: {transcript_text}\n\n"
                "Please modify the script according to these requests, "
                "keeping the same format and length."
            )
            
            updated_script = await generate_script(combined_prompt)
            if not updated_script:
                raise Exception("Failed to update script")
            
            context.user_data['current_script'] = updated_script
            context.user_data['edit_mode'] = False
            
            # Show updated script with action buttons
            keyboard = [
                [InlineKeyboardButton("✏️ Edit Again", callback_data="edit_script")],
                [InlineKeyboardButton("✅ Finalize Script", callback_data="finalize_script")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔄 Updated Script:\n\n{updated_script}\n\n"
                "What would you like to do next?",
                reply_markup=reply_markup
            )
            
        else:
            # Original voice message flow
            await update.message.reply_text("🔍 Processing your voice message...")
            transcript_text = await transcribe_audio(mp3_path)
            os.remove(mp3_path)
            
            if not transcript_text.strip():
                raise Exception("Empty transcription")
            
            context.user_data['transcript'] = transcript_text
            buttons = [
                [InlineKeyboardButton("✅ Generate Script", callback_data="generate")],
                [InlineKeyboardButton("🔄 Re-record", callback_data="rerecord")]
            ]
            
            await update.message.reply_text(
                f"🗣️ You said:\n\n{transcript_text}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        await update.message.reply_text(
            "❌ Error processing voice message. Please try again or send text."
        )

# Button callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "edit_script":
            context.user_data['edit_mode'] = True
            await query.edit_message_text(
                "✏️ Please send your additional instructions or record a new voice message "
                "to modify the script.\n\n"
                "Example: \"Make it more energetic\" or \"Focus on the price benefits\""
            )
            
        elif query.data == "finalize_script":
            final_script = context.user_data.get('current_script')
            if final_script:
                logger.info(f"Finalized script: {final_script}")
                await query.edit_message_text(
                    "✅ Script finalized! This will be used for video creation later.\n\n"
                    "Use /start to create a new script."
                )
                context.user_data.clear()
            else:
                await query.edit_message_text("❌ No script found to finalize.")
                
        elif query.data == "generate":
            transcript = context.user_data.get('transcript')
            if not transcript:
                await query.edit_message_text("❌ No transcription found. Please try again.")
                return
                
            await query.edit_message_text("🧠 Generating your script...")
            script = await generate_script(transcript)
            
            if not script:
                await query.message.reply_text("❌ Script generation failed. Please try again.")
                return
                
            context.user_data['current_script'] = script
            
            keyboard = [
                [InlineKeyboardButton("✏️ Edit Script", callback_data="edit_script")],
                [InlineKeyboardButton("✅ Finalize Script", callback_data="finalize_script")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"🎬 Here's your script:\n\n{script}\n\n"
                "What would you like to do next?",
                reply_markup=reply_markup
            )
            
        elif query.data == "rerecord":
            await query.edit_message_text("🔄 Please record your message again.")
            
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await query.message.reply_text("❌ An error occurred. Please try again.")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}", exc_info=True)
    if update and hasattr(update, 'message'):
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Main application setup
def main():
    try:
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Register handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        app.add_handler(MessageHandler(filters.VOICE, voice_handler))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_error_handler(error_handler)
        
        # Run bot
        if os.getenv("ENVIRONMENT") == "production":
            app.run_webhook(
                listen="0.0.0.0",
                port=int(os.getenv("PORT", 10000)),
                webhook_url=os.getenv("WEBHOOK_URL"),
                url_path="webhook",
                drop_pending_updates=True
            )
        else:
            print("Bot is running in polling mode...")
            app.run_polling()
            
    except Exception as e:
        logger.error(f"Application failed: {e}")

if __name__ == "__main__":
    main()
