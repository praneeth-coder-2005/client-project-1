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
TOKEN = "6343124020:AAFFap55YkVIN_pyXzGtsyTNk2nLeJ0_qRI"

# Set up detailed logging for better debugging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for more detailed output
)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1MB chunk size for streaming download
MAX_RETRIES = 5  # Maximum number of retries for failed downloads
TIMEOUT = 30  # Timeout increased to 30 seconds
DOWNLOAD_SPEED_LIMIT = 1.25 * 1024 * 1024  # 10 Mbps = 1.25 MB/s
UPLOAD_SPEED_LIMIT = 1.25 * 1024 * 1024  # 10 Mbps = 1.25 MB/s

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
    """Downloads the file with a speed limit of 1.25 MB/s (10 Mbps)."""
    try:
        logger.debug(f"Starting download from {url} to {file_path}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=TIMEOUT)) as session:
            async with session.get(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                logger.debug(f"Total size of the file: {total_size} bytes")
                bytes_downloaded = 0
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
                            percent_downloaded = (bytes_downloaded / total_size) * 100 if total_size else 0
                            elapsed_time = time.time() - start_time
                            download_speed = bytes_downloaded / elapsed_time

                            # Throttle download speed
                            if download_speed > DOWNLOAD_SPEED_LIMIT:
                                await asyncio.sleep((len(chunk) / DOWNLOAD_SPEED_LIMIT))

                            # Update progress message
                            await context.bot.edit_message_text(
                                chat_id=progress_message.chat_id,
                                message_id=progress_message.message_id,
                                text=f"Downloading... {percent_downloaded:.2f}%\nSpeed: {download_speed / 1024 / 1024:.2f} MB/s"
                            )
                        except (aiohttp.ClientPayloadError, asyncio.TimeoutError) as e:
                            logger.error(f"Download error: {e}")
                            await asyncio.sleep(2)  # Wait before retrying
                        except Exception as e:
                            logger.error(f"Error downloading file: {e}")
                            logger.error(traceback.format_exc())  # Log full traceback
                            raise

                logger.info(f"File downloaded successfully: {file_path}")
                return file_path
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        logger.error(traceback.format_exc())
        raise

async def upload_file(file_path: str, update: Update, context: ContextTypes.DEFAULT_TYPE, progress_message):
    """Uploads the processed file with a speed limit of 1.25 MB/s (10 Mbps)."""
    try:
        logger.debug(f"Starting upload of {file_path}")
        total_size = os.path.getsize(file_path)
        bytes_uploaded = 0
        chunk_size = 1024 * 1024  # 1MB
        start_time = time.time()

        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    logger.debug("Upload complete")
                    break
                bytes_uploaded += len(chunk)

                # Calculate percentage and speed
                percent_uploaded = (bytes_uploaded / total_size) * 100
                elapsed_time = time.time() - start_time
                upload_speed = bytes_uploaded / elapsed_time

                # Throttle upload speed
                if upload_speed > UPLOAD_SPEED_LIMIT:
                    await asyncio.sleep((len(chunk) / UPLOAD_SPEED_LIMIT))

                # Update progress message
                await context.bot.edit_message_text(
                    chat_id=progress_message.chat_id,
                    message_id=progress_message.message_id,
                    text=f"Uploading... {percent_uploaded:.2f}%\nSpeed: {upload_speed / 1024 / 1024:.2f} MB/s"
                )

        # Upload complete, send the final file
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        logger.error(traceback.format_exc())
        raise

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text.startswith('http'):
        progress_message = await update.message.reply_text("Starting download and processing...")

        local_filename = "downloaded_video.mp4"
        output_filename = "output_video.mp4"
        watermark_path = "watermark.png"
        title_text = "Your Video Title"

        try:
            logger.info(f"Handling message: {message_text}")
            # Download the file with progress tracking
            file_path = await download_file(message_text, local_filename, update, context, progress_message)

            # Process the video (add watermark, title, and timeline)
            logger.info("Starting video processing...")
            add_watermark_title_timeline(file_path, output_filename, title_text, watermark_path)

            # Notify the user and upload the processed file with progress tracking
            logger.info("Uploading the processed video...")
            await upload_file(output_filename, update, context, progress_message)

        except Exception as e:
            logger.error(f"Failed to process the video. Error: {e}")
            await context.bot.edit_message_text(
                chat_id=progress_message.chat_id,
                message_id=progress_message.message_id,
                text=f"Failed to process the video. Error: {e}"
            )
    else:
        await update.message.reply_text("Please provide a valid download link.")

def add_watermark_title_timeline(input_video_path, output_video_path, title_text, watermark_path):
    """Adds a watermark, title, and timeline to the video without processing audio."""
    try:
        logger.debug(f"Processing video: {input_video_path}")
        # Load the video, keeping the original audio
        video_clip = VideoFileClip(input_video_path)

        # Reduce the resolution to prevent resource overuse
        video_clip = video_clip.resize(height=360)

        video_duration = video_clip.duration

        # Create the title text
        title_clip = TextClip(title_text, fontsize=70, color='white').set_duration(video_duration).set_position('top').set_fps(24)

        # Create a timeline (time overlay)
        def time_text(t):
            minutes = int(t // 60)
            seconds = int(t % 60)
            return f"{minutes}:{seconds:02d}"

        timeline_clip = (TextClip(time_text(0), fontsize=40, color='white')
                         .set_duration(video_duration)
                         .set_position(('right', 'bottom'))
                         .set_fps(24))

        # Add watermark if provided
        if watermark_path and os.path.exists(watermark_path):
            watermark_clip = VideoFileClip(watermark_path).resize(height=50).set_duration(video_duration).set_position(('right', 'top'))
            video_clip = CompositeVideoClip([video_clip, title_clip, timeline_clip, watermark_clip])
        else:
            video_clip = CompositeVideoClip([video_clip, title_clip, timeline_clip])

        # Write the output video with the original audio (no audio processing)
        logger.debug(f"Writing video to {output_video_path}")
        video_clip.write_videofile(
            output_video_path,
            codec="libx264",
            audio=True,  # Retain the original audio without re-encoding
            preset="fast",  # Faster encoding preset
            threads=4  # Use multiple threads for faster encoding
        )
        logger.info(f"Video processing completed: {output_video_path}")
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        logger.error(traceback.format_exc())
        raise

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
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)

    # Use polling instead of webhooks
    application.run_polling()

if __name__ == "__main__":
    main()
