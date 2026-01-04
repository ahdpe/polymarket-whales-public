import asyncio
import logging
import aiohttp
import time
import sqlite3
import os
from decimal import Decimal
from collections import OrderedDict

from config import POLYGONSCAN_API_KEY

logger = logging.getLogger(__name__)

# Data API endpoint (public, no auth required)
DATA_API_URL = "https://data-api.polymarket.com"

# Polling configuration
POLL_INTERVAL = 3
MAX_LRU_SIZE = 10000
DB_PATH = "data/trades.db"
TTL_HOURS = 72

# Trader positions cache (TTL 60 seconds)
POSITIONS_CACHE_TTL = 60
_positions_cache = {}  # {proxy_wallet: {"data": {...}, "ts": timestamp}}

# Wallet age cache (TTL 7 days - age is static)
WALLET_AGE_CACHE_TTL = 7 * 24 * 60 * 60
_wallet_age_cache = {}  # {proxy_wallet: {"first_ts": timestamp, "cached_at": timestamp}}


class TradePersistence:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.lru = OrderedDict()
        self._init_db()
        self.last_cleanup = time.time()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        # Performance tuning
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_trades (
                trade_key TEXT PRIMARY KEY,
                seen_at INTEGER NOT NULL
            );
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_trades(seen_at);")
        self.conn.commit()

    def _normalize_decimal(self, val):
        try:
            return str(Decimal(str(val)).quantize(Decimal("0.000001")))
        except:
            return "0.000000"

    def generate_key(self, trade):
        # Normalization
        price = self._normalize_decimal(trade.get('price', 0))
        size = self._normalize_decimal(trade.get('size', 0))
        try:
            ts = int(trade.get('timestamp', 0))
        except:
            ts = 0
        
        parts = [
            trade.get('proxyWallet', ''),
            trade.get('conditionId', ''),
            trade.get('side', ''),
            trade.get('outcomeIndex', ''),
            price,
            size,
            ts,
            trade.get('transactionHash', '')
        ]
        return "|".join(str(p) for p in parts)

    def is_seen(self, key):
        # 1. Check LRU
        if key in self.lru:
            self.lru.move_to_end(key)
            return True
        
        # 2. Check DB
        cursor = self.conn.execute("SELECT 1 FROM seen_trades WHERE trade_key=? LIMIT 1", (key,))
        if cursor.fetchone():
            self._add_to_lru(key)
            return True
        
        return False

    def _add_to_lru(self, key):
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
                data
            )
        
        for k in keys:
            self._add_to_lru(k)

    def cleanup(self):
        # Run cleanup once hour
        if time.time() - self.last_cleanup < 3600:
            return

        logger.info("Running DB cleanup...")
        cutoff_ms = int((time.time() - (TTL_HOURS * 3600)) * 1000)
        with self.conn:
            self.conn.execute("DELETE FROM seen_trades WHERE seen_at < ?", (cutoff_ms,))
        self.last_cleanup = time.time()
        logger.info("DB cleanup completed")

    def close(self):
        self.conn.close()



