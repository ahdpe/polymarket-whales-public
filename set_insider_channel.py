# PUBLIC SHELL VERSION
"""Set insider alerts channel_id."""
import sys
from storage import alerts_storage
if __name__ == '__main__':
    channel_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not channel_id:
        print('Usage: python set_insider_channel.py <channel_id>')
        sys.exit(1)
    alerts_storage.init_db()
    alerts_storage.save_setting('channel_id', channel_id)
    saved_value = alerts_storage.get_setting('channel_id', '')
    if saved_value == channel_id:
        print(f'✅ Channel ID установлен: {channel_id}')
    else:
        print(f'❌ Ошибка: ожидалось {channel_id}, получено {saved_value}')
        sys.exit(1)