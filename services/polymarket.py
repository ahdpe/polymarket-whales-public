import asyncio
import logging
import aiohttp
import time
import sqlite3
import os
import random
from decimal import Decimal
from collections import OrderedDict

from config import POLYGONSCAN_API_KEY

logger = logging.getLogger(__name__)

DATA_API_URL = "https://data-api.polymarket.com"

POLL_INTERVAL = 3
MAX_LRU_SIZE = 10000
DB_PATH = "data/trades.db"
TTL_HOURS = 72
SQLITE_BUSY_TIMEOUT_MS = 5000

RECENT_WALLETS_WINDOW = 48 * 3600  # 48 hours
WALLET_ACTIVITY_CHECK_COOLDOWN = 300  # 5 minutes
MAX_CONCURRENT_CALLBACKS = 50
MAX_PENDING_CALLBACK_TASKS = 5000
CALLBACK_QUEUE_INFO_THRESHOLD = 200
CALLBACK_QUEUE_WARN_THRESHOLD = 1000
CALLBACK_HEALTH_LOG_INTERVAL = 30

POSITIONS_CACHE_TTL = 60
_positions_cache = {}  # {proxy_wallet: {"data": {...}, "ts": timestamp}}

WALLET_AGE_CACHE_TTL = 7 * 24 * 60 * 60
WALLET_AGE_FALLBACK_TTL = 600  # 10 min for fallback (non-Etherscan) values
_wallet_age_cache = {}  # {proxy_wallet: {"first_ts": timestamp, "cached_at": timestamp, "source": str}}


def norm_ts(x, default=0.0) -> float:
    """Normalize timestamp to seconds (handle ms)."""
    try:
        v = float(x)
        if v > 1e10:  # ms -> s
            v /= 1000.0
        return v
    except (TypeError, ValueError):
        return float(default)


def norm_ts_int(x, default=0) -> int:
    """Normalize timestamp to integer seconds (handle ms)."""
    return int(norm_ts(x, default=default))


class TradePersistence:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.lru = OrderedDict()
        self._init_db()
        self.last_cleanup = time.time()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS};")

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_trades (
                trade_key TEXT PRIMARY KEY,
                seen_at INTEGER NOT NULL
            );
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_trades(seen_at);")
        self.conn.commit()

    def _normalize_decimal(self, val):
        try:
            return str(Decimal(str(val)).quantize(Decimal("0.000001")))
        except Exception:
            return "0.000000"

    def generate_key(self, trade: dict) -> str:
        price = self._normalize_decimal(trade.get("price", 0))
        size = self._normalize_decimal(trade.get("size", 0))
        ts = norm_ts_int(trade.get("timestamp", 0))

        parts = [
            trade.get("proxyWallet", ""),
            trade.get("conditionId", ""),
            trade.get("side", ""),
            trade.get("outcomeIndex", ""),
            price,
            size,
            ts,
            trade.get("transactionHash", ""),
        ]
        return "|".join(str(p) for p in parts)

    def is_seen(self, key: str) -> bool:
        if key in self.lru:
            self.lru.move_to_end(key)
            return True

        cursor = self.conn.execute("SELECT 1 FROM seen_trades WHERE trade_key=? LIMIT 1", (key,))
        if cursor.fetchone():
            self._add_to_lru(key)
            return True

        return False

    def _add_to_lru(self, key: str):
        self.lru[key] = None
        self.lru.move_to_end(key)
        if len(self.lru) > MAX_LRU_SIZE:
            self.lru.popitem(last=False)

    def add_batch(self, keys):
        if not keys:
            return

        now_ms = int(time.time() * 1000)
        data = [(k, now_ms) for k in keys]

        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO seen_trades(trade_key, seen_at) VALUES (?, ?)",
                data,
            )

        for k in keys:
            self._add_to_lru(k)

    def cleanup(self):
        if time.time() - self.last_cleanup < 3600:
            return

        cutoff_ms = int((time.time() - (TTL_HOURS * 3600)) * 1000)
        deleted = 0
        with self.conn:
            cursor = self.conn.execute("DELETE FROM seen_trades WHERE seen_at < ?", (cutoff_ms,))
            deleted = cursor.rowcount

        # Run VACUUM periodically to reclaim space (every 24 hours or if deleted > 100k)
        # Must be outside a transaction or SQLite will reject it.
        should_vacuum = (time.time() - getattr(self, "_last_vacuum", 0) > 86400) or deleted > 100000
        if should_vacuum:
            try:
                logger.info(f"Running VACUUM on trades.db (deleted {deleted} old records)")
                self.conn.execute("VACUUM")
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._last_vacuum = time.time()
            except Exception as e:
                logger.error(f"Error during VACUUM: {e}")
        
        self.last_cleanup = time.time()

    def close(self):
        self.conn.close()


