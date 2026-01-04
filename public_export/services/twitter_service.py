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
from typing import Optional
logger = logging.getLogger(__name__)
TWITTER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_settings.json')
DEFAULT_TWEET_INTERVAL_SEC = 25 * 60
PAUSE_ON_403_SEC = 6 * 60 * 60
PROBABILITY_OPTIONS = {'any': None, '1_99': (0.01, 0.99), '5_95': (0.05, 0.95), '10_90': (0.1, 0.9)}
DEFAULT_SETTINGS = {'enabled': True, 'min_alert_usd': 25000, 'last_tweet_ts': 0, 'paused_until': 0, 'interval_minutes': 25, 'probability_filter': '1_99', 'allow_sell': False, 'allow_split': False, 'allow_redeem': False, 'categories': {'crypto': True, 'sports': True, 'other': True}}
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

def get_twitter_categories() -> dict:
    """Get category filter settings."""
    pass

def set_twitter_category(category: str, enabled: bool) -> bool:
    """Set category filter. Returns True if valid category."""
    pass

def is_twitter_paused() -> tuple[bool, int]:
    """Check if Twitter is paused due to 403. Returns (is_paused, seconds_remaining)."""
    pass

def get_seconds_until_next_tweet() -> int:
    """Get seconds until next tweet is allowed (rate limit)."""
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

    def should_post(self, trade_data: dict) -> tuple[bool, str]:
        """
        Check if trade should be posted to Twitter.
        Returns (should_post, reason_if_not).
        """
        pass

    def format_tweet(self, trade_data: dict) -> str:
        """Format trade data as a tweet. English only, no emojis in header."""
        pass

    async def post_tweet(self, tweet_text: str) -> Optional[str]:
        """Post a tweet. Returns tweet ID if successful, None otherwise."""
        pass

    async def post_trade_alert(self, trade_data: dict) -> Optional[str]:
        """Format and post a trade alert with anti-spam protection."""
        pass
_twitter_service = None

def get_twitter_service() -> Optional[TwitterService]:
    """Get the global Twitter service instance."""
    pass