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
from services.telegram_service import add_polymarket_ref

logger = logging.getLogger(__name__)

# Twitter settings file (stores min_alert_usd, enabled status, pause info)
TWITTER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_settings.json')
# Twitter queue file (stores pending queue for rate limits)
TWITTER_QUEUE_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_queue.json')
# Delayed queue file (stores trades waiting for 10‑minute hold + position re‑check)
TWITTER_DELAY_QUEUE_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_delay_queue.json')

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

# Twitter API limits
MAX_TWEETS_PER_24H = 17  # Maximum tweets per 24-hour rolling window
TWEET_WINDOW_SEC = 24 * 60 * 60  # 24 hours in seconds
MAX_TWEET_TEXT_LEN = 4000
AUTOPOST_FOOTER = "Auto-posted by bot."

# Insider Tweet Templates (Safe versions)
INSIDER_TEMPLATES = [
    # Group 1: Focus
    "Fresh wallet with heavy focus. Only {pos_count} active position(s). Betting {amount} straight out of the gate. 👀",
    "🎯 Brand new wallet ignoring everything else to deploy {amount} on this outcome.",
    "Single target detected. No history, minimal positions. Just a massive {amount} bet on this specific market.",
    
    # Group 2: Anomaly
    "Unusual market pattern. Large volume ({amount}) from a source with zero prior history.",
    "Anomaly detected. A silent wallet suddenly wakes up with a major position. Worth monitoring.",
    "Pattern watch: High-confidence trade from a completely fresh wallet. No previous track record.",
    
    # Group 3: Speed
    "Fresh wallet, no warmup trades. Starts directly with a {amount} position.",
    "Big entry, zero history. Just activated and dropping {amount}. Who is this?",
    "Aggressive newcomer. Skipping the small trades. First major move is a {amount} bet here.",
    
    # Group 4: Question
    "Brand new wallet bets {amount} on this single outcome.",
    "Gut feeling or calculations? Fresh wallet stakes {amount} immediately after funding.",
    "{amount} flows into this market from a wallet with no history."
]

# Default settings
DEFAULT_SETTINGS = {
    'enabled': False,              # Default: Disabled
    'min_alert_usd': 100000,       # Default: $100K minimum for Twitter
    'min_alert_insider_usd': 20000,# Default: $20K minimum for Insider tweets
    'max_insider_age_days': 2.0,   # Default: 2 days max for Insider
    'max_insider_positions': 3,    # Default: 3 positions max for Insider
    'tweet_timestamps': [],        # List of timestamps of successful tweets (for 24h rolling window)
    'paused_until': 0,            # Timestamp until which posting is paused (403 protection)
    'interval_minutes': 25,       # Minutes between tweets
    'probability_min': 1,         # Min probability (inclusive)
    'probability_max': 99,        # Max probability (inclusive)
    'probability_filter': '1_99', # Keeping for backward compatibility/migration
    'allow_sell': False,          # Allow SELL signals
    'allow_split': False,         # Allow SPLIT signals
    'allow_merge': False,         # Allow MERGE signals
    'allow_redeem': False,        # Allow REDEEM signals
    'categories': {               # Category filters
        'crypto': True,
        'sports': True,
        'other': True
    },
    'delay_seconds': 600,         # Delay before tweeting after trade (10 minutes)
}

# In-memory settings (loaded on startup)
_twitter_settings = None


def _trim_tweet_body_to_limit(body_text: str, max_body_len: int) -> str:
    """Trim tweet body by dropping trailing lines before hard cutting."""
    if len(body_text) <= max_body_len:
        return body_text

    lines = body_text.split("\n")
    while lines:
        candidate = "\n".join(lines).rstrip()
        if len(candidate) <= max_body_len:
            return candidate
        lines.pop()

    return body_text[:max_body_len].rstrip()


def _finalize_tweet_text(tweet_text: str) -> str:
    """Finalize outgoing tweet: add ref params, append footer, enforce max length."""
    body = (tweet_text or "").rstrip()
    if body.endswith(AUTOPOST_FOOTER):
        body = body[:-len(AUTOPOST_FOOTER)].rstrip()

    body = add_polymarket_ref(body).replace("via=PolymarketWhaleAlerts", "via=PmWhlAlerts")

    footer_block = f"\n\n{AUTOPOST_FOOTER}"
    max_body_len = MAX_TWEET_TEXT_LEN - len(footer_block)
    if max_body_len <= 0:
        return AUTOPOST_FOOTER[:MAX_TWEET_TEXT_LEN]

    trimmed_body = _trim_tweet_body_to_limit(body, max_body_len)
    if not trimmed_body:
        return AUTOPOST_FOOTER

    return f"{trimmed_body}{footer_block}"


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
                
                # Migration: convert old last_tweet_ts to tweet_timestamps
                if 'last_tweet_ts' in loaded and loaded['last_tweet_ts'] > 0:
                    if 'tweet_timestamps' not in loaded or not loaded.get('tweet_timestamps'):
                        _twitter_settings['tweet_timestamps'] = [loaded['last_tweet_ts']]
                        logger.info("Migrated last_tweet_ts to tweet_timestamps")
                    # Remove old key
                    if 'last_tweet_ts' in _twitter_settings:
                        del _twitter_settings['last_tweet_ts']
                        _save_settings()  # Save migrated settings
                
                # Ensure tweet_timestamps exists
                if 'tweet_timestamps' not in _twitter_settings:
                    _twitter_settings['tweet_timestamps'] = []
                
                # Run migrations
                _migrate_prob_filter(_twitter_settings)
                
                return _twitter_settings
    except Exception as e:
        logger.error(f"Error loading Twitter settings: {e}")
    
    _twitter_settings = DEFAULT_SETTINGS.copy()
    return _twitter_settings