class TradeAggregator:
    def __init__(self, window_sec=60, min_alert_usd=500):
        self.window_sec = window_sec
        self.min_alert_usd = min_alert_usd
        self.series = {}
        self.last_cleanup = time.time()

    def _get_key(self, trade):
        return (
            trade.get("proxyWallet", ""),
            trade.get("conditionId", ""),
            trade.get("side", ""),
            trade.get("outcomeIndex", str(trade.get("outcome", ""))),
        )

    def process_trade(self, trade):
        key = self._get_key(trade)
        now_ts = norm_ts(trade.get("timestamp", time.time()), default=time.time())

        price = float(trade.get("price", 0) or 0)
        size = float(trade.get("size", 0) or 0)
        
        # Use usdcSize from API if available (actual USD spent)
        # Fallback to price * size only if usdcSize not provided
        usdc_size = float(trade.get("usdcSize", 0) or 0)
        if usdc_size > 0:
            usd_val = usdc_size
        else:
            usd_val = price * size

        s = self.series.get(key)
        if s and (now_ts - s["first_ts"] > self.window_sec):
            del self.series[key]
            s = None

        if s is None:
            s = {
                "first_ts": now_ts,
                "last_ts": now_ts,
                "usd_sum": 0.0,
                "size_sum": 0.0,
                "volume_weighted_price_sum": 0.0,
                "fills": 0,
                "alert_sent": False,
                "base_trade": trade,
            }
            self.series[key] = s

        s["last_ts"] = max(s["last_ts"], now_ts)
        s["usd_sum"] += usd_val
        s["size_sum"] += size
        s["volume_weighted_price_sum"] += (price * size)
        s["fills"] += 1

        if s["usd_sum"] >= self.min_alert_usd and not s["alert_sent"]:
            s["alert_sent"] = True

            avg_price = s["volume_weighted_price_sum"] / s["size_sum"] if s["size_sum"] > 0 else 0.0

            agg_trade = s["base_trade"].copy()
            agg_trade.update(
                {
                    "is_aggregate": True,
                    "series_fills": s["fills"],
                    "series_usd_sum": s["usd_sum"],
                    "series_avg_price": avg_price,
                    "series_window_sec": self.window_sec,
                    "size": s["size_sum"],
                    "price": avg_price,
                    "value_usd": s["usd_sum"],
                    "timestamp": now_ts,  # normalized
                }
            )
            return agg_trade

        return None

    def cleanup(self):
        if time.time() - self.last_cleanup < 10:
            return

        now = time.time()
        keys_to_del = []
        for k, s in self.series.items():
            if now - s["last_ts"] > self.window_sec + 10:
                keys_to_del.append(k)

        for k in keys_to_del:
            del self.series[k]

        self.last_cleanup = now

    def reset_aggregator(self) -> int:
        """Clear all aggregation state. Call when filters change significantly or bot stops."""
        cleared = len(self.series)
        self.series.clear()
        if cleared > 0:
            logger.info(f"Reset aggregator (cleared {cleared} active series)")
        return cleared


