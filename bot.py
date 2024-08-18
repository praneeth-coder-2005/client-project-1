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
    await update.message.reply_text('Send me a video file or a download link. Use /help for more information.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message

You can send a video file or provide a download link for a video file, and the bot will download and process it.
"""
    await update.message.reply_text(help_text)

async def download_file(url: str, file_path: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)  # 1MB chunk size
                            if not chunk:
                                break
                            f.write(chunk)
                    logger.info(f"File downloaded successfully: {file_path}")
                    return file_path
                else:
                    raise Exception(f"Failed to download file: Status code {response.status}")
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text.startswith('http'):
        # Treat message as a download link
        download_url = message_text.strip()
        await update.message.reply_text("Starting download...")
        
        try:
            local_filename = f"downloaded_video.mp4"  # Fixed name for simplicity
            await download_file(download_url, local_filename)
            await update.message.reply_text(f"File downloaded successfully: {local_filename}")
        except Exception as e:
            await update.message.reply_text(f"Failed to download the file. Error: {e}")
    else:
        await update.message.reply_text("Please provide a valid download link.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text('An unexpected error occurred.')

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # This handler will capture all text messages (including download links)
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    application.add_error_handler(error_handler)
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
