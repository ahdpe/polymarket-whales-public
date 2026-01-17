# PUBLIC SHELL VERSION
"""
Twitter integration for posting whale alerts.
Isolated from main bot functionality - only activates if Twitter keys are configured.

Anti-spam & rate-limit protection:
- Minimum 25 min interval between tweets
- 6 hour pause on 403 Forbidden (no retries)
- Only BUY signals (no SELL)
- Only probability 1-99% (exclude near-resolved markets)
"""
import logging
import json
import os
import asyncio
import time
import random
from typing import Optional
logger = logging.getLogger(__name__)
TWITTER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_settings.json')
TWITTER_QUEUE_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_queue.json')
DEFAULT_TWEET_INTERVAL_SEC = 25 * 60
PAUSE_ON_403_SEC = 6 * 60 * 60
PROBABILITY_OPTIONS = {'any': None, '1_99': (0.01, 0.99), '5_95': (0.05, 0.95), '10_90': (0.1, 0.9)}
MAX_TWEETS_PER_24H = 17
TWEET_WINDOW_SEC = 24 * 60 * 60
INSIDER_TEMPLATES = ['Fresh wallet with heavy focus. Only {pos_count} active position(s). Betting {amount} straight out of the gate. 👀', 'Laser focus? 🎯 Brand new wallet ignoring everything else to deploy {amount} on this outcome.', 'Single target detected. No history, minimal positions. Just a massive {amount} bet on this specific market.', 'Unusual market pattern. Large volume ({amount}) from a source with zero prior history.', 'Anomaly detected. A silent wallet suddenly wakes up with a major position. Worth monitoring.', 'Pattern watch: High-confidence trade from a completely fresh wallet. No previous track record.', 'Straight to business. 💼 Fresh wallet, no warmup trades. Starts directly with a {amount} position.', 'Big entry, zero history. Just activated and dropping {amount}. Who is this?', 'Aggressive newcomer. Skipping the small trades. First major move is a {amount} bet here.', 'Smart tracking or something else? 🤔 Brand new wallet bets {amount} on this single outcome.', 'Gut feeling or calculations? Fresh wallet stakes {amount} immediately after funding.', 'What did they see? 👀 {amount} flows into this market from a wallet with no history.']
DEFAULT_SETTINGS = {'enabled': False, 'min_alert_usd': 100000, 'min_alert_insider_usd': 20000, 'max_insider_age_days': 2.0, 'max_insider_positions': 3, 'tweet_timestamps': [], 'paused_until': 0, 'interval_minutes': 25, 'probability_filter': '1_99', 'allow_sell': False, 'allow_split': False, 'allow_merge': False, 'allow_redeem': False, 'categories': {'crypto': True, 'sports': True, 'other': True}}
_twitter_settings = None

def _load_settings() -> dict:
    """Load Twitter settings from file."""
    pass

def _save_settings():
    """Save Twitter settings to file."""
    pass

def get_twitter_settings() -> dict:
    """Get current Twitter settings."""
    pass

def set_twitter_min_alert(min_usd: int) -> None:
    """Set minimum USD value for Twitter alerts."""
    pass

def set_twitter_enabled(enabled: bool) -> None:
    """Enable or disable Twitter posting."""
    pass

def is_twitter_enabled() -> bool:
    """Check if Twitter posting is enabled."""
    pass

def get_twitter_min_alert() -> int:
    """Get minimum USD value for Twitter alerts."""
    pass

def get_twitter_insider_min() -> int:
    """Get minimum USD value for INSIDER Twitter alerts."""
    pass

def set_twitter_insider_min(min_usd: int) -> None:
    """Set minimum USD value for INSIDER Twitter alerts."""
    pass

def get_twitter_insider_max_age() -> float:
    """Get max wallet age (days) for INSIDER Twitter alerts."""
    pass

def set_twitter_insider_max_age(days: float) -> None:
    """Set max wallet age (days) for INSIDER Twitter alerts."""
    pass

def get_twitter_insider_max_positions() -> int:
    """Get max positions for INSIDER Twitter alerts."""
    pass

def set_twitter_insider_max_positions(count: int) -> None:
    """Set max positions for INSIDER Twitter alerts."""
    pass

def get_twitter_interval() -> int:
    """Get interval between tweets in minutes."""
    pass

