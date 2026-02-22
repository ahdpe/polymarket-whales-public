"""
SQLite storage for saved whales (favorite traders).
Supports per-user saved list with optional comments.
"""
import sqlite3
import hashlib
import time
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/saved_whales.db"
MAX_COMMENT_LEN = 240
SQLITE_BUSY_TIMEOUT_MS = 5000

# In-memory cache: user_id (int) -> set of whale_ids with notifications enabled
_notifications_cache: dict[int, set[str]] = {}
# In-memory cache: user_id (int) -> set of whale_ids with state='ignore'
_ignore_cache: dict[int, set[str]] = {}
_cache_loaded = False

def _update_notification_cache(user_id: str | int, whale_id: str, enabled: bool) -> None:
    """Keep in-memory notifications cache in sync with DB."""
    uid = int(user_id)
    if uid not in _notifications_cache:
        _notifications_cache[uid] = set()
    if enabled:
        _notifications_cache[uid].add(whale_id)
    else:
        _notifications_cache[uid].discard(whale_id)


def _update_ignore_cache(user_id: str | int, whale_id: str, ignored: bool) -> None:
    """Keep in-memory ignore cache in sync with DB."""
    uid = int(user_id)
    if uid not in _ignore_cache:
        _ignore_cache[uid] = set()
    if ignored:
        _ignore_cache[uid].add(whale_id)
    else:
        _ignore_cache[uid].discard(whale_id)


def _get_connection():
    """Get database connection with WAL mode for performance."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS};")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_whales (
                user_id TEXT NOT NULL,
                whale_id TEXT NOT NULL,
                name TEXT,
                comment TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, whale_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sw_user ON saved_whales(user_id);")
        
        # Migration: add name column if not exists
        try:
            conn.execute("ALTER TABLE saved_whales ADD COLUMN name TEXT;")
            conn.commit()
            logger.info("Added 'name' column to saved_whales")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whale_keys (
                key TEXT PRIMARY KEY,
                whale_id TEXT UNIQUE NOT NULL,
                name TEXT
            );
        """)
        
        # Migration: add name to whale_keys if not exists
        try:
            conn.execute("ALTER TABLE whale_keys ADD COLUMN name TEXT;")
            conn.commit()
            logger.info("Added 'name' column to whale_keys")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: add level_icon column if not exists
        try:
            conn.execute("ALTER TABLE saved_whales ADD COLUMN level_icon TEXT;")
            conn.commit()
            logger.info("Added 'level_icon' column to saved_whales")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: apply to whale_keys too for passing data
        try:
            conn.execute("ALTER TABLE whale_keys ADD COLUMN level_icon TEXT;")
            conn.commit()
            logger.info("Added 'level_icon' column to whale_keys")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migration: add notifications_enabled column if not exists
        try:
            conn.execute("ALTER TABLE saved_whales ADD COLUMN notifications_enabled INTEGER DEFAULT 0;")
            conn.commit()
            logger.info("Added 'notifications_enabled' column to saved_whales")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: add state column if not exists (notify/ignore)
        try:
            conn.execute("ALTER TABLE saved_whales ADD COLUMN state TEXT DEFAULT 'notify';")
            conn.commit()
            logger.info("Added 'state' column to saved_whales")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
        logger.info("Saved whales DB initialized")
        _load_notifications_cache(conn)
    finally:
        conn.close()


def _load_notifications_cache(conn=None):
    """Load notifications and ignore caches from DB into memory."""
    global _notifications_cache, _ignore_cache, _cache_loaded
    close_conn = False
    if conn is None:
        conn = _get_connection()
        close_conn = True
    try:
        rows = conn.execute(
            "SELECT user_id, whale_id FROM saved_whales WHERE notifications_enabled = 1"
        ).fetchall()
        _notifications_cache.clear()
        for row in rows:
            uid = int(row["user_id"])
            wid = row["whale_id"]
            if uid not in _notifications_cache:
                _notifications_cache[uid] = set()
            _notifications_cache[uid].add(wid)
        
        # Load ignore cache
        ignore_rows = conn.execute(
            "SELECT user_id, whale_id FROM saved_whales WHERE state = 'ignore'"
        ).fetchall()
        _ignore_cache.clear()
        for row in ignore_rows:
            uid = int(row["user_id"])
            wid = row["whale_id"]
            if uid not in _ignore_cache:
                _ignore_cache[uid] = set()
            _ignore_cache[uid].add(wid)
        
        _cache_loaded = True
        logger.info(f"Notifications cache loaded: {sum(len(v) for v in _notifications_cache.values())} entries for {len(_notifications_cache)} users")
        logger.info(f"Ignore cache loaded: {sum(len(v) for v in _ignore_cache.values())} entries for {len(_ignore_cache)} users")
    finally:
        if close_conn:
            conn.close()


