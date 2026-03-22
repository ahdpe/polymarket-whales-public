# PUBLIC SHELL VERSION
import asyncio
import logging
import aiohttp
import time
import sqlite3
import os
import random
from decimal import Decimal
from collections import OrderedDict
from config import POLYGONSCAN_API_KEY
logger = logging.getLogger(__name__)
DATA_API_URL = 'https://data-api.polymarket.com'
POLL_INTERVAL = 3
MAX_LRU_SIZE = 10000
DB_PATH = 'data/trades.db'
TTL_HOURS = 72
SQLITE_BUSY_TIMEOUT_MS = 5000
RECENT_WALLETS_WINDOW = 48 * 3600
WALLET_ACTIVITY_CHECK_COOLDOWN = 300
MAX_CONCURRENT_CALLBACKS = 50
MAX_PENDING_CALLBACK_TASKS = 5000
CALLBACK_QUEUE_INFO_THRESHOLD = 200
CALLBACK_QUEUE_WARN_THRESHOLD = 1000
CALLBACK_HEALTH_LOG_INTERVAL = 30
POSITIONS_CACHE_TTL = 60
_positions_cache = {}
WALLET_AGE_CACHE_TTL = 7 * 24 * 60 * 60
WALLET_AGE_FALLBACK_TTL = 600
_wallet_age_cache = {}

def norm_ts(x, default=0.0) -> float:
    """Normalize timestamp to seconds (handle ms)."""
    pass

def norm_ts_int(x, default=0) -> int:
    """Normalize timestamp to integer seconds (handle ms)."""
    pass

class TradePersistence:

    def __init__(self, db_path=DB_PATH):
        pass

    def _init_db(self):
        pass

    def _normalize_decimal(self, val):
        pass

    def generate_key(self, trade: dict) -> str:
        pass

    def is_seen(self, key: str) -> bool:
        pass

    def _add_to_lru(self, key: str):
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
        pass

    def cleanup(self):
        pass

    def reset_aggregator(self) -> int:
        """Clear all aggregation state. Call when filters change significantly or bot stops."""
        pass

class PolymarketService:

    def __init__(self):
        pass

    async def _run_callback(self, callback, trade_data: dict):
        """Run callback with bounded concurrency to prevent event-loop overload."""
        pass

    def _schedule_callback(self, callback, trade_data: dict):
        """Schedule callback task with a hard cap on pending tasks."""
        pass

    def _log_callback_queue_health(self):
        """Periodic health log for callback queue to aid production monitoring."""
        pass

    def clear_callback_queue(self) -> int:
        """Cancel all pending callback tasks. Call when bot is stopped."""
        pass

    async def _fetch_recent_activities(self, session, user_address, activity_type, limit=50, offset=0):
        pass

    def _seen_activity_add(self, activity_id: str, ts: float):
        pass

    def _seen_activity_has(self, activity_id: str) -> bool:
        pass

    async def _fetch_recent_trades(self, session, limit=10000, offset=0, min_size=10):
        pass

    def _prune_recent_wallets(self, now: float):
        pass

    async def get_trader_positions(self, proxy_wallet, retries=3, use_stale_cache=False):
        pass

    async def check_wallet_has_position(self, proxy_wallet: str, condition_id: str) -> float:
        """
        Check if a wallet currently holds a position on a specific market.
        
        Args:
            proxy_wallet: The wallet address to check
            condition_id: The market's conditionId (same as market_id in alerts)
        
        Returns:
            Position value in USD if wallet holds position, 0.0 otherwise
        """
        pass

    async def get_trader_first_activity(self, proxy_wallet, bypass_cache=False):
        pass

    async def poll_trades(self, callback, interval=POLL_INTERVAL):
        pass

    def _map_activity_to_trade(self, activity: dict, activity_type: str) -> dict:
        pass

    async def poll_activities(self, callback, interval: int=15):
        pass

    def get_stats(self):
        pass

def get_wallet_age_cache():
    pass