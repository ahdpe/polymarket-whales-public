"""
SQLite storage for insider alerts detection system.
Stores raw trades for pattern analysis and manages alert settings.
"""
import sqlite3
import time
import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = "data/insider_alerts.db"


def _get_connection():
    """Get database connection with WAL mode for performance."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    # Set timeout to 5 seconds to prevent indefinite blocking on locks
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = _get_connection()
    try:
        # Table for storing raw trades for analysis
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_raw_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                wallet TEXT NOT NULL,
                wallet_age_hours REAL,
                outcome TEXT,
                trade_size_usd REAL NOT NULL,
                trade_action TEXT,
                timestamp INTEGER NOT NULL,
                username TEXT,
                market_title TEXT,
                event_slug TEXT,
                category TEXT,
                open_positions INTEGER,
                price REAL
            );
        """)
        
        # Migration: Add category column if missing
        try:
            conn.execute("ALTER TABLE alerts_raw_trades ADD COLUMN category TEXT;")
            logger.info("Migrated alerts_raw_trades: added category column")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: Add open_positions column if missing
        try:
            conn.execute("ALTER TABLE alerts_raw_trades ADD COLUMN open_positions INTEGER;")
            logger.info("Migrated alerts_raw_trades: added open_positions column")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: Add consumed_by_scenario column if missing
        try:
            conn.execute("ALTER TABLE alerts_raw_trades ADD COLUMN consumed_by_scenario TEXT;")
            logger.info("Migrated alerts_raw_trades: added consumed_by_scenario column")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: Add trade_key column for deduplication
        try:
            conn.execute("ALTER TABLE alerts_raw_trades ADD COLUMN trade_key TEXT;")
            logger.info("Migrated alerts_raw_trades: added trade_key column")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: Add price column if missing
        try:
            conn.execute("ALTER TABLE alerts_raw_trades ADD COLUMN price REAL;")
            logger.info("Migrated alerts_raw_trades: added price column")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        conn.execute("CREATE INDEX IF NOT EXISTS idx_market_timestamp ON alerts_raw_trades(market_id, timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON alerts_raw_trades(timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet ON alerts_raw_trades(wallet);")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_key ON alerts_raw_trades(trade_key);")
        
        # Table for settings persistence
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        
        # Table for deduplication (prevent spamming same alert)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_published (
                scenario TEXT NOT NULL,
                market_id TEXT NOT NULL,
                outcome TEXT,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (scenario, market_id, outcome)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_published_timestamp ON alerts_published(timestamp);")
        
        # Migration: Add extended columns to alerts_published if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN market_title TEXT;")
            conn.execute("ALTER TABLE alerts_published ADD COLUMN total_volume REAL;")
            conn.execute("ALTER TABLE alerts_published ADD COLUMN participants_count INTEGER;")
            logger.info("Migrated alerts_published: added extended columns")
        except sqlite3.OperationalError:
            pass  # Columns already exist
        
        # Migration: Add wallet_list column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN wallet_list TEXT;")
            logger.info("Migrated alerts_published: added wallet_list column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()
        logger.info("Insider alerts DB initialized")
    finally:
        conn.close()


def _generate_trade_key(trade_data: Dict[str, Any]) -> str:
    """
    Generate a unique key for trade deduplication.
    Key is based on: wallet + market_id + trade_size (rounded) + timestamp (rounded to 5 sec window).
    """
    wallet = trade_data.get('wallet', '')
    market_id = trade_data.get('market_id', '')
    # Round trade size to whole number to handle minor floating point differences
    trade_size = round(trade_data.get('trade_size_usd', 0), 0)
    # Round timestamp to 30-second window to catch near-duplicate entries
    # (same wallet, same market, same amount within 30 seconds = likely duplicate)
    timestamp = trade_data.get('timestamp', int(time.time()))
    ts_window = (timestamp // 30) * 30
    outcome = trade_data.get('outcome', '')
    
    return f"{wallet}|{market_id}|{trade_size}|{ts_window}|{outcome}"


def store_trade(trade_data: Dict[str, Any]) -> None:
    """
    Store trade for insider analysis.
    Uses trade_key for deduplication to prevent counting the same trade multiple times.
    """
    trade_key = _generate_trade_key(trade_data)
    
    conn = _get_connection()
    try:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO alerts_raw_trades 
            (market_id, wallet, wallet_age_hours, outcome, trade_size_usd, 
             trade_action, timestamp, username, market_title, event_slug, category, open_positions, consumed_by_scenario, trade_key, price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """, (
            trade_data.get('market_id'),
            trade_data.get('wallet'),
            trade_data.get('wallet_age_hours'),
            trade_data.get('outcome'),
            trade_data.get('trade_size_usd'),
            trade_data.get('trade_action'),
            trade_data.get('timestamp', int(time.time())),
            trade_data.get('username'),
            trade_data.get('market_title'),
            trade_data.get('event_slug'),
            trade_data.get('category'),
            trade_data.get('open_positions'),
            trade_key,
            trade_data.get('price')
        ))
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.debug(f"Stored trade for insider alerts: market={trade_data.get('market_id')}, size=${trade_data.get('trade_size_usd', 0):,.0f}")
        else:
            logger.debug(f"Skipped duplicate trade: {trade_key[:50]}...")
    finally:
        conn.close()


def cleanup_old_trades(ttl_hours: int = 72) -> int:
    """Remove trades older than TTL."""
    cutoff = int(time.time()) - (ttl_hours * 3600)
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM alerts_raw_trades WHERE timestamp < ?",
            (cutoff,)
        )
        deleted = cursor.rowcount
        conn.commit()
        
        # Run VACUUM periodically to reclaim space (every 24 hours or if deleted > 10k)
        import os
        vacuum_file = os.path.join(os.path.dirname(DB_PATH), '.last_vacuum_insider')
        last_vacuum = 0
        if os.path.exists(vacuum_file):
            try:
                last_vacuum = float(open(vacuum_file).read().strip())
            except:
                pass
        
        should_vacuum = (time.time() - last_vacuum > 86400) or deleted > 10000
        if should_vacuum:
            try:
                logger.info(f"Running VACUUM on insider_alerts.db (deleted {deleted} old trades)")
                conn.execute("VACUUM")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                with open(vacuum_file, 'w') as f:
                    f.write(str(time.time()))
            except Exception as e:
                logger.error(f"Error during VACUUM: {e}")
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old trades (older than {ttl_hours}h)")
        return deleted
    finally:
        conn.close()


def mark_trades_consumed(trade_ids: List[int], scenario: str) -> int:
    """
    Mark trades as consumed by a specific scenario.
    Consumed trades will not be returned by get_trades_window anymore.
    
    Args:
        trade_ids: List of trade IDs to mark
        scenario: The scenario that consumed them (CLUSTER, BURST, etc.)
        
    Returns:
        Number of updated rows
    """
    if not trade_ids:
        return 0
        
    conn = _get_connection()
    try:
        placeholders = ','.join(['?'] * len(trade_ids))
        cursor = conn.execute(
            f"""
            UPDATE alerts_raw_trades 
            SET consumed_by_scenario = ? 
            WHERE id IN ({placeholders})
            """,
            [scenario] + trade_ids
        )
        updated = cursor.rowcount
        conn.commit()
        logger.info(f"Marked {updated} trades as consumed by {scenario}")
        return updated
    finally:
        conn.close()


def get_trades_window(
    market_id: str,
    window_hours: float,
    max_wallet_age_hours: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Get trades for a market within a time window.
    EXCLUDES trades already consumed by another scenario.
    """
    cutoff = int(time.time()) - int(window_hours * 3600)
    conn = _get_connection()
    try:
        # Base query excludes consumed trades
        base_query = """
            SELECT * FROM alerts_raw_trades
            WHERE market_id = ? 
              AND timestamp >= ?
              AND consumed_by_scenario IS NULL
        """
        
        if max_wallet_age_hours is not None:
            query = base_query + " AND (wallet_age_hours IS NULL OR wallet_age_hours <= ?) ORDER BY timestamp DESC"
            rows = conn.execute(query, (market_id, cutoff, max_wallet_age_hours)).fetchall()
        else:
            query = base_query + " ORDER BY timestamp DESC"
            rows = conn.execute(query, (market_id, cutoff)).fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_trades_for_repeat(
    market_id: str,
    days_back: int = 14
) -> List[Dict[str, Any]]:
    """
    Get trades for REPEAT scenario (multi-day analysis).
    
    Args:
        market_id: Market identifier
        days_back: How many days to look back
    
    Returns:
        List of trade dicts
    """
    cutoff = int(time.time()) - (days_back * 24 * 3600)
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM alerts_raw_trades
            WHERE market_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (market_id, cutoff)).fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_active_markets(hours_back: float = 24) -> List[Dict[str, str]]:
    """
    Get list of market_ids with recent activity, including their category.
    
    Args:
        hours_back: How far back to look for activity
    
    Returns:
        List of dicts with 'market_id' and 'category'
    """
    cutoff = int(time.time()) - int(hours_back * 3600)
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT DISTINCT market_id, category
            FROM alerts_raw_trades
            WHERE timestamp >= ?
              AND consumed_by_scenario IS NULL
        """, (cutoff,)).fetchall()
        
        return [{'market_id': row['market_id'], 'category': row['category'] or 'other'} for row in rows]
    finally:
        conn.close()


def reclassify_recent_trades(hours_back: float = 72, batch_limit: int = 5000, reclassifier=None) -> int:
    """
    Re-run category detection for recent trades (helps fix misclassified sports/crypto).
    
    Args:
        hours_back: how many hours back to reclassify
        batch_limit: safety limit to avoid huge updates
        reclassifier: callable(title, slug, url) -> category
    
    Returns:
        number of rows updated
    """
    if reclassifier is None:
        return 0
    
    cutoff = int(time.time()) - int(hours_back * 3600)
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, market_title, event_slug, category
            FROM alerts_raw_trades
            WHERE timestamp >= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (cutoff, batch_limit),
        ).fetchall()

        updated = 0
        for row in rows:
            title = row["market_title"] or ""
            slug = row["event_slug"] or ""
            url = f"https://polymarket.com/event/{slug}" if slug else ""
            new_cat = reclassifier(title, slug, url)
            if new_cat and new_cat != (row["category"] or ""):
                conn.execute(
                    "UPDATE alerts_raw_trades SET category = ? WHERE id = ?",
                    (new_cat, row["id"]),
                )
                updated += 1

        if updated:
            conn.commit()
        return updated
    finally:
        conn.close()


def save_setting(key: str, value: Any) -> None:
    """Save a configuration setting."""
    conn = _get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO alerts_settings (key, value)
            VALUES (?, ?)
        """, (key, str(value)))
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: Any = None) -> Optional[str]:
    """Get a configuration setting."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM alerts_settings WHERE key = ?",
            (key,)
        ).fetchone()
        return row['value'] if row else default
    finally:
        conn.close()


def mark_published(
    scenario: str, 
    market_id: str, 
    outcome: str, 
    market_title: str = None, 
    total_volume: float = 0.0, 
    participants_count: int = 0,
    wallet_list: List[str] = None
) -> None:
    """Mark an alert as published to prevent duplicates."""
    import json
    conn = _get_connection()
    try:
        # Serialize wallet_list to JSON string
        wallet_list_json = json.dumps(wallet_list) if wallet_list else None
        
        conn.execute("""
            INSERT OR REPLACE INTO alerts_published 
            (scenario, market_id, outcome, timestamp, market_title, total_volume, participants_count, wallet_list)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scenario, 
            market_id, 
            outcome, 
            int(time.time()),
            market_title,
            total_volume,
            participants_count,
            wallet_list_json
        ))
        conn.commit()
    finally:
        conn.close()


