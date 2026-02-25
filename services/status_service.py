"""
Status Dashboard Service for PolymarketWhales Bot.
Collects and aggregates all bot metrics for the web dashboard.
"""
import os
import time
import json
import sqlite3
import threading
import psutil
import logging
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)

# Bot start time (set by main.py)
BOT_START_TIME = None

# Reference to PolymarketService (set by main.py)
_poly_service = None

# Reference to InsiderAlertsService (set by main.py)
_insider_service = None

# Whale trades ring buffer (BUY trades >= $10K for /whale-trades page)
_whale_trades_lock = threading.Lock()
_whale_trades_buffer = []  # List of dicts, newest first
_WHALE_TRADES_MAX = 200    # Keep last 200 trades in memory

# Small in-memory cache to reduce expensive status recomputation under concurrent dashboard opens.
try:
    STATUS_CACHE_TTL_SEC = max(0.0, float(os.getenv("STATUS_CACHE_TTL_SEC", "2.0")))
except (TypeError, ValueError):
    STATUS_CACHE_TTL_SEC = 2.0
_status_cache_lock = threading.Lock()
_status_cache_payload = None
_status_cache_ts = 0.0


def set_start_time(start_time: float):
    """Set bot start time for uptime calculation."""
    global BOT_START_TIME
    BOT_START_TIME = start_time


def set_poly_service(service):
    """Set reference to PolymarketService for stats."""
    global _poly_service
    _poly_service = service


def set_insider_service(service):
    """Set reference to InsiderAlertsService for stats."""
    global _insider_service
    _insider_service = service