def set_twitter_interval(minutes: int) -> None:
    """Set interval between tweets in minutes."""
    pass

def get_twitter_probability_filter() -> str:
    """Get probability filter key."""
    pass

def set_twitter_probability_filter(filter_key: str) -> bool:
    """Set probability filter. Returns True if valid."""
    pass

def is_twitter_sell_allowed() -> bool:
    """Check if SELL signals are allowed."""
    pass

def set_twitter_sell_allowed(allowed: bool) -> None:
    """Enable or disable SELL signals."""
    pass

def is_twitter_split_allowed() -> bool:
    """Check if SPLIT signals are allowed."""
    pass

def set_twitter_split_allowed(allowed: bool) -> None:
    """Enable or disable SPLIT signals."""
    pass

def is_twitter_redeem_allowed() -> bool:
    """Check if REDEEM signals are allowed."""
    pass

def set_twitter_redeem_allowed(allowed: bool) -> None:
    """Enable or disable REDEEM signals."""
    pass

def is_twitter_merge_allowed() -> bool:
    """Check if MERGE signals are allowed."""
    pass

def set_twitter_merge_allowed(allowed: bool) -> None:
    """Enable or disable MERGE signals."""
    pass

def get_twitter_categories() -> dict:
    """Get category filter settings."""
    pass

def set_twitter_category(category: str, enabled: bool) -> bool:
    """Set category filter. Returns True if valid category."""
    pass

def is_twitter_paused() -> tuple[bool, int]:
    """Check if Twitter is paused due to 403. Returns (is_paused, seconds_remaining)."""
    pass

def _clean_old_timestamps(timestamps: list, now: float) -> list:
    """Remove timestamps older than 24 hours."""
    pass

def get_tweets_in_last_24h() -> int:
    """Get count of tweets sent in the last 24 hours."""
    pass

def get_seconds_until_next_tweet() -> int:
    """Get seconds until next tweet slot is available (24h rolling window)."""
    pass

def _record_successful_tweet():
    """Record timestamp of successful tweet."""
    pass

def _activate_403_pause():
    """Activate 6-hour pause after 403 error."""
    pass

class TwitterService:
    """Service for posting tweets about whale trades with anti-spam protection."""

    def __init__(self):
        pass

    def _init_client(self):
        """Initialize Twitter client."""
        pass

    def wants_trade(self, trade_data: dict) -> tuple[bool, str]:
        """
        Check if Twitter wants this trade (filters only, no rate limits).
        Returns (wants_trade, reason_if_not).
        Used to determine if we should call post_trade_alert (which handles queue).
        """
        pass

    def should_post(self, trade_data: dict) -> tuple[bool, str]:
        """
        Check if trade should be posted to Twitter right now (includes rate limits).
        Returns (should_post, reason_if_not).
        """
        pass

    def format_tweet(self, trade_data: dict) -> str:
        """Format trade data as a tweet with dynamic labels for BUY trades only."""
        pass

    async def post_tweet(self, tweet_text: str) -> Optional[str]:
        """Post a tweet. Returns tweet ID if successful, None otherwise."""
        pass

    async def post_trade_alert(self, trade_data: dict) -> Optional[str]:
        """Format and post a trade alert with anti-spam protection."""
        pass

    def _get_queue_lock(self):
        """Get or create queue lock."""
        pass

    def _load_queue(self):
        """Load queue from disk."""
        pass

    def _save_queue(self):
        """Save queue to disk."""
        pass

    def _get_trade_value_usd(self, trade_data: dict) -> float:
        """Calculate trade value in USD."""
        pass

    def _get_trader_id(self, trade_data: dict) -> str:
        """Get unique trader identifier (address or name)."""
        pass

    async def _add_to_queue(self, trade_data: dict):
        """
        Add trade to pending queue with smart prioritization:
        1. Deduplicate by trader: if same trader exists, keep only the largest trade
        2. If queue is full (>= 10), prioritize by trade size, keep largest 10
        3. If queue is not full, maintain FIFO order
        """
        pass

    async def _process_pending_queue(self):
        """Process pending queue - try to post tweets if interval allows."""
        pass

    async def process_queue_periodically(self, interval=60):
        """Background task to periodically check and process pending queue."""
        pass
_twitter_service = None

def get_twitter_service() -> Optional[TwitterService]:
    """Get the global Twitter service instance."""
    pass