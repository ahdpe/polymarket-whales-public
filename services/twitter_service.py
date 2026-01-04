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

# Twitter settings file (stores min_alert_usd, enabled status, pause info)
TWITTER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_settings.json')

# Rate limit constants
DEFAULT_TWEET_INTERVAL_SEC = 25 * 60  # 25 minutes default
PAUSE_ON_403_SEC = 6 * 60 * 60    # 6 hours

# Probability filter options (same as Telegram)
PROBABILITY_OPTIONS = {
    'any': None,           # No filter
    '1_99': (0.01, 0.99),
    '5_95': (0.05, 0.95),
    '10_90': (0.10, 0.90),
}

# Default settings
DEFAULT_SETTINGS = {
    'enabled': False,              # Default: Disabled
    'min_alert_usd': 100000,       # Default: $100K minimum for Twitter
    'last_tweet_ts': 0,           # Timestamp of last successful tweet
    'paused_until': 0,            # Timestamp until which posting is paused (403 protection)
    'interval_minutes': 25,       # Minutes between tweets
    'probability_filter': '1_99', # Probability range filter
    'allow_sell': False,          # Allow SELL signals
    'allow_split': False,         # Allow SPLIT signals
    'allow_merge': False,         # Allow MERGE signals
    'allow_redeem': False,        # Allow REDEEM signals
    'categories': {               # Category filters
        'crypto': True,
        'sports': True,
        'other': True
    }
}

# In-memory settings (loaded on startup)
_twitter_settings = None


