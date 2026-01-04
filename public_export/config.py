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
POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_API_KEY')
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
CLOB_API_URL = 'https://clob.polymarket.com'
WS_URL = 'wss://ws-gamma-clob.polymarket.com/'
PROD_WS_URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
FILTERS = [{'min': 100000, 'emoji': '🔥 МЕГА КИТ', 'emoji_en': '🔥 MEGA WHALE', 'name': 'Мега Кит'}, {'min': 50000, 'emoji': '⚡ СУПЕР КИТ', 'emoji_en': '⚡ SUPER WHALE', 'name': 'Супер Кит'}, {'min': 25000, 'emoji': '🐋 КИТ', 'emoji_en': '🐋 WHALE', 'name': 'Кит'}, {'min': 10000, 'emoji': '🦈 АКУЛА', 'emoji_en': '🦈 SHARK', 'name': 'Акула'}, {'min': 5000, 'emoji': '🐬 ДЕЛЬФИН', 'emoji_en': '🐬 DOLPHIN', 'name': 'Дельфин'}, {'min': 2000, 'emoji': '🐟 РЫБА', 'emoji_en': '🐟 FISH', 'name': 'Рыба'}, {'min': 500, 'emoji': '🦐 КРЕВЕТКА', 'emoji_en': '🦐 SHRIMP', 'name': 'Креветка'}]
OWNER_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))