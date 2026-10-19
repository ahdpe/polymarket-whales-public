# PUBLIC SHELL VERSION
import asyncio
import logging
import aiohttp
import time
import sqlite3
import os
import random
import math
import json
from datetime import datetime, timezone
from decimal import Decimal
from collections import OrderedDict
from typing import Optional, Tuple
from config import POLYGONSCAN_API_KEY
from core.utils import polymarket_event_url
logger = logging.getLogger(__name__)
DATA_API_URL = 'https://data-api.polymarket.com'
GAMMA_PUBLIC_PROFILE_URL = 'https://gamma-api.polymarket.com/public-profile'
DATA_API_ACTIVITY_LIMIT = 500
DATA_API_ACTIVITY_MAX_OFFSET = 5000
try:
    POLL_INTERVAL = max(1.0, float(os.getenv('TRADES_POLL_INTERVAL_SEC', '10')))
except (TypeError, ValueError):
    POLL_INTERVAL = 10.0
try:
    STARTUP_MAX_ALERT_AGE_SEC = max(0, int(os.getenv('STARTUP_MAX_ALERT_AGE_SEC', '900')))
except (TypeError, ValueError):
    STARTUP_MAX_ALERT_AGE_SEC = 900
MAX_LRU_SIZE = 10000
DB_PATH = 'data/trades.db'
try:
    TTL_HOURS = max(1.0, float(os.getenv('DEDUP_TTL_HOURS', '6')))
except (TypeError, ValueError):
    TTL_HOURS = 6.0
CLEANUP_INTERVAL_SEC = 3600
try:
    CLEANUP_BATCH_SIZE = max(100, int(os.getenv('DEDUP_CLEANUP_BATCH_SIZE', '5000')))
except (TypeError, ValueError):
    CLEANUP_BATCH_SIZE = 5000
try:
    CLEANUP_BATCH_PAUSE_SEC = max(0.0, float(os.getenv('DEDUP_CLEANUP_BATCH_PAUSE_SEC', '0.05')))
except (TypeError, ValueError):
    CLEANUP_BATCH_PAUSE_SEC = 0.05
SQLITE_BUSY_TIMEOUT_MS = 5000
RECENT_WALLETS_WINDOW = 48 * 3600
WALLET_ACTIVITY_CHECK_COOLDOWN = 300
MAX_CONCURRENT_CALLBACKS = 50
MAX_PENDING_CALLBACK_TASKS = 5000
CALLBACK_QUEUE_INFO_THRESHOLD = 200
CALLBACK_QUEUE_WARN_THRESHOLD = 1000
CALLBACK_HEALTH_LOG_INTERVAL = 30

def _env_int(name: str, default: int) -> int:
    pass

class BoundedCache(OrderedDict):
    """Dict with LRU eviction and periodic removal of expired entries.

    ``is_expired(entry, now)`` decides when an entry is physically dropped;
    freshness checks at read sites stay unchanged.
    """

    def __init__(self, max_size: int, is_expired, prune_every: int=500):
        pass

    def get(self, key, default=None):
        pass

    def __setitem__(self, key, value):
        pass

    def prune(self, now: Optional[float]=None) -> int:
        pass

    def copy(self):
        pass
POSITIONS_CACHE_TTL = 60
POSITIONS_CACHE_STALE_MAX = _env_int('POSITIONS_CACHE_STALE_MAX_SEC', 3600)
_positions_cache = BoundedCache(_env_int('POSITIONS_CACHE_MAX_SIZE', 20000), lambda entry, now: now - entry['ts'] >= POSITIONS_CACHE_STALE_MAX)
WALLET_AGE_CACHE_TTL = 7 * 24 * 60 * 60
WALLET_AGE_FALLBACK_TTL = 600
_WALLET_AGE_STABLE_SOURCES = {'etherscan', 'gamma_profile', 'polymarket_full'}

def _wallet_age_entry_expired(entry, now) -> bool:
    pass
_wallet_age_cache = BoundedCache(_env_int('WALLET_AGE_CACHE_MAX_SIZE', 50000), _wallet_age_entry_expired)

def norm_ts(x, default=0.0) -> float:
    """Normalize timestamp to seconds (handle ms)."""
    pass

def norm_ts_int(x, default=0) -> int:
    """Normalize timestamp to integer seconds (handle ms)."""
    pass

def parse_profile_created_at(value, now=None) -> Optional[float]:
    """Parse Gamma profile creation time, rejecting invalid or future values."""
    pass

def oldest_activity_timestamp(activities) -> Optional[float]:
    """Return the oldest valid timestamp without assuming API sort order."""
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

    def add_batch(self, keys, *, aggregation_state=None):
        pass

    def get_aggregation_state(self):
        pass

    def cleanup_due(self) -> bool:
        pass

    def delete_expired_batched(self, batch_size=None, pause_sec=None) -> int:
        """Delete expired keys in small batches (no VACUUM).

        Runs in a worker thread with its own connection, so the event loop and
        self.conn are never blocked for long; each batch holds the write lock
        only briefly and add_batch() waits via busy_timeout.
        """
        pass

    def close(self):
        pass

class TradeAggregator:

    def __init__(self, window_sec=60, min_alert_usd=500, *, on_reset=None):
        pass

    def export_state(self, *, incomplete_poll=False):
        pass

    def restore_state(self, state, *, max_age_sec=None):
        pass

    def _get_key(self, trade):
        pass

    def process_trade(self, trade):
        pass

    def _snapshot(self, series):
        pass

    def cleanup(self, *, max_ready=None):
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

    def _schedule_dedup_cleanup(self):
        """Start the hourly batched trades.db cleanup in a worker thread."""
        pass

    def _prune_recent_wallets(self, now: float):
        pass

    async def get_trader_positions(self, proxy_wallet, retries=3, use_stale_cache=False):
        pass

    async def check_wallet_has_position_safe(self, proxy_wallet: str, condition_id: str) -> tuple[float, str]:
        """
        Check position with explicit status (for insider buffer / sold detection).

        Returns:
            (value_usd, status)
            status:
              'found'    — matching conditionId present (value may be 0 in edge cases)
              'empty'    — HTTP OK, full paginated scan completed, no matching position
              'error'    — timeout, non-200, or invalid payload (do NOT treat as "sold")
        """
        pass

    async def get_wallet_market_position_financials(self, proxy_wallet: str, condition_id: str, outcome: Optional[str]=None) -> Tuple[float, float, str]:
        """
        Sum currentValue (mark-to-market) and initialValue (cost basis / amount invested)
        for positions matching condition_id and optional outcome (YES/NO, case-insensitive).

        Returns:
            (current_value_usd, initial_value_usd, status)
            status: 'found' if at least one matching row exists, else 'empty' or 'error'.
        """
        pass

    async def confirm_wallet_has_no_position(self, proxy_wallet: str, condition_id: str, *, rounds: int=3, pause_sec: float=0.65) -> bool:
        """
        Return True only if every round reports status 'empty' with value 0.
        False if any round errors, finds value > 0, or returns 'found' with value > 0.

        Used before marking insider buffer trades as sold — avoids false positives
        from transient API issues.
        """
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

    def _aggregate_poll_batch(self, callback, trades, *, complete=True, seen_keys=()):
        pass

    def _reset_aggregation(self):
        pass

    def _map_activity_to_trade(self, activity: dict, activity_type: str) -> dict:
        pass

    async def poll_activities(self, callback, interval: int=15):
        pass

    def get_stats(self):
        pass

def get_wallet_age_cache():
    pass
