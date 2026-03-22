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

        # ===== Published alert events history (for website) =====
        # Each published "signal" becomes its own event row so history is preserved.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_published_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario TEXT NOT NULL,
                market_id TEXT NOT NULL,
                outcome TEXT,
                published_at INTEGER NOT NULL,
                market_title TEXT,
                event_slug TEXT,
                directionality REAL,
                entry_price REAL,
                total_volume REAL,
                participants_count INTEGER,
                result_status TEXT DEFAULT 'pending'
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_published_events_time
            ON alerts_published_events(published_at DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_published_events_key
            ON alerts_published_events(scenario, market_id, outcome, published_at DESC);
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_published_event_wallets (
                event_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                role TEXT NOT NULL, -- 'original' or 'appended'
                outcome TEXT,
                added_at INTEGER NOT NULL,
                PRIMARY KEY (event_id, wallet),
                FOREIGN KEY (event_id) REFERENCES alerts_published_events(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_wallets_event_role
            ON alerts_published_event_wallets(event_id, role);
        """)
        
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

        # Migration: Add event_slug column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN event_slug TEXT;")
            logger.info("Migrated alerts_published: added event_slug column")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: Add directionality column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN directionality REAL;")
            logger.info("Migrated alerts_published: added directionality column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add entry_price column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN entry_price REAL;")
            logger.info("Migrated alerts_published: added entry_price column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add result_status column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN result_status TEXT DEFAULT 'pending';")
            logger.info("Migrated alerts_published: added result_status column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add original_wallet_list column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN original_wallet_list TEXT;")
            logger.info("Migrated alerts_published: added original_wallet_list column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add appended_wallets_info column if missing
        try:
            conn.execute("ALTER TABLE alerts_published ADD COLUMN appended_wallets_info TEXT;")
            logger.info("Migrated alerts_published: added appended_wallets_info column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Backfill: if we already have alerts_published rows but no events history,
        # create a baseline event for each current published record so the website
        # can show something immediately. Older overwritten history cannot be recovered here.
        try:
            existing_events = conn.execute("SELECT COUNT(1) AS c FROM alerts_published_events").fetchone()
            if existing_events and int(existing_events["c"] or 0) == 0:
                rows = conn.execute("""
                    SELECT scenario, market_id, outcome, timestamp, market_title, event_slug,
                           directionality, entry_price, total_volume, participants_count,
                           wallet_list, original_wallet_list, appended_wallets_info, result_status
                    FROM alerts_published
                    ORDER BY timestamp DESC
                """).fetchall()
                import json

                def _loads_list(v):
                    if not v:
                        return []
                    try:
                        return json.loads(v)
                    except Exception:
                        return []

                def _loads_dict(v):
                    if not v:
                        return {}
                    try:
                        return json.loads(v)
                    except Exception:
                        return {}

                for r in rows:
                    conn.execute("""
                        INSERT INTO alerts_published_events
                        (scenario, market_id, outcome, published_at, market_title, event_slug,
                         directionality, entry_price, total_volume, participants_count, result_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        r["scenario"],
                        r["market_id"],
                        r["outcome"],
                        int(r["timestamp"] or int(time.time())),
                        r["market_title"],
                        r["event_slug"],
                        r["directionality"],
                        r["entry_price"],
                        r["total_volume"],
                        r["participants_count"],
                        r["result_status"] or "pending",
                    ))
                    event_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

                    original_wallets = _loads_list(r["original_wallet_list"]) or _loads_list(r["wallet_list"])
                    appended_info = _loads_dict(r["appended_wallets_info"])
                    appended_wallets = list(appended_info.keys()) if appended_info else []

                    now_ts = int(time.time())
                    for w in original_wallets:
                        if not w:
                            continue
                        conn.execute("""
                            INSERT OR IGNORE INTO alerts_published_event_wallets
                            (event_id, wallet, role, outcome, added_at)
                            VALUES (?, ?, 'original', NULL, ?)
                        """, (event_id, w, now_ts))
                    for w in appended_wallets:
                        if not w:
                            continue
                        conn.execute("""
                            INSERT OR IGNORE INTO alerts_published_event_wallets
                            (event_id, wallet, role, outcome, added_at)
                            VALUES (?, ?, 'appended', ?, ?)
                        """, (event_id, w, appended_info.get(w), now_ts))

                logger.info(f"Backfilled {len(rows)} baseline published events for website history")
        except Exception as e:
            logger.error(f"Backfill alerts_published_events failed: {e}")
            
        conn.commit()
        logger.info("Insider alerts DB initialized")
    finally:
        conn.close()


def _get_latest_event_id(conn, scenario: str, market_id: str, outcome: str) -> Optional[int]:
    row = conn.execute(
        """
        SELECT id FROM alerts_published_events
        WHERE scenario = ? AND market_id = ? AND outcome = ?
        ORDER BY published_at DESC, id DESC
        LIMIT 1
        """,
        (scenario, market_id, outcome),
    ).fetchone()
    if not row:
        return None
    try:
        return int(row["id"])
    except Exception:
        return None


def create_published_event(
    scenario: str,
    market_id: str,
    outcome: str,
    published_at: int,
    market_title: Optional[str] = None,
    event_slug: Optional[str] = None,
    directionality: Optional[float] = None,
    entry_price: Optional[float] = None,
    total_volume: float = 0.0,
    participants_count: int = 0,
    original_wallets: Optional[List[str]] = None,
) -> int:
    """
    Create a new published event for website history.

    Also performs de-dup transfer:
    wallets that were previously appended to the prior event for the same (scenario, market_id, outcome)
    and are now part of this new event's original set will be removed from that prior event's appended list,
    so the website never shows the same wallet duplicated across published events.
    """
    original_wallets = [w for w in (original_wallets or []) if w]
    conn = _get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        previous_event_id = _get_latest_event_id(conn, scenario, market_id, outcome)

        conn.execute(
            """
            INSERT INTO alerts_published_events
            (scenario, market_id, outcome, published_at, market_title, event_slug,
             directionality, entry_price, total_volume, participants_count, result_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                scenario,
                market_id,
                outcome,
                int(published_at),
                market_title,
                event_slug,
                directionality,
                entry_price,
                float(total_volume or 0.0),
                int(participants_count or 0),
            ),
        )
        event_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

        now_ts = int(time.time())
        for w in original_wallets:
            conn.execute(
                """
                INSERT OR IGNORE INTO alerts_published_event_wallets
                (event_id, wallet, role, outcome, added_at)
                VALUES (?, ?, 'original', NULL, ?)
                """,
                (event_id, w, now_ts),
            )

        if previous_event_id and original_wallets:
            placeholders = ",".join(["?"] * len(original_wallets))
            conn.execute(
                f"""
                DELETE FROM alerts_published_event_wallets
                WHERE event_id = ?
                  AND role = 'appended'
                  AND wallet IN ({placeholders})
                """,
                (previous_event_id, *original_wallets),
            )

        conn.commit()
        return event_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def append_wallets_to_latest_event(
    scenario: str,
    market_id: str,
    outcome: str,
    new_wallets: List[str],
    additional_volume: float,
    wallet_outcomes: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Append wallets to the latest published event for a given key.

    This is website-only enrichment ("+N since signal"). When a new published event is created for
    the same key, any overlapping wallets will be removed from the prior event's appended set.
    """
    new_wallets = [w for w in (new_wallets or []) if w]
    if not new_wallets and additional_volume <= 0:
        return False

    conn = _get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        event_id = _get_latest_event_id(conn, scenario, market_id, outcome)
        if not event_id:
            conn.rollback()
            return False

        now_ts = int(time.time())
        inserted_any = False
        for w in new_wallets:
            exists = conn.execute(
                """
                SELECT role FROM alerts_published_event_wallets
                WHERE event_id = ? AND wallet = ?
                """,
                (event_id, w),
            ).fetchone()
            if exists and (exists["role"] or "") == "original":
                continue

            out = (wallet_outcomes or {}).get(w)
            conn.execute(
                """
                INSERT OR REPLACE INTO alerts_published_event_wallets
                (event_id, wallet, role, outcome, added_at)
                VALUES (?, ?, 'appended', ?, ?)
                """,
                (event_id, w, out, now_ts),
            )
            inserted_any = True

        if additional_volume:
            conn.execute(
                """
                UPDATE alerts_published_events
                SET total_volume = COALESCE(total_volume, 0) + ?
                WHERE id = ?
                """,
                (float(additional_volume), event_id),
            )

        conn.commit()
        return inserted_any or bool(additional_volume)
    except Exception as e:
        conn.rollback()
        logger.error(f"Error appending wallets to latest event: {e}")
        return False
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
    wallet_list: List[str] = None,
    event_slug: str = None,
    directionality: float = 0.0
) -> None:
    """Mark an alert as published to prevent duplicates."""
    import json
    conn = _get_connection()
    try:
        # Serialize wallet_list to JSON string
        wallet_list_json = json.dumps(wallet_list) if wallet_list else None
        
        conn.execute("""
            INSERT OR REPLACE INTO alerts_published 
            (scenario, market_id, outcome, timestamp, market_title, total_volume, participants_count, wallet_list, event_slug, directionality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scenario, 
            market_id, 
            outcome, 
            int(time.time()),
            market_title,
            total_volume,
            participants_count,
            wallet_list_json,
            event_slug,
            directionality
        ))
        conn.commit()
    finally:
        conn.close()


def get_recent_published(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recently published alerts for dashboard."""
    import json
    conn = _get_connection()
    try:
        # Prefer event history (website): each signal is its own event, preserving history.
        events = conn.execute(
            """
            SELECT id, scenario, market_id, outcome, published_at, market_title, event_slug,
                   directionality, entry_price, total_volume, participants_count, result_status
            FROM alerts_published_events
            ORDER BY published_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for e in events:
            event_id = int(e["id"])
            wallets = conn.execute(
                """
                SELECT wallet, role, outcome
                FROM alerts_published_event_wallets
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchall()

            original_wallets: List[str] = []
            appended_wallets: List[str] = []
            appended_info: Dict[str, str] = {}

            for w in wallets:
                addr = w["wallet"]
                role = (w["role"] or "").lower()
                if role == "original":
                    original_wallets.append(addr)
                elif role == "appended":
                    appended_wallets.append(addr)
                    if w["outcome"]:
                        appended_info[addr] = w["outcome"]

            # wallet_list drives the UI list; keep originals first, then appended.
            wallet_list = original_wallets + [w for w in appended_wallets if w not in set(original_wallets)]

            row_dict = {
                "scenario": e["scenario"],
                "market_id": e["market_id"],
                "outcome": e["outcome"],
                # Keep legacy key name for frontend code:
                "timestamp": int(e["published_at"] or 0),
                "market_title": e["market_title"],
                "event_slug": e["event_slug"],
                "directionality": e["directionality"],
                "entry_price": e["entry_price"],
                "total_volume": e["total_volume"] or 0,
                "participants_count": e["participants_count"] or 0,
                "result_status": e["result_status"] or "pending",
                "wallet_list": wallet_list,
                "original_wallet_list": original_wallets,
                "appended_wallets_info": appended_info,
                "event_id": event_id,
            }
            result.append(row_dict)

        # Fallback to legacy table if events table is empty (should only happen before init_db/backfill runs).
        if result:
            return result

        rows = conn.execute(
            """
            SELECT * FROM alerts_published
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        legacy: List[Dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get("wallet_list"):
                try:
                    row_dict["wallet_list"] = json.loads(row_dict["wallet_list"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["wallet_list"] = []
            else:
                row_dict["wallet_list"] = []
            if row_dict.get("original_wallet_list"):
                try:
                    row_dict["original_wallet_list"] = json.loads(row_dict["original_wallet_list"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["original_wallet_list"] = []
            else:
                row_dict["original_wallet_list"] = []
            if row_dict.get("appended_wallets_info"):
                try:
                    row_dict["appended_wallets_info"] = json.loads(row_dict["appended_wallets_info"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["appended_wallets_info"] = {}
            else:
                row_dict["appended_wallets_info"] = {}
            legacy.append(row_dict)
        return legacy
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


def try_mark_published_atomic(
    scenario: str, 
    market_id: str, 
    outcome: str,
    cooldown_hours: int = 24,
    market_title: str = None,
    total_volume: float = 0.0,
    participants_count: int = 0,
    wallet_list: List[str] = None,
    event_slug: str = None,
    directionality: float = 0.0,
    entry_price: float = None
) -> bool:
    """
    Atomically check if already published and mark as published if not.
    This prevents race conditions when multiple threads/processes try to publish the same alert.
    
    Args:
        scenario: Scenario name (CLUSTER, REPEAT, BURST)
        market_id: Market identifier
        outcome: YES or NO
        cooldown_hours: How long to suppress duplicates
        market_title: Market title for record
        total_volume: Total volume for record
        participants_count: Number of participants for record
        wallet_list: List of wallets for record
        event_slug: Polymarket event slug for URL generation
        directionality: The dominant outcome directionality percent
        entry_price: The price of the outcome when the alert was fired
    
    Returns:
        True if successfully marked (was not already published), False if already published
    """
    import json
    cutoff = int(time.time()) - (cooldown_hours * 3600)
    conn = _get_connection()
    try:
        # Explicit write transaction to avoid race between SELECT and INSERT.
        conn.execute("BEGIN IMMEDIATE")

        # First check if already published within cooldown
        row = conn.execute("""
            SELECT timestamp FROM alerts_published
            WHERE scenario = ? AND market_id = ? AND outcome = ?
              AND timestamp >= ?
        """, (scenario, market_id, outcome, cutoff)).fetchone()
        
        if row is not None:
            # Already published, return False
            conn.commit()
            return False
        
        # Not published yet - mark it now atomically
        wallet_list_json = json.dumps(wallet_list) if wallet_list else None
        # Snapshot original wallets at publication time
        original_wallet_list_json = wallet_list_json
        conn.execute("""
            INSERT OR REPLACE INTO alerts_published 
            (scenario, market_id, outcome, timestamp, market_title, total_volume, participants_count, wallet_list, event_slug, directionality, entry_price, result_status, original_wallet_list, appended_wallets_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL)
        """, (
            scenario,
            market_id,
            outcome,
            int(time.time()),
            market_title,
            total_volume,
            participants_count,
            wallet_list_json,
            event_slug,
            directionality,
            entry_price,
            original_wallet_list_json
        ))
        conn.commit()
        return True  # Successfully marked
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def append_to_published_alert(
    scenario: str,
    market_id: str,
    outcome: str,
    new_wallets: List[str],
    additional_volume: float,
    wallet_outcomes: Dict[str, str] = None
) -> bool:
    """
    Appends new wallets and volume to an existing published alert.
    Updates wallet_list, total_volume, participants_count, and appended_wallets_info.
    
    Args:
        wallet_outcomes: Dict mapping wallet address -> outcome ("YES"/"NO")
                         for tracking post-publication direction.
    """
    import json
    if not new_wallets and additional_volume <= 0:
        return False

    # Keep the old dashboard row updated for cooldown/dedup and backwards compatibility,
    # but also write to the website events history (latest event) so history is preserved.
    conn = _get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT wallet_list, total_volume, participants_count, appended_wallets_info, original_wallet_list
            FROM alerts_published
            WHERE scenario = ? AND market_id = ? AND outcome = ?
        """, (scenario, market_id, outcome)).fetchone()

        if not row:
            conn.rollback()
            return False

        existing_wallets = []
        if row['wallet_list']:
            try:
                existing_wallets = json.loads(row['wallet_list'])
            except Exception:
                existing_wallets = []

        existing_original = []
        if row.get('original_wallet_list'):
            try:
                existing_original = json.loads(row['original_wallet_list'])
            except Exception:
                existing_original = []

        existing_appended = {}
        if row['appended_wallets_info']:
            try:
                existing_appended = json.loads(row['appended_wallets_info'])
            except Exception:
                existing_appended = {}

        # Only allow appending wallets that aren't already part of the original snapshot
        original_set = set(existing_original or [])
        new_wallets_filtered = [w for w in (new_wallets or []) if w and w not in original_set]

        merged_wallets = list(set(existing_wallets + new_wallets_filtered))
        new_count = len(merged_wallets)
        new_volume = float(row['total_volume'] or 0) + additional_volume

        if wallet_outcomes:
            for w, w_outcome in wallet_outcomes.items():
                if w in new_wallets_filtered and w not in existing_appended:
                    existing_appended[w] = w_outcome

        wallet_list_json = json.dumps(merged_wallets)
        appended_info_json = json.dumps(existing_appended) if existing_appended else None
        conn.execute("""
            UPDATE alerts_published
            SET wallet_list = ?, total_volume = ?, participants_count = ?, appended_wallets_info = ?
            WHERE scenario = ? AND market_id = ? AND outcome = ?
        """, (wallet_list_json, new_volume, new_count, appended_info_json, scenario, market_id, outcome))

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error appending to published alert: {e}")
        return False
    finally:
        conn.close()

    # Write to events history (outside the above transaction to keep the logic isolated).
    try:
        ok = append_wallets_to_latest_event(
            scenario=scenario,
            market_id=market_id,
            outcome=outcome,
            new_wallets=new_wallets_filtered,
            additional_volume=additional_volume,
            wallet_outcomes=wallet_outcomes,
        )
        if ok:
            logger.info(f"Appended {len(new_wallets_filtered)} wallets and ${additional_volume:,.0f} to latest {scenario} event for {market_id}")
        return ok
    except Exception as e:
        logger.error(f"Error appending to latest event: {e}")
        return False

async def update_published_alert_results():
    """
    Periodic background task to check and update the win/loss status of recently
    published alerts by querying the Polymarket Gamma API.
    Updates `result_status` based on `entry_price` compared to current or final price.
    """
    import aiohttp
    LIMIT = 30 # Check the last 30 published alerts
    
    conn = _get_connection()
    try:
        # Get recent alerts that are either still pending, or maybe we just want to update all recent ones
        # just in case prices changed
        c = conn.execute("""
            SELECT scenario, market_id, outcome, event_slug, entry_price, result_status 
            FROM alerts_published 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (LIMIT,))
        
        alerts = c.fetchall()
        print(f"Loaded {len(alerts)} alerts inside alerts_storage.py")
        if not alerts:
            return
            
        import json
        async with aiohttp.ClientSession() as session:
            for alert in alerts:
                scenario = alert['scenario']
                market_id = alert['market_id']
                slug = alert['event_slug']
                target_outcome = alert['outcome']
                entry_price = alert['entry_price']
                current_status = alert['result_status']
                
                if not slug:
                    continue
                    
                # If it's already a decided win/loss from a closed market, we could skip it
                # But sometimes markets re-resolve. Let's just blindly update the last 30.
                
                url = f"https://gamma-api.polymarket.com/events?slug={slug}"
                try:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        if not data or len(data) == 0:
                            continue
                            
                        event = data[0]
                        markets = event.get('markets', [])
                        if not markets:
                            continue
                            
                        # Find the specific market
                        market = None
                        for m in markets:
                            if m.get('conditionId') == market_id:
                                market = m
                                break
                                
                        if not market:
                            # Fallback to the first market if not found (unexpected)
                            market = markets[0]
                            
                        closed = market.get('closed', False)
                        
                        try:
                            outcomes = json.loads(market.get('outcomes', '[]'))
                            prices = json.loads(market.get('outcomePrices', '[]'))
                        except Exception as e:
                            logger.error(f"Error parsing outcomes for {market_id}: {e}")
                            continue
                            
                        # Find the index of our target outcome
                        target_idx = -1
                        for i, name in enumerate(outcomes):
                            if name.upper() == target_outcome.upper():
                                target_idx = i
                                break
                                
                        if target_idx == -1 or target_idx >= len(prices):
                            continue
                            
                        current_price = float(prices[target_idx])
                        
                        # Determine new status
                        # Only set win/loss when market is CLOSED (resolved).
                        # Open markets stay 'pending' until resolution.
                        new_status = 'pending'
                        if closed:
                            if current_price >= 0.99:
                                new_status = 'win'
                            else:
                                new_status = 'loss'
                                
                        if new_status != current_status:
                            conn.execute(
                                "UPDATE alerts_published SET result_status = ? WHERE scenario = ? AND market_id = ? AND outcome = ?",
                                (new_status, scenario, market_id, target_outcome)
                            )
                            logger.debug(f"Updated alert {market_id} status: {current_status} -> {new_status} (Price: {current_price:.3f}, Entry: {entry_price if entry_price is not None else -1:.3f})")
                            
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    logger.debug(f"Error updating result for {slug}: {e}")
                    
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update published alert results: {e}")
    finally:
        conn.close()


def cleanup_old_published(days: int = 7) -> int:
    """
    Clean up old published records.
    (Disabled per user request to keep all alerts forever)
    
    Args:
        days: Keep records from last N days
    
    Returns:
        Number of deleted rows
    """
    # Simply return 0 to prevent deletion of published alerts
    return 0


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
