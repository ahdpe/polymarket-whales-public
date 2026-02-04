"""
SQLite storage for saved markets (favorite markets).
Supports per-user saved list with notifications toggle.
"""
import sqlite3
import hashlib
import time
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/saved_markets.db"
DEFAULT_MARKET_MIN_USD = 500
SQLITE_BUSY_TIMEOUT_MS = 5000

# In-memory cache: user_id (int) -> set of market_refs with notifications enabled
_notifications_cache: dict[int, set[str]] = {}
_cache_loaded = False

def _update_notification_cache(user_id: str | int, market_ref: str, enabled: bool) -> None:
    """Keep in-memory notifications cache in sync with DB."""
    uid = int(user_id)
    if uid not in _notifications_cache:
        _notifications_cache[uid] = set()
    if enabled:
        _notifications_cache[uid].add(market_ref)
    else:
        _notifications_cache[uid].discard(market_ref)


def _get_connection():
    """Get database connection with WAL mode for performance."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS};")
    conn.row_factory = sqlite3.Row
    return conn


def make_market_ref(market_id: str | None, event_slug: str | None) -> str | None:
    """Create canonical market ref (id:... or slug:...)."""
    market_id = (market_id or "").strip()
    event_slug = (event_slug or "").strip()
    if market_id:
        return f"id:{market_id}"
    if event_slug:
        return f"slug:{event_slug}"
    return None


def _get_market_refs(market_id: str | None, event_slug: str | None) -> list[str]:
    refs: list[str] = []
    if market_id:
        refs.append(f"id:{market_id}")
    if event_slug:
        refs.append(f"slug:{event_slug}")
    return refs


def init_db():
    """Initialize database tables."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_markets (
                user_id TEXT NOT NULL,
                market_ref TEXT NOT NULL,
                market_id TEXT,
                event_slug TEXT,
                title TEXT,
                min_usd INTEGER NOT NULL,
                notifications_enabled INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, market_ref)
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_user ON saved_markets(user_id);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_keys (
                key TEXT PRIMARY KEY,
                market_ref TEXT UNIQUE NOT NULL,
                market_id TEXT,
                event_slug TEXT,
                title TEXT,
                updated_at INTEGER NOT NULL
            );
            """
        )

        # Migrations: add columns if missing
        for col, ddl in (
            ("market_id", "ALTER TABLE saved_markets ADD COLUMN market_id TEXT;"),
            ("event_slug", "ALTER TABLE saved_markets ADD COLUMN event_slug TEXT;"),
            ("title", "ALTER TABLE saved_markets ADD COLUMN title TEXT;"),
            ("min_usd", "ALTER TABLE saved_markets ADD COLUMN min_usd INTEGER NOT NULL DEFAULT 500;"),
            ("notifications_enabled", "ALTER TABLE saved_markets ADD COLUMN notifications_enabled INTEGER DEFAULT 0;"),
        ):
            try:
                conn.execute(ddl)
                conn.commit()
                logger.info(f"Added '{col}' column to saved_markets")
            except sqlite3.OperationalError:
                pass

        for col, ddl in (
            ("market_id", "ALTER TABLE market_keys ADD COLUMN market_id TEXT;"),
            ("event_slug", "ALTER TABLE market_keys ADD COLUMN event_slug TEXT;"),
            ("title", "ALTER TABLE market_keys ADD COLUMN title TEXT;"),
            ("updated_at", "ALTER TABLE market_keys ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0;"),
        ):
            try:
                conn.execute(ddl)
                conn.commit()
                logger.info(f"Added '{col}' column to market_keys")
            except sqlite3.OperationalError:
                pass

        conn.commit()
        logger.info("Saved markets DB initialized")
        _load_notifications_cache(conn)
    finally:
        conn.close()


def _load_notifications_cache(conn=None):
    """Load notifications cache from DB into memory."""
    global _notifications_cache, _cache_loaded
    close_conn = False
    if conn is None:
        conn = _get_connection()
        close_conn = True
    try:
        rows = conn.execute(
            "SELECT user_id, market_ref FROM saved_markets WHERE notifications_enabled = 1"
        ).fetchall()
        _notifications_cache.clear()
        for row in rows:
            uid = int(row["user_id"])
            mref = row["market_ref"]
            if uid not in _notifications_cache:
                _notifications_cache[uid] = set()
            _notifications_cache[uid].add(mref)
        _cache_loaded = True
        logger.info(f"Market notifications cache loaded: {sum(len(v) for v in _notifications_cache.values())} entries for {len(_notifications_cache)} users")
    finally:
        if close_conn:
            conn.close()


def get_or_create_key(
    market_ref: str,
    market_id: str | None = None,
    event_slug: str | None = None,
    title: str | None = None,
) -> str:
    """
    Get or create a short key for a market ref.
    Key = sha1(market_ref)[:10] for compact callback_data.
    """
    if not market_ref:
        return ""

    key = hashlib.sha1(market_ref.encode()).hexdigest()[:10]
    now = int(time.time())

    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT market_ref FROM market_keys WHERE key = ?", (key,)
        ).fetchone()

        if row:
            if row["market_ref"] != market_ref:
                # Collision: extend key
                key = hashlib.sha1(market_ref.encode()).hexdigest()[:16]
                extended_row = conn.execute(
                    "SELECT market_ref FROM market_keys WHERE key = ?", (key,)
                ).fetchone()
                if not extended_row:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO market_keys
                        (key, market_ref, market_id, event_slug, title, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (key, market_ref, market_id, event_slug, title, now),
                    )
                    conn.commit()
                    return key

            # Update optional data if provided
            updates = []
            params = []
            if market_id:
                updates.append("market_id = ?")
                params.append(market_id)
            if event_slug:
                updates.append("event_slug = ?")
                params.append(event_slug)
            if title:
                updates.append("title = ?")
                params.append(title)
            if updates:
                updates.append("updated_at = ?")
                params.append(now)
                query = "UPDATE market_keys SET " + ", ".join(updates) + " WHERE key = ?"
                params.append(key)
                conn.execute(query, params)
                conn.commit()
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO market_keys
                (key, market_ref, market_id, event_slug, title, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (key, market_ref, market_id, event_slug, title, now),
            )
            conn.commit()

        return key
    finally:
        conn.close()


def get_market_ref(key: str) -> str | None:
    """Resolve short key to market_ref."""
    if not key:
        return None
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT market_ref FROM market_keys WHERE key = ?", (key,)
        ).fetchone()
        return row["market_ref"] if row else None
    finally:
        conn.close()


def get_market_data(key: str) -> dict | None:
    """Get market data (ref, id, slug, title) from key."""
    if not key:
        return None
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT market_ref, market_id, event_slug, title FROM market_keys WHERE key = ?",
            (key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_saved_market(user_id: str | int, market_id: str | None, event_slug: str | None) -> dict | None:
    """Get saved market row for user by market_id or event_slug."""
    refs = _get_market_refs(market_id, event_slug)
    if not refs:
        return None

    conn = _get_connection()
    try:
        placeholders = ",".join("?" for _ in refs)
        params = [str(user_id)] + refs
        row = conn.execute(
            f"""
            SELECT user_id, market_ref, market_id, event_slug, title, min_usd,
                   notifications_enabled, created_at, updated_at
            FROM saved_markets
            WHERE user_id = ? AND market_ref IN ({placeholders})
            LIMIT 1
            """,
            params,
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_saved(user_id: str | int, market_id: str | None, event_slug: str | None) -> bool:
    return get_saved_market(user_id, market_id, event_slug) is not None


def is_notifications_enabled(user_id: str | int, market_id: str | None, event_slug: str | None) -> bool:
    """Check if notifications are enabled for this market (uses cache)."""
    uid = int(user_id)
    if _cache_loaded:
        refs = _get_market_refs(market_id, event_slug)
        user_set = _notifications_cache.get(uid, set())
        return any(r in user_set for r in refs)
    # Fallback to DB
    row = get_saved_market(user_id, market_id, event_slug)
    return bool(row["notifications_enabled"]) if row else False


def toggle_notifications(user_id: str | int, market_ref: str) -> bool:
    """Toggle notification status and return new state."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT notifications_enabled FROM saved_markets WHERE user_id = ? AND market_ref = ?",
            (str(user_id), market_ref),
        ).fetchone()
        current = bool(row["notifications_enabled"]) if row else False
        new_state = not current
        now = int(time.time())
        conn.execute(
            """
            UPDATE saved_markets
               SET notifications_enabled = ?, updated_at = ?
             WHERE user_id = ? AND market_ref = ?
            """,
            (1 if new_state else 0, now, str(user_id), market_ref),
        )
        conn.commit()
        _update_notification_cache(user_id, market_ref, new_state)
        return new_state
    finally:
        conn.close()


