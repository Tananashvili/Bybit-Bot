import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

bot_token = os.getenv('bot_token')
chat_id = os.getenv('chat_id')

# Initialize bot and dispatcher
bot = Bot(token=bot_token)
dp = Dispatcher()

# Function to send messages asynchronously
async def send_telegram_message(message: str):
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

# Handle incoming text messages
async def handle_message(message: types.Message):
    user_message = message.text

    # Check for specific commands or keywords
    if user_message == "start_process":
        await send_telegram_message("Starting the process now!")
        # Trigger server-side action here
    elif user_message == "stop_process":
        await send_telegram_message("Stopping the process.")
        # Trigger server-side stop action
    else:
        await send_telegram_message("Unrecognized command.")
        # Optionally, perform other actions based on the user's input

# Main function to run the bot
async def main():
    # Register the handler for text messages (no filter)
    dp.message.register(handle_message)

    # Start polling for updates
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

# Run the bot
if __name__ == '__main__':
    asyncio.run(main())
