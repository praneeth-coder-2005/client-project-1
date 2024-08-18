import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Replace with your actual bot token and the webhook URL
TOKEN = os.environ.get('TOKEN')  # Set this in your environment variables in Render
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')  # This should be your Render public URL

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text.startswith('http'):
        await update.message.reply_text("Handling download link...")
        # Here, you can implement the download functionality as described earlier.
        await update.message.reply_text(f"Received download link: {message_text}")
    else:
        await update.message.reply_text("Please provide a valid download link.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text('An unexpected error occurred.')

def main():
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add the command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Add a message handler to capture text messages (download links)
    application.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Set up error handling
    application.add_error_handler(error_handler)

    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),  # Use PORT from environment or default to 8443
        url_path=TOKEN,
        webhook_url=f"https://test-1-9bmd.onrender.com/6343124020:AAFFap55YkVIN_pyXzGtsyTNk2nLeJ0_qRI"  # Public URL on Render for Telegram to reach your bot
    )

if __name__ == '__main__':
    main()
