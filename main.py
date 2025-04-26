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

# Start command handler - SIMPLIFIED TO ENSURE IT WORKS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🎤 Welcome! Send me text or a voice message to create a promotional script."
        )
    except Exception as e:
        logger.error(f"Start command error: {e}")

# SIMPLIFIED text handler to ensure responses work
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_text = update.message.text
        await update.message.reply_text("🧠 Processing your text...")
        
        # Direct response for testing
        await update.message.reply_text(
            f"🎬 Here's your script based on: '{user_text}'\n\n"
            "[This would be your generated script in production]"
        )
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await update.message.reply_text("❌ Error processing your text. Please try again.")

# Main application setup
def main():
    try:
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Handlers - SIMPLIFIED for testing
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        
        # Error handler
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Error: {context.error}")
            if update and hasattr(update, 'message'):
                await update.message.reply_text("❌ An error occurred. Please try again.")
        
        app.add_error_handler(error_handler)
        
        # For local testing (use this instead of webhook when testing locally)
        print("Bot is polling...")
        app.run_polling()
        
        # For production (comment out run_polling and uncomment this)
        # app.run_webhook(
        #     listen="0.0.0.0",
        #     port=int(os.getenv("PORT", 10000)),
        #     webhook_url=os.getenv("WEBHOOK_URL"),
        #     url_path="webhook",
        #     drop_pending_updates=True
        # )
        
    except Exception as e:
        logger.error(f"Application failed: {e}")

if __name__ == "__main__":
    main()
