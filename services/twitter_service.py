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
# Twitter queue file (stores pending queue)
TWITTER_QUEUE_FILE = os.path.join(os.path.dirname(__file__), '..', 'twitter_queue.json')

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

# Default settings
DEFAULT_SETTINGS = {
    'enabled': False,              # Default: Disabled
    'min_alert_usd': 100000,       # Default: $100K minimum for Twitter
    'tweet_timestamps': [],        # List of timestamps of successful tweets (for 24h rolling window)
    'paused_until': 0,            # Timestamp until which posting is paused (403 protection)
    'interval_minutes': 25,       # Minutes between tweets (minimum interval, but 24h limit takes priority)
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
        
        if self.is_configured:
            self._init_client()
            self._load_queue()  # Load queue from disk
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
        """Format trade data as a tweet. English only, no emojis in header."""
        # Extract data
        market_title = trade_data.get('title', 'Unknown Market')
        side = trade_data.get('side', 'UNKNOWN')
        outcome = trade_data.get('outcome', '')
        price = float(trade_data.get('price', 0))
        size = float(trade_data.get('size', 0))
        value_usd = price * size
        
        # For SPLIT/MERGE/REDEEM, use side if outcome is empty
        side_upper = side.upper()
        is_special = side_upper in ('SPLIT', 'MERGE', 'REDEEM')
        if is_special:
            # For special events, use side name (SPLIT, MERGE, or REDEEM + outcome if available)
            first_line_text = f"{side_upper} {outcome}".strip() if outcome else side_upper
        else:
            # For BUY/SELL, add side before outcome
            if outcome:
                first_line_text = f"{side_upper} {outcome}"  # "BUY Knicks"
            else:
                first_line_text = side_upper  # "BUY" or "SELL"
        
        # Trader info
        trader_address = trade_data.get('trader_address', '')
        trader_name = trade_data.get('name', '') or trade_data.get('trader_name', '')
        
        # Shorten address for display: 0xfffa…8864 (4-6 chars + … + 4 chars)
        if trader_address and len(trader_address) > 12:
            # Use 4-6 characters from start + … + 4 characters from end
            short_address = f"{trader_address[:4]}…{trader_address[-4:]}"
        else:
            short_address = trader_address or 'Unknown'
        
        # Trader display: always "Trader: ... 🐋"
        if trader_name and trader_name.strip():
            trader_display = f"Trader: {trader_name} 🐋"
        else:
            trader_display = f"Trader: {short_address} 🐋"
        
        # Profile URL with https://
        trader_url = f"https://polymarket.com/profile/{trader_address}" if trader_address else ""
        
        # Wallet age
        wallet_age = trade_data.get('wallet_age_str', '')
        
        # Money display - only first value with 💵
        money_line = f"Size: ${value_usd:,.0f} 💵"
        
        # Build tweet lines - new format
        # For SPLIT/MERGE/REDEEM, don't show price percentage
        if is_special:
            first_line = first_line_text  # Just "SPLIT", "MERGE", or "REDEEM"
        else:
            first_line = f"{first_line_text} @ {price*100:.1f}%"  # "YES @ 91.0%"
        
        lines = [
            first_line,
            money_line,  # "Size: $189,596 💵"
            "",
            f"Market: {market_title}",  # Market title without URL
            "",
            trader_display,  # "Trader: GoriIIa 🐋" or "Trader: 0xfffa…8864 🐋"
            f"Profile: {trader_url}" if trader_url else None,  # "Profile: https://polymarket.com/profile/0xfffa..."
        ]
        
        if wallet_age:
            lines.append(f"Wallet age: {wallet_age}")  # Lowercase "age"
        
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


# Global instance (lazy initialization)
_twitter_service = None


def get_twitter_service() -> Optional[TwitterService]:
    """Get the global Twitter service instance."""
    global _twitter_service
    if _twitter_service is None:
        _twitter_service = TwitterService()
    return _twitter_service if _twitter_service.is_configured else None
