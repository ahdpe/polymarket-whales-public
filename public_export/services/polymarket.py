# PUBLIC SHELL VERSION
import asyncio
import logging
import aiohttp
import time
import sqlite3
import os
from decimal import Decimal
from collections import OrderedDict
from config import POLYGONSCAN_API_KEY
logger = logging.getLogger(__name__)
DATA_API_URL = 'https://data-api.polymarket.com'
POLL_INTERVAL = 3
MAX_LRU_SIZE = 10000
DB_PATH = 'data/trades.db'
TTL_HOURS = 72
POSITIONS_CACHE_TTL = 60
_positions_cache = {}
WALLET_AGE_CACHE_TTL = 7 * 24 * 60 * 60
_wallet_age_cache = {}

class TradePersistence:

    def __init__(self, db_path=DB_PATH):
        pass

    def _init_db(self):
        pass

    def _normalize_decimal(self, val):
        pass

    def generate_key(self, trade):
        pass

    def is_seen(self, key):
        pass

    def _add_to_lru(self, key):
        pass

    def add_batch(self, keys):
        pass

    def cleanup(self):
        pass

    def close(self):
        pass

class TradeAggregator:

    def __init__(self, window_sec=60, min_alert_usd=500):
        pass

    def _get_key(self, trade):
        pass

    def process_trade(self, trade):
        """
        Process a new trade.
        Returns: aggregated_trade dict if a series triggers an alert, else None.
        """
        pass

    def cleanup(self):
        """Garbage collect old series."""
        pass

class PolymarketService:

    def __init__(self):
        pass

    async def _fetch_recent_trades(self, limit=10000, offset=0, min_size=10):
        """Fetch recent trades from Data API."""
        pass

    async def get_trader_positions(self, proxy_wallet):
        """
        Fetch trader's open positions from Data API.
        Returns: {"pnl_usd": float, "pnl_percent": float, "open_count": int, "total_value": float, "alltime_pnl": float}
        Uses TTL cache (60 seconds).
        """
        pass

    async def get_trader_first_activity(self, proxy_wallet):
        """
        Fetch trader's first activity timestamp from Data API.
        Returns: Unix timestamp (seconds) of first activity, or None.
        Uses TTL cache (5 minutes).
        """
        pass

    async def poll_trades(self, callback, interval=POLL_INTERVAL):
        """
        Poll for new trades every `interval` seconds.
        Uses pagination, SQLite persistence, and Aggregation.
        """
        pass

    def get_stats(self):
        """Get service statistics."""
        pass

def get_wallet_age_cache():
    """Get copy of wallet age cache for debugging."""
    pass