class PolymarketService:
    def __init__(self):
        self.persistence = TradePersistence()
        self.aggregator = TradeAggregator(window_sec=60, min_alert_usd=500)

        self.last_timestamp = 0.0  # ALWAYS seconds
        self.consecutive_errors = 0
        self.total_trades_processed = 0

        self.recent_wallets = OrderedDict()  # {wallet: last_seen_ts}
        self.wallet_last_activity_check = {}  # {wallet: last_check_ts}

        self.seen_activities = OrderedDict()  # {activity_id: ts}
        self.seen_activities_max = 10000
        self.last_activity_poll = 0
        self._callback_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLBACKS)
        self._callback_tasks: set[asyncio.Task] = set()
        self._dropped_callbacks = 0
        self._last_callback_health_log = 0.0

        logger.info("PolymarketService initialized - Data API + SQLite + aggregation")

    async def _run_callback(self, callback, trade_data: dict):
        """Run callback with bounded concurrency to prevent event-loop overload."""
        async with self._callback_semaphore:
            try:
                await callback(trade_data)
            except Exception:
                logger.exception("Error in trade callback")

    def _schedule_callback(self, callback, trade_data: dict):
        """Schedule callback task with a hard cap on pending tasks."""
        if len(self._callback_tasks) >= MAX_PENDING_CALLBACK_TASKS:
            self._dropped_callbacks += 1
            if self._dropped_callbacks % 100 == 1:
                logger.warning(
                    "Dropping trade callbacks due to overload "
                    "(pending=%s, dropped=%s)",
                    len(self._callback_tasks),
                    self._dropped_callbacks,
                )
            return

        task = asyncio.create_task(self._run_callback(callback, trade_data))
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_tasks.discard)

    def _log_callback_queue_health(self):
        """Periodic health log for callback queue to aid production monitoring."""
        pending = len(self._callback_tasks)
        if pending < CALLBACK_QUEUE_INFO_THRESHOLD:
            return

        now = time.time()
        if now - self._last_callback_health_log < CALLBACK_HEALTH_LOG_INTERVAL:
            return
        self._last_callback_health_log = now

        if pending >= CALLBACK_QUEUE_WARN_THRESHOLD:
            logger.warning(
                "Callback queue pressure: pending=%s dropped=%s",
                pending,
                self._dropped_callbacks,
            )
        else:
            logger.info(
                "Callback queue backlog: pending=%s dropped=%s",
                pending,
                self._dropped_callbacks,
            )

    def clear_callback_queue(self) -> int:
        """Cancel all pending callback tasks. Call when bot is stopped."""
        cancelled_count = 0
        for task in list(self._callback_tasks):
            if not task.done():
                task.cancel()
                cancelled_count += 1
        self._callback_tasks.clear()
        if cancelled_count > 0:
            logger.info(f"Cleared {cancelled_count} pending callback tasks")
        return cancelled_count

    async def _fetch_recent_activities(self, session, user_address, activity_type, limit=50, offset=0):
        url = f"{DATA_API_URL}/activity?user={user_address}&type={activity_type}&limit={limit}&offset={offset}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.debug(
                        f"Failed to fetch {activity_type} for {user_address[:10]}...: {resp.status} - {text[:100]}"
                    )
                    return None
                data = await resp.json()
                return data if (data and isinstance(data, list)) else []
        except asyncio.TimeoutError:
            logger.debug(f"Timeout fetching {activity_type} for {user_address[:10]}...")
            return None
        except Exception as e:
            logger.debug(f"Error fetching {activity_type} activities: {e}")
            return None

    def _seen_activity_add(self, activity_id: str, ts: float):
        self.seen_activities[activity_id] = ts
        self.seen_activities.move_to_end(activity_id)
        while len(self.seen_activities) > self.seen_activities_max:
            self.seen_activities.popitem(last=False)

    def _seen_activity_has(self, activity_id: str) -> bool:
        if activity_id in self.seen_activities:
            self.seen_activities.move_to_end(activity_id)
            return True
        return False

    async def _fetch_recent_trades(self, session, limit=10000, offset=0, min_size=10):
        url = (
            f"{DATA_API_URL}/trades?limit={limit}&offset={offset}"
            f"&takerOnly=true&filterType=CASH&filterAmount={min_size}"
        )
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    trades = await resp.json()
                    if trades and isinstance(trades, list):
                        self.consecutive_errors = 0
                        return trades
                    return []

                text = await resp.text()
                self.consecutive_errors += 1
                logger.error(f"Failed to fetch trades: {resp.status} - {text[:200]}")
                return []
        except asyncio.TimeoutError:
            self.consecutive_errors += 1
            logger.error("Timeout fetching trades from Data API")
            return []
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Error fetching trades: {e}")
            return []

    def _prune_recent_wallets(self, now: float):
        cutoff = now - RECENT_WALLETS_WINDOW
        while self.recent_wallets:
            w, last_seen = next(iter(self.recent_wallets.items()))
            if last_seen >= cutoff:
                break
            self.recent_wallets.popitem(last=False)

    async def get_trader_positions(self, proxy_wallet, retries=3):
        if not proxy_wallet or not str(proxy_wallet).startswith("0x"):
            return None

        now = time.time()
        cached = _positions_cache.get(proxy_wallet)
        if cached and (now - cached["ts"] < POSITIONS_CACHE_TTL):
            return cached["data"]

        # Limit concurrent API requests to avoid Cloudflare bans
        if not hasattr(self, '_api_semaphore'):
            self._api_semaphore = asyncio.Semaphore(3)

        async with self._api_semaphore:
            for attempt in range(1, retries + 1):
                try:
                    async with aiohttp.ClientSession() as session:
                        all_positions = []
                        offset = 0
                        limit = 1000

                        while True:
                            url_open = f"{DATA_API_URL}/positions?user={proxy_wallet}&limit={limit}&offset={offset}"
                            async with session.get(url_open, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                if resp.status == 429 or resp.status >= 500:
                                    if attempt < retries:
                                        logger.debug(f"Rate limited or server error ({resp.status}) fetching positions for {proxy_wallet[:10]}, retrying in {attempt * 2}s (attempt {attempt}/{retries})...")
                                        await asyncio.sleep(attempt * 2)
                                        # Force a retry of the whole fetch process for this user
                                        raise aiohttp.ClientError("Retry triggered by status code")
                                    else:
                                        if offset == 0:
                                            return None
                                        break
                                
                                if resp.status != 200:
                                    if offset == 0:
                                        return None
                                    break
                                
                                batch = await resp.json()
                                if not batch or not isinstance(batch, list):
                                    if offset == 0:
                                        return None
                                    break

                                all_positions.extend(batch)
                                if len(batch) < 500:
                                    break

                                offset += len(batch)
                                if offset >= 5000:
                                    break

                        active_positions = [
                            p for p in all_positions 
                            if float(p.get("currentValue", 0) or 0) > 0
                        ] if all_positions else []

                        total_value = sum(float(p.get("currentValue", 0) or 0) for p in active_positions)
                        initial_value = sum(float(p.get("initialValue", 0) or 0) for p in active_positions)
                        open_pnl = total_value - initial_value
                        open_count = len(active_positions)

                        pnl_percent = (open_pnl / initial_value) * 100 if initial_value > 0 else 0.0

                        result = {
                            "pnl_usd": open_pnl,
                            "pnl_percent": pnl_percent,
                            "open_count": open_count,
                            "total_value": total_value,
                        }
                        _positions_cache[proxy_wallet] = {"data": result, "ts": now}
                        return result

                except asyncio.TimeoutError:
                    if attempt < retries:
                        logger.debug(f"Timeout fetching positions for {proxy_wallet[:10]}, retrying in {attempt * 2}s (attempt {attempt}/{retries})...")
                        await asyncio.sleep(attempt * 2)
                    else:
                        logger.debug(f"Timeout fading out after {retries} attempts for {proxy_wallet[:10]}...")
                        return None
                except aiohttp.ClientError as e:
                    if str(e) == "Retry triggered by status code":
                        continue # inner exception was thrown to restart the attempt loop
                    if attempt < retries:
                        logger.debug(f"Network error fetching positions for {proxy_wallet[:10]}, retrying in {attempt * 2}s (attempt {attempt}/{retries})...")
                        await asyncio.sleep(attempt * 2)
                    else:
                        logger.debug(f"Network error fetching positions: {e}")
                        return None
                except Exception as e:
                    logger.debug(f"Error fetching positions: {e}")
                    return None
            return None

    async def check_wallet_has_position(self, proxy_wallet: str, condition_id: str) -> float:
        """
        Check if a wallet currently holds a position on a specific market.
        
        Args:
            proxy_wallet: The wallet address to check
            condition_id: The market's conditionId (same as market_id in alerts)
        
        Returns:
            Position value in USD if wallet holds position, 0.0 otherwise
        """
        if not proxy_wallet or not condition_id:
            return 0.0
        
        try:
            async with aiohttp.ClientSession() as session:
                # Query positions for this wallet
                url = f"{DATA_API_URL}/positions?user={proxy_wallet}&limit=500"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return 0.0
                    
                    positions = await resp.json()
                    if not positions or not isinstance(positions, list):
                        return 0.0
                    
                    # Find position for this market and return its value
                    for pos in positions:
                        pos_condition = pos.get('conditionId', '') or pos.get('condition_id', '')
                        current_value = float(pos.get('currentValue', 0) or 0)
                        
                        # Match by conditionId
                        if pos_condition == condition_id:
                            return current_value
                    
                    return 0.0
                    
        except asyncio.TimeoutError:
            logger.debug(f"Timeout checking position for {proxy_wallet[:10]}...")
            return 0.0  # Assume no position on timeout
        except Exception as e:
            logger.debug(f"Error checking position: {e}")
            return 0.0

    async def get_trader_first_activity(self, proxy_wallet, bypass_cache=False):
        if not proxy_wallet or not str(proxy_wallet).startswith("0x"):
            return None

        now = time.time()
        if not bypass_cache:
            cached = _wallet_age_cache.get(proxy_wallet)
            if cached:
                ttl = WALLET_AGE_CACHE_TTL if cached.get("source") == "etherscan" else WALLET_AGE_FALLBACK_TTL
                if now - cached["cached_at"] < ttl:
                    return cached["first_ts"]

        try:
            oldest_ts = None
            is_full_batch = False

            async with aiohttp.ClientSession() as session:
                url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=100&offset=0"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if not data or not isinstance(data, list):
                        return None

                    if len(data) == 100:
                        is_full_batch = True
                    
                    # Always capture oldest from this batch as fallback
                    if data:
                        oldest_ts = norm_ts(data[-1].get("timestamp", 0))

                    if len(data) < 100:
                        if oldest_ts:
                            _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now, "source": "etherscan"}
                            return oldest_ts

                poly_api_key = POLYGONSCAN_API_KEY
                if isinstance(poly_api_key, list):
                    poly_api_key = random.choice(poly_api_key)

                if is_full_batch and poly_api_key:
                    try:
                        actions = ["txlist", "tokentx", "token1155tx"]
                        min_ts = None

                        for act in actions:
                            ps_url = (
                                "https://api.etherscan.io/v2/api"
                                f"?chainid=137&module=account&action={act}"
                                f"&address={proxy_wallet}&startblock=0&endblock=99999999"
                                f"&page=1&offset=1&sort=asc&apikey={poly_api_key}"
                            )
                            async with session.get(ps_url, timeout=aiohttp.ClientTimeout(total=10)) as ps_resp:
                                if ps_resp.status != 200:
                                    continue
                                ps_data = await ps_resp.json()
                                if ps_data.get("status") == "1" and ps_data.get("result"):
                                    ts = int(ps_data["result"][0].get("timeStamp", 0) or 0)
                                    if ts > 0 and (min_ts is None or ts < min_ts):
                                        min_ts = ts

                        if min_ts:
                            oldest_ts = float(min_ts)
                            _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now, "source": "etherscan"}
                            return oldest_ts
                    except Exception as e:
                        logger.error(f"Error checking PolygonScan for {proxy_wallet}: {e}")
                
                # If PolygonScan failed or not configured, use Polymarket Data API fallback
                # This gives us at least the oldest timestamp from the first 100 activities
                # Note: This may underestimate wallet age for very active wallets, but is better than None
                if oldest_ts:
                    logger.debug(f"PolygonScan unavailable, using Polymarket Data API fallback for {proxy_wallet[:10]}...")
                    _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now, "source": "fallback"}
                    return oldest_ts

            return None

        except Exception as e:
            logger.debug(f"Error fetching first activity: {e}")
            return None

    async def poll_trades(self, callback, interval=POLL_INTERVAL):
        logger.info(f"Starting trade polling (every {interval}s)...")
        last_prune = 0.0
        
        # API has a hard limit of offset 3000 and max items per response of 1000
        MAX_OFFSET = 3000

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    now = time.time()

                    if now - last_prune >= 60:
                        self._prune_recent_wallets(now)
                        last_prune = now

                    offset = 0
                    max_pages = 5
                    new_keys_batch = []

                    baseline_last_ts = norm_ts(self.last_timestamp)

                    for _ in range(max_pages):
                        # Ensure we don't exceed the max historical offset
                        if offset > MAX_OFFSET:
                            break
                            
                        trades = await self._fetch_recent_trades(session, limit=1000, offset=offset)
                        if not trades:
                            break

                        trades_sorted = sorted(trades, key=lambda t: norm_ts(t.get("timestamp", 0)))
                        oldest_trade_ts = norm_ts(trades_sorted[0].get("timestamp", 0))
                        newest_trade_ts = norm_ts(trades_sorted[-1].get("timestamp", 0))

                        for trade in trades_sorted:
                            key = self.persistence.generate_key(trade)
                            if self.persistence.is_seen(key):
                                continue

                            self.persistence._add_to_lru(key)
                            new_keys_batch.append(key)
                            self.total_trades_processed += 1

                            trader_address = trade.get("proxyWallet") or trade.get("maker")
                            if trader_address:
                                self.recent_wallets[trader_address] = now
                                self.recent_wallets.move_to_end(trader_address)
                                while len(self.recent_wallets) > 1000:
                                    self.recent_wallets.popitem(last=False)

                            agg_trade = self.aggregator.process_trade(trade)
                            if agg_trade:
                                self._schedule_callback(callback, agg_trade)

                        # keep last_timestamp clean (seconds)
                        self.last_timestamp = max(norm_ts(self.last_timestamp), newest_trade_ts)

                        if baseline_last_ts > 0 and oldest_trade_ts > baseline_last_ts:
                            logger.info(
                                f"Paging deeper: page oldest {oldest_trade_ts} > baseline {baseline_last_ts} "
                                f"(next offset {offset + 1000})"
                            )
                            offset += 1000
                        else:
                            break

                    if new_keys_batch:
                        self.persistence.add_batch(new_keys_batch)
                        logger.info(f"Processed {len(new_keys_batch)} new raw trades. Aggregator active.")

                    self.aggregator.cleanup()
                    self.persistence.cleanup()
                    self._log_callback_queue_health()

                    if self.consecutive_errors >= 3:
                        logger.warning(f"Data API experiencing issues ({self.consecutive_errors} consecutive errors)")

                except Exception as e:
                    logger.error(f"Polling error: {e}")

                await asyncio.sleep(interval)

    def _map_activity_to_trade(self, activity: dict, activity_type: str) -> dict:
        activity_id = activity.get("id")
        timestamp = norm_ts(activity.get("timestamp", time.time()), default=time.time())
        user_address = activity.get("user") or activity.get("proxyWallet") or activity.get("maker", "")

        market_title = activity.get("title") or activity.get("marketTitle") or "Unknown Market"
        slug = activity.get("slug") or activity.get("eventSlug", "")
        event_slug = activity.get("eventSlug") or slug
        market_url = f"https://polymarket.com/event/{event_slug}" if event_slug else ""

        outcome = activity.get("outcome") or activity.get("outcomeIndex", "")
        if isinstance(outcome, int):
            outcome = "YES" if outcome == 0 else "NO"

        price = float(activity.get("price", 0) or 0)
        size = float(activity.get("size", 0) or activity.get("amount", 0) or 0)

        usdc_size = float(activity.get("usdcSize", 0) or 0)
        if usdc_size > 0:
            value_usd = usdc_size
        elif price > 0:
            value_usd = price * size
        else:
            value_usd = size

        if value_usd == 0:
            value_usd = float(activity.get("value", 0) or activity.get("valueUsd", 0) or 0)

        return {
            "id": activity_id,
            "timestamp": timestamp,
            "title": market_title,
            "market_url": market_url,
            "slug": slug,
            "eventSlug": event_slug,
            "side": activity_type.upper(),
            "type": activity_type.upper(),
            "outcome": outcome,
            "price": price if price > 0 else 0.5,
            "size": size if size > 0 else value_usd,
            "value_usd": value_usd,
            "proxyWallet": user_address,
            "maker": user_address,
            "name": activity.get("name") or activity.get("pseudonym", ""),
            "is_aggregate": False,
            "series_fills": 1,
        }

    async def poll_activities(self, callback, interval: int = 15):
        logger.info(f"Activity polling for SPLIT/REDEEM/MERGE (every {interval}s)...")

        activity_types = ["SPLIT", "REDEEM", "MERGE"]
        max_wallets_to_check = 25

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    now = time.time()

                    candidate_wallets = [
                        w for w, last_seen in self.recent_wallets.items()
                        if now - last_seen < RECENT_WALLETS_WINDOW
                    ]

                    to_check = []
                    for w in candidate_wallets:
                        last_check = self.wallet_last_activity_check.get(w, 0)
                        if now - last_check >= WALLET_ACTIVITY_CHECK_COOLDOWN:
                            to_check.append((w, last_check))

                    to_check.sort(key=lambda x: x[1])
                    wallets_to_poll = [w for (w, _) in to_check][:max_wallets_to_check]

                    if not wallets_to_poll:
                        await asyncio.sleep(interval)
                        continue

                    min_timestamp = now - 600  # 10 minutes

                    for wallet_address in wallets_to_poll:
                        checked_ok = False

                        for activity_type in activity_types:
                            activities = await self._fetch_recent_activities(
                                session, wallet_address, activity_type, limit=50, offset=0
                            )
                            if activities is None:
                                continue

                            checked_ok = True

                            for activity in activities:
                                activity_timestamp = norm_ts(activity.get("timestamp", 0))
                                if activity_timestamp < min_timestamp:
                                    continue

                                tx_hash = activity.get("transactionHash", "")
                                condition_id = activity.get("conditionId", "")
                                if not tx_hash:
                                    continue

                                activity_id = f"{tx_hash}|{condition_id}|{activity_type}"
                                if self._seen_activity_has(activity_id):
                                    continue

                                self._seen_activity_add(activity_id, activity_timestamp)

                                trade_data = self._map_activity_to_trade(activity, activity_type)
                                if trade_data.get("value_usd", 0) >= 500:
                                    logger.info(
                                        f"🔔 {activity_type} detected: "
                                        f"${trade_data.get('value_usd', 0):,.0f} by {wallet_address[:10]}... "
                                        f"in {trade_data.get('title', 'Unknown Market')[:50]}"
                                    )
                                    self._schedule_callback(callback, trade_data)

                            await asyncio.sleep(0.2)

                        if checked_ok:
                            self.wallet_last_activity_check[wallet_address] = now

                    if len(self.wallet_last_activity_check) > 5000:
                        current_wallets = set(self.recent_wallets.keys())
                        for w in list(self.wallet_last_activity_check.keys()):
                            if w not in current_wallets:
                                self.wallet_last_activity_check.pop(w, None)

                    self.last_activity_poll = now
                    self._log_callback_queue_health()

                except Exception as e:
                    logger.error(f"Activity polling error: {e}")

                await asyncio.sleep(interval)

    def get_stats(self):
        return {
            "total_processed": self.total_trades_processed,
            "lru_size": len(self.persistence.lru),
            "active_series": len(self.aggregator.series),
            "last_timestamp": self.last_timestamp,
            "consecutive_errors": self.consecutive_errors,
        }


def get_wallet_age_cache():
    return _wallet_age_cache.copy()
