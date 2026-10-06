# PUBLIC SHELL VERSION
import asyncio
import os
import json
from aiogram import Bot
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MESSAGE = '➕ Update\nNow you can manually add traders to Favorites (⭐ → ➕ Add). \nSend a Polymarket profile link (polymarket.com/profile/0x123...) or wallet address (0x123...).'

async def broadcast():
    pass
if __name__ == '__main__':
    asyncio.run(broadcast())