def save(
    user_id: str | int,
    market_id: str | None,
    event_slug: str | None,
    title: str | None,
    notifications_enabled: int | None = None,
) -> str | None:
    """Save market for user with optional notification settings."""
    market_ref = make_market_ref(market_id, event_slug)
    if not market_ref:
        return None

    now = int(time.time())
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO saved_markets
            (user_id, market_ref, market_id, event_slug, title, min_usd, notifications_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(user_id),
                market_ref,
                market_id,
                event_slug,
                title,
                DEFAULT_MARKET_MIN_USD,
                1 if notifications_enabled else 0,
                now,
                now,
            ),
        )

        # Update optional fields without overwriting min_usd/notifications unless provided
        updates = []
        params = []
        if market_id:
            updates.append("market_id = ?")
            params.append(market_id)
        if event_slug:
            updates.append("event_slug = ?")
            params.append(event_slug)
        if title:
            updates.append("title = ?")
            params.append(title)
        if notifications_enabled is not None:
            updates.append("notifications_enabled = ?")
            params.append(1 if notifications_enabled else 0)
        if updates:
            updates.append("updated_at = ?")
            params.append(now)
            query = "UPDATE saved_markets SET " + ", ".join(updates) + " WHERE user_id = ? AND market_ref = ?"
            params.extend([str(user_id), market_ref])
            conn.execute(query, params)

        row = conn.execute(
            """
            SELECT notifications_enabled
            FROM saved_markets
            WHERE user_id = ? AND market_ref = ?
            """,
            (str(user_id), market_ref),
        ).fetchone()
        conn.commit()
        if row is not None:
            _update_notification_cache(user_id, market_ref, bool(row["notifications_enabled"]))
        return market_ref
    finally:
        conn.close()

