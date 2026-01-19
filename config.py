import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# We will start with a placeholder, but in main.py we might ask user or just print it.
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") 

# Polymarket CLOB API credentials
POLY_API_KEY = os.getenv("POLY_API_KEY")
POLY_API_SECRET = os.getenv("POLY_API_SECRET")
POLY_PASSPHRASE = os.getenv("POLY_PASSPHRASE")
POLY_WALLET_ADDRESS = os.getenv("POLY_WALLET_ADDRESS")
POLY_PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY") 

# PolygonScan API Keys (Optional, for accurate wallet age)
# Supports multiple keys separated by comma for load balancing
_polygonscan_keys_raw = os.getenv("POLYGONSCAN_API_KEYS", "") or os.getenv("POLYGONSCAN_API_KEY", "")
POLYGONSCAN_API_KEYS = [k.strip() for k in _polygonscan_keys_raw.split(",") if k.strip()]
POLYGONSCAN_API_KEY = POLYGONSCAN_API_KEYS[0] if POLYGONSCAN_API_KEYS else None  # Backward compatibility

# Round Robin counter for API key rotation
_polygonscan_key_index = 0

def get_polygonscan_api_key():
    """Get next PolygonScan API key using Round Robin rotation."""
    global _polygonscan_key_index
    if not POLYGONSCAN_API_KEYS:
        return None
    key = POLYGONSCAN_API_KEYS[_polygonscan_key_index % len(POLYGONSCAN_API_KEYS)]
    _polygonscan_key_index += 1
    return key

# Twitter API (for posting alerts)
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

CLOB_API_URL = "https://clob.polymarket.com"
WS_URL = "wss://ws-gamma-clob.polymarket.com/" # Gamma is usually testnet, CLOB prod is `wss://ws-clob.polymarket.com/` ?
# Note: "Gamma" is often used in docs, but the production CLOB is different.
# Let's use the production endpoint if possible. 
# Production HTTP: https://clob.polymarket.com/
# Production WS: wss://ws-clob.polymarket.com/ws (check docs, usually /ws or just root)
# Found correct host via nslookup: ws-subscriptions-clob.polymarket.com
PROD_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

FILTERS = [
    {"min": 100000, "emoji": "🔥 МЕГА КИТ", "emoji_en": "🔥 MEGA WHALE", "name": "Мега Кит"},
    {"min": 50000, "emoji": "⚡ СУПЕР КИТ", "emoji_en": "⚡ SUPER WHALE", "name": "Супер Кит"},
    {"min": 25000, "emoji": "🐋 КИТ", "emoji_en": "🐋 WHALE", "name": "Кит"},
    {"min": 10000, "emoji": "🦈 АКУЛА", "emoji_en": "🦈 SHARK", "name": "Акула"},
    {"min": 5000, "emoji": "🐬 ДЕЛЬФИН", "emoji_en": "🐬 DOLPHIN", "name": "Дельфин"},
    {"min": 2000, "emoji": "🐟 РЫБА", "emoji_en": "🐟 FISH", "name": "Рыба"},
    {"min": 500, "emoji": "🦐 КРЕВЕТКА", "emoji_en": "🦐 SHRIMP", "name": "Креветка"},
]

# Bot owner ID (for admin commands)
OWNER_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
