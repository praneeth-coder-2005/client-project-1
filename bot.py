import os
import logging
import aiohttp
import time
import asyncio
import traceback
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Replace with your actual bot token
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG to get detailed logs
)
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunk size for faster download
TIMEOUT = 10  # Timeout for download operations
MAX_RETRIES = 3  # Maximum number of retries for download failures

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Send me a video link, and I will add a watermark, title, and timestamp.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message

You can send a video file or provide a download link for a video file, and the bot will download, add a watermark, title, and timestamp, then send it back.
"""
    await update.message.reply_text(help_text)

async def download_file(url: str, file_path: str, update: Update, context: ContextTypes.DEFAULT_TYPE, progress_message):
    """Downloads the file with optimized speed and improved logging."""
    try:
        logger.info(f"Starting download from {url} to {file_path}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=TIMEOUT)) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await context.bot.edit_message_text(
                        chat_id=progress_message.chat_id,
                        message_id=progress_message.message_id,
                        text=f"Failed to download file. HTTP Status Code: {response.status}"
                    )
                    logger.error(f"Failed to download file. HTTP Status Code: {response.status}")
                    return

                total_size = int(response.headers.get('content-length', 0))
                logger.debug(f"Total file size: {total_size} bytes")
                bytes_downloaded = 0
                retries = 0
                start_time = time.time()

                # Open the file for writing in binary mode
                with open(file_path, 'wb') as f:
                    while True:
                        try:
                            chunk = await response.content.read(CHUNK_SIZE)
                            if not chunk:
                                logger.debug("Download complete")
                                break  # Download finished
                            f.write(chunk)
                            bytes_downloaded += len(chunk)

                            # Calculate percentage and speed
                            elapsed_time = time.time() - start_time
                            download_speed = bytes_downloaded / elapsed_time

                            # Update progress message
                            percent_downloaded = (bytes_downloaded / total_size) * 100 if total_size else 0
                            await context.bot.edit_message_text(
                                chat_id=progress_message.chat_id,
                                message_id=progress_message.message_id,
                                text=f"Downloading... {percent_downloaded:.2f}%\nSpeed: {download_speed / 1024 / 1024:.2f} MB/s"
                            )

                        except (aiohttp.ClientPayloadError, asyncio.TimeoutError) as e:
                            logger.error(f"Download error: {e}")
                            retries += 1
                            if retries > MAX_RETRIES:
                                raise Exception("Max retries exceeded during download.")
                            await asyncio.sleep(2)  # Wait before retrying
                        except Exception as e:
                            logger.error(f"Error downloading file: {e}")
                            logger.error(traceback.format_exc())
                            raise

                logger.info(f"File downloaded successfully: {file_path}")
                return file_path
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=progress_message.chat_id,
            message_id=progress_message.message_id,
            text=f"Failed to download the file. Error: {e}"
        )
        logger.error(f"Error downloading file: {e}")
        logger.error(traceback.format_exc())
        raise

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text.startswith('http'):
        progress_message = await update.message.reply_text("Starting download and processing...")

        local_filename = "downloaded_video.mp4"
        output_filename = "output_video.mp4"

        try:
            # Download the file with progress tracking
            file_path = await download_file(message_text, local_filename, update, context, progress_message)

            # Add your video processing function here if needed
            # await process_video(file_path, output_filename)

            # Notify user of download completion
            await context.bot.edit_message_text(
                chat_id=progress_message.chat_id,
                message_id=progress_message.message_id,
                text="Download complete. Processing the video..."
            )

            # Send the processed video
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(output_filename, 'rb'))

        except Exception as e:
            await context.bot.edit_message_text(
                chat_id=progress_message.chat_id,
                message_id=progress_message.message_id,
                text=f"Failed to process the video. Error: {e}"
            )
            logger.error(f"Failed to process the video. Error: {e}")
    else:
        await update.message.reply_text("Please provide a valid download link.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text('An unexpected error occurred.')

def main():
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Message handler to capture download links
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
