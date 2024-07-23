import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import cv2
import numpy as np
import os
import logging
import subprocess

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

To process a video:
1. Send a video file
2. Provide a title
"""
    await update.message.reply_text(help_text)

async def set_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Please send the watermark image.')

async def handle_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        watermark_file = await context.bot.get_file(update.message.photo[-1].file_id)
        await watermark_file.download_to_drive(DEFAULT_WATERMARK_PATH)
        await update.message.reply_text('Watermark image has been set.')
    except Exception as e:
        logger.error(f"Error processing watermark image: {e}")
        await update.message.reply_text('An error occurred while processing the watermark image.')

async def ask_for_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['video_file'] = update.message.video.file_id
    await update.message.reply_text('Please provide a title for the video.')
    return TITLE

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text('Processing your video...')
    await process_video(update, context)
    return ConversationHandler.END

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        video_file_id = context.user_data.get('video_file')
        title = context.user_data.get('title')

        video_file = await context.bot.get_file(video_file_id)
        video_path = video_file.file_path

        # Download the video file
        local_video_path = 'input_video.mp4'
        progress_message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Download progress: 0%")
        await download_file_with_progress(video_path, local_video_path, progress_message, context)

        # Process the video
        processed_video_path = process_video_opencv(local_video_path, title)

        # Send the processed video
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Uploading processed video...")
        with open(processed_video_path, 'rb') as video:
            await context.bot.send_video(chat_id=update.effective_chat.id, video=video)

        # Clean up
        os.remove(local_video_path)
        os.remove(processed_video_path)

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await update.effective_message.reply_text('An error occurred while processing the video.')

def process_video_opencv(video_path: str, title: str) -> str:
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    temp_output = 'temp_output.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

    watermark = cv2.imread(DEFAULT_WATERMARK_PATH, cv2.IMREAD_UNCHANGED)
    if watermark is not None:
        watermark_height = int(height * 0.1)  # 10% of video height
        watermark_width = int(watermark_height * watermark.shape[1] / watermark.shape[0])
        watermark = cv2.resize(watermark, (watermark_width, watermark_height))
        if watermark.shape[2] == 4:  # If the watermark has an alpha channel
            watermark = cv2.cvtColor(watermark, cv2.COLOR_BGRA2BGR)

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Add title (bottom right, medium size)
        title_font_scale = height / 720  # Adjust scale based on video height
        title_thickness = max(1, int(height / 360))  # Adjust thickness based on video height
        title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, title_font_scale, title_thickness)[0]
        title_x = width - title_size[0] - 10
        title_y = height - 10
        cv2.putText(frame, title, (title_x, title_y), cv2.FONT_HERSHEY_SIMPLEX, title_font_scale, (255, 255, 255), title_thickness)

        # Add watermark (top left)
        if watermark is not None:
            watermark_y = 10
            watermark_x = 10
            roi = frame[watermark_y:watermark_y+watermark.shape[0], watermark_x:watermark_x+watermark.shape[1]]
            frame[watermark_y:watermark_y+watermark.shape[0], watermark_x:watermark_x+watermark.shape[1]] = cv2.addWeighted(roi, 1, watermark, 0.3, 0)

        # Add timeline (bottom left)
        current_time = frame_count / fps
        total_time = total_frames / fps
        timeline_text = f"{int(current_time // 60):02d}:{int(current_time % 60):02d} / {int(total_time // 60):02d}:{int(total_time % 60):02d}"
        timeline_font_scale = height / 1080  # Adjust scale based on video height
        timeline_thickness = max(1, int(height / 540))  # Adjust thickness based on video height
        cv2.putText(frame, timeline_text, (10, height - 10), cv2.FONT_HERSHEY_SIMPLEX, timeline_font_scale, (255, 255, 255), timeline_thickness)

        out.write(frame)
        frame_count += 1

    cap.release()
    out.release()

    # Use FFmpeg to copy the audio from the original video to the processed video
    output_path = 'processed_video.mp4'
    ffmpeg_command = [
        'ffmpeg',
        '-i', temp_output,
        '-i', video_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-shortest',
        output_path
    ]
    subprocess.run(ffmpeg_command, check=True)

    # Remove the temporary file
    os.remove(temp_output)

    return output_path

async def download_file_with_progress(url: str, local_path: str, progress_message, context: ContextTypes.DEFAULT_TYPE):
    response = requests.get(url, stream=True)
    total_length = int(response.headers.get('content-length', 0))

    with open(local_path, 'wb') as f:
        downloaded = 0
        last_percentage = 0
        for chunk in response.iter_content(chunk_size=8192):
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
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
