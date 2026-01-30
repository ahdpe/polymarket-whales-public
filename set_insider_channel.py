#!/usr/bin/env python3
"""Set insider alerts channel_id."""
import sys
from storage import alerts_storage

if __name__ == "__main__":
    channel_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not channel_id:
        print("Usage: python set_insider_channel.py <channel_id>")
        sys.exit(1)
    
    # Initialize DB
    alerts_storage.init_db()
    
    # Save channel_id setting
    alerts_storage.save_setting('channel_id', channel_id)
    
    # Verify it was saved
    saved_value = alerts_storage.get_setting('channel_id', '')
    if saved_value == channel_id:
        print(f"✅ Channel ID установлен: {channel_id}")
    else:
        print(f"❌ Ошибка: ожидалось {channel_id}, получено {saved_value}")
        sys.exit(1)
