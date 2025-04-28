import os
import logging
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from pydub import AudioSegment

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tokens
TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLY_API = os.getenv("ASSEMBLYAI_API_KEY")
RUNWAY_API = os.getenv("RUNWAY_API_KEY")

# Storage
user_scripts = {}

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Send text/voice to create AI videos!")

# Generate Video with Runway
async def generate_video(prompt: str, user_id: int):
    headers = {
        "Authorization": f"Bearer {RUNWAY_API}",
        "Content-Type": "application/json"
    }
    
    # Start generation
    data = {
        "prompt": prompt,
        "width": 1024,
        "height": 576,
        "seed": user_id  # For consistency
    }
    response = requests.post(
        "https://api.runwayml.com/v1/videos/generate",
        headers=headers,
        json=data
    )
    generation_id = response.json()["id"]
    
    # Poll for completion
    while True:
        status = requests.get(
            f"https://api.runwayml.com/v1/videos/{generation_id}",
            headers=headers
        ).json()
        
        if status["status"] == "succeeded":
            return status["output"]["url"]  # Video URL
        elif status["status"] == "failed":
            raise Exception("Generation failed")
        
        time.sleep(5)

# Text Handler
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    user_scripts[user_id] = text
    
    buttons = [
        [InlineKeyboardButton("🎥 Generate Video", callback_data="gen_video")],
        [InlineKeyboardButton("✏️ Edit Text", callback_data="edit_text")]
    ]
    
    await update.message.reply_text(
        f"📝 Your script:\n\n{text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Button Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "gen_video":
        await query.edit_message_text("🎬 Generating video (2-3 mins)...")
        try:
            video_url = await generate_video(user_scripts[user_id], user_id)
            
            # Download and send
            video_data = requests.get(video_url).content
            with open(f"{user_id}.mp4", "wb") as f:
                f.write(video_data)
            
            await context.bot.send_video(
                chat_id=user_id,
                video=open(f"{user_id}.mp4", "rb"),
                caption="Here's your AI-generated video!"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    # Webhook for Render
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=os.getenv("WEBHOOK_URL"),
        url_path="webhook",
        drop_pending_updates=True
    )
