# PUBLIC SHELL VERSION
"""Script to send broadcast message to all users with detailed statistics."""
import asyncio
import json
import os
import sys
from aiogram import Bot
from config import TELEGRAM_BOT_TOKEN, OWNER_ID
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'user_settings.json')

def load_user_ids():
    """Load all user chat IDs from settings."""
    pass

async def send_broadcast():
    """Send broadcast message to all users."""
    pass
if __name__ == '__main__':
    asyncio.run(send_broadcast())