def get_or_create_key(whale_id: str, name: str = None, level_icon: str = None) -> str:
    """
    Get or create a short key for a whale address.
    Key = sha1(whale_id)[:10] for compact callback_data.
    Also stores/updates the name and level_icon if provided.
    """
    if not whale_id:
        return ""
    
    key = hashlib.sha1(whale_id.encode()).hexdigest()[:10]
    logger.info(f"get_or_create_key: name={name}, level_icon={level_icon}")
    
    conn = _get_connection()
    try:
        # Check if key exists
        row = conn.execute(
            "SELECT whale_id FROM whale_keys WHERE key = ?", (key,)
        ).fetchone()
        
        if row:
            # Key exists - verify it maps to same whale_id (collision check)
            if row["whale_id"] != whale_id:
                # Collision! Extend key to 16 chars
                key = hashlib.sha1(whale_id.encode()).hexdigest()[:16]
                # Check if extended key exists for this whale_id
                extended_row = conn.execute(
                    "SELECT whale_id FROM whale_keys WHERE key = ?", (key,)
                ).fetchone()
                
                if not extended_row:
                    # Create new record with extended key
                    logger.debug(f"INSERT whale_keys (collision): key={key}, whale_id={whale_id[:16]}, name={name}, level_icon={level_icon}")
                    conn.execute(
                        "INSERT OR IGNORE INTO whale_keys (key, whale_id, name, level_icon) VALUES (?, ?, ?, ?)",
                        (key, whale_id, name, level_icon)
                    )
                    conn.commit()
                    return key
            
            # Update name/icon if provided (for existing record)
            if name or level_icon:
                query = "UPDATE whale_keys SET "
                params = []
                if name:
                    query += "name = ?, "
                    params.append(name)
                if level_icon:
                    query += "level_icon = ?, "
                    params.append(level_icon)
                
                # Remove trailing comma
                query = query.rstrip(", ")
                query += " WHERE key = ?"
                params.append(key)
                
                logger.debug(f"UPDATE whale_keys: query={query}, params={params}")
                conn.execute(query, params)
                conn.commit()
        else:
            # New key
            logger.debug(f"INSERT whale_keys: key={key}, whale_id={whale_id[:16]}, name={name}, level_icon={level_icon}")
            conn.execute(
                "INSERT OR IGNORE INTO whale_keys (key, whale_id, name, level_icon) VALUES (?, ?, ?, ?)",
                (key, whale_id, name, level_icon)
            )
            conn.commit()
        
        return key
    finally:
        conn.close()


def get_whale_id(key: str) -> str | None:
    """Resolve short key to whale_id."""
    if not key:
        return None
    
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT whale_id FROM whale_keys WHERE key = ?", (key,)
        ).fetchone()
        return row["whale_id"] if row else None
    finally:
        conn.close()


def get_whale_data(key: str) -> dict | None:
    """Get full whale data (id, name, level_icon) from key."""
    if not key:
        return None
    
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT whale_id, name, level_icon FROM whale_keys WHERE key = ?", (key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_whale_name(key: str) -> str | None:
    """Get whale name from key."""
    data = get_whale_data(key)
    return data['name'] if data else None