def _migrate_prob_filter(settings: dict) -> None:
    """Migrate old probability_filter string to min/max values."""
    if 'probability_filter' in settings and ('probability_min' not in settings or 'probability_max' not in settings):
        pf = settings['probability_filter']
        if pf in PROBABILITY_OPTIONS and PROBABILITY_OPTIONS[pf]:
            min_val, max_val = PROBABILITY_OPTIONS[pf]
            settings['probability_min'] = int(min_val * 100)
            settings['probability_max'] = int(max_val * 100)
            logger.info(f"Migrated Twitter prob filter {pf} to {settings['probability_min']}-{settings['probability_max']}%")


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


def get_twitter_delay_seconds() -> int:
    """Get delay before tweeting after trade (in seconds)."""
    return int(_load_settings().get('delay_seconds', 600))


def set_twitter_delay_seconds(delay_seconds: int) -> None:
    """Set delay before tweeting after trade (in seconds)."""
    settings = _load_settings()
    settings['delay_seconds'] = max(0, int(delay_seconds))
    _save_settings()
    logger.info(f"Twitter delay set to {settings['delay_seconds']} seconds")


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


def get_twitter_insider_min() -> int:
    """Get minimum USD value for INSIDER Twitter alerts."""
    return _load_settings().get('min_alert_insider_usd', 20000)


def set_twitter_insider_min(min_usd: int) -> None:
    """Set minimum USD value for INSIDER Twitter alerts."""
    settings = _load_settings()
    settings['min_alert_insider_usd'] = min_usd
    _save_settings()
    logger.info(f"Twitter INSIDER min alert set to ${min_usd:,}")


def get_twitter_insider_max_age() -> float:
    """Get max wallet age (days) for INSIDER Twitter alerts."""
    return _load_settings().get('max_insider_age_days', 2.0)


def set_twitter_insider_max_age(days: float) -> None:
    """Set max wallet age (days) for INSIDER Twitter alerts."""
    settings = _load_settings()
    settings['max_insider_age_days'] = float(days)
    _save_settings()
    logger.info(f"Twitter INSIDER max age set to {days} days")


def get_twitter_insider_max_positions() -> int:
    """Get max positions for INSIDER Twitter alerts."""
    return _load_settings().get('max_insider_positions', 3)


def set_twitter_insider_max_positions(count: int) -> None:
    """Set max positions for INSIDER Twitter alerts."""
    settings = _load_settings()
    settings['max_insider_positions'] = int(count)
    _save_settings()
    logger.info(f"Twitter INSIDER max positions set to {count}")


def get_twitter_interval() -> int:
    """Get interval between tweets in minutes."""
    return _load_settings().get('interval_minutes', 25)


def set_twitter_interval(minutes: int) -> None:
    """Set interval between tweets in minutes."""
    settings = _load_settings()
    settings['interval_minutes'] = max(1, minutes)  # Min 1 minute
    _save_settings()
    logger.info(f"Twitter interval set to {minutes} minutes")


def get_twitter_probability_range() -> tuple[int, int]:
    """Get probability range (min, max)."""
    settings = _load_settings()
    return (
        int(settings.get('probability_min', 1)),
        int(settings.get('probability_max', 99))
    )


def set_twitter_probability_range(min_p: int, max_p: int) -> None:
    """Set probability range."""
    settings = _load_settings()
    settings['probability_min'] = int(min_p)
    settings['probability_max'] = int(max_p)
    _save_settings()
    logger.info(f"Twitter probability range set to {min_p}-{max_p}%")


def get_twitter_probability_filter() -> str:
    """Deprecated: Get probability filter key."""
    return _load_settings().get('probability_filter', '1_99')


def set_twitter_probability_filter(filter_key: str) -> bool:
    """Deprecated: Set probability filter via legacy key."""
    if filter_key not in PROBABILITY_OPTIONS:
        return False
    
    settings = _load_settings()
    settings['probability_filter'] = filter_key
    
    # Also update the new range values
    if PROBABILITY_OPTIONS[filter_key]:
        min_v, max_v = PROBABILITY_OPTIONS[filter_key]
        settings['probability_min'] = int(min_v * 100)
        settings['probability_max'] = int(max_v * 100)
    
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


def _clean_old_timestamps(timestamps: list, now: float) -> list:
    """Remove timestamps older than 24 hours."""
    cutoff = now - TWEET_WINDOW_SEC
    return [ts for ts in timestamps if ts > cutoff]


def get_tweets_in_last_24h() -> int:
    """Get count of tweets sent in the last 24 hours."""
    settings = _load_settings()
    timestamps = settings.get('tweet_timestamps', [])
    now = time.time()
    cleaned = _clean_old_timestamps(timestamps, now)
    return len(cleaned)


def get_seconds_until_next_tweet() -> int:
    """Get seconds until next tweet slot is available (24h rolling window)."""
    settings = _load_settings()
    timestamps = settings.get('tweet_timestamps', [])
    now = time.time()
    
    # Clean old timestamps
    cleaned = _clean_old_timestamps(timestamps, now)
    
    # Check if we're at the limit
    if len(cleaned) >= MAX_TWEETS_PER_24H:
        # Find the oldest tweet in the window - it will free up first
        if cleaned:
            oldest_ts = min(cleaned)
            next_available = oldest_ts + TWEET_WINDOW_SEC
            wait_secs = next_available - now
            return max(0, int(wait_secs))
        return TWEET_WINDOW_SEC  # Fallback: wait full 24h
    
    # Also check minimum interval (if configured)
    interval_sec = settings.get('interval_minutes', 25) * 60
    if cleaned:
        last_tweet_ts = max(cleaned)
        next_allowed = last_tweet_ts + interval_sec
        if next_allowed > now:
            return int(next_allowed - now)
    
    return 0


