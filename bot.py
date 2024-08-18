import os
import logging
import aiohttp
import time
import asyncio
import traceback
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Replace with your actual bot token
TOKEN = "6343124020:AAFFap55YkVIN_pyXzGtsyTNk2nLeJ0_qRI"

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store user settings
user_settings = {}

# Constants for conversation states
SET_WATERMARK, SET_TITLE, SET_TIMELINE = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Send me a video link, and I will add a watermark, title, and timestamp.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
/settings - Adjust your watermark, title, and timeline settings

You can send a video file or provide a download link for a video file, and the bot will download, add a watermark, title, and timestamp, then send it back.
"""
    await update.message.reply_text(help_text)

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Let's set up your preferences. Please upload a watermark image or type 'skip' to skip setting a watermark."
    )
    return SET_WATERMARK

async def set_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    if update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        watermark_path = f"{user_id}_watermark.png"
        await file.download(watermark_path)
        user_settings[user_id] = {"watermark_path": watermark_path}
        await update.message.reply_text("Watermark set successfully.")
    else:
        user_settings[user_id] = {"watermark_path": None}
        await update.message.reply_text("Watermark skipped.")

    await update.message.reply_text("Please enter your custom title text or type 'skip' to skip.")
    return SET_TITLE

async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    title_text = update.message.text
    if title_text.lower() != "skip":
        user_settings[user_id]["title_text"] = title_text
        await update.message.reply_text(f"Title set to: {title_text}")
    else:
        user_settings[user_id]["title_text"] = "Your Video Title"
        await update.message.reply_text("Title skipped.")

    await update.message.reply_text("Do you want to add a timeline? (yes/no)")
    return SET_TIMELINE

async def set_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    timeline_choice = update.message.text.lower()
    if timeline_choice == "yes":
        user_settings[user_id]["add_timeline"] = True
        await update.message.reply_text("Timeline will be added.")
    else:
        user_settings[user_id]["add_timeline"] = False
        await update.message.reply_text("Timeline will not be added.")

    await update.message.reply_text("Settings saved! You can now send me a video link.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Settings update canceled.")
    return ConversationHandler.END

async def download_file(url: str, file_path: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Downloads the file from the provided URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                with open(file_path, 'wb') as f:
                    f.write(await response.read())
        return file_path
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_pref = user_settings.get(user_id, {
        "watermark_path": None,
        "title_text": "Your Video Title",
        "add_timeline": True
    })

    message_text = update.message.text
    if message_text.startswith('http'):
        local_filename = "downloaded_video.mp4"
        output_filename = "output_video.mp4"

        try:
            # Download the file
            file_path = await download_file(message_text, local_filename, update, context)

            # Process the video
            add_watermark_title_timeline(file_path, output_filename, user_pref["title_text"], user_pref["watermark_path"], user_pref["add_timeline"])

            # Send the processed video
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(output_filename, 'rb'))

        except Exception as e:
            await update.message.reply_text(f"Failed to process the video. Error: {e}")
            logger.error(f"Failed to process the video. Error: {e}")
    else:
        await update.message.reply_text("Please provide a valid download link.")

def add_watermark_title_timeline(input_video_path, output_video_path, title_text, watermark_path, add_timeline):
    """Adds a watermark, title, and optional timeline to the video."""
    try:
        # Load the video, keeping the original audio
        video_clip = VideoFileClip(input_video_path)

        # Reduce the resolution to prevent resource overuse
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

            timeline_clip = (TextClip(time_text(0), fontsize=40, color='white')
                             .set_duration(video_duration)
                             .set_position(('right', 'bottom'))
                             .set_fps(24))
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

        # Write the output video with the original audio (no audio processing)
        final_clip.write_videofile(output_video_path, codec="libx264", audio=True, preset="fast", threads=4)

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise

def main():
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Conversation handler for settings
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('settings', settings)],
        states={
            SET_WATERMARK: [MessageHandler(filters.ALL, set_watermark)],
            SET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_title)],
            SET_TIMELINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_timeline)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(conv_handler)

    # Message handler to capture download links
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