def get_whale_data_by_id(whale_id: str) -> dict | None:
    """Get full whale data (key, name, level_icon) from whale_id."""
    if not whale_id:
        return None
    
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT key, name, level_icon FROM whale_keys WHERE whale_id = ?", (whale_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_saved(user_id: str | int, whale_id: str) -> bool:
    """Check if whale is saved by user and not ignored."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM saved_whales WHERE user_id = ? AND whale_id = ? AND state != 'ignore'",
            (str(user_id), whale_id)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def is_notifications_enabled(user_id: str | int, whale_id: str) -> bool:
    """Check if notifications are enabled for this trader for this user (uses cache)."""
    uid = int(user_id)
    if _cache_loaded:
        return whale_id in _notifications_cache.get(uid, set())
    # Fallback to DB if cache not loaded
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT notifications_enabled FROM saved_whales WHERE user_id = ? AND whale_id = ?",
            (str(user_id), whale_id)
        ).fetchone()
        return bool(row["notifications_enabled"]) if row else False
    finally:
        conn.close()


def is_ignored(user_id: str | int, whale_id: str) -> bool:
    """Check if this trader is ignored by this user (uses cache)."""
    uid = int(user_id)
    if _cache_loaded:
        return whale_id in _ignore_cache.get(uid, set())
    # Fallback to DB if cache not loaded
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT state FROM saved_whales WHERE user_id = ? AND whale_id = ?",
            (str(user_id), whale_id)
        ).fetchone()
        return row["state"] == 'ignore' if row else False
    finally:
        conn.close()


def set_state(user_id: str | int, whale_id: str, state: str) -> None:
    """Set state ('notify' or 'ignore') for a saved whale."""
    if state not in ('notify', 'ignore'):
        raise ValueError(f"Invalid state: {state}")
    now = int(time.time())
    conn = _get_connection()
    try:
        if state == 'ignore':
            conn.execute(
                """UPDATE saved_whales 
                   SET state = ?, notifications_enabled = 0, updated_at = ?
                   WHERE user_id = ? AND whale_id = ?""",
                (state, now, str(user_id), whale_id)
            )
        else:
            conn.execute(
                """UPDATE saved_whales 
                   SET state = ?, updated_at = ?
                   WHERE user_id = ? AND whale_id = ?""",
                (state, now, str(user_id), whale_id)
            )
        conn.commit()
        _update_ignore_cache(user_id, whale_id, state == 'ignore')
        # If switching to ignore, also disable notifications
        if state == 'ignore':
            _update_notification_cache(user_id, whale_id, False)
    finally:
        conn.close()

def cycle_state(user_id: str | int, whale_id: str) -> dict:
    """
    Atomically cycle the notification state:
    🔕 off (notify, 0) -> 🔔 on (notify, 1) -> 🚫 ignore (ignore, 0) -> 🔕 off (notify, 0)
    Returns dict: {'state': str, 'notifications_enabled': int}
    """
    now = int(time.time())
    conn = _get_connection()
    try:
        conn.execute(
            """UPDATE saved_whales 
               SET state = CASE 
                     WHEN state = 'ignore' THEN 'notify'
                     WHEN notifications_enabled = 1 THEN 'ignore'
                     ELSE 'notify'
                   END,
                   notifications_enabled = CASE
                     WHEN state = 'ignore' THEN 0
                     WHEN notifications_enabled = 1 THEN 0
                     ELSE 1
                   END,
                   updated_at = ?
               WHERE user_id = ? AND whale_id = ?""",
            (now, str(user_id), whale_id)
        )
        row = conn.execute(
            "SELECT notifications_enabled, COALESCE(state, 'notify') as state FROM saved_whales WHERE user_id = ? AND whale_id = ?",
            (str(user_id), whale_id)
        ).fetchone()
        conn.commit()
        if row:
            res = dict(row)
            _update_notification_cache(user_id, whale_id, bool(res["notifications_enabled"]))
            _update_ignore_cache(user_id, whale_id, res["state"] == 'ignore')
            return res
        return None
    finally:
        conn.close()


def toggle_notifications(user_id: str | int, whale_id: str) -> bool:
    """Toggle notification status and return the new state."""
    current = is_notifications_enabled(user_id, whale_id)
    new_state = not current
    now = int(time.time())
    
    conn = _get_connection()
    try:
        conn.execute(
            """UPDATE saved_whales 
               SET notifications_enabled = ?, updated_at = ?
               WHERE user_id = ? AND whale_id = ?""",
            (1 if new_state else 0, now, str(user_id), whale_id)
        )
        conn.commit()
        _update_notification_cache(user_id, whale_id, new_state)
        return new_state
    finally:
        conn.close()


def save(user_id: str | int, whale_id: str, name: str = None, level_icon: str = None, notifications_enabled: int = None, state: str = None) -> None:
    """Save whale for user with optional name, level_icon, notification settings, and state."""
    # If name or level_icon not provided, try to get them from whale_keys
    if not name or not level_icon:
        whale_data = get_whale_data_by_id(whale_id)
        if whale_data:
            if not name and whale_data.get('name'):
                name = whale_data.get('name')
            if not level_icon and whale_data.get('level_icon'):
                level_icon = whale_data.get('level_icon')
    
    now = int(time.time())
    insert_state = state or 'notify'
    conn = _get_connection()
    try:
        # Try to insert, if exists - update name/icon if provided
        query = """INSERT INTO saved_whales 
               (user_id, whale_id, name, level_icon, notifications_enabled, state, comment, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
               ON CONFLICT(user_id, whale_id) DO UPDATE SET """
        
        notifications_was_explicit = notifications_enabled is not None
        insert_notifications = 1 if notifications_enabled else 0

        params = [str(user_id), whale_id, name, level_icon, insert_notifications, insert_state, now, now]
        
        updates = ["updated_at = excluded.updated_at"]
        if name:
            updates.append("name = excluded.name")
        # Update notifications only when explicitly provided by caller.
        if notifications_was_explicit:
            updates.append("notifications_enabled = excluded.notifications_enabled")
        # Update state only when explicitly provided by caller.
        if state is not None:
            updates.append("state = excluded.state")
            
        query += ", ".join(updates)
        
        conn.execute(query, params)
        row = conn.execute(
            "SELECT notifications_enabled, state FROM saved_whales WHERE user_id = ? AND whale_id = ?",
            (str(user_id), whale_id),
        ).fetchone()
        conn.commit()
        if row is not None:
            _update_notification_cache(user_id, whale_id, bool(row["notifications_enabled"]))
            _update_ignore_cache(user_id, whale_id, row["state"] == 'ignore')
    finally:
        conn.close()


def set_comment(user_id: str | int, whale_id: str, comment: str | None) -> None:
    """Set or remove comment for saved whale."""
    now = int(time.time())
    
    # Sanitize comment
    if comment:
        comment = comment.strip()
        if comment in ("", "-", "–", "—"):
            comment = None
        elif len(comment) > MAX_COMMENT_LEN:
            comment = comment[:MAX_COMMENT_LEN]
    
    conn = _get_connection()
    try:
        conn.execute(
            """UPDATE saved_whales 
               SET comment = ?, updated_at = ?
               WHERE user_id = ? AND whale_id = ?""",
            (comment, now, str(user_id), whale_id)
        )
        conn.commit()
    finally:
        conn.close()


def list_saved(user_id: str | int, offset: int = 0, limit: int = 10) -> list[dict]:
    """
    List saved whales for user with pagination.
    Returns list of dicts: {whale_id, name, level_icon, notifications_enabled, state, comment, created_at, updated_at}
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT whale_id, name, level_icon, notifications_enabled, COALESCE(state, 'notify') as state, comment, created_at, updated_at 
               FROM saved_whales 
               WHERE user_id = ?
               ORDER BY created_at DESC, rowid DESC
               LIMIT ? OFFSET ?""",
            (str(user_id), limit, offset)
        ).fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def count_saved(user_id: str | int) -> int:
    """Count total saved whales for user."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM saved_whales WHERE user_id = ?",
            (str(user_id),)
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def count_notifications_enabled(user_id: str | int) -> int:
    """Count saved whales with notifications enabled for user."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM saved_whales WHERE user_id = ? AND notifications_enabled = 1",
            (str(user_id),)
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def set_notifications_for_user(user_id: str | int, enabled: bool) -> None:
    """Set notifications_enabled for all saved whales for a user."""
    now = int(time.time())
    conn = _get_connection()
    try:
        conn.execute(
            """
            UPDATE saved_whales
               SET notifications_enabled = ?, updated_at = ?
             WHERE user_id = ?
            """,
            (1 if enabled else 0, now, str(user_id))
        )
        conn.commit()
        # Update cache
        uid = int(user_id)
        if enabled:
            # Load all whale_ids for this user into cache
            rows = conn.execute(
                "SELECT whale_id FROM saved_whales WHERE user_id = ?", (str(user_id),)
            ).fetchall()
            _notifications_cache[uid] = {row["whale_id"] for row in rows}
        else:
            _notifications_cache[uid] = set()
    finally:
        conn.close()


def delete(user_id: str | int, whale_id: str) -> None:
    """Delete whale from user's saved list."""
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM saved_whales WHERE user_id = ? AND whale_id = ?",
            (str(user_id), whale_id)
        )
        conn.commit()
        # Update caches
        uid = int(user_id)
        if uid in _notifications_cache:
            _notifications_cache[uid].discard(whale_id)
        if uid in _ignore_cache:
            _ignore_cache[uid].discard(whale_id)
    finally:
        conn.close()


def clear_all(user_id: str | int) -> int:
    """Delete all saved whales for a user. Returns count of deleted items."""
    conn = _get_connection()
    try:
        # Get count first
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM saved_whales WHERE user_id = ?",
            (str(user_id),)
        ).fetchone()
        count = row["cnt"] if row else 0
        
        # Delete all
        conn.execute(
            "DELETE FROM saved_whales WHERE user_id = ?",
            (str(user_id),)
        )
        conn.commit()
        # Update caches
        uid = int(user_id)
        _notifications_cache.pop(uid, None)
        _ignore_cache.pop(uid, None)
        return count
    finally:
        conn.close()