def _record_successful_tweet():
    """Record timestamp of successful tweet."""
    settings = _load_settings()
    now = time.time()
    
    # Get current timestamps and clean old ones
    timestamps = settings.get('tweet_timestamps', [])
    timestamps = _clean_old_timestamps(timestamps, now)
    
    # Add new timestamp
    timestamps.append(now)
    
    # Keep only recent timestamps (last 24h + some buffer)
    # This prevents the list from growing indefinitely
    settings['tweet_timestamps'] = timestamps
    _save_settings()
    logger.debug(f"Recorded tweet. Total in last 24h: {len(timestamps)}/{MAX_TWEETS_PER_24H}")


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
        
        # Queue for pending tweets (when interval limit is active but 24h limit is OK)
        self.pending_queue = []  # List of (trade_data, timestamp) tuples
        self.max_queue_size = 10  # Maximum tweets in queue
        self._queue_lock = None  # Will be initialized when needed
        
         # Delayed queue for 10‑minute hold + position re‑check
        self.delayed_queue = []  # List of dicts with twitter_data + metadata
        self._delayed_lock = None  # Initialized lazily
        self.delayed_queue_file = TWITTER_DELAY_QUEUE_FILE
        self.poly_service = None  # Set from main.py to re-check open positions
        
        if self.is_configured:
            self._init_client()
            self._load_queue()  # Load queue from disk
            self._load_delayed_queue()  # Load delayed queue from disk
            logger.info(f"TwitterService initialized successfully (queue size: {len(self.pending_queue)})")
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
    
    def wants_trade(self, trade_data: dict) -> tuple[bool, str]:
        """
        Check if Twitter wants this trade (filters only, no rate limits).
        Returns (wants_trade, reason_if_not).
        Used to determine if we should call post_trade_alert (which handles queue).
        """
        if not self.is_configured:
            return False, "not_configured"
        
        if not is_twitter_enabled():
            return False, "disabled"
        
        # Check 403 pause (this is a hard stop, not a rate limit)
        paused, secs = is_twitter_paused()
        if paused:
            return False, f"paused_403_{secs}s"
        
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
        
        # Check probability filter (New Logic)
        price = float(trade_data.get('price', 0))
        prob_pct = price * 100
        
        # Use new range settings
        min_p = _load_settings().get('probability_min', 1)
        max_p = _load_settings().get('probability_max', 99)
        
        if prob_pct < min_p or prob_pct > max_p:
             return False, f"probability_{prob_pct:.1f}_outside_{min_p}-{max_p}"
        
        # Check category filter
        category = trade_data.get('category', 'other')
        categories = get_twitter_categories()
        if not categories.get(category, True):
            return False, f"category_{category}_disabled"
        
        # Check minimum amount
        value_usd = self._get_trade_value_usd(trade_data)
        
        # Check if this qualifies as an "Insider Candidate"
        # (Conditions must match logic in format_tweet)
        wallet_age_str = trade_data.get('wallet_age_str', '')
        pos_count = trade_data.get('open_positions_count', 999)
        is_fresh = False
        if wallet_age_str:
            age_lower = wallet_age_str.lower()
            if 'h' in age_lower or '<' in age_lower or 'less' in age_lower:
                is_fresh = True
            elif 'd' in age_lower:
                try:
                    days = float(age_lower.replace('d', '').split()[0])
                    # Check against configured max age
                    max_days = get_twitter_insider_max_age()
                    if days <= max_days:
                        is_fresh = True
                except Exception:
                    pass
        
        # Check against configured max positions
        max_pos = get_twitter_insider_max_positions()
        
        is_insider_candidate = (
            is_fresh and 
            side == 'BUY' and 
            pos_count <= max_pos
        )
        
        # Filter Logic:
        # 1. If Insider Candidate -> Check Insider Min
        # 2. If NOT Insider Candidate -> Check Global Min
        
        min_required = get_twitter_min_alert()
        
        if is_insider_candidate:
            insider_min = get_twitter_insider_min()
            # If insider min is LOWER than global min, we allow it to bypass global min
            # If insider min is HIGHER (unlikely but possible), strict check
            
            # Actually, the user wants "separate" logic.
            # If it's insider -> accepted if > insider_min
            # If standard -> accepted if > global_min
            
            if value_usd >= insider_min:
                return True, "ok_insider"
            # If < insider_min, fall through to check global min?
            # Or fail? Usually 'insider min' is lower, so if it fails insider min, it likely fails global min too ($100k).
            # But let's be safe: if fails insider criteria (amount), it shouldn't auto-fail if it somehow passes global
            # although conventionally insider_min < global_min.
            
            if value_usd < min_required and value_usd < insider_min:
                 return False, f"amount_{value_usd:.0f}_below_mins"
            elif value_usd < min_required:
                 # It was candidate but failed insider min, and is below global min
                 return False, f"amount_{value_usd:.0f}_below_global_min"
                 
        else:
            # Standard trade
            if value_usd < min_required:
                return False, f"amount_{value_usd:.0f}_below_min"
        
        return True, "ok"
    
    def should_post(self, trade_data: dict) -> tuple[bool, str]:
        """
        Check if trade should be posted to Twitter right now (includes rate limits).
        Returns (should_post, reason_if_not).
        """
        # First check if we want this trade at all (filters)
        wants, reason = self.wants_trade(trade_data)
        if not wants:
            return False, reason
        
        # Check 24-hour rolling window limit (17 tweets max)
        tweets_count = get_tweets_in_last_24h()
        if tweets_count >= MAX_TWEETS_PER_24H:
            wait_secs = get_seconds_until_next_tweet()
            wait_mins = wait_secs // 60
            wait_hours = wait_mins // 60
            return False, f"daily_limit_{tweets_count}/{MAX_TWEETS_PER_24H}_wait_{wait_hours}h{wait_mins%60}m"
        
        # Check minimum interval (if configured)
        wait_secs = get_seconds_until_next_tweet()
        if wait_secs > 0:
            wait_mins = wait_secs // 60
            return False, f"interval_limit_{wait_mins}m"
        
        return True, "ok"
    
    def format_tweet(self, trade_data: dict) -> str:
        """Format trade data as a tweet with dynamic labels for BUY trades only."""
        # Extract data
        market_title = trade_data.get('title', 'Unknown Market')
        side = trade_data.get('side', 'UNKNOWN')
        outcome = trade_data.get('outcome', '')
        price = float(trade_data.get('price', 0))
        value_usd = self._get_trade_value_usd(trade_data)
        
        side_upper = side.upper()
        is_buy = side_upper == 'BUY'
        is_special = side_upper in ('SPLIT', 'MERGE', 'REDEEM')

        # Trader info extraction (needed early for Insider logic)
        trader_address = trade_data.get('trader_address', '')
        trader_name = trade_data.get('name', '') or trade_data.get('trader_name', '')
        
        # Strip timestamp suffix
        if trader_name and trader_name.startswith('0x') and '-' in trader_name:
             trader_name = trader_name.split('-')[0]

        # Wallet age
        wallet_age_str = trade_data.get('wallet_age_str', '')

        # --- INSIDER LOGIC START ---
        # 1. Fresh wallet check
        is_fresh = False
        if wallet_age_str:
            age_lower = wallet_age_str.lower()
            if 'h' in age_lower or '<' in age_lower or 'less' in age_lower:
                is_fresh = True
            elif 'd' in age_lower:
                try:
                    # simplistic parse: "4d" -> 4.0
                    days = float(age_lower.replace('d', '').split()[0])
                    # Check against configured max age
                    max_days = get_twitter_insider_max_age()
                    if days <= max_days:
                        is_fresh = True
                except Exception:
                    pass

        # 2. Position count (default high to avoid false positive if missing)
        pos_count = trade_data.get('open_positions_count', 999) 
        max_pos = get_twitter_insider_max_positions()
        
        # 3. Trade size (Check against configured insider min)
        insider_min_val = get_twitter_insider_min()
        is_large = value_usd >= insider_min_val

        # Check condition: Fresh + Large + Few Positions + BUY
        if is_fresh and is_large and pos_count <= max_pos and is_buy:
             try:
                 template = random.choice(INSIDER_TEMPLATES)
                 
                 # Format amount
                 amount_str = f"${value_usd:,.0f}"
                 if value_usd >= 1000:
                      amount_str = f"${value_usd/1000:.1f}k"
                 
                 insider_text = template.format(
                     amount=amount_str,
                     pos_count=pos_count,
                     wallet_age=wallet_age_str
                 )
                 
                 # Construct valid profile link
                 profile_link = ""
                 if trader_address and trader_address.startswith('0x'):
                      profile_link = f"https://polymarket.com/profile/{trader_address}"
                 
                 # Build display for trader
                 # Use same logic as standard but maybe simpler or consistent
                 if trader_name and trader_name.strip():
                      t_display = f"{trader_name} 🐋" # Simplified for insider view
                 elif trader_address and len(trader_address) > 12:
                      short = f"{trader_address[:4]}…{trader_address[-4:]}"
                      t_display = f"Fresh wallet: {short} 🐋"
                 else:
                      t_display = f"Fresh wallet: {trader_address} 🐋"

                 lines = [
                    market_title,
                    "",
                    insider_text,
                    "",
                    f"{side_upper} {outcome} @ {price*100:.1f}%",
                    f"Traded: ${value_usd:,.0f} 💵",
                    "",
                    t_display
                 ]
                 
                 if profile_link:
                     lines.append(profile_link)

                 if wallet_age_str:
                     lines.append(f"Wallet age: {wallet_age_str}")
                
                 tweet = "\n".join(lines)
                 
                 # Truncation logic (same as standard)
                 if len(tweet) > MAX_TWEET_TEXT_LEN:
                    max_title_len = MAX_TWEET_TEXT_LEN - (len(tweet) - len(market_title)) - 3
                    if max_title_len > 20:
                        market_title = market_title[:max_title_len] + "..."
                        lines[0] = market_title
                        tweet = "\n".join(lines)
                 
                 return tweet

             except Exception as e:
                 logger.error(f"Error formatting insider tweet: {e}")
                 # Fallback to standard
        # --- INSIDER LOGIC END ---
        
        # Helper: Get probability label for BUY trades
        def get_probability_label(prob_pct):
            if prob_pct >= 80:
                return "High-conviction buy"
            elif prob_pct >= 65:
                return "Confident buy"
            elif prob_pct >= 50:
                return "Balanced buy"
            elif prob_pct >= 35:
                return "Risky buy"
            else:
                return "High-risk buy"
        
        # Helper: Get size label
        def get_size_label(usd):
            if usd >= 300000:
                return "MEGA Whale"
            elif usd >= 150000:
                return "Big Whale"
            elif usd >= 100000:
                return "Whale"
            return None  # Only label if >= $100K
        
        # Helper: Get trader description (size × probability)
        def get_trader_description(usd, prob_pct):
            if 100000 <= usd < 150000:
                if prob_pct >= 65:
                    return "Conviction trader"
                elif prob_pct >= 40:
                    return "Directional trader"
                else:
                    return "Speculative trader"
            elif 150000 <= usd < 300000:
                if prob_pct >= 70:
                    return "Strong-conviction whale"
                elif prob_pct >= 45:
                    return "Aggressive whale"
                else:
                    return "High-risk whale"
            elif usd >= 300000:
                if prob_pct >= 75:
                    return "High-confidence mega whale"
                elif prob_pct >= 40:
                    return "Aggressive mega whale"
                else:
                    return "Extreme-risk mega whale"
            return None
        
        # Helper: Get wallet age label
        def get_wallet_age_label(age_str):
            """Parse wallet age string and return label."""
            if not age_str:
                return None
            
            age_lower = age_str.lower()
            
            # Parse different formats: "2d", "3mo", "2y 3mo", "1y", etc.
            if 'y' in age_lower:
                # Extract years
                years_match = None
                for part in age_lower.split():
                    if 'y' in part:
                        try:
                            years_match = float(part.replace('y', '').replace('mo', '').replace('d', ''))
                            break
                        except Exception:
                            pass
                
                if years_match is not None:
                    if years_match >= 3:
                        return "Very old wallet"
                    elif years_match >= 1:
                        return "Old wallet"
            
            if 'mo' in age_lower:
                months_match = None
                for part in age_lower.split():
                    if 'mo' in part:
                        try:
                            months_match = float(part.replace('mo', '').replace('d', ''))
                            break
                        except Exception:
                            pass
                
                if months_match is not None:
                    if months_match >= 6:
                        return "Established wallet"
                    elif months_match >= 1:
                        return "Young wallet"
            
            if 'd' in age_lower or 'h' in age_lower:
                days_match = None
                hours_match = None
                for part in age_lower.split():
                    if 'd' in part:
                        try:
                            days_match = float(part.replace('d', '').replace('h', ''))
                            break
                        except Exception:
                            pass
                    elif 'h' in part:
                        try:
                            hours_match = float(part.replace('h', ''))
                            break
                        except Exception:
                            pass
                
                if days_match is not None:
                    if days_match >= 7:
                        return "Young wallet"
                    elif days_match >= 1:
                        return "Fresh wallet"
                elif hours_match is not None:
                    return "Brand-new wallet"
                else:
                    # Check for "<1h" or similar
                    if '<' in age_lower or 'less' in age_lower:
                        return "Brand-new wallet"
            
            return None
        
        # Build first line
        if is_buy:
            # BUY trades: dynamic labels based on probability
            prob_pct = price * 100
            
            # Check if binary market (YES/NO)
            outcome_upper = outcome.upper() if outcome else ""
            is_binary = outcome_upper in ('YES', 'NO')
            
            if is_binary:
                # Binary market: YES @ X% or NO @ X%
                first_line = f"{get_probability_label(prob_pct)} — {outcome_upper} @ {prob_pct:.1f}%"
            else:
                # Non-binary market: BUY <outcome> @ X%
                outcome_text = outcome if outcome else "Unknown"
                first_line = f"{get_probability_label(prob_pct)} — BUY {outcome_text} @ {prob_pct:.1f}%"
        elif is_special:
            # SPLIT/MERGE/REDEEM: neutral format
            first_line = f"{side_upper} {outcome}".strip() if outcome else side_upper
        else:
            # SELL: neutral format
            if outcome:
                first_line = f"{side_upper} {outcome} @ {price*100:.1f}%"
            else:
                first_line = f"{side_upper} @ {price*100:.1f}%"
        
        # Build size line
        size_label = get_size_label(value_usd)
        if size_label:
            money_line = f"Size: ${value_usd:,.0f} 💵 — {size_label}"
        else:
            money_line = f"Size: ${value_usd:,.0f} 💵"
        
        # Trader info
        trader_address = trade_data.get('trader_address', '')
        trader_name = trade_data.get('name', '') or trade_data.get('trader_name', '')
        
        # Strip timestamp suffix if present (e.g. 0x...-123456789)
        if trader_name and trader_name.startswith('0x') and '-' in trader_name:
             trader_name = trader_name.split('-')[0]
        
        # Shorten address for display
        if trader_address and len(trader_address) > 12:
            short_address = f"{trader_address[:4]}…{trader_address[-4:]}"
        else:
            short_address = trader_address or 'Unknown'
        
        # Build trader display (description first, then colon and value)
        if is_buy and value_usd >= 100000:
            # BUY trades >= $100K: add description
            prob_pct = price * 100
            trader_desc = get_trader_description(value_usd, prob_pct)
            if trader_desc:
                if trader_name and trader_name.strip():
                    trader_display = f"{trader_desc}: {trader_name} 🐋"
                else:
                    trader_display = f"{trader_desc}: {short_address} 🐋"
            else:
                # Fallback if no description (shouldn't happen for >= $100K BUY)
                if trader_name and trader_name.strip():
                    trader_display = f"Trader: {trader_name} 🐋"
                else:
                    trader_display = f"Trader: {short_address} 🐋"
        else:
            # Non-BUY or < $100K: no description, use default format
            if trader_name and trader_name.strip():
                trader_display = f"Trader: {trader_name} 🐋"
            else:
                trader_display = f"Trader: {short_address} 🐋"
        
        # Wallet age (label first, then "age:", then value)
        wallet_age_str = trade_data.get('wallet_age_str', '')
        wallet_age_label = get_wallet_age_label(wallet_age_str) if wallet_age_str else None
        
        # Build tweet lines (strictly multi-line with blank lines)
        lines = [
            market_title,
            "",
            first_line,
            money_line,
            "",
            trader_display,
        ]
        
        if wallet_age_str:
            if wallet_age_label:
                lines.append(f"{wallet_age_label}, age: {wallet_age_str}")
            else:
                lines.append(f"Wallet age: {wallet_age_str}")
        
        # Add profile link to whale tweets
        if trader_address and trader_address.startswith('0x'):
            profile_link = f"https://polymarket.com/profile/{trader_address}"
            lines.append(profile_link)
        
        # Join with newlines
        tweet = "\n".join(lines)
        
        # Ensure tweet is under 4000 chars
        if len(tweet) > MAX_TWEET_TEXT_LEN:
            # Truncate market title
            max_title_len = MAX_TWEET_TEXT_LEN - (len(tweet) - len(market_title)) - 3
            if max_title_len > 20:
                market_title = market_title[:max_title_len] + "..."
                lines[0] = market_title
                tweet = "\n".join(lines)
        
        return tweet
    
    async def post_tweet(self, tweet_text: str) -> Optional[str]:
        """Post a tweet. Returns tweet ID if successful, None otherwise."""
        if not self.is_configured or not self.client:
            logger.warning("Twitter not configured, skipping post")
            return None
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            tweet_text = _finalize_tweet_text(tweet_text)
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
            
            # Check for 429 Rate Limit - calculate when next slot frees up
            if '429' in error_str or 'rate limit' in error_str.lower():
                wait_secs = get_seconds_until_next_tweet()
                wait_mins = wait_secs // 60
                wait_hours = wait_mins // 60
                tweets_count = get_tweets_in_last_24h()
                logger.warning(
                    f"Twitter 429 Rate Limit - {tweets_count}/{MAX_TWEETS_PER_24H} tweets in last 24h. "
                    f"Next slot available in {wait_hours}h{wait_mins%60}m"
                )
                return None
            
            # Log other errors
            logger.error(f"Failed to post tweet: {error_str}")
            return None
    
    async def post_trade_alert(self, trade_data: dict) -> Optional[str]:
        """Format and post a trade alert with anti-spam protection."""
        should, reason = self.should_post(trade_data)
        
        if not should:
            # If it's an interval limit or daily limit (but not paused/disabled), add to queue
            if reason.startswith('interval_limit') or reason.startswith('daily_limit'):
                await self._add_to_queue(trade_data)
                return None
            
            # For other reasons (disabled, paused, etc.), skip
            trader_id = self._get_trader_id(trade_data)
            trade_value = self._get_trade_value_usd(trade_data)
            logger.info(f"Tweet skipped: {reason} (trader: {trader_id[:10]}..., value: ${trade_value:,.0f})")
            return None
        
        # Can post immediately
        tweet_text = self.format_tweet(trade_data)
        result = await self.post_tweet(tweet_text)
        
        # If posted successfully, try to process queue
        if result:
            await self._process_pending_queue()
        
        return result
    
    def _get_queue_lock(self):
        """Get or create queue lock."""
        if self._queue_lock is None:
            self._queue_lock = asyncio.Lock()
        return self._queue_lock
    
    def _load_queue(self):
        """Load queue from disk."""
        try:
            if os.path.exists(TWITTER_QUEUE_FILE):
                with open(TWITTER_QUEUE_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert back to list of tuples
                    self.pending_queue = [(item['trade_data'], item['queued_at']) for item in data]
                    logger.info(f"Loaded {len(self.pending_queue)} items from Twitter queue")
        except Exception as e:
            logger.error(f"Error loading Twitter queue: {e}")
            self.pending_queue = []
    
    def _save_queue(self):
        """Save queue to disk."""
        try:
            # Convert to JSON-serializable format
            data = [{'trade_data': trade_data, 'queued_at': queued_at} 
                   for trade_data, queued_at in self.pending_queue]
            with open(TWITTER_QUEUE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving Twitter queue: {e}")
    
    def _get_trade_value_usd(self, trade_data: dict) -> float:
        """Calculate trade value in USD."""
        value_usd = trade_data.get('value_usd')
        if value_usd is not None:
            return float(value_usd)
        price = float(trade_data.get('price', 0))
        size = float(trade_data.get('size', 0))
        return price * size
    
    def _get_trader_id(self, trade_data: dict) -> str:
        """Get unique trader identifier (address or name)."""
        trader_address = trade_data.get('trader_address', '')
        if trader_address:
            return trader_address.lower()  # Normalize to lowercase
        # Fallback to trader name if no address
        trader_name = trade_data.get('trader_name', '') or trade_data.get('name', '')
        return trader_name.lower() if trader_name else 'unknown'
    
    async def _add_to_queue(self, trade_data: dict):
        """
        Add trade to pending queue with smart prioritization:
        1. Deduplicate by trader: if same trader exists, keep only the largest trade
        2. If queue is full (>= 10), prioritize by trade size, keep largest 10
        3. If queue is not full, maintain FIFO order
        """
        async with self._get_queue_lock():
            trader_id = self._get_trader_id(trade_data)
            trade_value = self._get_trade_value_usd(trade_data)
            queued_at = time.time()
            
            # Step 1: Check for duplicate trader - if exists, keep only the largest
            existing_index = None
            existing_value = 0
            for idx, (existing_trade, _) in enumerate(self.pending_queue):
                existing_trader_id = self._get_trader_id(existing_trade)
                if existing_trader_id == trader_id:
                    existing_value = self._get_trade_value_usd(existing_trade)
                    if trade_value > existing_value:
                        # New trade is larger, replace the existing one
                        existing_index = idx
                    else:
                        # Existing trade is larger or equal, skip adding new one
                        logger.info(f"Tweet skipped: trader {trader_id} already in queue with larger trade (${existing_value:,.0f} vs ${trade_value:,.0f})")
                        return
            
            # Remove existing duplicate if we found a larger trade
            if existing_index is not None:
                removed_trade = self.pending_queue.pop(existing_index)
                removed_value = self._get_trade_value_usd(removed_trade[0])
                logger.info(f"Replaced smaller trade from trader {trader_id} (${removed_value:,.0f} → ${trade_value:,.0f})")
            
            # Step 2: Add new trade to queue
            self.pending_queue.append((trade_data, queued_at))
            
            # Step 3: If queue is full (>= 10), prioritize by trade size
            if len(self.pending_queue) > self.max_queue_size:
                # Sort by trade value (descending) and keep only top max_queue_size
                self.pending_queue.sort(key=lambda x: self._get_trade_value_usd(x[0]), reverse=True)
                removed_count = len(self.pending_queue) - self.max_queue_size
                removed_trades = self.pending_queue[self.max_queue_size:]
                self.pending_queue = self.pending_queue[:self.max_queue_size]
                
                removed_values = [self._get_trade_value_usd(t[0]) for t in removed_trades]
                logger.warning(f"Twitter queue full ({len(self.pending_queue) + removed_count} > {self.max_queue_size}), "
                             f"removed {removed_count} smallest trades (values: ${', '.join(f'{v:,.0f}' for v in sorted(removed_values))})")
            
            logger.info(f"Tweet added to queue (size: {len(self.pending_queue)}/{self.max_queue_size}, "
                       f"value: ${trade_value:,.0f}, trader: {trader_id[:10]}...)")
            # Save queue to disk
            self._save_queue()
    
    async def _process_pending_queue(self):
        """Process pending queue - try to post tweets if interval allows."""
        async with self._get_queue_lock():
            queue_size = len(self.pending_queue)
            if not self.pending_queue:
                return
        
        # Check if we can post now
        wait_secs = get_seconds_until_next_tweet()
        if wait_secs > 0:
            # Still need to wait
            wait_mins = wait_secs // 60
            logger.info(f"Twitter queue: {queue_size} items waiting, need to wait {wait_mins}m {wait_secs%60}s")
            return
        
        # Try to post from queue
        async with self._get_queue_lock():
            if not self.pending_queue:
                return
            
            # Get oldest tweet from queue
            trade_data, queued_at = self.pending_queue.pop(0)
            queue_age_secs = int(time.time() - queued_at)
            queue_age_mins = queue_age_secs // 60
        
        # Double-check we can post
        should, reason = self.should_post(trade_data)
        if not should:
            # Still can't post, put it back at the end
            logger.warning(f"Twitter queue: Cannot post tweet queued {queue_age_mins}m ago, reason: {reason}. Returning to queue.")
            async with self._get_queue_lock():
                self.pending_queue.append((trade_data, queued_at))
                # Save queue to disk
                self._save_queue()
            return
        
        # Post the tweet
        trader_id = self._get_trader_id(trade_data)
        trade_value = self._get_trade_value_usd(trade_data)
        logger.info(f"Twitter queue: Processing tweet queued {queue_age_mins}m ago (trader: {trader_id[:10]}..., value: ${trade_value:,.0f})")
        tweet_text = self.format_tweet(trade_data)
        result = await self.post_tweet(tweet_text)
        
        if result:
            logger.info(f"Posted queued tweet (queue size: {len(self.pending_queue)})")
            # Save queue to disk
            self._save_queue()
            # Recursively process more from queue if possible
            await self._process_pending_queue()
        else:
            # Failed to post, put it back
            logger.warning(f"Twitter queue: Failed to post tweet, returning to front of queue")
            async with self._get_queue_lock():
                self.pending_queue.insert(0, (trade_data, queued_at))
                # Save queue to disk
                self._save_queue()
    
    def _get_delayed_lock(self):
        """Get or create lock for delayed queue operations."""
        if self._delayed_lock is None:
            self._delayed_lock = asyncio.Lock()
        return self._delayed_lock

    def _load_delayed_queue(self):
        """Load delayed queue (10‑minute hold) from disk."""
        try:
            if os.path.exists(self.delayed_queue_file):
                with open(self.delayed_queue_file, 'r') as f:
                    data = json.load(f)
                    # Basic validation: ensure it's a list of dicts
                    if isinstance(data, list):
                        self.delayed_queue = [item for item in data if isinstance(item, dict)]
                    else:
                        self.delayed_queue = []
                if self.delayed_queue:
                    logger.info(f"Loaded {len(self.delayed_queue)} items from Twitter delayed queue")
        except Exception as e:
            logger.error(f"Error loading Twitter delayed queue: {e}")
            self.delayed_queue = []

    def _save_delayed_queue(self):
        """Persist delayed queue to disk."""
        try:
            with open(self.delayed_queue_file, 'w') as f:
                json.dump(self.delayed_queue, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving Twitter delayed queue: {e}")

    def set_poly_service(self, poly_service):
        """Inject PolymarketService instance for position verification before tweeting."""
        self.poly_service = poly_service
        if poly_service:
            logger.info("TwitterService linked to PolymarketService for position re-checks")

    async def enqueue_with_delay(
        self,
        twitter_data: dict,
        *,
        condition_id: str,
        trader_address: str,
        trade_timestamp: float,
        delay_seconds: int | None = None,
    ) -> None:
        """
        Enqueue trade for delayed Twitter posting.
        
        Trade will be eligible for tweeting only after `delay_seconds`
        and only if wallet still holds a position on this market.
        """
        if not self.is_configured:
            logger.debug("Twitter not configured, skipping delayed enqueue")
            return

        # Resolve delay: explicit argument has priority over settings
        if delay_seconds is None:
            try:
                delay_seconds = int(_load_settings().get('delay_seconds', 600))
            except Exception:
                delay_seconds = 600

        # Normalize timestamp
        try:
            trade_ts = float(trade_timestamp or time.time())
        except (TypeError, ValueError):
            trade_ts = time.time()
        # Accept both seconds and milliseconds timestamps.
        if trade_ts > 1e10:
            trade_ts /= 1000.0

        ready_at = trade_ts + max(0, delay_seconds)

        entry = {
            "twitter_data": twitter_data,
            "condition_id": condition_id or "",
            "trader_address": trader_address or "",
            "trade_ts": trade_ts,
            "ready_at": ready_at,
        }

        async with self._get_delayed_lock():
            self.delayed_queue.append(entry)
            self._save_delayed_queue()
            logger.info(
                f"Twitter delayed enqueue: trader={trader_address[:10]}..., "
                f"market={condition_id[:10]}..., ready_in={int(ready_at - time.time())}s"
            )

    async def _process_delayed_queue_once(self):
        """
        Process delayed queue:
        - Only consider trades whose ready_at has passed (>= 10 minutes since trade)
        - For each, verify wallet still holds position on this market
        - If yes, forward to standard Twitter posting pipeline
        - In all cases, remove processed entries from delayed queue
        """
        async with self._get_delayed_lock():
            if not self.delayed_queue:
                return

            now = time.time()
            remaining = []

            for entry in self.delayed_queue:
                ready_at = float(entry.get("ready_at", 0))
                # Backward compatibility: old queue files may store ms timestamps.
                if ready_at > 1e10:
                    ready_at /= 1000.0
                condition_id = entry.get("condition_id") or ""
                trader_address = entry.get("trader_address") or ""
                twitter_data = entry.get("twitter_data") or {}

                # Not yet ready – keep in queue
                if now < ready_at:
                    remaining.append(entry)
                    continue

                # Must have both market and trader to verify
                if not condition_id or not trader_address:
                    logger.info("Dropping delayed Twitter entry: missing condition_id or trader_address")
                    continue

                if not self.poly_service:
                    # Polymarket service not wired – safer to skip tweeting than post without check
                    logger.warning(
                        f"Skipping delayed Twitter entry for {trader_address[:10]}... "
                        f"(no PolymarketService injected for position check)"
                    )
                    continue

                try:
                    position_value = await self.poly_service.check_wallet_has_position(trader_address, condition_id)
                except Exception as e:
                    logger.error(
                        f"Error checking position before Twitter post for {trader_address[:10]}...: {e}"
                    )
                    # On error, act conservatively and skip this tweet
                    continue

                if position_value <= 0:
                    logger.info(
                        f"Skipping Twitter signal: wallet {trader_address[:10]}... "
                        f"no longer holds market {condition_id[:10]}..."
                    )
                    continue

                # Wallet still holds position – forward to normal Twitter pipeline
                logger.info(
                    f"Delayed Twitter signal ready: wallet {trader_address[:10]}..., "
                    f"market {condition_id[:10]}..., position=${position_value:,.0f}"
                )
                
                # Re-fetch wallet age with cache bypass for accurate Twitter data
                try:
                    fresh_first_activity = await self.poly_service.get_trader_first_activity(
                        trader_address, bypass_cache=True
                    )
                    if fresh_first_activity:
                        # Calculate age string
                        import time as time_module
                        age_seconds = time_module.time() - fresh_first_activity
                        if age_seconds >= 0:
                            days = int(age_seconds / 86400)
                            if days >= 365:
                                years = days // 365
                                months = (days % 365) // 30
                                fresh_age_str = f"{years}y {months}mo" if months > 0 else f"{years}y"
                            elif days >= 30:
                                months = days // 30
                                remaining_days = days % 30
                                fresh_age_str = f"{months}mo {remaining_days}d" if remaining_days >= 7 else f"{months}mo"
                            elif days >= 1:
                                fresh_age_str = f"{days}d"
                            else:
                                hours = int(age_seconds / 3600)
                                fresh_age_str = f"{hours}h" if hours > 0 else "<1h"
                            
                            old_age = twitter_data.get('wallet_age_str', '')
                            if old_age != fresh_age_str:
                                logger.info(
                                    f"Twitter wallet age updated for {trader_address[:10]}...: "
                                    f"'{old_age}' -> '{fresh_age_str}'"
                                )
                            twitter_data['wallet_age_str'] = fresh_age_str
                except Exception as age_err:
                    logger.warning(f"Failed to refresh wallet age for Twitter: {age_err}")
                
                await self.post_trade_alert(twitter_data)

            # Replace queue with remaining entries and persist
            self.delayed_queue = remaining
            self._save_delayed_queue()
    
    async def process_queue_periodically(self, interval=60):
        """Background task to periodically check and process pending queue."""
        logger.info("Twitter queue processor started")
        while True:
            try:
                await asyncio.sleep(interval)
                await self._process_pending_queue()
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(interval)
    
    async def process_delayed_queue_periodically(self, interval=30):
        """Background task: periodically process delayed (10‑minute hold) queue."""
        logger.info("Twitter delayed queue processor started")
        while True:
            try:
                await self._process_delayed_queue_once()
            except Exception as e:
                logger.error(f"Error in delayed queue processor: {e}")
            await asyncio.sleep(interval)


# Global instance (lazy initialization)
_twitter_service = None


def get_twitter_service() -> Optional[TwitterService]:
    """Get the global Twitter service instance."""
    global _twitter_service
    if _twitter_service is None:
        _twitter_service = TwitterService()
    return _twitter_service if _twitter_service.is_configured else None
