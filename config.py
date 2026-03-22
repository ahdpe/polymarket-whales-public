# PUBLIC SHELL VERSION
import os
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
POLY_API_KEY = os.getenv('POLY_API_KEY')
POLY_API_SECRET = os.getenv('POLY_API_SECRET')
POLY_PASSPHRASE = os.getenv('POLY_PASSPHRASE')
POLY_WALLET_ADDRESS = os.getenv('POLY_WALLET_ADDRESS')
POLY_PRIVATE_KEY = os.getenv('POLY_PRIVATE_KEY')
_poly_keys = os.getenv('POLYGONSCAN_API_KEY', '')
if ',' in _poly_keys:
    POLYGONSCAN_API_KEY = [k.strip() for k in _poly_keys.split(',') if k.strip()]
else:
    POLYGONSCAN_API_KEY = _poly_keys
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
CLOB_API_URL = 'https://clob.polymarket.com'
WS_URL = 'wss://ws-gamma-clob.polymarket.com/'
PROD_WS_URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
FILTERS = [{'min': 100000, 'emoji': '🔥 МЕГА КИТ', 'emoji_en': '🔥 MEGA WHALE', 'name': 'Мега Кит'}, {'min': 50000, 'emoji': '⚡ СУПЕР КИТ', 'emoji_en': '⚡ SUPER WHALE', 'name': 'Супер Кит'}, {'min': 25000, 'emoji': '🐋 КИТ', 'emoji_en': '🐋 WHALE', 'name': 'Кит'}, {'min': 10000, 'emoji': '🦈 АКУЛА', 'emoji_en': '🦈 SHARK', 'name': 'Акула'}, {'min': 5000, 'emoji': '🐬 ДЕЛЬФИН', 'emoji_en': '🐬 DOLPHIN', 'name': 'Дельфин'}, {'min': 2000, 'emoji': '🐟 РЫБА', 'emoji_en': '🐟 FISH', 'name': 'Рыба'}, {'min': 500, 'emoji': '🦐 КРЕВЕТКА', 'emoji_en': '🦐 SHRIMP', 'name': 'Креветка'}]
OWNER_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))
RETRY_SHORT_MAX = int(os.getenv('RETRY_SHORT_MAX', '10'))
FAIL_STREAK_MUTE_THRESHOLD = int(os.getenv('FAIL_STREAK_MUTE_THRESHOLD', '3'))
_mute_durations_str = os.getenv('MUTE_DURATIONS', '3600,21600,86400')
MUTE_DURATIONS = {1: int(_mute_durations_str.split(',')[0]), 2: int(_mute_durations_str.split(',')[1]) if len(_mute_durations_str.split(',')) > 1 else 21600, 3: int(_mute_durations_str.split(',')[2]) if len(_mute_durations_str.split(',')) > 2 else 86400}
HOTFIX_CHAT_ID = int(os.getenv('HOTFIX_CHAT_ID', '1580869819'))
HOTFIX_THRESHOLD = int(os.getenv('HOTFIX_THRESHOLD', '60'))
HOTFIX_MUTE = int(os.getenv('HOTFIX_MUTE', '86400'))
QUEUE_MAX_SIZE = int(os.getenv('QUEUE_MAX_SIZE', '10000'))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', '5'))
GLOBAL_RATE = float(os.getenv('GLOBAL_RATE', '25'))
PER_CHAT_RATE = float(os.getenv('PER_CHAT_RATE', '0.5'))