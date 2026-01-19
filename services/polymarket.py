import asyncio
import logging
import aiohttp
import time
import sqlite3
import os
from decimal import Decimal
from collections import OrderedDict

from config import get_polygonscan_api_key

logger = logging.getLogger(__name__)

DATA_API_URL = "https://data-api.polymarket.com"

POLL_INTERVAL = 3
MAX_LRU_SIZE = 10000
DB_PATH = "data/trades.db"
TTL_HOURS = 72

RECENT_WALLETS_WINDOW = 48 * 3600  # 48 hours
WALLET_ACTIVITY_CHECK_COOLDOWN = 300  # 5 minutes

POSITIONS_CACHE_TTL = 60
_positions_cache = {}  # {proxy_wallet: {"data": {...}, "ts": timestamp}}

WALLET_AGE_CACHE_TTL = 7 * 24 * 60 * 60
_wallet_age_cache = {}  # {proxy_wallet: {"first_ts": timestamp, "cached_at": timestamp}}


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
        with self.conn:
            self.conn.execute("DELETE FROM seen_trades WHERE seen_at < ?", (cutoff_ms,))
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

        logger.info("PolymarketService initialized - Data API + SQLite + aggregation")

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

    async def get_trader_positions(self, proxy_wallet):
        if not proxy_wallet:
            return None

        now = time.time()
        cached = _positions_cache.get(proxy_wallet)
        if cached and (now - cached["ts"] < POSITIONS_CACHE_TTL):
            return cached["data"]

        try:
            async with aiohttp.ClientSession() as session:
                all_positions = []
                offset = 0
                limit = 1000

                while True:
                    url_open = f"{DATA_API_URL}/positions?user={proxy_wallet}&limit={limit}&offset={offset}"
                    async with session.get(url_open, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status != 200:
                            break
                        batch = await resp.json()
                        if not batch or not isinstance(batch, list):
                            break

                        all_positions.extend(batch)
                        if len(batch) < 500:
                            break

                        offset += len(batch)
                        if offset >= 5000:
                            break

                total_value = sum(float(p.get("currentValue", 0) or 0) for p in all_positions) if all_positions else 0.0
                initial_value = sum(float(p.get("initialValue", 0) or 0) for p in all_positions) if all_positions else 0.0
                open_pnl = total_value - initial_value
                open_count = len(all_positions)

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
            logger.debug(f"Timeout fetching positions for {proxy_wallet[:10]}...")
            return None
        except Exception as e:
            logger.debug(f"Error fetching positions: {e}")
            return None

    async def get_trader_first_activity(self, proxy_wallet):
        if not proxy_wallet:
            return None

        now = time.time()
        cached = _wallet_age_cache.get(proxy_wallet)
        if cached and (now - cached["cached_at"] < WALLET_AGE_CACHE_TTL):
            return cached["first_ts"]

        try:
            oldest_ts = None
            is_full_batch = False

            async with aiohttp.ClientSession() as session:
                url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=100&offset=0"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if not data or not isinstance(data, list):
                        return None

                    if len(data) == 100:
                        is_full_batch = True
                    if len(data) < 100:
                        oldest_ts = norm_ts(data[-1].get("timestamp", 0))
                        if oldest_ts:
                            _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now}
                            return oldest_ts

                poly_api_key = get_polygonscan_api_key()

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
                            async with session.get(ps_url, timeout=aiohttp.ClientTimeout(total=5)) as ps_resp:
                                if ps_resp.status != 200:
                                    continue
                                ps_data = await ps_resp.json()
                                if ps_data.get("status") == "1" and ps_data.get("result"):
                                    ts = int(ps_data["result"][0].get("timeStamp", 0) or 0)
                                    if ts > 0 and (min_ts is None or ts < min_ts):
                                        min_ts = ts

                        if min_ts:
                            oldest_ts = float(min_ts)
                            _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now}
                            return oldest_ts

                    except Exception as e:
                        logger.debug(f"PolygonScan fetch failed: {e}")

                steps = [500, 1000, 5000, 10000, 20000, 50000]
                low, high = 100, 50000
                found_upper_bound = False

                for step in steps:
                    url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=1&offset={step}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        has_data = False
                        if resp.status == 200:
                            d = await resp.json()
                            has_data = bool(d and isinstance(d, list) and len(d) > 0)

                        if has_data:
                            low = step
                        else:
                            high = step
                            found_upper_bound = True
                            break

                if not found_upper_bound and low == 50000:
                    high = 50000

                max_valid_offset = low
                while low <= high:
                    mid = (low + high) // 2
                    if mid == max_valid_offset:
                        low = mid + 1
                        continue

                    url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=1&offset={mid}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status != 200:
                            high = mid - 1
                            continue
                        d = await resp.json()
                        if d and isinstance(d, list) and len(d) > 0:
                            max_valid_offset = mid
                            low = mid + 1
                        else:
                            high = mid - 1

                if max_valid_offset > 0:
                    url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=1&offset={max_valid_offset}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            if d and isinstance(d, list) and len(d) > 0:
                                oldest_ts = norm_ts(d[0].get("timestamp", 0))

            if oldest_ts:
                _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now}
                return oldest_ts

            return None

        except Exception as e:
            logger.debug(f"Error fetching first activity: {e}")
            return None

    async def poll_trades(self, callback, interval=POLL_INTERVAL):
        logger.info(f"Starting trade polling (every {interval}s)...")
        limit = 10000
        last_prune = 0.0

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
                        trades = await self._fetch_recent_trades(session, limit=limit, offset=offset)
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
                                await callback(agg_trade)

                        # keep last_timestamp clean (seconds)
                        self.last_timestamp = max(norm_ts(self.last_timestamp), newest_trade_ts)

                        if baseline_last_ts > 0 and oldest_trade_ts > baseline_last_ts:
                            logger.info(
                                f"Paging deeper: page oldest {oldest_trade_ts} > baseline {baseline_last_ts} "
                                f"(next offset {offset + limit})"
                            )
                            offset += limit
                        else:
                            break

                    if new_keys_batch:
                        self.persistence.add_batch(new_keys_batch)
                        logger.info(f"Processed {len(new_keys_batch)} new raw trades. Aggregator active.")

                    self.aggregator.cleanup()
                    self.persistence.cleanup()

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
                                    await callback(trade_data)

                            await asyncio.sleep(0.2)

                        if checked_ok:
                            self.wallet_last_activity_check[wallet_address] = now

                    if len(self.wallet_last_activity_check) > 5000:
                        current_wallets = set(self.recent_wallets.keys())
                        for w in list(self.wallet_last_activity_check.keys()):
                            if w not in current_wallets:
                                self.wallet_last_activity_check.pop(w, None)

                    self.last_activity_poll = now

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
