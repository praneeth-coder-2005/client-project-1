import os
import logging
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Replace with your actual bot token and webhook URL
TOKEN = "6343124020:AAFFap55YkVIN_pyXzGtsyTNk2nLeJ0_qRI"
WEBHOOK_URL = "https://test-1-9bmd.onrender.com/6343124020:AAFFap55YkVIN_pyXzGtsyTNk2nLeJ0_qRI"

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def download_file(url: str, file_path: str):
    """Downloads the file from the provided URL and saves it locally."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
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

def add_watermark_title_timeline(input_video_path, output_video_path, title_text, watermark_path):
    """Adds a watermark, title, and timeline to the video."""
    video_clip = VideoFileClip(input_video_path)
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

    # Write the output video
    video_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text.startswith('http'):
        download_url = message_text.strip()
        await update.message.reply_text("Starting download and processing...")

        local_filename = "downloaded_video.mp4"  # Adjust filename based on file type if needed
        output_filename = "output_video.mp4"
        watermark_path = "watermark.png"  # Path to your watermark file (should be available in the bot's directory)
        title_text = "Your Video Title"  # Example title text

        try:
            # Download the file
            file_path = await download_file(download_url, local_filename)

            # Process the video (add watermark, title, and timeline)
            add_watermark_title_timeline(file_path, output_filename, title_text, watermark_path)

            # Notify the user and upload the processed file
            await update.message.reply_text(f"Video processed successfully: {output_filename}")
            with open(output_filename, 'rb') as f:
                await update.message.reply_document(document=f, filename=output_filename)

        except Exception as e:
            await update.message.reply_text(f"Failed to process the video. Error: {e}")
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
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)

    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL  # Static webhook URL
    )

if __name__ == '__main__':
    main()