def list_saved(user_id: str | int, offset: int = 0, limit: int = 10) -> list[dict]:
    """
    List saved markets for user with pagination.
    Returns list of dicts: {market_ref, market_id, event_slug, title, min_usd, notifications_enabled, created_at, updated_at}
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT market_ref, market_id, event_slug, title, min_usd, notifications_enabled, created_at, updated_at
            FROM saved_markets
            WHERE user_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ? OFFSET ?
            """,
            (str(user_id), limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_title(user_id: str | int, market_ref: str, title: str | None) -> None:
    """Update market title without changing notification settings."""
    if not market_ref or not title:
        return
    now = int(time.time())
    conn = _get_connection()
    try:
        conn.execute(
            """
            UPDATE saved_markets
               SET title = ?, updated_at = ?
             WHERE user_id = ? AND market_ref = ?
            """,
            (title, now, str(user_id), market_ref),
        )
        conn.commit()
    finally:
        conn.close()


def count_saved(user_id: str | int) -> int:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM saved_markets WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def count_notifications_enabled(user_id: str | int) -> int:
    """Count saved markets with notifications enabled for user."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM saved_markets WHERE user_id = ? AND notifications_enabled = 1",
            (str(user_id),),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def set_notifications_for_user(user_id: str | int, enabled: bool) -> None:
    """Set notifications_enabled for all saved markets for a user."""
    now = int(time.time())
    conn = _get_connection()
    try:
        conn.execute(
            """
            UPDATE saved_markets
               SET notifications_enabled = ?, updated_at = ?
             WHERE user_id = ?
            """,
            (1 if enabled else 0, now, str(user_id)),
        )
        conn.commit()
        # Update cache
        uid = int(user_id)
        if enabled:
            rows = conn.execute(
                "SELECT market_ref FROM saved_markets WHERE user_id = ?", (str(user_id),)
            ).fetchall()
            _notifications_cache[uid] = {row["market_ref"] for row in rows}
        else:
            _notifications_cache[uid] = set()
    finally:
        conn.close()


def delete(user_id: str | int, market_ref: str) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM saved_markets WHERE user_id = ? AND market_ref = ?",
            (str(user_id), market_ref),
        )
        conn.commit()
        # Update cache
        uid = int(user_id)
        if uid in _notifications_cache:
            _notifications_cache[uid].discard(market_ref)
    finally:
        conn.close()


def clear_all(user_id: str | int) -> int:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM saved_markets WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        count = row["cnt"] if row else 0

        conn.execute(
            "DELETE FROM saved_markets WHERE user_id = ?",
            (str(user_id),),
        )
        conn.commit()
        # Update cache
        uid = int(user_id)
        _notifications_cache.pop(uid, None)
        return count
    finally:
        conn.close()
