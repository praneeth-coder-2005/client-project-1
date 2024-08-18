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
    level=logging.INFO
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
    """Downloads the file with optimized speed."""
    try:
        logger.info(f"Starting download from {url} to {file_path}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=TIMEOUT)) as session:
            async with session.get(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                bytes_downloaded = 0
                retries = 0

                start_time = time.time()

                # Open the file for writing in binary mode
                with open(file_path, 'wb') as f:
                    while True:
                        try:
                            chunk = await response.content.read(CHUNK_SIZE)
                            if not chunk:
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

                logger.info(f"File downloaded successfully: {file_path}")
                return file_path
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        logger.error(traceback.format_exc())
        raise

async def process_video(input_video_path, output_video_path, title_text="Your Video Title", watermark_path=None, add_timeline=True):
    """Processes the video by adding a watermark, title, and timeline."""
    try:
        logger.info("Starting video processing...")
        
        # Load the video, keeping the original audio
        video_clip = VideoFileClip(input_video_path)

        # Reduce the resolution and speed up the process
        video_clip = video_clip.resize(height=360)

        video_duration = video_clip.duration

        # Create the title text
        title_clip = TextClip(title_text, fontsize=70, color='white').set_duration(video_duration).set_position('top').set_fps(24)

        # Create a timeline (time overlay)
        if add_timeline:
            def time_text(t):
                minutes = int(t // 60)
                seconds = int(t % 60)
                return f"{minutes}:{seconds:02d}"

            timeline_clip = TextClip(time_text(0), fontsize=40, color='white').set_duration(video_duration).set_position(('right', 'bottom')).set_fps(24)
        else:
            timeline_clip = None

        # Add watermark if provided
        if watermark_path and os.path.exists(watermark_path):
            watermark_clip = VideoFileClip(watermark_path).resize(height=50).set_duration(video_duration).set_position(('right', 'top'))
            video_clips = [video_clip, title_clip, watermark_clip]
        else:
            video_clips = [video_clip, title_clip]

        if timeline_clip:
            video_clips.append(timeline_clip)

        final_clip = CompositeVideoClip(video_clips)

        # Write the output video with faster processing
        final_clip.write_videofile(output_video_path, codec="libx264", audio=True, preset="ultrafast", threads=8)

        logger.info(f"Video processing completed: {output_video_path}")
    except Exception as e:
        logger.error(f"Error processing video: {e}")
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

            # Process the video
            await process_video(file_path, output_filename)

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
