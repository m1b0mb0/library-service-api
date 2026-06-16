from asgiref.sync import async_to_sync
from telegram import Bot
from django.conf import settings


@async_to_sync
async def send_telegram_message(message: str):
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=message)
