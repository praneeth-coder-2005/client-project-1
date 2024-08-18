import os
import asyncio
import logging
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import cv2
import numpy as np
import aiohttp
import time

# Define the maximum file size (2GB)
MAX_FILESIZE_UPLOAD = 2 * 1024 * 1024 * 1024  # 2GB in bytes

# Replace with your actual bot token
TOKEN = os.environ.get('6940650370:AAHKGmVNhxXb37W6Ty7o4o0wL8oEeRxffZY')
DEFAULT_WATERMARK_PATH = 'default_watermark.png'

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States for conversation handler
TITLE = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Send me a video file to process. Use /help for more information.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
/watermark - Set a custom watermark image

To process a video, just send it to me!
"""
    await update.message.reply_text(help_text)

async def set_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Please send the watermark image.')

async def handle_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Handle the watermarking process here
    pass

async def ask_for_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Please provide a title for the video.')

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = update.message.text
    await update.message.reply_text(f'Title received: {title}')
    # Handle the rest of the video processing with the title

async def download_file_with_progress(url: str, local_path: str, progress_message, context: ContextTypes.DEFAULT_TYPE):
    response = requests.get(url, stream=True)
    total_length = int(response.headers.get('content-length', 0))

    with open(local_path, 'wb') as f:
        downloaded = 0
        last_percentage = 0
        for chunk in response.iter_content(chunk_size=1048576):  # 1MB chunk size
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                percentage = int(100 * downloaded / total_length)
                if percentage > last_percentage:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=progress_message.chat_id,
                            message_id=progress_message.message_id,
                            text=f"Download progress: {percentage}%"
                        )
                        last_percentage = percentage
                    except Exception as e:
                        logger.warning(f"Failed to update progress message: {e}")

async def handle_large_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.video or update.message.photo[-1]
    file_size = file.file_size

    if file_size > MAX_FILESIZE_UPLOAD:
        await update.message.reply_text("The file is too large for Telegram (max 2GB).")
        return

    await update.message.reply_text(f"File received. Preparing to upload {file_size / (1024 * 1024):.2f} MB...")
    file_path = await file.get_file()
    await download_file_with_progress(file_path.file_path, f"{file.file_id}.ext", update.message, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text('An unexpected error occurred.')

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("watermark", set_watermark))
    application.add_handler(MessageHandler(filters.PHOTO, handle_watermark))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.VIDEO, ask_for_title)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        },
        fallbacks=[],
        name="my_conversation",
        persistent=False,
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.ALL | filters.Video.ALL, handle_large_file))
    application.add_error_handler(error_handler)
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