class TradeAggregator:
    def __init__(self, window_sec=60, min_alert_usd=500):
        self.window_sec = window_sec
        self.min_alert_usd = min_alert_usd
        self.series = {}  # key -> SeriesData
        self.last_cleanup = time.time()

    def _get_key(self, trade):
        return (
            trade.get('proxyWallet', ''),
            trade.get('conditionId', ''),
            trade.get('side', ''),
            trade.get('outcomeIndex', str(trade.get('outcome', '')))
        )

    def process_trade(self, trade):
        """
        Process a new trade.
        Returns: aggregated_trade dict if a series triggers an alert, else None.
        """
        key = self._get_key(trade)
        now_ts = trade.get('timestamp', time.time())
        try:
             # Ensure timestamp is int/float
            now_ts = float(now_ts)
        except:
            now_ts = time.time()

        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        usd_val = price * size

        # Check if series exists and is within window
        if key in self.series:
            s = self.series[key]
            # Window check: 60s from first trade
            if now_ts - s['first_ts'] > self.window_sec:
                # Series expired, close old one and start new
                del self.series[key]
                s = None
        else:
            s = None

        if s is None:
            # Start new series
            s = {
                'first_ts': now_ts,
                'last_ts': now_ts,
                'usd_sum': 0.0,
                'size_sum': 0.0,
                'volume_weighted_price_sum': 0.0, # price * size sum for VWAP
                'fills': 0,
                'alert_sent': False,
                'base_trade': trade # Keep reference for metadata (title, slug, etc)
            }
            self.series[key] = s

        # Update series
        s['last_ts'] = max(s['last_ts'], now_ts)
        s['usd_sum'] += usd_val
        s['size_sum'] += size
        s['volume_weighted_price_sum'] += (price * size)
        s['fills'] += 1

        # Check Trigger
        if s['usd_sum'] >= self.min_alert_usd and not s['alert_sent']:
            s['alert_sent'] = True
            
            # Construct Aggregate Trade Object
            avg_price = s['volume_weighted_price_sum'] / s['size_sum'] if s['size_sum'] > 0 else 0
            
            agg_trade = s['base_trade'].copy()
            agg_trade.update({
                'is_aggregate': True,
                'series_fills': s['fills'],
                'series_usd_sum': s['usd_sum'],
                'series_avg_price': avg_price,
                'series_window_sec': self.window_sec,
                # Override size/price with totals for accurate display logic
                'size': s['size_sum'], 
                'price': avg_price,
                'value_usd': s['usd_sum'] # Pre-calculate for main.py
            })
            return agg_trade
        
        return None

    def cleanup(self):
        """Garbage collect old series."""
        if time.time() - self.last_cleanup < 10:
            return
            
        now = time.time()
        keys_to_del = []
        for k, s in self.series.items():
            # If nothing happened for window_sec + buffer, delete
            if now - s['last_ts'] > self.window_sec + 10:
                keys_to_del.append(k)
        
        for k in keys_to_del:
            del self.series[k]
            
        self.last_cleanup = now


