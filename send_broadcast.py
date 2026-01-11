#!/usr/bin/env python3
"""Script to send broadcast message to all users with detailed statistics."""
import asyncio
import json
import os
import sys
from aiogram import Bot
from config import TELEGRAM_BOT_TOKEN, OWNER_ID

# Load user settings to get all chat_ids
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'user_settings.json')

def load_user_ids():
    """Load all user chat IDs from settings."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                filters = data.get('filters', {})
                # Convert string keys to int
                return [int(k) for k in filters.keys()]
    except Exception as e:
        print(f"Error loading user IDs: {e}")
    return []

async def send_broadcast():
    """Send broadcast message to all users."""
    # Read message from file
    message_file = os.path.join(os.path.dirname(__file__), 'update_message_en.txt')
    try:
        with open(message_file, 'r', encoding='utf-8') as f:
            message_text = f.read().strip()
    except Exception as e:
        print(f"Error reading message file: {e}")
        return
    
    if not message_text:
        print("Message file is empty!")
        return
    
    # Initialize bot
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Load all user IDs
    user_ids = load_user_ids()
    
    if not user_ids:
        print("No users found!")
        return
    
    print(f"Found {len(user_ids)} users. Starting broadcast...")
    print(f"Message:\n{message_text}\n")
    print("-" * 50)
    
    # Statistics
    sent = []
    failed = []
    
    # Send to all users
    for chat_id in user_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="Markdown"
            )
            sent.append(chat_id)
            print(f"✅ Sent to {chat_id}")
        except Exception as e:
            error_msg = str(e)
            failed.append((chat_id, error_msg))
            print(f"❌ Failed to send to {chat_id}: {error_msg}")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.1)
    
    # Print summary
    print("-" * 50)
    print(f"\n📊 Broadcast Summary:")
    print(f"✅ Successfully sent: {len(sent)}/{len(user_ids)}")
    print(f"❌ Failed: {len(failed)}/{len(user_ids)}")
    
    if failed:
        print(f"\n❌ Failed to send to {len(failed)} users:")
        for chat_id, error in failed:
            print(f"  • Chat ID {chat_id}: {error}")
    else:
        print("\n✅ Message delivered to all users!")
    
    # Send summary to owner
    try:
        summary = f"""📢 **Broadcast Complete**

✅ Successfully sent: {len(sent)}/{len(user_ids)}
❌ Failed: {len(failed)}/{len(user_ids)}"""
        
        if failed:
            failed_list = "\n".join([f"• Chat ID {cid}: {err[:50]}" for cid, err in failed[:10]])
            if len(failed) > 10:
                failed_list += f"\n... and {len(failed) - 10} more"
            summary += f"\n\n❌ **Failed deliveries:**\n{failed_list}"
        
        await bot.send_message(
            chat_id=OWNER_ID,
            text=summary,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Warning: Could not send summary to owner: {e}")
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_broadcast())
