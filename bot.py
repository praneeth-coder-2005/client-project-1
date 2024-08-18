import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Define the maximum file size (2GB)
MAX_FILESIZE_UPLOAD = 2 * 1024 * 1024 * 1024  # 2GB in bytes

# Replace with your actual bot token
TOKEN = os.environ.get('TOKEN')

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Send me a video file to process. Use /help for more information.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
"""
    await update.message.reply_text(help_text)

async def download_file(url: str, file_path: str):
    # Download file in chunks to handle large file sizes efficiently
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024 * 1024)  # 1MB chunk size
                        if not chunk:
                            break
                        f.write(chunk)
            else:
                raise Exception(f"Failed to download file: Status code {response.status}")

async def handle_large_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.video
    file_size = file.file_size

    # Check if the file is too large
    if file_size > MAX_FILESIZE_UPLOAD:
        await update.message.reply_text("The file is too large for Telegram (max 2GB).")
        return

    # Check if the document has a video MIME type
    if update.message.document and 'video' in update.message.document.mime_type:
        file = update.message.document

    # Get the direct download URL
    file_info = await file.get_file()
    download_url = file_info.file_path

    # Download the file using the URL
    local_filename = f"{file.file_id}.mp4"  # Adjust the extension based on the file type
    await update.message.reply_text(f"Downloading file: {local_filename}")

    try:
        await download_file(download_url, local_filename)
        await update.message.reply_text(f"File downloaded successfully: {local_filename}")
    except Exception as e:
        await update.message.reply_text(f"Error downloading file: {e}")
        logger.error(f"Error downloading file: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text('An unexpected error occurred.')

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Using filters.VIDEO for video files and filters.Document for documents
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document, handle_large_file))
    
    application.add_error_handler(error_handler)
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
