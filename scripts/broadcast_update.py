import asyncio
import os
import json
from aiogram import Bot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Message to broadcast
MESSAGE = """➕ Update
Now you can manually add traders to Favorites (⭐ → ➕ Add). 
Send a Polymarket profile link (polymarket.com/profile/0x123...) or wallet address (0x123...)."""

async def broadcast():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in env")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Load users
    try:
        with open('user_settings.json', 'r') as f:
            data = json.load(f)
            # Users are keys in 'filters' dict (or any other config dict)
            user_ids = list(data.get('filters', {}).keys())
    except FileNotFoundError:
        print("Error: user_settings.json not found")
        return

    print(f"Found {len(user_ids)} users. Starting broadcast...")
    
    sent = 0
    failed = 0
    
    for chat_id in user_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=MESSAGE, parse_mode="Markdown")
            sent += 1
            # Add small delay to avoid hitting limits
            await asyncio.sleep(0.05) 
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")
            failed += 1
            
    print(f"Broadcast complete! Sent: {sent}, Failed: {failed}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(broadcast())