def format_uptime(seconds: float) -> str:
    """Format uptime as human-readable string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes} B"


def get_system_stats() -> dict:
    """Get system resource statistics."""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_percent = process.memory_percent()
        system_mem = psutil.virtual_memory()
        
        uptime_seconds = time.time() - BOT_START_TIME if BOT_START_TIME else 0
        
        return {
            "pid": os.getpid(),
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": format_uptime(uptime_seconds),
            "start_time": datetime.fromtimestamp(BOT_START_TIME).strftime("%Y-%m-%d %H:%M:%S") if BOT_START_TIME else "N/A",
            "memory": {
                "rss_bytes": mem_info.rss,
                "rss_formatted": format_bytes(mem_info.rss),
                "percent": round(mem_percent, 2),
            },
            "system_memory": {
                "total_bytes": system_mem.total,
                "total_formatted": format_bytes(system_mem.total),
                "used_bytes": system_mem.used,
                "used_formatted": format_bytes(system_mem.used),
                "available_bytes": system_mem.available,
                "available_formatted": format_bytes(system_mem.available),
                "percent": round(system_mem.percent, 1),
            }
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {"error": str(e)}


def get_user_stats() -> dict:
    """Get user statistics from user_settings.json."""
    try:
        with open("user_settings.json", "r") as f:
            data = json.load(f)
        
        filters = data.get("filters", {})
        statuses = data.get("statuses", {})
        languages = data.get("languages", {})
        categories = data.get("categories", {})
        probabilities = data.get("probabilities", {})
        side_types = data.get("side_types", {})
        wallet_ages = data.get("wallet_ages", {})
        open_positions = data.get("open_positions", {})
        blocked_users = data.get("blocked_users", {})  # Track blocked users
        
        total_users = len(filters)
        active_users = sum(1 for v in statuses.values() if v)
        blocked_count = len(blocked_users)
        # Paused = inactive users who are NOT blocked
        paused_users = total_users - active_users - blocked_count
        inactive_users = total_users - active_users  # Total inactive (paused + blocked)
        
        # Language distribution
        lang_counter = Counter(languages.values())
        
        # Threshold distribution
        threshold_counter = Counter(filters.values())
        
        # Category preferences (how many enabled each)
        cat_enabled = {"crypto": 0, "sports": 0, "other": 0, "all": 0}
        for user_cats in categories.values():
            for cat, enabled in user_cats.items():
                if enabled and cat in cat_enabled:
                    cat_enabled[cat] += 1
        
        # Probability filter distribution
        prob_counter = Counter(probabilities.values())
        
        # Side type preferences (how many enabled each)
        side_enabled = {"BUY": 0, "SELL": 0, "SPLIT": 0, "MERGE": 0, "REDEEM": 0, "all": 0}
        for user_sides in side_types.values():
            for side, enabled in user_sides.items():
                if enabled and side in side_enabled:
                    side_enabled[side] += 1
        
        # Wallet age filter usage
        age_filter_users = sum(1 for v in wallet_ages.values() 
                               if v and (v.get("min_days") is not None or v.get("max_days") is not None))
        
        # Open positions filter usage
        pos_filter_users = sum(1 for v in open_positions.values() 
                               if v and (v.get("min_count") is not None or v.get("max_count") is not None))
        
        return {
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users,
            "paused": paused_users,  # Manually paused
            "blocked": blocked_count,  # Blocked the bot
            "bot_enabled": data.get("bot_enabled", True),
            "languages": dict(lang_counter),
            "thresholds": {str(k): v for k, v in sorted(threshold_counter.items())},
            "categories": cat_enabled,
            "probabilities": dict(prob_counter),
            "side_types": side_enabled,
            "age_filter_users": age_filter_users,
            "positions_filter_users": pos_filter_users,
        }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {"error": str(e)}


def get_twitter_stats() -> dict:
    """Get Twitter integration statistics."""
    try:
        settings_path = "twitter_settings.json"
        if not os.path.exists(settings_path):
            return {"enabled": False, "configured": False}
        
        with open(settings_path, "r") as f:
            settings = json.load(f)
        
        # Count tweets in last 24 hours
        timestamps = settings.get("tweet_timestamps", [])
        now = time.time()
        cutoff = now - 86400  # 24 hours ago
        tweets_24h = sum(1 for ts in timestamps if ts > cutoff)
        
        # Check if paused
        paused_until = settings.get("paused_until", 0)
        is_paused = paused_until > now
        pause_remaining = max(0, paused_until - now) if is_paused else 0
        
        # Queue size
        queue_size = 0
        queue_path = "twitter_queue.json"
        if os.path.exists(queue_path):
            try:
                with open(queue_path, "r") as f:
                    queue = json.load(f)
                    queue_size = len(queue) if isinstance(queue, list) else 0
            except Exception:
                pass
        
        return {
            "enabled": settings.get("enabled", False),
            "configured": True,
            "min_alert_usd": settings.get("min_alert_usd", 100000),
            "min_insider_usd": settings.get("min_alert_insider_usd", 20000),
            "max_insider_age_days": settings.get("max_insider_age_days", 7),
            "max_insider_positions": settings.get("max_insider_positions", 5),
            "interval_minutes": settings.get("interval_minutes", 25),
            "probability_filter": f"{settings.get('probability_min', 1)}_{settings.get('probability_max', 99)}" if settings.get("probability_min") is not None and settings.get("probability_max") is not None else settings.get("probability_filter", "any"),
            "allow_sell": settings.get("allow_sell", True),
            "allow_split": settings.get("allow_split", True),
            "allow_merge": settings.get("allow_merge", True),
            "allow_redeem": settings.get("allow_redeem", True),
            "categories": settings.get("categories", {}),
            "tweets_24h": tweets_24h,
            "max_tweets_24h": 17,
            "is_paused": is_paused,
            "pause_remaining_seconds": int(pause_remaining),
            "queue_size": queue_size,
        }
    except Exception as e:
        logger.error(f"Error getting Twitter stats: {e}")
        return {"error": str(e)}


def get_database_stats() -> dict:
    """Get database statistics."""
    stats = {
        "saved_whales": {},
        "trades": {},
    }
    
    # Saved whales DB
    try:
        db_path = "data/saved_whales.db"
        if os.path.exists(db_path):
            stats["saved_whales"]["size_bytes"] = os.path.getsize(db_path)
            stats["saved_whales"]["size_formatted"] = format_bytes(os.path.getsize(db_path))
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM saved_whales")
            stats["saved_whales"]["saved_count"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM whale_keys")
            stats["saved_whales"]["keys_count"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM saved_whales")
            stats["saved_whales"]["users_with_favorites"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM saved_whales WHERE notifications_enabled = 1")
            stats["saved_whales"]["notifications_enabled"] = cursor.fetchone()[0]
            
            conn.close()
    except Exception as e:
        logger.error(f"Error getting saved_whales stats: {e}")
        stats["saved_whales"]["error"] = str(e)
    
    # Trades DB
    try:
        db_path = "data/trades.db"
        if os.path.exists(db_path):
            total_size = os.path.getsize(db_path)
            
            # Include WAL file if exists
            wal_path = db_path + "-wal"
            if os.path.exists(wal_path):
                total_size += os.path.getsize(wal_path)
            
            stats["trades"]["size_bytes"] = total_size
            stats["trades"]["size_formatted"] = format_bytes(total_size)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM seen_trades")
            stats["trades"]["count"] = cursor.fetchone()[0]
            
            conn.close()
    except Exception as e:
        logger.error(f"Error getting trades stats: {e}")
        stats["trades"]["error"] = str(e)
    
    return stats


def get_file_stats() -> dict:
    """Get data file sizes."""
    files = {}
    
    file_list = [
        ("user_settings.json", "user_settings.json"),
        ("twitter_settings.json", "twitter_settings.json"),
        ("twitter_queue.json", "twitter_queue.json"),
        ("bot_output.log", "bot_output.log"),
        ("bot.log", "bot.log"),
    ]
    
    total_size = 0
    for name, path in file_list:
        if os.path.exists(path):
            size = os.path.getsize(path)
            total_size += size
            files[name] = {
                "size_bytes": size,
                "size_formatted": format_bytes(size),
            }
    
    files["_total"] = {
        "size_bytes": total_size,
        "size_formatted": format_bytes(total_size),
    }
    
    return files


def get_polymarket_stats() -> dict:
    """Get Polymarket service statistics."""
    if not _poly_service:
        return {"available": False}
    
    try:
        stats = _poly_service.get_stats()
        
        # Calculate time since last update
        last_ts = stats.get("last_timestamp", 0)
        if last_ts:
            # Support both seconds and legacy milliseconds timestamps.
            last_ts_sec = float(last_ts)
            if last_ts_sec > 1e10:
                last_ts_sec /= 1000.0
            seconds_ago = int(time.time() - last_ts_sec)
            if seconds_ago < 0:
                seconds_ago = 0
        else:
            seconds_ago = None
        
        return {
            "available": True,
            "total_processed": stats.get("total_processed", 0),
            "lru_size": stats.get("lru_size", 0),
            "active_series": stats.get("active_series", 0),
            "consecutive_errors": stats.get("consecutive_errors", 0),
            "last_update_seconds_ago": seconds_ago,
        }
    except Exception as e:
        logger.error(f"Error getting Polymarket stats: {e}")
        return {"available": False, "error": str(e)}


def get_insider_stats() -> dict:
    """Get Insider Alerts statistics."""
    if not _insider_service:
        return {"enabled": False, "available": False}
    
    try:
        # Re-use get_status from service which returns settings + stats + pending
        return _insider_service.get_status()
    except Exception as e:
        logger.error(f"Error getting Insider stats: {e}")
        return {"available": False, "error": str(e)}


def get_full_status() -> dict:
    """Get complete bot status with all metrics."""
    global _status_cache_payload, _status_cache_ts

    now = time.time()
    with _status_cache_lock:
        if (
            _status_cache_payload is not None
            and STATUS_CACHE_TTL_SEC > 0
            and (now - _status_cache_ts) < STATUS_CACHE_TTL_SEC
        ):
            return _status_cache_payload

    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp_unix": int(now),
        "system": get_system_stats(),
        "users": get_user_stats(),
        "twitter": get_twitter_stats(),
        "databases": get_database_stats(),
        "files": get_file_stats(),
        "polymarket": get_polymarket_stats(),
        "insider": get_insider_stats(),
    }

    with _status_cache_lock:
        _status_cache_payload = payload
        _status_cache_ts = now

    return payload


def add_whale_trade(trade_entry: dict):
    """Add a whale BUY trade (>=$10K) to the ring buffer for /whale-trades page.
    
    Expected fields: market_title, event_slug, trader_name, trader_address,
    amount, outcome, price, open_pnl, open_pnl_pct, open_positions,
    positions_value, wallet_age_hours, category, timestamp
    """
    with _whale_trades_lock:
        _whale_trades_buffer.insert(0, trade_entry)
        if len(_whale_trades_buffer) > _WHALE_TRADES_MAX:
            del _whale_trades_buffer[_WHALE_TRADES_MAX:]


def get_whale_trades(limit: int = 100) -> list:
    """Return whale trades from the ring buffer, newest first."""
    with _whale_trades_lock:
        return list(_whale_trades_buffer[:limit])