def get_recent_published(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recently published alerts for dashboard."""
    import json
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM alerts_published
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        result = []
        for row in rows:
            row_dict = dict(row)
            # Deserialize wallet_list from JSON string
            if row_dict.get('wallet_list'):
                try:
                    row_dict['wallet_list'] = json.loads(row_dict['wallet_list'])
                except (json.JSONDecodeError, TypeError):
                    row_dict['wallet_list'] = []
            else:
                row_dict['wallet_list'] = []
            result.append(row_dict)
        return result
    finally:
        conn.close()


def was_published(
    scenario: str,
    market_id: str,
    outcome: str,
    cooldown_hours: int = 24
) -> bool:
    """
    Check if alert was recently published.
    
    Args:
        scenario: Scenario name (CLUSTER, REPEAT, BURST)
        market_id: Market identifier
        outcome: YES or NO
        cooldown_hours: How long to suppress duplicates
    
    Returns:
        True if already published within cooldown period
    """
    cutoff = int(time.time()) - (cooldown_hours * 3600)
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT timestamp FROM alerts_published
            WHERE scenario = ? AND market_id = ? AND outcome = ?
              AND timestamp >= ?
        """, (scenario, market_id, outcome, cutoff)).fetchone()
        
        return row is not None
    finally:
        conn.close()