class PolymarketService:
    def __init__(self):
        self.persistence = TradePersistence()
        self.aggregator = TradeAggregator(window_sec=60, min_alert_usd=500)
        self.last_timestamp = 0
        self.consecutive_errors = 0
        self.total_trades_processed = 0
        self.recent_wallets = OrderedDict()  # {wallet_address: last_seen_timestamp}
        self.seen_activities = set()  # Set of activity IDs we've already processed
        self.last_activity_poll = 0
        
        logger.info("PolymarketService initialized - using Data API with SQLite Persistence & Aggregation")
        
    async def _fetch_recent_activities(self, user_address: str, activity_type: str, limit=100, offset=0):
        """Fetch recent activities (SPLIT/REDEEM/MERGE) for a specific user from Data API."""
        try:
            url = f"{DATA_API_URL}/activity?user={user_address}&type={activity_type}&limit={limit}&offset={offset}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        activities = await resp.json()
                        if activities and isinstance(activities, list):
                            return activities
                        return []
                    else:
                        text = await resp.text()
                        logger.debug(f"Failed to fetch {activity_type} activities for {user_address[:10]}...: {resp.status} - {text[:100]}")
                        return []
        except asyncio.TimeoutError:
            logger.debug(f"Timeout fetching {activity_type} activities for {user_address[:10]}...")
            return []
        except Exception as e:
            logger.debug(f"Error fetching {activity_type} activities: {e}")
            return []

    async def _fetch_recent_trades(self, limit=10000, offset=0, min_size=10):
        """Fetch recent trades from Data API."""
        try:
            # Optimized API request with server-side filtering
            # Lowered min_size to 10 to capture shards for aggregation
            url = f"{DATA_API_URL}/trades?limit={limit}&offset={offset}&takerOnly=true&filterType=CASH&filterAmount={min_size}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        trades = await resp.json()
                        if trades and isinstance(trades, list):
                            self.consecutive_errors = 0
                            return trades
                        return []
                    else:
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

    async def get_trader_positions(self, proxy_wallet):
        """
        Fetch trader's open positions from Data API.
        Returns: {"pnl_usd": float, "pnl_percent": float, "open_count": int, "total_value": float, "alltime_pnl": float}
        Uses TTL cache (60 seconds).
        """
        if not proxy_wallet:
            return None
            
        # Check cache
        now = time.time()
        if proxy_wallet in _positions_cache:
            cached = _positions_cache[proxy_wallet]
            if now - cached["ts"] < POSITIONS_CACHE_TTL:
                return cached["data"]
        
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch open positions with pagination
                # API has a hard limit of 500 positions per request
                open_pnl = 0
                total_value = 0
                initial_value = 0
                all_positions = []
                
                offset = 0
                limit = 1000 # Request more, but API will cap at 500
                
                while True:
                    url_open = f"{DATA_API_URL}/positions?user={proxy_wallet}&limit={limit}&offset={offset}"
                    async with session.get(url_open, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            batch = await resp.json()
                            if batch and isinstance(batch, list) and len(batch) > 0:
                                all_positions.extend(batch)
                                
                                # If we got fewer than 500, we reached the end
                                if len(batch) < 500:
                                    break
                                
                                offset += len(batch)
                                
                                # Safety break to avoid too many requests (max 5000 positions)
                                if offset >= 5000:
                                    break
                            else:
                                break
                        else:
                            break
                            
                if all_positions:
                    total_value = sum(float(p.get("currentValue", 0) or 0) for p in all_positions)
                    initial_value = sum(float(p.get("initialValue", 0) or 0) for p in all_positions)
                    # Calculate Open PnL as currentValue - initialValue
                    open_pnl = total_value - initial_value
                    open_count = len(all_positions)
                
                # Calculate percentage PnL for open positions
                if initial_value > 0:
                    pnl_percent = (open_pnl / initial_value) * 100
                else:
                    pnl_percent = 0
                
                result = {
                    "pnl_usd": open_pnl,
                    "pnl_percent": pnl_percent,
                    "open_count": open_count,
                    "total_value": total_value
                }
                
                # Cache result
                _positions_cache[proxy_wallet] = {"data": result, "ts": now}
                return result
                
        except asyncio.TimeoutError:
            logger.debug(f"Timeout fetching positions for {proxy_wallet[:10]}...")
            return None
        except Exception as e:
            logger.debug(f"Error fetching positions: {e}")
            return None

    async def get_trader_first_activity(self, proxy_wallet):
        """
        Fetch trader's first activity timestamp from Data API.
        Returns: Unix timestamp (seconds) of first activity, or None.
        Uses TTL cache (5 minutes).
        """
        if not proxy_wallet:
            return None
            
        # Check cache
        now = time.time()
        if proxy_wallet in _wallet_age_cache:
            cached = _wallet_age_cache[proxy_wallet]
            if now - cached["cached_at"] < WALLET_AGE_CACHE_TTL:
                return cached["first_ts"]
        
        try:
            # API returns newest first. We need to find the LAST page of results.
            # Strategy:
            # 1. Fetch first 100.
            # 2. If < 100, we have the full history (last item is oldest).
            # 3. If == 100, user is "active" (potentially truncated).
            #    a) If we have POLYGONSCAN_API_KEY, query blockchain immediately.
            #    b) If no key, attempt binary search on Poly API.
            
            oldest_ts = None
            is_full_batch = False
            
            async with aiohttp.ClientSession() as session:
                # 1. Fetch first batch
                url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=100&offset=0"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if not data or not isinstance(data, list) or len(data) == 0:
                        return None
                    
                    if len(data) == 100:
                        is_full_batch = True
                    
                    if len(data) < 100:
                        # Found it in first batch
                        oldest_ts = data[-1].get("timestamp", 0)
                        if oldest_ts:
                            _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now}
                            return oldest_ts
            
                # If we are here, we have >= 100 items.
                
                # --- PolygonScan Check ---
                poly_api_key = POLYGONSCAN_API_KEY
                
                if is_full_batch and poly_api_key:
                    try:
                        # Query multiple endpoints: txlist, tokentx (ERC20), token1155tx (ERC1155)
                        # Proxy wallets often show 'No transactions found' in txlist but have token transfers.
                        actions = ["txlist", "tokentx", "token1155tx"]
                        min_ts = None
                        
                        # We can do this concurrently or sequentially. 
                        # Sequential is safer for rate limits (3-5 req/sec). 
                        # We only need 1st page, 1 item.
                        
                        for act in actions:
                            ps_url = f"https://api.etherscan.io/v2/api?chainid=137&module=account&action={act}&address={proxy_wallet}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey={poly_api_key}"
                            async with session.get(ps_url, timeout=aiohttp.ClientTimeout(total=5)) as ps_resp:
                                if ps_resp.status == 200:
                                    ps_data = await ps_resp.json()
                                    if ps_data.get("status") == "1" and ps_data.get("result"):
                                        first_tx = ps_data["result"][0]
                                        ts = int(first_tx.get("timeStamp", 0))
                                        if ts > 0:
                                            if min_ts is None or ts < min_ts:
                                                min_ts = ts
                                                
                        if min_ts:
                            _wallet_age_cache[proxy_wallet] = {"first_ts": min_ts, "cached_at": now}
                            return min_ts

                    except Exception as e:
                        logger.debug(f"PolygonScan fetch failed: {e}")
                
                # --- Poly API Fallback (Binary/Step Search) ---
                # Used if no API key OR blockchain fetch failed.
                
                # 2. Step up to find upper bound
                steps = [500, 1000, 5000, 10000, 20000, 50000]
                low = 100
                high = 50000
                
                found_upper_bound = False
                # If high is 500, we don't need to check steps > 500
                valid_steps = [s for s in steps if s < high]
                for step in valid_steps:
                   # ... reuse existing step logic or simplified loop ...
                   pass
                   
                # Let's reuse the existing comprehensive step search to be safe and robust
                # (Keep existing logic for binary search below)
                
                # 2. Step up to find upper bound
                steps = [500, 1000, 5000, 10000, 20000, 50000]
                low = 100
                high = 50000
                
                found_upper_bound = False
                for step in steps:
                    url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=1&offset={step}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        has_data = False
                        if resp.status == 200:
                            d = await resp.json()
                            if d and isinstance(d, list) and len(d) > 0:
                                has_data = True
                        
                        if has_data:
                            low = step # This offset has data, so oldest is at least here
                        else:
                            high = step # This offset empty, so oldest is before here
                            found_upper_bound = True
                            break
                
                # If we went through all steps and still have data at 50000, use 50000
                if not found_upper_bound and low == 50000:
                     high = 50000 # Just use this as max
                
                # 3. Binary search between low and high
                max_valid_offset = low
                
                while low <= high:
                    mid = (low + high) // 2
                    if mid == max_valid_offset:
                        low = mid + 1
                        continue
                        
                    url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=1&offset={mid}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and isinstance(data, list) and len(data) > 0:
                                max_valid_offset = mid
                                low = mid + 1
                            else:
                                high = mid - 1
                        else:
                            high = mid - 1 # Treat error as no data to be safe
                
                # 4. Fetch the record at max_valid_offset
                if max_valid_offset > 0:
                    url = f"{DATA_API_URL}/activity?user={proxy_wallet}&limit=1&offset={max_valid_offset}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and len(data) > 0:
                                oldest_ts = data[0].get("timestamp", 0)
                else:
                    # Fallback to first batch's last item
                    # oldest_ts should be set from step 1, but if we entered loop it might be overwritten?
                    # Re-check first batch if needed, but oldest_ts should correspond to offset=0 last item if max_valid_offset=0
                    pass
            
            if oldest_ts:
                _wallet_age_cache[proxy_wallet] = {"first_ts": oldest_ts, "cached_at": now}
                return oldest_ts
            
            return None
            
        except Exception as e:
            logger.debug(f"Error fetching first activity: {e}")
            return None

    async def poll_trades(self, callback, interval=POLL_INTERVAL):
        """
        Poll for new trades every `interval` seconds.
        Uses pagination, SQLite persistence, and Aggregation.
        """
        logger.info(f"Starting trade polling (every {interval}s)...")
        limit = 10000 
        
        while True:
            try:
                offset = 0
                max_pages = 5
                trades_found_in_poll = 0
                new_keys_batch = []
                
                for page in range(max_pages):
                    trades = await self._fetch_recent_trades(limit=limit, offset=offset)
                    
                    if not trades:
                        break
                        
                    # Sort by timestamp (oldest first)
                    trades_sorted = sorted(trades, key=lambda t: t.get('timestamp', 0))
                    
                    oldest_trade_ts = trades_sorted[0].get('timestamp', 0)
                    newest_trade_ts = trades_sorted[-1].get('timestamp', 0)
                    
                    for trade in trades_sorted:
                        key = self.persistence.generate_key(trade)
                        
                        if self.persistence.is_seen(key):
                            continue
                        
                        # New trade confirmed
                        self.persistence._add_to_lru(key)
                        new_keys_batch.append(key)
                        trades_found_in_poll += 1
                        self.total_trades_processed += 1
                        
                        # Collect wallet address for activity polling
                        trader_address = trade.get('proxyWallet') or trade.get('maker')
                        if trader_address:
                            self.recent_wallets[trader_address] = time.time()
                            # Keep only the most recent N wallets
                            while len(self.recent_wallets) > 100:  # Keep last 100 active wallets
                                self.recent_wallets.popitem(last=False)
                        
                        # Pass to Aggregator
                        agg_trade = self.aggregator.process_trade(trade)
                        if agg_trade:
                            # If aggregator triggered a series alert, send IT
                            await callback(agg_trade)
                            
                        # If you wanted to support single non-aggregated alerts for random big trades, 
                        # you could add logic here. But per request, we focus on Aggregate >= 500.
                        # Note: _fetch_recent_trades filters < 10. Aggregator filters sum < 500.
                        # So a single trade of $1000 will be aggregated immediately (fills=1) and sent.

                    # Update global last timestamp
                    if newest_trade_ts > self.last_timestamp:
                        self.last_timestamp = newest_trade_ts

                    # Robustness Check
                    if self.last_timestamp > 0 and oldest_trade_ts > self.last_timestamp:
                        logger.info(f"Gap detected! Oldest fetch: {oldest_trade_ts}, Last seen: {self.last_timestamp}. Paging deeper (offset {offset + limit})...")
                        offset += limit
                    else:
                        break
                
                # Batch insert new keys to DB
                if new_keys_batch:
                    self.persistence.add_batch(new_keys_batch)
                    logger.info(f"Processed {len(new_keys_batch)} new raw trades. Aggregator active.")
                
                # Aggregator Cleanup
                self.aggregator.cleanup()

                # Persistence Cleanup
                self.persistence.cleanup()
                
                # Health Check
                if self.consecutive_errors >= 3:
                     logger.warning(f"Data API experiencing issues ({self.consecutive_errors} consecutive errors)")
                     
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(interval)
    
    def _map_activity_to_trade(self, activity: dict, activity_type: str) -> dict:
        """Map activity data to a trade-like dictionary for consistent processing."""
        # Extract common fields
        activity_id = activity.get('id')
        timestamp = activity.get('timestamp', time.time())
        user_address = activity.get('user') or activity.get('proxyWallet') or activity.get('maker', '')
        
        # Market info
        market_title = activity.get('title') or activity.get('marketTitle') or 'Unknown Market'
        slug = activity.get('slug') or activity.get('eventSlug', '')
        event_slug = activity.get('eventSlug') or slug
        market_url = f"https://polymarket.com/event/{event_slug}" if event_slug else ""
        
        # Outcome
        outcome = activity.get('outcome') or activity.get('outcomeIndex', '')
        if isinstance(outcome, int):
            outcome = 'YES' if outcome == 0 else 'NO'
        
        # Price and size
        price = float(activity.get('price', 0))
        size = float(activity.get('size', 0) or activity.get('amount', 0))
        
        # For SPLIT/MERGE/REDEEM, the API provides usdcSize which is the actual USD value
        # price is always 0.5 for these operations, so price * size gives wrong result
        usdc_size = float(activity.get('usdcSize', 0) or 0)
        if usdc_size > 0:
            value_usd = usdc_size
        elif price > 0:
            value_usd = price * size
        else:
            value_usd = size  # Fallback: size might already be USD
        
        # If value_usd is still 0, try to get from other fields
        if value_usd == 0:
            value_usd = float(activity.get('value', 0) or activity.get('valueUsd', 0) or 0)
        
        return {
            'id': activity_id,
            'timestamp': timestamp,
            'title': market_title,
            'market_url': market_url,
            'slug': slug,
            'eventSlug': event_slug,
            'side': activity_type.upper(),  # Use activity type as 'side'
            'type': activity_type.upper(),  # Use activity type as 'type'
            'outcome': outcome,
            'price': price if price > 0 else 0.5,  # Default price if missing
            'size': size if size > 0 else value_usd,  # Use value_usd as size if size is 0
            'value_usd': value_usd,
            'proxyWallet': user_address,
            'maker': user_address,
            'name': activity.get('name') or activity.get('pseudonym', ''),
            'is_aggregate': False,  # Activities are not aggregated
            'series_fills': 1
        }
    
    async def poll_activities(self, callback, interval=30):
        """
        Poll for new SPLIT/REDEEM/MERGE activities for recently active traders.
        Runs separately from trade polling to avoid blocking.
        """
        logger.info(f"Activity polling for SPLIT/REDEEM/MERGE (every {interval}s)...")
        activity_types = ['SPLIT', 'REDEEM', 'MERGE']
        max_wallets_to_check = 25  # Limit to recent active wallets
        
        while True:
            try:
                # Get recently active wallets (last 1 hour)
                now = time.time()
                recent_wallets = [
                    wallet for wallet, last_seen in self.recent_wallets.items()
                    if now - last_seen < 3600  # Last hour
                ][:max_wallets_to_check]
                
                if not recent_wallets:
                    # Log periodically that we're waiting for wallets
                    if now - self.last_activity_poll > 300:  # Every 5 minutes
                        logger.debug(f"Activity polling: waiting for active wallets (tracking {len(self.recent_wallets)} total)")
                    await asyncio.sleep(interval)
                    continue
                
                logger.debug(f"Activity polling: checking {len(recent_wallets)} wallets for SPLIT/REDEEM/MERGE")
                
                for wallet_address in recent_wallets:
                    for activity_type in activity_types:
                        activities = await self._fetch_recent_activities(wallet_address, activity_type, limit=10, offset=0)
                        
                        for activity in activities:
                            # Generate synthetic activity ID (API doesn't provide 'id' field)
                            tx_hash = activity.get('transactionHash', '')
                            condition_id = activity.get('conditionId', '')
                            activity_id = f"{tx_hash}|{condition_id}|{activity_type}"
                            
                            if not tx_hash:  # Skip if no transaction hash
                                continue
                            
                            # Check if we've seen this activity
                            if activity_id in self.seen_activities:
                                continue
                            
                            self.seen_activities.add(activity_id)
                            
                            # Clean old activity IDs (keep last 10000)
                            if len(self.seen_activities) > 10000:
                                # Remove oldest 2000
                                old_ids = list(self.seen_activities)[:2000]
                                for old_id in old_ids:
                                    self.seen_activities.discard(old_id)
                            
                            # Map activity to trade-like format
                            trade_data = self._map_activity_to_trade(activity, activity_type)
                            
                            # Only process if value is significant
                            if trade_data.get('value_usd', 0) >= 500:
                                logger.info(f"🔔 {activity_type} detected: ${trade_data.get('value_usd', 0):,.0f} by {wallet_address[:10]}... in {trade_data.get('title', 'Unknown Market')[:50]}")
                                await callback(trade_data)
                        
                        # Small delay between requests to avoid rate limiting
                        await asyncio.sleep(0.5)
                
                self.last_activity_poll = now
                
            except Exception as e:
                logger.error(f"Activity polling error: {e}")
            
            await asyncio.sleep(interval)
    
    def get_stats(self):
        """Get service statistics."""
        return {
            "total_processed": self.total_trades_processed,
            "lru_size": len(self.persistence.lru),
            "active_series": len(self.aggregator.series),
            "last_timestamp": self.last_timestamp,
            "consecutive_errors": self.consecutive_errors
        }

def get_wallet_age_cache():
    """Get copy of wallet age cache for debugging."""
    return _wallet_age_cache.copy()