def _load_settings() -> dict:
    """Load Twitter settings from file."""
    global _twitter_settings
    if _twitter_settings is not None:
        return _twitter_settings
    
    try:
        if os.path.exists(TWITTER_SETTINGS_FILE):
            with open(TWITTER_SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults to ensure all keys exist
                _twitter_settings = {**DEFAULT_SETTINGS, **loaded}
                return _twitter_settings
    except Exception as e:
        logger.error(f"Error loading Twitter settings: {e}")
    
    _twitter_settings = DEFAULT_SETTINGS.copy()
    return _twitter_settings


def _save_settings():
    """Save Twitter settings to file."""
    try:
        with open(TWITTER_SETTINGS_FILE, 'w') as f:
            json.dump(_twitter_settings, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving Twitter settings: {e}")


def get_twitter_settings() -> dict:
    """Get current Twitter settings."""
    return _load_settings()


def set_twitter_min_alert(min_usd: int) -> None:
    """Set minimum USD value for Twitter alerts."""
    settings = _load_settings()
    settings['min_alert_usd'] = min_usd
    _save_settings()
    logger.info(f"Twitter min alert set to ${min_usd:,}")


def set_twitter_enabled(enabled: bool) -> None:
    """Enable or disable Twitter posting."""
    settings = _load_settings()
    settings['enabled'] = enabled
    if enabled:
        # Clear pause when manually enabling
        settings['paused_until'] = 0
    _save_settings()
    logger.info(f"Twitter posting {'enabled' if enabled else 'disabled'}")


def is_twitter_enabled() -> bool:
    """Check if Twitter posting is enabled."""
    return _load_settings().get('enabled', True)


def get_twitter_min_alert() -> int:
    """Get minimum USD value for Twitter alerts."""
    return _load_settings().get('min_alert_usd', 25000)


def get_twitter_interval() -> int:
    """Get interval between tweets in minutes."""
    return _load_settings().get('interval_minutes', 25)


def set_twitter_interval(minutes: int) -> None:
    """Set interval between tweets in minutes."""
    settings = _load_settings()
    settings['interval_minutes'] = max(1, minutes)  # Min 1 minute
    _save_settings()
    logger.info(f"Twitter interval set to {minutes} minutes")


def get_twitter_probability_filter() -> str:
    """Get probability filter key."""
    return _load_settings().get('probability_filter', '1_99')


def set_twitter_probability_filter(filter_key: str) -> bool:
    """Set probability filter. Returns True if valid."""
    if filter_key not in PROBABILITY_OPTIONS:
        return False
    settings = _load_settings()
    settings['probability_filter'] = filter_key
    _save_settings()
    logger.info(f"Twitter probability filter set to {filter_key}")
    return True


def is_twitter_sell_allowed() -> bool:
    """Check if SELL signals are allowed."""
    return _load_settings().get('allow_sell', False)


def set_twitter_sell_allowed(allowed: bool) -> None:
    """Enable or disable SELL signals."""
    settings = _load_settings()
    settings['allow_sell'] = allowed
    _save_settings()
    logger.info(f"Twitter SELL signals {'allowed' if allowed else 'disabled'}")


def is_twitter_split_allowed() -> bool:
    """Check if SPLIT signals are allowed."""
    return _load_settings().get('allow_split', False)


def set_twitter_split_allowed(allowed: bool) -> None:
    """Enable or disable SPLIT signals."""
    settings = _load_settings()
    settings['allow_split'] = allowed
    _save_settings()
    logger.info(f"Twitter SPLIT signals {'allowed' if allowed else 'disabled'}")


def is_twitter_redeem_allowed() -> bool:
    """Check if REDEEM signals are allowed."""
    return _load_settings().get('allow_redeem', False)


def set_twitter_redeem_allowed(allowed: bool) -> None:
    """Enable or disable REDEEM signals."""
    settings = _load_settings()
    settings['allow_redeem'] = allowed
    _save_settings()
    logger.info(f"Twitter REDEEM signals {'allowed' if allowed else 'disabled'}")


def is_twitter_merge_allowed() -> bool:
    """Check if MERGE signals are allowed."""
    return _load_settings().get('allow_merge', False)


def set_twitter_merge_allowed(allowed: bool) -> None:
    """Enable or disable MERGE signals."""
    settings = _load_settings()
    settings['allow_merge'] = allowed
    _save_settings()
    logger.info(f"Twitter MERGE signals {'allowed' if allowed else 'disabled'}")


def get_twitter_categories() -> dict:
    """Get category filter settings."""
    return _load_settings().get('categories', {'crypto': True, 'sports': True, 'other': True})


def set_twitter_category(category: str, enabled: bool) -> bool:
    """Set category filter. Returns True if valid category."""
    if category not in ['crypto', 'sports', 'other', 'all']:
        return False
    settings = _load_settings()
    if 'categories' not in settings:
        settings['categories'] = {'crypto': True, 'sports': True, 'other': True}
    
    if category == 'all':
        settings['categories'] = {'crypto': enabled, 'sports': enabled, 'other': enabled}
    else:
        settings['categories'][category] = enabled
    _save_settings()
    logger.info(f"Twitter category {category} set to {enabled}")
    return True


def is_twitter_paused() -> tuple[bool, int]:
    """Check if Twitter is paused due to 403. Returns (is_paused, seconds_remaining)."""
    settings = _load_settings()
    paused_until = settings.get('paused_until', 0)
    now = time.time()
    if paused_until > now:
        return True, int(paused_until - now)
    return False, 0


def get_seconds_until_next_tweet() -> int:
    """Get seconds until next tweet is allowed (rate limit)."""
    settings = _load_settings()
    last_tweet_ts = settings.get('last_tweet_ts', 0)
    interval_sec = settings.get('interval_minutes', 25) * 60
    next_allowed = last_tweet_ts + interval_sec
    now = time.time()
    if next_allowed > now:
        return int(next_allowed - now)
    return 0


def _record_successful_tweet():
    """Record timestamp of successful tweet."""
    settings = _load_settings()
    settings['last_tweet_ts'] = time.time()
    _save_settings()


def _activate_403_pause():
    """Activate 6-hour pause after 403 error."""
    settings = _load_settings()
    settings['paused_until'] = time.time() + PAUSE_ON_403_SEC
    _save_settings()
    logger.warning(f"Twitter 403 detected! Pausing for 6 hours until {time.ctime(settings['paused_until'])}")


class TwitterService:
    """Service for posting tweets about whale trades with anti-spam protection."""
    
    def __init__(self):
        from config import (
            TWITTER_API_KEY, TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
        )
        
        self.api_key = TWITTER_API_KEY
        self.api_secret = TWITTER_API_SECRET
        self.access_token = TWITTER_ACCESS_TOKEN
        self.access_token_secret = TWITTER_ACCESS_TOKEN_SECRET
        
        self.client = None
        self.is_configured = all([
            self.api_key, self.api_secret,
            self.access_token, self.access_token_secret
        ])
        
        if self.is_configured:
            self._init_client()
            logger.info("TwitterService initialized successfully")
        else:
            logger.warning("TwitterService not configured - missing API keys")
    
    def _init_client(self):
        """Initialize Twitter client."""
        try:
            import tweepy
            
            self.client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            logger.info("Twitter client initialized")
        except ImportError:
            logger.error("tweepy not installed. Run: pip install tweepy")
            self.is_configured = False
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            self.is_configured = False
    
    def should_post(self, trade_data: dict) -> tuple[bool, str]:
        """
        Check if trade should be posted to Twitter.
        Returns (should_post, reason_if_not).
        """
        if not self.is_configured:
            return False, "not_configured"
        
        if not is_twitter_enabled():
            return False, "disabled"
        
        # Check 403 pause
        paused, secs = is_twitter_paused()
        if paused:
            return False, f"paused_403_{secs}s"
        
        # Check rate limit (configurable interval)
        wait_secs = get_seconds_until_next_tweet()
        if wait_secs > 0:
            return False, f"rate_limit_{wait_secs}s"
        
        # Check side/type signals
        side = trade_data.get('side', '').upper()
        trade_type = trade_data.get('type', '').upper()
        
        # Check for SPLIT
        is_split = side == 'SPLIT' or trade_type == 'SPLIT'
        if is_split:
            if not is_twitter_split_allowed():
                return False, "split_disabled"
            # SPLIT is allowed, continue
        # Check for MERGE
        elif side == 'MERGE' or trade_type == 'MERGE':
            if not is_twitter_merge_allowed():
                return False, "merge_disabled"
            # MERGE is allowed, continue
        # Check for REDEEM
        elif side == 'REDEEM' or trade_type == 'REDEEM':
            if not is_twitter_redeem_allowed():
                return False, "redeem_disabled"
            # REDEEM is allowed, continue
        # Check for SELL
        elif side == 'SELL':
            if not is_twitter_sell_allowed():
                return False, "sell_disabled"
        # Check for BUY (always allowed)
        elif side == 'BUY':
            pass  # BUY is always allowed
        else:
            return False, f"side_{side}_invalid"
        
        # Check probability filter
        price = float(trade_data.get('price', 0))
        prob_filter = get_twitter_probability_filter()
        prob_range = PROBABILITY_OPTIONS.get(prob_filter)
        if prob_range:
            min_prob, max_prob = prob_range
            if price < min_prob or price > max_prob:
                return False, f"probability_{price*100:.1f}_outside_{prob_filter}"
        
        # Check category filter
        category = trade_data.get('category', 'other')
        categories = get_twitter_categories()
        if not categories.get(category, True):
            return False, f"category_{category}_disabled"
        
        # Check minimum amount
        value_usd = price * float(trade_data.get('size', 0))
        if value_usd < get_twitter_min_alert():
            return False, f"amount_{value_usd:.0f}_below_min"
        
        return True, "ok"
    
    def format_tweet(self, trade_data: dict) -> str:
        """Format trade data as a tweet. English only, no emojis in header."""
        # Extract data
        market_title = trade_data.get('title', 'Unknown Market')
        market_url = trade_data.get('market_url', '')
        side = trade_data.get('side', 'UNKNOWN')
        outcome = trade_data.get('outcome', '')
        price = float(trade_data.get('price', 0))
        size = float(trade_data.get('size', 0))
        value_usd = price * size
        
        # Map level_name to English (no emojis)
        level_name_raw = trade_data.get('level_name', 'WHALE')
        level_map = {
            'Креветка': 'SHRIMP', 'Shrimp': 'SHRIMP', 'SHRIMP': 'SHRIMP',
            'Рыба': 'FISH', 'Fish': 'FISH', 'FISH': 'FISH',
            'Дельфин': 'DOLPHIN', 'Dolphin': 'DOLPHIN', 'DOLPHIN': 'DOLPHIN',
            'Акула': 'SHARK', 'Shark': 'SHARK', 'SHARK': 'SHARK',
            'Кит': 'WHALE', 'Whale': 'WHALE', 'WHALE': 'WHALE',
            'Супер Кит': 'SUPER WHALE', 'Super Whale': 'SUPER WHALE', 'SUPER WHALE': 'SUPER WHALE',
            'Мега Кит': 'MEGA WHALE', 'Mega Whale': 'MEGA WHALE', 'MEGA WHALE': 'MEGA WHALE',
        }
        level_name = level_map.get(level_name_raw, 'WHALE')
        
        # Trader info
        trader_address = trade_data.get('trader_address', '')
        trader_name = trade_data.get('name', '') or trade_data.get('trader_name', '')
        
        # Shorten address for display: 0xcd36...0f01
        if trader_address and len(trader_address) > 12:
            short_address = f"{trader_address[:6]}...{trader_address[-4:]}"
        else:
            short_address = trader_address or 'Unknown'
        
        # Trader display: full name (bold) if available, otherwise Wallet: short_address
        if trader_name and trader_name.strip():
            trader_display = f"Trader: {trader_name}"
        else:
            trader_display = f"Wallet: {short_address}"
        
        trader_url = f"https://polymarket.com/profile/{trader_address}" if trader_address else ""
        
        # Position stats
        pos_data = trade_data.get('position_stats') or {}
        pnl_usd = pos_data.get('pnl_usd', 0) if pos_data else 0
        pnl_pct = pos_data.get('pnl_percent', 0) if pos_data else 0
        open_count = pos_data.get('open_count', 0) if pos_data else 0
        total_value = pos_data.get('total_value', 0) if pos_data else 0
        
        # Format values (K/M notation)
        def fmt_val(v):
            v_abs = abs(v)
            if v_abs >= 1_000_000:
                return f"${v_abs/1_000_000:.1f}M"
            elif v_abs >= 1_000:
                return f"${v_abs/1_000:.1f}K"
            else:
                return f"${v_abs:.0f}"
        
        # PnL formatting
        if pnl_usd >= 0:
            pnl_str = f"+{fmt_val(pnl_usd)}"
        else:
            pnl_str = f"-{fmt_val(pnl_usd)}"
        pnl_pct_str = f"({pnl_pct:+.0f}%)" if pnl_pct else "(0%)"
        
        # Wallet age
        wallet_age = trade_data.get('wallet_age_str', '')
        
        # Money display - bold only the entry amount
        money_line = f"${value_usd:,.0f} → ${size:,.0f}"
        
        # Build tweet lines
        lines = [
            f"{level_name} trade",
            "",
            market_title,
            market_url if market_url else None,
            "",
            f"{side} {outcome} @ {price*100:.1f}%",
            money_line,
            "",
            trader_display,
            trader_url if trader_url else None,
            f"Open PnL: {pnl_str} {pnl_pct_str}",
            f"Open Positions: {open_count} | Val: {fmt_val(total_value)}",
        ]
        
        if wallet_age:
            lines.append(f"Wallet Age: {wallet_age}")
        
        lines.extend([
            "",
            "Alerts 👇",
            "t.me/PolymarketWhales_bot"
        ])
        
        # Filter None values and join
        tweet = "\n".join(line for line in lines if line is not None)
        
        # Ensure tweet is under 280 chars
        if len(tweet) > 280:
            # Truncate market title
            max_title_len = 280 - (len(tweet) - len(market_title)) - 3
            if max_title_len > 20:
                market_title = market_title[:max_title_len] + "..."
                lines[2] = market_title
                tweet = "\n".join(line for line in lines if line is not None)
        
        return tweet
    
    async def post_tweet(self, tweet_text: str) -> Optional[str]:
        """Post a tweet. Returns tweet ID if successful, None otherwise."""
        if not self.is_configured or not self.client:
            logger.warning("Twitter not configured, skipping post")
            return None
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.create_tweet(text=tweet_text)
            )
            
            tweet_id = response.data.get('id') if response.data else None
            if tweet_id:
                logger.info(f"Tweet posted successfully: {tweet_id}")
                _record_successful_tweet()
            return tweet_id
            
        except Exception as e:
            error_str = str(e)
            
            # Check for 403 Forbidden - activate 6 hour pause
            if '403' in error_str:
                _activate_403_pause()
                logger.error(f"Twitter 403 Forbidden - pausing for 6 hours. Error: {error_str}")
                return None
            
            # Log other errors
            logger.error(f"Failed to post tweet: {error_str}")
            return None
    
    async def post_trade_alert(self, trade_data: dict) -> Optional[str]:
        """Format and post a trade alert with anti-spam protection."""
        should, reason = self.should_post(trade_data)
        
        if not should:
            # Log skipped tweets for debugging (but not too verbose)
            if not reason.startswith('rate_limit') and not reason.startswith('amount'):
                logger.debug(f"Tweet skipped: {reason}")
            return None
        
        tweet_text = self.format_tweet(trade_data)
        return await self.post_tweet(tweet_text)


# Global instance (lazy initialization)
_twitter_service = None


def get_twitter_service() -> Optional[TwitterService]:
    """Get the global Twitter service instance."""
    global _twitter_service
    if _twitter_service is None:
        _twitter_service = TwitterService()
    return _twitter_service if _twitter_service.is_configured else None