def cleanup_old_published(days: int = 7) -> int:
    """
    Clean up old published records.
    
    Args:
        days: Keep records from last N days
    
    Returns:
        Number of deleted rows
    """
    cutoff = int(time.time()) - (days * 24 * 3600)
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM alerts_published WHERE timestamp < ?",
            (cutoff,)
        )
        deleted = cursor.rowcount
        conn.commit()
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old published records")
        
        return deleted
    finally:
        conn.close()


def get_stats() -> Dict[str, Any]:
    """Get database statistics for monitoring."""
    conn = _get_connection()
    try:
        trades_count = conn.execute("SELECT COUNT(*) as cnt FROM alerts_raw_trades").fetchone()['cnt']
        settings_count = conn.execute("SELECT COUNT(*) as cnt FROM alerts_settings").fetchone()['cnt']
        published_count = conn.execute("SELECT COUNT(*) as cnt FROM alerts_published").fetchone()['cnt']
        
        # Get oldest and newest trade timestamps
        oldest = conn.execute("SELECT MIN(timestamp) as ts FROM alerts_raw_trades").fetchone()['ts']
        newest = conn.execute("SELECT MAX(timestamp) as ts FROM alerts_raw_trades").fetchone()['ts']
        
        return {
            'trades_stored': trades_count,
            'settings_count': settings_count,
            'alerts_published': published_count,
            'oldest_trade': oldest,
            'newest_trade': newest,
            'db_path': DB_PATH
        }
    finally:
        conn.close()
