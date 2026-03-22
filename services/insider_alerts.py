"""
Insider Alerts Detection Service.
Analyzes trading patterns to detect coordinated activity by fresh wallets.
"""
import asyncio
import logging
import os
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from storage import alerts_storage
from core.categories import detect_category
from services.telegram_service import add_polymarket_ref
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SETTINGS = {
    # Global
    'enabled': 'false',
    'channel_id': '',
    'cooldown_hours': '24',

    # Categories
    'cat_sports_enabled': 'true',
    'cat_crypto_enabled': 'true',
    'cat_other_enabled': 'true',

    # Probability (Global Insider Filter)
    'probability_min': '0',
    'probability_max': '100',

    # CLUSTER scenario
    'cluster_enabled': 'false',
    'cluster_interval_hours': '2',
    'cluster_wallet_age_hours': '24',
    'cluster_min_usd': '5000',
    'cluster_min_total_usd': '10000',
    'cluster_min_wallets': '4',
    'cluster_min_direction_pct': '75',
    'cluster_side': 'both',
    'cluster_include_profiles': 'true',
    'cluster_max_positions': '3',

    # ACCUMULATION scenario (slow multi-wallet accumulation)
    'accumulation_enabled': 'false',
    'accumulation_interval_days': '14',
    'accumulation_min_usd': '10000',
    'accumulation_min_total_usd': '50000',
    'accumulation_min_wallets': '3',
    'accumulation_wallet_age_hours': '48',
    'accumulation_min_direction_pct': '70',
    'accumulation_include_profiles': 'true',
    'accumulation_max_positions': '3',

    # BURST scenario
    'burst_enabled': 'false',
    'burst_interval_hours': '1',
    'burst_wallet_age_hours': '72',
    'burst_min_usd': '1000',
    'burst_min_total_usd': '5000',
    'burst_min_wallets': '8',
    'burst_min_direction_pct': '70',
    'burst_include_profiles': 'true',
    'burst_max_positions': '3',
}


class InsiderAlertsService:
    """Service for detecting and publishing insider trading alerts."""

    def __init__(self):
        """Initialize service and load settings."""
        # Ensure DB is initialized
        alerts_storage.init_db()

        # Load settings or initialize with defaults
        self._load_settings()

        # Refresh recent trade categories to avoid dashboard leaks
        try:
            alerts_storage.reclassify_recent_trades(
                hours_back=72,
                reclassifier=lambda title, slug, url: detect_category(title, slug, url),
            )
        except Exception as e:
            logger.debug(f"Failed to reclassify recent trades: {e}")

        # Reference to bot for sending messages (set externally)
        self._bot = None
        
        # Reference to PolymarketService for position checks (set externally)
        self._poly_service = None
        
        # Tracking active patterns
        self._active_clusters = {}      # market_id -> data
        self._active_accumulations = {} # market_id -> data
        self._active_bursts = {}        # market_id -> data
        self._scenario_debounce_sec = max(0.1, float(os.getenv("INSIDER_SCENARIO_DEBOUNCE_SEC", "1.5")))
        self._pending_scenario_checks: Dict[str, Dict[str, Any]] = {}
        self._scenario_tasks: Dict[str, asyncio.Task] = {}

        logger.info("InsiderAlertsService v2 (Bold Formatting) initialized")

    def _get_buffer_dict_for_scenario(self, scenario: str) -> Optional[Dict[str, Dict[str, Any]]]:
        s = (scenario or "").upper()
        if s == "CLUSTER":
            return self._active_clusters
        if s == "ACCUMULATION":
            return self._active_accumulations
        if s == "BURST":
            return self._active_bursts
        return None

    def _set_blocked_reason(
        self,
        buffer_dict: Dict[str, Dict[str, Any]],
        market_id: str,
        *,
        code: str,
        reason: str,
    ) -> None:
        """
        Non-invasive: store diagnostics for status UI only.
        Safe to call even if buffer entry doesn't exist.
        """
        if not buffer_dict or not market_id:
            return
        entry = buffer_dict.get(market_id)
        if not isinstance(entry, dict):
            return
        entry["blocked_code"] = code
        entry["blocked_reason"] = reason
        entry["blocked_at"] = int(time.time())

    def _clear_blocked_reason(self, buffer_dict: Dict[str, Dict[str, Any]], market_id: str) -> None:
        """Clear diagnostics after successful publish or when no longer relevant."""
        if not buffer_dict or not market_id:
            return
        entry = buffer_dict.get(market_id)
        if not isinstance(entry, dict):
            return
        entry.pop("blocked_code", None)
        entry.pop("blocked_reason", None)
        entry.pop("blocked_at", None)

    def set_bot(self, bot):
        """Set bot instance for sending messages."""
        self._bot = bot

    def set_poly_service(self, poly_service):
        """Set PolymarketService instance for position verification."""
        self._poly_service = poly_service

    async def _run_debounced_scenario_check(self, market_id: str) -> None:
        """Run scenario checks once per market after short quiet period."""
        try:
            await asyncio.sleep(self._scenario_debounce_sec)
            payload = self._pending_scenario_checks.pop(market_id, None)
            if not payload:
                return
            category = payload.get("category", "other")
            await self.check_scenarios(market_id, category)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in debounced scenario check for {market_id}: {e}", exc_info=True)

    def _schedule_scenario_check_debounced(self, market_id: str, category: str) -> None:
        """
        Debounce scenario checks by market_id to reduce repeated heavy checks
        during short trade bursts.
        """
        if not market_id:
            return

        self._pending_scenario_checks[market_id] = {
            "category": category,
            "updated_at": time.time(),
        }

        existing_task = self._scenario_tasks.get(market_id)
        if existing_task and not existing_task.done():
            existing_task.cancel()

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_debounced_scenario_check(market_id))
        self._scenario_tasks[market_id] = task

        def _cleanup(done_task: asyncio.Task) -> None:
            current = self._scenario_tasks.get(market_id)
            if current is done_task:
                self._scenario_tasks.pop(market_id, None)

        task.add_done_callback(_cleanup)

    def _load_settings(self):
        """Load settings from database or use defaults."""
        self.settings = {}
        for key, default_value in DEFAULT_SETTINGS.items():
            value = alerts_storage.get_setting(key, default_value)
            self.settings[key] = value

    def _save_setting(self, key: str, value: Any):
        """Save a setting to database."""
        alerts_storage.save_setting(key, str(value))
        self.settings[key] = str(value)

    def is_enabled(self) -> bool:
        """Check if insider alerts are globally enabled."""
        return self.settings.get('enabled', 'false').lower() == 'true'

    def get_channel_id(self) -> Optional[str]:
        """Get configured Telegram channel ID (env INSIDER_ALERTS_CHANNEL_ID or DB)."""
        channel_id = os.environ.get('INSIDER_ALERTS_CHANNEL_ID') or self.settings.get('channel_id', '')
        return channel_id.strip() if channel_id else None

    def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """
        Process incoming trade and store if relevant for analysis.
        """
        try:
            # Extract relevant data
            market_id = trade_data.get('market_id') or trade_data.get('conditionId')
            if not market_id:
                logger.debug("Trade missing market_id, skipping insider storage")
                return

            wallet = trade_data.get('proxyWallet') or trade_data.get('maker')
            if not wallet:
                return

            value_usd = trade_data.get('value_usd', 0)
            if value_usd < 500:  # Minimum threshold for any scenario
                return

            # Category detection (align with main bot)
            market_title = trade_data.get('title') or trade_data.get('marketTitle', '') or ''
            slug = trade_data.get('slug') or trade_data.get('marketSlug') or ''
            event_slug = trade_data.get('eventSlug') or trade_data.get('event_slug') or slug
            market_url = (
                trade_data.get('market_url')
                or trade_data.get('marketUrl')
                or (f"https://polymarket.com/event/{event_slug}" if event_slug else "")
                or ''
            )
            
            # Use robust detection from core/categories.py (use slug+event_slug for coverage)
            category = detect_category(market_title, f"{slug} {event_slug}", market_url)

            # Check category filter - skip if category is disabled
            cat_key = f"cat_{category}_enabled"
            if self.settings.get(cat_key, 'true').lower() != 'true':
                logger.debug(f"Skipping trade: category '{category}' is disabled")
                return

            # Check Probability Filter (Global Insider)
            try:
                price = None
                # Price is usually passed as 'price' (0.0-1.0) or 'outcome_prob' etc.
                # In Polymarket data api it's often 'price' or 'order_price'
                # Let's check available fields
                if 'price' in trade_data:
                    price = float(trade_data['price'])
                elif 'outcome_price' in trade_data:
                    price = float(trade_data['outcome_price'])
                
                if price is not None:
                     # Convert to percentage 0-100 for comparison
                    prob_pct = price * 100
                    min_p = float(self.settings.get('probability_min', '0'))
                    max_p = float(self.settings.get('probability_max', '100'))
                    
                    if not (min_p <= prob_pct <= max_p):
                        # Skip strictly if outside range
                        # logger.debug(f"Skipping trade: prob {prob_pct:.1f}% outside {min_p}-{max_p}%")
                        return
            except Exception as e:
                logger.debug(f"Error checking probability: {e}")

            # Calculate wallet age in hours
            wallet_age_hours = None
            first_activity_ts = trade_data.get('first_activity_ts')
            if first_activity_ts:
                import asyncio
                if asyncio.iscoroutine(first_activity_ts) or asyncio.isfuture(first_activity_ts):
                    logger.error("first_activity_ts is a coroutine/future! Trade processing concurrency issue. Skipping age check.")
                    wallet_age_hours = None
                else:
                    try:
                        age_seconds = time.time() - float(first_activity_ts)
                        wallet_age_hours = age_seconds / 3600
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid first_activity_ts: {first_activity_ts} ({e})")
                        wallet_age_hours = None

            # Determine trade action
            side = trade_data.get('side', '').upper()
            trade_type = trade_data.get('type', '').upper()

            if side == 'SPLIT' or trade_type == 'SPLIT':
                trade_action = 'split'
            elif side == 'MERGE' or trade_type == 'MERGE':
                trade_action = 'merge'
            elif side == 'REDEEM' or trade_type == 'REDEEM':
                trade_action = 'redeem'
            elif side == 'BUY':
                trade_action = 'buy'
            elif side == 'SELL':
                trade_action = 'sell'
            else:
                trade_action = 'unknown'

            # Only process BUY trades
            if trade_action != 'buy':
                return

            # Skip trades without verified wallet age (PolygonScan unavailable)
            # These would produce unreliable insider patterns
            if wallet_age_hours is None:
                logger.debug(f"Skipping trade: wallet age not verified (PolygonScan unavailable)")
                return

            # Store trade for analysis
            alerts_storage.store_trade({
                'market_id': market_id,
                'wallet': wallet,
                'wallet_age_hours': wallet_age_hours,
                'outcome': trade_data.get('outcome', ''),
                'trade_size_usd': value_usd,
                'trade_action': trade_action,
                'timestamp': int(time.time()),
                'username': trade_data.get('name') or trade_data.get('pseudonym'),
                'market_title': trade_data.get('title', ''),
                'event_slug': trade_data.get('eventSlug', ''),
                'category': category,
                'open_positions': trade_data.get('open_positions', 0),
                'price': price
            })


            logger.debug(f"Stored trade for insider alerts: market={market_id[:20]}..., ${value_usd:,.0f}")

            # Only check scenarios if enabled
            if self.is_enabled():
                # Schedule debounced async check to avoid repeated checks during bursts.
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        self._schedule_scenario_check_debounced(market_id, category)
                    else:
                        loop.run_until_complete(self.check_scenarios(market_id, category))
                except RuntimeError:
                    # No event loop, create new one
                    asyncio.run(self.check_scenarios(market_id, category))

        except Exception as e:
            logger.error(f"Error processing trade for insider alerts: {e}", exc_info=True)

    async def check_all_markets(self) -> None:
        """Check all active markets for insider patterns (called periodically)."""
        if not self.is_enabled():
            return

        try:
            # Get markets with activity in last 24 hours
            markets = alerts_storage.get_all_active_markets(hours_back=24)

            logger.debug(f"Checking {len(markets)} active markets for insider patterns")
            
            # Reset active clusters/patterns tracking for this scan cycle
            self._active_clusters = {}
            self._active_accumulations = {}
            self._active_bursts = {}

            for market_data in markets:
                # Extract market_id and category from the new return format
                market_id = market_data['market_id']
                category = market_data.get('category', 'other')
                
                # Pass the actual category to check_scenarios for proper filtering
                await self.check_scenarios(market_id, category)

            # Cleanup old data
            alerts_storage.cleanup_old_trades(ttl_hours=72)
            alerts_storage.cleanup_old_published(days=7)

        except Exception as e:
            logger.error(f"Error checking markets for insider patterns: {e}", exc_info=True)

    async def check_scenarios(self, market_id: str, category: str = 'other') -> None:
        """
        Check all enabled scenarios for a specific market.
        Now async to support position verification before scenario checks.
        """
        if not self.is_enabled():
            return
            
        # Check Category Filter
        # If category is 'other' (default from check_all_markets), we might be lenient or strict.
        # User usually wants to block 'sports' not 'other'.
        # Let's check the specific category flag.
        cat_key = f"cat_{category}_enabled"
        # If key doesn't exist (e.g. unknown category), default to true
        if self.settings.get(cat_key, 'true').lower() != 'true':
            return

        # NEW STEP: Check for appending to existing alerts (updates website without new Telegram message)
        await self._check_and_append_to_existing_alerts(market_id)

        # Pre-filter: Remove trades from wallets that no longer qualify (too many positions)
        # This keeps the buffer clean and allows new qualifying trades to accumulate
        await self._cleanup_invalid_trades(market_id)

        # Check CLUSTER
        if self.settings.get('cluster_enabled', 'false').lower() == 'true':
            alert_data = self._check_cluster(market_id)
            if alert_data:
                self._publish_alert('CLUSTER', alert_data)

        # Check ACCUMULATION
        if self.settings.get('accumulation_enabled', 'false').lower() == 'true':
            alert_data = self._check_accumulation(market_id)
            if alert_data:
                self._publish_alert('ACCUMULATION', alert_data)

        # Check BURST
        if self.settings.get('burst_enabled', 'false').lower() == 'true':
            alert_data = self._check_burst(market_id)
            if alert_data:
                self._publish_alert('BURST', alert_data)

    async def _check_and_append_to_existing_alerts(self, market_id: str) -> None:
        """
        Check if there are new unconsumed trades for a market that already has an active
        published alert (on website). If so, fetch them, filter by scenario settings, 
        append to the website DB, and mark as consumed.
        """
        cooldown_hours = int(self.settings.get('cooldown_hours', '24'))
        
        # Scenarios we support appending to:
        supported_scenarios = ['CLUSTER', 'BURST', 'ACCUMULATION']
        
        for scenario in supported_scenarios:
            for outcome in ['YES', 'NO']:
                if alerts_storage.was_published(scenario, market_id, outcome, cooldown_hours):
                    # We have an active published alert for this market/outcome combination.
                    # Let's see if there are new unconsumed trades we can append.
                    
                    if scenario == 'CLUSTER':
                        if self.settings.get('cluster_enabled', 'false').lower() != 'true': continue
                        interval = float(self.settings.get('cluster_interval_hours', '2'))
                        max_age = float(self.settings.get('cluster_wallet_age_hours', '24'))
                        min_usd = float(self.settings.get('cluster_min_usd', '5000'))
                        max_pos = int(self.settings.get('cluster_max_positions', '3'))
                    elif scenario == 'BURST':
                        if self.settings.get('burst_enabled', 'false').lower() != 'true': continue
                        interval = float(self.settings.get('burst_interval_hours', '1'))
                        max_age = float(self.settings.get('burst_wallet_age_hours', '72'))
                        min_usd = float(self.settings.get('burst_min_usd', '1000'))
                        max_pos = int(self.settings.get('burst_max_positions', '3'))
                    elif scenario == 'ACCUMULATION':
                        if self.settings.get('accumulation_enabled', 'false').lower() != 'true': continue
                        interval_days = float(self.settings.get('accumulation_interval_days', '14'))
                        interval = max(1.0, interval_days) * 24
                        max_age = float(self.settings.get('accumulation_wallet_age_hours', '48'))
                        min_usd = float(self.settings.get('accumulation_min_usd', '10000'))
                        max_pos = int(self.settings.get('accumulation_max_positions', '3'))
                    else:
                        continue

                    new_trades = alerts_storage.get_trades_window(
                        market_id=market_id,
                        window_hours=interval,
                        max_wallet_age_hours=max_age
                    )

                    if not new_trades:
                        continue

                    # Filter for trades matching size and positions criteria (any outcome direction)
                    valid_trades = []
                    new_wallets_set = set()
                    additional_volume = 0.0
                    wallet_outcomes = {}  # wallet -> outcome (YES/NO)

                    for t in new_trades:
                        if t.get('trade_size_usd', 0) >= min_usd:
                            if (t.get('open_positions') or 0) <= max_pos:
                                valid_trades.append(t)
                                wallet = t.get('wallet')
                                if wallet:
                                    new_wallets_set.add(wallet)
                                    wallet_outcomes[wallet] = t.get('outcome', '').upper()
                                additional_volume += t.get('trade_size_usd', 0)

                    if not valid_trades:
                        continue

                    # Optionally verify positions against polymarket to ensure they still hold them
                    if self._poly_service:
                        verified_trades = []
                        wallets_to_keep = set()
                        for wallet in new_wallets_set:
                            try:
                                position_value = await self._poly_service.check_wallet_has_position(wallet, market_id)
                                if position_value >= min_usd:
                                    wallets_to_keep.add(wallet)
                            except Exception as e:
                                logger.debug(f"Append validation error for {wallet}: {e}")
                                # Assume no if error
                        
                        valid_trades = [t for t in valid_trades if t.get('wallet') in wallets_to_keep]
                        new_wallets_set = wallets_to_keep
                        additional_volume = sum(t.get('trade_size_usd', 0) for t in valid_trades)
                        # Keep only verified wallet outcomes
                        wallet_outcomes = {w: o for w, o in wallet_outcomes.items() if w in wallets_to_keep}

                    if valid_trades:
                        success = alerts_storage.append_to_published_alert(
                            scenario=scenario,
                            market_id=market_id,
                            outcome=outcome,
                            new_wallets=list(new_wallets_set),
                            additional_volume=additional_volume,
                            wallet_outcomes=wallet_outcomes
                        )

                        if success:
                            trade_ids = [t['id'] for t in valid_trades if t.get('id')]
                            alerts_storage.mark_trades_consumed(trade_ids, 'APPENDED')
                            logger.info(f"Appended {len(trade_ids)} new trades ({len(new_wallets_set)} wallets) to active {scenario} alert for {market_id}")

    def _check_cluster(self, market_id: str) -> Optional[Dict[str, Any]]:
        try:
            interval = float(self.settings.get('cluster_interval_hours', '2'))
            max_age = float(self.settings.get('cluster_wallet_age_hours', '24'))
            min_usd = float(self.settings.get('cluster_min_usd', '5000'))
            min_total = float(self.settings.get('cluster_min_total_usd', '10000'))
            min_wallets = int(self.settings.get('cluster_min_wallets', '4'))
            min_dir = float(self.settings.get('cluster_min_direction_pct', '75'))
            max_pos = int(self.settings.get('cluster_max_positions', '3'))
            side_filter = self.settings.get('cluster_side', 'both').lower()

            trades = alerts_storage.get_trades_window(
                market_id=market_id,
                window_hours=interval,
                max_wallet_age_hours=max_age
            )

            if not trades:
                return None

            # DOUBLE CHECK CATEGORY (Fix for dashboard leak)
            # Re-detect category from the actual trades to ensure we filter out disabled categories
            if trades:
                sample = trades[0]
                detected_cat = detect_category(
                    sample.get('market_title', ''), 
                    sample.get('event_slug', ''), 
                    "" # URL not stored in raw trade, but slug/title is usually enough
                )
                
                cat_key = f"cat_{detected_cat}_enabled"
                if self.settings.get(cat_key, 'true').lower() != 'true':
                    # logger.debug(f"Skipping CLUSTER: re-detected category '{detected_cat}' is disabled")
                    return None

            # Filter by side
            if side_filter != 'both':
                filtered = []
                for t in trades:
                    act = (t['trade_action'] or '').lower()
                    if side_filter == 'buy' and act in ['buy', 'split']:
                        filtered.append(t)
                    elif side_filter == 'sell' and act in ['sell', 'merge', 'redeem']:
                        filtered.append(t)
                trades = filtered
            
            if not trades:
                return None

            # Filter by min individual trade size for calculation
            trades = [t for t in trades if t['trade_size_usd'] >= min_usd]
            if not trades:
                return None
            
            # Filter by max positions (fresh wallets have few positions)
            trades = [t for t in trades if (t.get('open_positions') or 0) <= max_pos]
            if not trades:
                return None

            unique_wallets = set(t['wallet'] for t in trades)
            total_volume = sum(t['trade_size_usd'] for t in trades)
            dominant_outcome, directionality = self._calculate_directionality(trades)

            # Store as pending/active pattern - any wallet passing basic filters goes to buffer
            # Buffer accumulates wallets over time
            if trades:
                self._active_clusters[market_id] = {
                    'market_id': market_id,
                    'event_slug': trades[0].get('event_slug', ''),
                    'wallets': len(unique_wallets),
                    'wallet_list': list(unique_wallets),
                    'volume': total_volume,
                    'last_ts': max(t['timestamp'] for t in trades) if trades else 0,
                    'title': trades[0].get('market_title', 'Unknown'),
                    'min_wallets': min_wallets,
                    'min_total': min_total,
                    'outcome': dominant_outcome,
                    'directionality': directionality,
                }

            # Check publication conditions
            if len(unique_wallets) < min_wallets:
                self._set_blocked_reason(
                    self._active_clusters,
                    market_id,
                    code="MIN_WALLETS",
                    reason=f"wallets {len(unique_wallets)}/{min_wallets}",
                )
                return None
            
            if total_volume < min_total:
                self._set_blocked_reason(
                    self._active_clusters,
                    market_id,
                    code="MIN_TOTAL",
                    reason=f"volume ${total_volume:,.0f} < ${min_total:,.0f}",
                )
                return None

            if directionality < min_dir:
                self._set_blocked_reason(
                    self._active_clusters,
                    market_id,
                    code="DIRECTIONALITY_TOO_LOW",
                    reason=f"direction {directionality:.1f}% < {min_dir:.1f}%",
                )
                return None

            # Filter trades to only dominant outcome direction
            dominant_trades = [t for t in trades if (t.get('outcome', '').upper()) == dominant_outcome.upper()]
            dominant_wallets = set(t['wallet'] for t in dominant_trades)
            dominant_volume = sum(t['trade_size_usd'] for t in dominant_trades)

            # Check min_wallets on dominant-direction wallets only
            if len(dominant_wallets) < min_wallets:
                self._set_blocked_reason(
                    self._active_clusters,
                    market_id,
                    code="MIN_WALLETS_DOMINANT",
                    reason=f"dominant wallets {len(dominant_wallets)}/{min_wallets}",
                )
                return None

            # Check if already published recently
            cooldown = int(self.settings.get('cooldown_hours', '24'))
            if alerts_storage.was_published('CLUSTER', market_id, dominant_outcome, cooldown):
                self._set_blocked_reason(
                    self._active_clusters,
                    market_id,
                    code="COOLDOWN_ACTIVE",
                    reason=f"cooldown {cooldown}h active",
                )
                return None

            self._clear_blocked_reason(self._active_clusters, market_id)
            return {
                'market_id': market_id,
                'outcome': dominant_outcome,
                'window_hours': interval,
                'wallet_count': len(dominant_wallets),
                'total_volume': dominant_volume,
                'directionality': directionality,
                'trades': dominant_trades,
                'max_wallet_age_hours': max_age,
                'include_profiles': self.settings.get('cluster_include_profiles', 'true')
            }

        except Exception as e:
            logger.error(f"Error in CLUSTER check for {market_id}: {e}", exc_info=True)
            return None

    def _check_accumulation(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Check for slow multi-wallet accumulation pattern."""
        try:
            interval_days = float(self.settings.get('accumulation_interval_days', '14'))
            min_usd = float(self.settings.get('accumulation_min_usd', '10000'))
            min_total = float(self.settings.get('accumulation_min_total_usd', '50000'))
            min_wallets = int(self.settings.get('accumulation_min_wallets', '3'))
            max_age = float(self.settings.get('accumulation_wallet_age_hours', '48'))
            min_dir = float(self.settings.get('accumulation_min_direction_pct', '70'))
            max_pos = int(self.settings.get('accumulation_max_positions', '3'))

            # Use configurable accumulation interval.
            window_hours = max(1.0, interval_days) * 24
            trades = alerts_storage.get_trades_window(market_id, window_hours, max_age)

            if not trades:
                return None

            # DOUBLE CHECK CATEGORY (Fix for dashboard leak)
            if trades:
                sample = trades[0]
                detected_cat = detect_category(
                    sample.get('market_title', ''), 
                    sample.get('event_slug', ''), 
                    "" 
                )
                
                cat_key = f"cat_{detected_cat}_enabled"
                if self.settings.get(cat_key, 'true').lower() != 'true':
                    return None

            large_trades = [t for t in trades if t['trade_size_usd'] >= min_usd]
            if not large_trades:
                return None
            
            # Filter by max positions (fresh wallets have few positions)
            large_trades = [t for t in large_trades if (t.get('open_positions') or 0) <= max_pos]
            if not large_trades:
                return None

            # Calculate unique wallets and total volume
            unique_wallets = set(t['wallet'] for t in large_trades)
            total_volume = sum(t['trade_size_usd'] for t in large_trades)
            dominant_outcome, directionality = self._calculate_directionality(large_trades)

            days_with_activity = set()
            for trade in large_trades:
                trade_date = datetime.fromtimestamp(trade['timestamp']).date()
                days_with_activity.add(trade_date)

            # Store pending data for dashboard - any wallet passing basic filters goes to buffer
            # Buffer accumulates wallets over time
            if large_trades:
                self._active_accumulations[market_id] = {
                    'market_id': market_id,
                    'event_slug': large_trades[0].get('event_slug', ''),
                    'wallets': len(unique_wallets),
                    'wallet_list': list(unique_wallets),
                    'volume': total_volume,
                    'last_ts': max(t['timestamp'] for t in large_trades) if large_trades else 0,
                    'title': large_trades[0].get('market_title', 'Unknown'),
                    'days': len(days_with_activity),
                    'min_wallets': min_wallets,
                    'min_total': min_total,
                    'outcome': dominant_outcome,
                    'directionality': directionality,
                }

            # Check publication conditions
            if len(unique_wallets) < min_wallets:
                self._set_blocked_reason(
                    self._active_accumulations,
                    market_id,
                    code="MIN_WALLETS",
                    reason=f"wallets {len(unique_wallets)}/{min_wallets}",
                )
                return None

            if total_volume < min_total:
                self._set_blocked_reason(
                    self._active_accumulations,
                    market_id,
                    code="MIN_TOTAL",
                    reason=f"volume ${total_volume:,.0f} < ${min_total:,.0f}",
                )
                return None

            if directionality < min_dir:
                self._set_blocked_reason(
                    self._active_accumulations,
                    market_id,
                    code="DIRECTIONALITY_TOO_LOW",
                    reason=f"direction {directionality:.1f}% < {min_dir:.1f}%",
                )
                return None

            # Filter trades to only dominant outcome direction
            dominant_trades = [t for t in large_trades if (t.get('outcome', '').upper()) == dominant_outcome.upper()]
            dominant_wallets = set(t['wallet'] for t in dominant_trades)
            dominant_volume = sum(t['trade_size_usd'] for t in dominant_trades)

            # Recalculate days with activity for dominant trades only
            dominant_days = set()
            for trade in dominant_trades:
                trade_date = datetime.fromtimestamp(trade['timestamp']).date()
                dominant_days.add(trade_date)

            # Check min_wallets on dominant-direction wallets only
            if len(dominant_wallets) < min_wallets:
                self._set_blocked_reason(
                    self._active_accumulations,
                    market_id,
                    code="MIN_WALLETS_DOMINANT",
                    reason=f"dominant wallets {len(dominant_wallets)}/{min_wallets}",
                )
                return None

            cooldown = int(self.settings.get('cooldown_hours', '24'))
            if alerts_storage.was_published('ACCUMULATION', market_id, dominant_outcome, cooldown):
                self._set_blocked_reason(
                    self._active_accumulations,
                    market_id,
                    code="COOLDOWN_ACTIVE",
                    reason=f"cooldown {cooldown}h active",
                )
                return None

            self._clear_blocked_reason(self._active_accumulations, market_id)
            return {
                'market_id': market_id,
                'outcome': dominant_outcome,
                'days_count': len(dominant_days),
                'wallet_count': len(dominant_wallets),
                'total_volume': dominant_volume,
                'directionality': directionality,
                'trades': dominant_trades,
                'trade_count': len(dominant_trades),
                'include_profiles': self.settings.get('accumulation_include_profiles', 'true')
            }

        except Exception as e:
            logger.error(f"Error in ACCUMULATION check for {market_id}: {e}", exc_info=True)
            return None

    def _check_burst(self, market_id: str) -> Optional[Dict[str, Any]]:
        try:
            interval = float(self.settings.get('burst_interval_hours', '1'))
            max_age = float(self.settings.get('burst_wallet_age_hours', '72'))
            min_usd = float(self.settings.get('burst_min_usd', '1000'))
            min_total = float(self.settings.get('burst_min_total_usd', '5000'))
            min_wallets = int(self.settings.get('burst_min_wallets', '8'))
            min_dir = float(self.settings.get('burst_min_direction_pct', '70'))
            max_pos = int(self.settings.get('burst_max_positions', '3'))

            trades = alerts_storage.get_trades_window(
                market_id=market_id,
                window_hours=interval,
                max_wallet_age_hours=max_age
            )

            if not trades:
                return None

            # DOUBLE CHECK CATEGORY (Fix for dashboard leak)
            if trades:
                sample = trades[0]
                detected_cat = detect_category(
                    sample.get('market_title', ''), 
                    sample.get('event_slug', ''), 
                    "" 
                )
                
                cat_key = f"cat_{detected_cat}_enabled"
                if self.settings.get(cat_key, 'true').lower() != 'true':
                    return None

            qualifying_trades = [t for t in trades if t['trade_size_usd'] >= min_usd]
            if not qualifying_trades:
                return None
            
            # Filter by max positions (fresh wallets have few positions)
            qualifying_trades = [t for t in qualifying_trades if (t.get('open_positions') or 0) <= max_pos]
            if not qualifying_trades:
                return None

            unique_wallets = set(t['wallet'] for t in qualifying_trades)
            total_volume = sum(t['trade_size_usd'] for t in qualifying_trades)
            dominant_outcome, directionality = self._calculate_directionality(qualifying_trades)

            # Store as pending/active pattern - any wallet passing basic filters goes to buffer
            # Buffer accumulates wallets over time
            if qualifying_trades:
                self._active_bursts[market_id] = {
                    'market_id': market_id,
                    'event_slug': qualifying_trades[0].get('event_slug', ''),
                    'wallets': len(unique_wallets),
                    'wallet_list': list(unique_wallets),
                    'volume': total_volume,
                    'last_ts': max(t['timestamp'] for t in qualifying_trades) if qualifying_trades else 0,
                    'title': qualifying_trades[0].get('market_title', 'Unknown'),
                    'min_wallets': min_wallets,
                    'min_total': min_total,
                    'outcome': dominant_outcome,
                    'directionality': directionality,
                }

            # Check publication conditions
            if len(unique_wallets) < min_wallets:
                self._set_blocked_reason(
                    self._active_bursts,
                    market_id,
                    code="MIN_WALLETS",
                    reason=f"wallets {len(unique_wallets)}/{min_wallets}",
                )
                return None
            
            if total_volume < min_total:
                self._set_blocked_reason(
                    self._active_bursts,
                    market_id,
                    code="MIN_TOTAL",
                    reason=f"volume ${total_volume:,.0f} < ${min_total:,.0f}",
                )
                return None

            if directionality < min_dir:
                self._set_blocked_reason(
                    self._active_bursts,
                    market_id,
                    code="DIRECTIONALITY_TOO_LOW",
                    reason=f"direction {directionality:.1f}% < {min_dir:.1f}%",
                )
                return None

            # Filter trades to only dominant outcome direction
            dominant_trades = [t for t in qualifying_trades if (t.get('outcome', '').upper()) == dominant_outcome.upper()]
            dominant_wallets = set(t['wallet'] for t in dominant_trades)
            dominant_volume = sum(t['trade_size_usd'] for t in dominant_trades)

            # Check min_wallets on dominant-direction wallets only
            if len(dominant_wallets) < min_wallets:
                self._set_blocked_reason(
                    self._active_bursts,
                    market_id,
                    code="MIN_WALLETS_DOMINANT",
                    reason=f"dominant wallets {len(dominant_wallets)}/{min_wallets}",
                )
                return None

            cooldown = int(self.settings.get('cooldown_hours', '24'))
            if alerts_storage.was_published('BURST', market_id, dominant_outcome, cooldown):
                self._set_blocked_reason(
                    self._active_bursts,
                    market_id,
                    code="COOLDOWN_ACTIVE",
                    reason=f"cooldown {cooldown}h active",
                )
                return None

            self._clear_blocked_reason(self._active_bursts, market_id)
            return {
                'market_id': market_id,
                'outcome': dominant_outcome,
                'window_hours': interval,
                'wallet_count': len(dominant_wallets),
                'total_volume': dominant_volume,
                'directionality': directionality,
                'trades': dominant_trades,
                'include_profiles': self.settings.get('burst_include_profiles', 'true')
            }

        except Exception as e:
            logger.error(f"Error in BURST check for {market_id}: {e}", exc_info=True)
            return None

    def _calculate_directionality(self, trades: List[Dict]) -> Tuple[str, float]:
        if not trades:
            return ("UNKNOWN", 0.0)

        outcome_volumes = defaultdict(float)
        total_volume = 0.0

        for trade in trades:
            outcome = trade.get('outcome', 'UNKNOWN').upper()
            if not outcome:
                outcome = 'UNKNOWN'

            volume = trade.get('trade_size_usd', 0)
            outcome_volumes[outcome] += volume
            total_volume += volume

        if total_volume == 0:
            return ("UNKNOWN", 0.0)

        dominant_outcome = max(outcome_volumes.items(), key=lambda x: x[1])
        directionality = (dominant_outcome[1] / total_volume) * 100

        return (dominant_outcome[0], directionality)

    def _format_alert_message(self, scenario: str, alert_data: Dict[str, Any], shared_wallets: set = None) -> str:
        market_id = alert_data.get('market_id') or ''
        outcome = alert_data.get('outcome', 'UNKNOWN')
        directionality = alert_data.get('directionality', 0)
        total_volume = alert_data.get('total_volume', 0)
        trades = alert_data.get('trades', [])
        include_profiles = alert_data.get('include_profiles', 'true').lower() == 'true'

        market_title = trades[0].get('market_title', 'Unknown Market') if trades else 'Unknown Market'
        event_slug = trades[0].get('event_slug', '') if trades else ''
        
        # Build market URL - prefer event_slug, fallback to market_id
        if event_slug:
            market_url = f"https://polymarket.com/event/{event_slug}"
        elif market_id:
            market_url = f"https://polymarket.com/event/{market_id}"
        else:
            market_url = ""

        details = ""
        if scenario == 'CLUSTER':
            win = alert_data.get('window_hours', 0)
            cnt = alert_data.get('wallet_count', 0)
            details = f"Window: {win:.0f}h\nFresh Wallets: {cnt}"
        
        elif scenario == 'ACCUMULATION':
            days = alert_data.get('days_count', 0)
            wallets = alert_data.get('wallet_count', 0)
            cnt = alert_data.get('trade_count', 0)
            details = f"Days Active: {days}\nUnique Wallets: {wallets}\nLarge Trades: {cnt}"
        
        elif scenario == 'BURST':
            win = alert_data.get('window_hours', 0)
            cnt = alert_data.get('wallet_count', 0)
            details = f"Window: {win:.1f}h\nUnique Wallets: {cnt}"
        
        else:
            details = "Custom Pattern"

        msg = (
            f"🚨 *Potential Insider ({scenario})*\n\n"
            f"Market: [{market_title[:80]}]({market_url})\n"
            f"Outcome: *{outcome}*\n\n"
            f"{details}\n"
            f"Volume: *${total_volume:,.0f}* ({directionality:.0f}% {outcome})\n"
        )
        
        # Add shared funding warning if detected
        if shared_wallets:
            msg += "⚠️ Shared funding detected"
            # Add link(s) to funding source(s) if available
            shared_sources = alert_data.get('shared_sources', [])
            if shared_sources:
                source_links = []
                for source in shared_sources:
                    # Format address: first 10 chars + last 4 chars
                    source_display = f"{source[:10]}...{source[-4:]}" if len(source) > 14 else source
                    source_url = f"https://polygonscan.com/address/{source}"
                    source_links.append(f"[{source_display}]({source_url})")
                
                if len(source_links) == 1:
                    msg += f"\nSource: {source_links[0]}"
                else:
                    msg += f"\nSources:\n"
                    for link in source_links:
                        msg += f"• {link}\n"
            else:
                msg += "\n"

        if include_profiles:
            msg += "\nParticipants:\n"
            wallet_data = {}
            for t in trades:
                w = t.get('wallet')
                if not w: continue
                if w not in wallet_data:
                    # Get display name - shorten if it's a wallet address
                    raw_name = t.get('username') or w
                    if raw_name.startswith('0x') and len(raw_name) > 20:
                        display_name = f"{raw_name[:5]}...{raw_name[-4:]}"
                    else:
                        display_name = raw_name
                    
                    wallet_data[w] = {
                        'volume': 0,
                        'total_cost': 0,
                        'volume_for_price': 0,
                        'name': display_name,
                        'open_positions': t.get('open_positions'),
                        'wallet_age_hours': t.get('wallet_age_hours')
                    }
                wallet_data[w]['volume'] += t.get('trade_size_usd', 0)
                
                # Calculate weighted average entry price for the dominant outcome
                t_outcome = t.get('outcome', '').upper()
                if t_outcome == outcome.upper():
                    p = t.get('price')
                    if p is not None:
                        vol = t.get('trade_size_usd', 0)
                        wallet_data[w]['total_cost'] += vol * p
                        wallet_data[w]['volume_for_price'] += vol
            
            # Sort by volume (show all participants)
            sorted_w = sorted(wallet_data.items(), key=lambda x: x[1]['volume'], reverse=True)
            
            for w, data in sorted_w:
                n = data['name']
                v = data['volume']
                
                # Format wallet age
                age_str = ""
                if data['wallet_age_hours'] is not None:
                    hours = data['wallet_age_hours']
                    if hours < 24:
                        age_str = f"{hours:.0f}h"
                    else:
                        days = hours / 24
                        if days < 30:
                            age_str = f"{days:.0f}d"
                        else:
                            months = days / 30
                            age_str = f"{months:.1f}mo"
                
                # Format positions
                pos_str = ""
                if data['open_positions'] is not None:
                    pos_str = f"{data['open_positions']} pos"
                
                # Build info string
                
                # Calculate average price
                price_str = ""
                if data['volume_for_price'] > 0:
                    avg_price = (data['total_cost'] / data['volume_for_price']) * 100
                    price_str = f"({outcome} {avg_price:.0f}%)"
                
                info_parts = [f"*${v:,.0f}{price_str}*"]
                if age_str:
                    info_parts.append(age_str)
                if pos_str:
                    info_parts.append(pos_str)
                info = " | ".join(info_parts)
                
                # Mark wallets with shared funding
                shared_marker = "⚠️ " if shared_wallets and w.lower() in {sw.lower() for sw in shared_wallets} else ""
                msg += f"• {shared_marker}[{n}](https://polymarket.com/profile/{w}) {info}\n"


        # Removed market ID display

        return msg

    def _publish_alert(self, scenario: str, alert_data: Dict[str, Any]) -> None:
        try:
            channel_id = self.get_channel_id()
            if not channel_id:
                logger.warning(f"Cannot publish {scenario} alert: no channel_id configured")
                buffer_dict = self._get_buffer_dict_for_scenario(scenario)
                if buffer_dict is not None:
                    self._set_blocked_reason(
                        buffer_dict,
                        alert_data.get("market_id", ""),
                        code="NO_CHANNEL_ID",
                        reason="no channel_id configured",
                    )
                return

            if not self._bot:
                logger.warning(f"Cannot publish {scenario} alert: bot not set")
                buffer_dict = self._get_buffer_dict_for_scenario(scenario)
                if buffer_dict is not None:
                    self._set_blocked_reason(
                        buffer_dict,
                        alert_data.get("market_id", ""),
                        code="BOT_NOT_SET",
                        reason="bot not set",
                    )
                return

            import asyncio
            
            # Verify positions before sending (async wrapper)
            async def verify_and_send():
                buffer_dict = self._get_buffer_dict_for_scenario(scenario)
                market_id = alert_data.get("market_id", "")
                try:
                    # Filter out wallets that already sold
                    verified_data = await self._verify_positions(alert_data, scenario)
                    
                    if verified_data is None:
                        logger.info(f"Skipping {scenario} alert: not enough wallets still holding positions")
                        if buffer_dict is not None:
                            self._set_blocked_reason(
                                buffer_dict,
                                market_id,
                                code="NOT_ENOUGH_HOLDING",
                                reason="not enough wallets still holding positions",
                            )
                        return
                    
                    # Extract wallet list from verified trades (needed for atomic check)
                    wallet_list = list(set(
                        t.get('wallet') for t in verified_data.get('trades', []) 
                        if t.get('wallet')
                    ))
                    
                    # Calculate average entry price
                    entry_price = 0.0
                    try:
                        total_cost = 0.0
                        total_vol_for_price = 0.0
                        target_outcome = alert_data.get('outcome', '').upper()
                        for t in verified_data.get('trades', []):
                            if t.get('outcome', '').upper() == target_outcome and t.get('price') is not None:
                                vol = t.get('trade_size_usd', 0)
                                total_cost += vol * t.get('price')
                                total_vol_for_price += vol
                        
                        if total_vol_for_price > 0:
                            entry_price = total_cost / total_vol_for_price
                    except Exception as e:
                        logger.error(f"Error calculating entry price for alert: {e}")

                    # CRITICAL: Atomically check and mark as published BEFORE sending
                    # This prevents duplicate sends when multiple check_scenarios calls happen concurrently
                    cooldown = int(self.settings.get('cooldown_hours', '24'))
                    market_title = alert_data.get('trade_title') or verified_data.get('trades', [{}])[0].get('market_title', '')
                    event_slug = verified_data.get('trades', [{}])[0].get('event_slug', '') or alert_data.get('event_slug', '')
                    
                    was_marked = alerts_storage.try_mark_published_atomic(
                        scenario=scenario,
                        market_id=alert_data['market_id'],
                        outcome=alert_data.get('outcome', ''),
                        cooldown_hours=cooldown,
                        market_title=market_title,
                        total_volume=alert_data.get('total_volume', 0),
                        participants_count=len(verified_data.get('trades', [])),
                        wallet_list=wallet_list,
                        event_slug=event_slug,
                        directionality=alert_data.get('directionality', 0),
                        entry_price=entry_price
                    )
                    
                    if not was_marked:
                        # Another process/thread already published this alert (race condition prevented)
                        logger.info(f"Skipping {scenario} alert: already published by another process (race condition prevented)")
                        if buffer_dict is not None:
                            self._set_blocked_reason(
                                buffer_dict,
                                market_id,
                                code="ALREADY_PUBLISHED",
                                reason="already published (race condition prevented)",
                            )
                        return

                    # Website-only: record a historical published event (does NOT affect Telegram).
                    # This preserves multiple signals per market/outcome/scenario on the site.
                    try:
                        alerts_storage.create_published_event(
                            scenario=scenario,
                            market_id=alert_data['market_id'],
                            outcome=alert_data.get('outcome', ''),
                            published_at=int(time.time()),
                            market_title=market_title,
                            event_slug=event_slug,
                            directionality=alert_data.get('directionality', 0),
                            entry_price=entry_price,
                            total_volume=alert_data.get('total_volume', 0),
                            participants_count=len(verified_data.get('trades', [])),
                            original_wallets=wallet_list,
                        )
                    except Exception as e:
                        logger.error(f"Failed to create website published event: {e}")
                    
                    # Analyze shared funding sources (enrichment only, not filtering)
                    shared_wallets = set()
                    shared_sources = []
                    try:
                        from services.shared_funding import analyze_shared_funding
                        
                        if wallet_list:
                            funding_result = await analyze_shared_funding(scenario, wallet_list)
                            shared_wallets = funding_result.get('shared_wallets', set())
                            shared_sources = funding_result.get('shared_sources', [])
                            
                            if funding_result.get('has_shared'):
                                logger.info(f"Shared funding detected in {scenario}: {len(shared_wallets)} wallets from {len(shared_sources)} source(s)")
                    except Exception as e:
                        logger.debug(f"Shared funding check skipped: {e}")
                    
                    # Add shared_sources to verified_data so _format_alert_message can access it
                    verified_data['shared_sources'] = shared_sources
                    
                    message = self._format_alert_message(scenario, verified_data, shared_wallets=shared_wallets)
                    
                    await self._bot.send_message(
                        chat_id=channel_id,
                        text=add_polymarket_ref(message),
                        parse_mode='Markdown',
                        disable_web_page_preview=False
                    )
                    
                    logger.info(f"Published {scenario} alert for market {alert_data['market_id']}")
                    if buffer_dict is not None:
                        self._clear_blocked_reason(buffer_dict, market_id)

                    # Mark trades as consumed so they don't trigger other scenarios simultaneously
                    # User requirement: "if a trade fell into a signal, it must be cleared from buffer"
                    try:
                        trade_ids = [t['id'] for t in verified_data.get('trades', []) if t.get('id')]
                        if trade_ids:
                            alerts_storage.mark_trades_consumed(trade_ids, scenario)
                    except Exception as e:
                        logger.error(f"Error marking trades consumed: {e}")
                    
                except Exception as e:
                    logger.error(f"Error in verify_and_send: {e}", exc_info=True)
                    if buffer_dict is not None:
                        # Keep it short for UI; still helpful for debugging
                        self._set_blocked_reason(
                            buffer_dict,
                            market_id,
                            code="PUBLISH_ERROR",
                            reason=str(e)[:180],
                        )
            
            asyncio.create_task(verify_and_send())

        except Exception as e:
            logger.error(f"Error publishing {scenario} alert: {e}", exc_info=True)
            buffer_dict = self._get_buffer_dict_for_scenario(scenario)
            if buffer_dict is not None:
                self._set_blocked_reason(
                    buffer_dict,
                    alert_data.get("market_id", ""),
                    code="PUBLISH_ERROR",
                    reason=str(e)[:180],
                )

    async def _cleanup_invalid_trades(self, market_id: str) -> None:
        """
        Remove trades from wallets that no longer qualify (too many positions).
        This keeps the buffer clean and allows new qualifying trades to accumulate.
        """
        if not self._poly_service:
            return
        
        # Get max positions threshold (use the strictest one from scenarios)
        max_positions = min(
            int(self.settings.get('burst_max_positions', '3')),
            int(self.settings.get('cluster_max_positions', '3')),
            int(self.settings.get('accumulation_max_positions', '3'))
        )
        
        # Get all unconsumed trades for this market (within reasonable window)
        # Use a large window to catch all potentially invalid trades
        window_hours = max(
            float(self.settings.get('burst_interval_hours', '1')),
            float(self.settings.get('cluster_interval_hours', '2')),
            14 * 24  # For accumulation
        )
        
        try:
            trades = alerts_storage.get_trades_window(
                market_id=market_id,
                window_hours=window_hours,
                max_wallet_age_hours=None  # Don't filter by age here
            )
            
            if not trades:
                return
            
            # Get unique wallets
            unique_wallets = set(t.get('wallet') for t in trades if t.get('wallet'))
            
            # Check current positions for each wallet
            invalid_wallets = set()
            for wallet in unique_wallets:
                try:
                    pos_data = await self._poly_service.get_trader_positions(wallet)
                    current_pos_count = pos_data.get('open_count', 0) if pos_data else 0
                    
                    if current_pos_count > max_positions:
                        invalid_wallets.add(wallet)
                        logger.debug(f"Marking trades from wallet {wallet[:10]}... as invalid (positions: {current_pos_count} > {max_positions})")
                except Exception as e:
                    logger.debug(f"Error checking positions for {wallet[:10]}...: {e}")
                    # On error, skip (don't mark as invalid)
            
            # Mark trades from invalid wallets as consumed
            if invalid_wallets:
                invalid_trade_ids = [
                    t['id'] for t in trades 
                    if t.get('wallet') in invalid_wallets and t.get('id')
                ]
                
                if invalid_trade_ids:
                    alerts_storage.mark_trades_consumed(invalid_trade_ids, 'TOO_MANY_POSITIONS')
                    logger.info(f"Cleaned up {len(invalid_trade_ids)} trades from {len(invalid_wallets)} wallets (positions > {max_positions})")
                    
                    # Update active buffers to reflect cleanup
                    self._update_active_buffers_after_cleanup(market_id, invalid_wallets)
        
        except Exception as e:
            logger.error(f"Error cleaning up invalid trades for {market_id}: {e}")
    
    def _update_active_buffers_after_cleanup(self, market_id: str, excluded_wallets: set) -> None:
        """Update active buffers after removing invalid wallets."""
        # Remove excluded wallets from active buffer entries
        for buffer_dict in [self._active_bursts, self._active_clusters, self._active_accumulations]:
            if market_id in buffer_dict:
                wallet_list = buffer_dict[market_id].get('wallet_list', [])
                # Filter out excluded wallets
                valid_wallets = [w for w in wallet_list if w not in excluded_wallets]
                
                if len(valid_wallets) < buffer_dict[market_id].get('min_wallets', 2):
                    # Not enough wallets left, remove from buffer
                    del buffer_dict[market_id]
                    logger.debug(f"Removed {market_id} from active buffer (not enough wallets after cleanup)")
                else:
                    # Update wallet count
                    buffer_dict[market_id]['wallets'] = len(valid_wallets)
                    buffer_dict[market_id]['wallet_list'] = valid_wallets

    async def _verify_positions(self, alert_data: Dict[str, Any], scenario: str = 'CLUSTER') -> Optional[Dict[str, Any]]:
        """
        Verify that participants still hold significant positions AND still have few total positions.
        Returns filtered alert_data or None if not enough wallets remain.
        Also marks trades from wallets that sold as consumed to remove them from buffer.
        
        A wallet is considered valid if:
        1. Position value in this market >= minimum threshold
        2. Current total open positions <= max_positions threshold
        
        Args:
            alert_data: Alert data to verify
            scenario: Scenario name (CLUSTER, BURST, ACCUMULATION) to use correct settings
        """
        if not self._poly_service:
            logger.debug("No poly_service set, skipping position verification")
            return alert_data  # Skip verification if no service
        
        market_id = alert_data.get('market_id', '')
        trades = alert_data.get('trades', [])
        
        # Get settings based on scenario
        if scenario == 'BURST':
            min_wallets = int(self.settings.get('burst_min_wallets', '8'))
            min_position_value = float(self.settings.get('burst_min_usd', '1000'))
            max_positions = int(self.settings.get('burst_max_positions', '3'))
        elif scenario == 'ACCUMULATION':
            min_wallets = int(self.settings.get('accumulation_min_wallets', '3'))
            min_position_value = float(self.settings.get('accumulation_min_usd', '10000'))
            max_positions = int(self.settings.get('accumulation_max_positions', '3'))
        else:  # CLUSTER (default)
            min_wallets = int(self.settings.get('cluster_min_wallets', '4'))
            min_position_value = float(self.settings.get('cluster_min_usd', '5000'))
            max_positions = int(self.settings.get('cluster_max_positions', '3'))
        
        if not market_id or not trades:
            return alert_data
        
        # Get unique wallets
        unique_wallets = set(t.get('wallet') for t in trades if t.get('wallet'))
        
        # Check each wallet's position value AND current total positions
        wallets_still_holding = set()
        wallets_excluded = set()
        wallet_positions = {}  # wallet -> position_value
        wallet_current_pos_count = {}  # wallet -> current open positions count
        exclusion_reasons = {}  # wallet -> reason
        
        for wallet in unique_wallets:
            try:
                # Check position in this specific market
                position_value = await self._poly_service.check_wallet_has_position(wallet, market_id)
                wallet_positions[wallet] = position_value
                
                # Check current total open positions count
                pos_data = await self._poly_service.get_trader_positions(wallet)
                current_pos_count = pos_data.get('open_count', 0) if pos_data else 0
                wallet_current_pos_count[wallet] = current_pos_count
                
                # Wallet must pass BOTH checks:
                # 1. Still holds position >= minimum threshold
                # 2. Current total positions <= max_positions
                if position_value < min_position_value:
                    wallets_excluded.add(wallet)
                    if position_value > 0:
                        exclusion_reasons[wallet] = f"position ${position_value:.0f} < min ${min_position_value:.0f}"
                    else:
                        exclusion_reasons[wallet] = "no longer holds position"
                elif current_pos_count > max_positions:
                    wallets_excluded.add(wallet)
                    exclusion_reasons[wallet] = f"positions {current_pos_count} > max {max_positions}"
                    logger.debug(f"Wallet {wallet[:10]}... excluded: now has {current_pos_count} positions (max: {max_positions})")
                else:
                    wallets_still_holding.add(wallet)
                    
            except Exception as e:
                logger.debug(f"Error checking wallet {wallet[:10]}...: {e}")
                # On error, EXCLUDE wallet (strict mode - don't show uncertain data)
                wallets_excluded.add(wallet)
                exclusion_reasons[wallet] = f"verification error: {e}"
        
        # Mark trades from excluded wallets as consumed (remove from buffer)
        if wallets_excluded:
            try:
                excluded_trade_ids = [t['id'] for t in trades if t.get('wallet') in wallets_excluded and t.get('id')]
                if excluded_trade_ids:
                    alerts_storage.mark_trades_consumed(excluded_trade_ids, 'EXCLUDED')
                    logger.info(f"Removed {len(excluded_trade_ids)} trades from buffer (wallets excluded)")
                    for wallet in wallets_excluded:
                        reason = exclusion_reasons.get(wallet, 'unknown')
                        logger.debug(f"  - {wallet[:10]}...: {reason}")
            except Exception as e:
                logger.error(f"Error marking excluded trades: {e}")
        
        # Filter trades to only include valid wallets
        filtered_trades = [t for t in trades if t.get('wallet') in wallets_still_holding]
        
        # Check if we still have enough wallets
        if len(wallets_still_holding) < min_wallets:
            logger.info(f"Position verification: only {len(wallets_still_holding)}/{len(unique_wallets)} wallets valid (min: {min_wallets})")
            return None
        
        # Update alert data with filtered info
        filtered_data = alert_data.copy()
        filtered_data['trades'] = filtered_trades
        filtered_data['wallet_count'] = len(wallets_still_holding)
        filtered_data['total_volume'] = sum(t.get('trade_size_usd', 0) for t in filtered_trades)
        
        logger.info(f"Position verification: {len(wallets_still_holding)}/{len(unique_wallets)} wallets valid (pos >= ${min_position_value:.0f}, count <= {max_positions})")
        
        return filtered_data

    def get_status(self) -> Dict[str, Any]:
        """Get current status and settings for admin command."""
        status = {
            'enabled': self.is_enabled(),
            'channel_id': self.get_channel_id(),
            'probability_min': self.settings.get('probability_min', '0'),
            'probability_max': self.settings.get('probability_max', '100'),
            'scenarios': {}
        }

        # Categories
        status['categories'] = {
            'Sports': self.settings.get('cat_sports_enabled', 'true'),
            'Crypto': self.settings.get('cat_crypto_enabled', 'true'),
            'Other': self.settings.get('cat_other_enabled', 'true'),
        }

        # CLUSTER status
        status['scenarios']['CLUSTER'] = {
            'enabled': self.settings.get('cluster_enabled', 'false'),
            'interval': self.settings.get('cluster_interval_hours', '2'),
            'max_age': self.settings.get('cluster_wallet_age_hours', '24'),
            'min_usd': self.settings.get('cluster_min_usd', '5000'),
            'min_total': self.settings.get('cluster_min_total_usd', '10000'),
            'min_wallets': self.settings.get('cluster_min_wallets', '4'),
            'min_dir': self.settings.get('cluster_min_direction_pct', '75'),
            'side': self.settings.get('cluster_side', 'both'),
            'profiles': self.settings.get('cluster_include_profiles', 'true'),
            'max_pos': self.settings.get('cluster_max_positions', '3')
        }

        # BURST status
        status['scenarios']['BURST'] = {
            'enabled': self.settings.get('burst_enabled', 'false'),
            'interval': self.settings.get('burst_interval_hours', '1'),
            'max_age': self.settings.get('burst_wallet_age_hours', '72'),
            'min_usd': self.settings.get('burst_min_usd', '1000'),
            'min_total': self.settings.get('burst_min_total_usd', '5000'),
            'min_wallets': self.settings.get('burst_min_wallets', '8'),
            'min_dir': self.settings.get('burst_min_direction_pct', '70'),
            'profiles': self.settings.get('burst_include_profiles', 'true'),
            'max_pos': self.settings.get('burst_max_positions', '3')
        }

        # ACCUMULATION status
        status['scenarios']['ACCUMULATION'] = {
            'enabled': self.settings.get('accumulation_enabled', 'false'),
            'interval': self.settings.get('accumulation_interval_days', '14'),
            'min_usd': self.settings.get('accumulation_min_usd', '10000'),
            'min_total': self.settings.get('accumulation_min_total_usd', '50000'),
            'min_wallets': self.settings.get('accumulation_min_wallets', '3'),
            'max_age': self.settings.get('accumulation_wallet_age_hours', '48'),
            'min_dir': self.settings.get('accumulation_min_direction_pct', '70'),
            'profiles': self.settings.get('accumulation_include_profiles', 'true'),
            'max_pos': self.settings.get('accumulation_max_positions', '3')
        }

        # Database stats
        status['stats'] = alerts_storage.get_stats()

        # Add pending patterns to status
        status['pending_patterns'] = {
            'clusters': sorted(list(self._active_clusters.values()), key=lambda x: x['last_ts'], reverse=True)[:20],
            'accumulations': sorted(list(self._active_accumulations.values()), key=lambda x: x['last_ts'], reverse=True)[:20],
            'bursts': sorted(list(self._active_bursts.values()), key=lambda x: x['last_ts'], reverse=True)[:20]
        }
        
        # Add recently published alerts
        status['published_history'] = alerts_storage.get_recent_published(limit=20)
        
        return status

    def update_setting(self, key: str, value: Any) -> None:
        """Update a setting."""
        self._save_setting(key, value)
        logger.info(f"Updated setting: {key} = {value}")

    def get_pending_alerts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get markets that are close to triggering alerts but haven't reached threshold yet.
        Returns dict with scenario names as keys and list of pending market info as values.
        """
        pending = {'CLUSTER': [], 'BURST': []}
        
        try:
            # Get all active markets
            markets = alerts_storage.get_all_active_markets(hours_back=24)
            
            for market_data in markets:
                if isinstance(market_data, dict):
                    market_id = market_data.get('market_id')
                else:
                    market_id = str(market_data) if market_data is not None else None
                if not market_id:
                    continue
                # Check CLUSTER pending
                cluster_pending = self._get_cluster_pending(market_id)
                if cluster_pending:
                    pending['CLUSTER'].append(cluster_pending)
                
                # Check BURST pending
                burst_pending = self._get_burst_pending(market_id)
                if burst_pending:
                    pending['BURST'].append(burst_pending)
        
        except Exception as e:
            logger.error(f"Error getting pending alerts: {e}")
        
        return pending

    def _get_cluster_pending(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get pending CLUSTER info for a market (if close to threshold)."""
        try:
            interval = float(self.settings.get('cluster_interval_hours', '2'))
            max_age = float(self.settings.get('cluster_wallet_age_hours', '24'))
            min_usd = float(self.settings.get('cluster_min_usd', '5000'))
            min_wallets = int(self.settings.get('cluster_min_wallets', '4'))
            max_pos = int(self.settings.get('cluster_max_positions', '3'))
            side_filter = self.settings.get('cluster_side', 'both').lower()

            trades = alerts_storage.get_trades_window(
                market_id=market_id,
                window_hours=interval,
                max_wallet_age_hours=max_age
            )

            if not trades:
                return None

            # Apply same filters as _check_cluster
            if side_filter != 'both':
                filtered = []
                for t in trades:
                    act = (t.get('trade_action') or '').lower()
                    if side_filter == 'buy' and act in ['buy', 'split']:
                        filtered.append(t)
                    elif side_filter == 'sell' and act in ['sell', 'merge', 'redeem']:
                        filtered.append(t)
                trades = filtered

            trades = [t for t in trades if t.get('trade_size_usd', 0) >= min_usd]
            trades = [t for t in trades if (t.get('open_positions') or 0) <= max_pos]

            if not trades:
                return None

            unique_wallets = set(t['wallet'] for t in trades)
            wallet_count = len(unique_wallets)

            # Only show if we have at least 1 wallet but less than threshold
            if wallet_count < 1 or wallet_count >= min_wallets:
                return None

            total_volume = sum(t.get('trade_size_usd', 0) for t in trades)
            dominant_outcome, directionality = self._calculate_directionality(trades)
            market_title = trades[0].get('market_title', 'Unknown')[:40] if trades else 'Unknown'

            return {
                'market_id': market_id,
                'market_title': market_title,
                'wallet_count': wallet_count,
                'min_wallets': min_wallets,
                'total_volume': total_volume,
                'outcome': dominant_outcome,
                'directionality': directionality
            }

        except Exception as e:
            logger.debug(f"Error in _get_cluster_pending: {e}")
            return None

    def _get_burst_pending(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get pending BURST info for a market (if close to threshold)."""
        try:
            interval = float(self.settings.get('burst_interval_hours', '1'))
            max_age = float(self.settings.get('burst_wallet_age_hours', '72'))
            min_usd = float(self.settings.get('burst_min_usd', '1000'))
            min_wallets = int(self.settings.get('burst_min_wallets', '8'))
            max_pos = int(self.settings.get('burst_max_positions', '3'))

            trades = alerts_storage.get_trades_window(
                market_id=market_id,
                window_hours=interval,
                max_wallet_age_hours=max_age
            )

            if not trades:
                return None

            trades = [t for t in trades if t.get('trade_size_usd', 0) >= min_usd]
            trades = [t for t in trades if (t.get('open_positions') or 0) <= max_pos]

            if not trades:
                return None

            unique_wallets = set(t['wallet'] for t in trades)
            wallet_count = len(unique_wallets)

            # Only show if we have at least 1 wallet but less than threshold
            if wallet_count < 1 or wallet_count >= min_wallets:
                return None

            total_volume = sum(t.get('trade_size_usd', 0) for t in trades)
            dominant_outcome, directionality = self._calculate_directionality(trades)
            market_title = trades[0].get('market_title', 'Unknown')[:40] if trades else 'Unknown'

            return {
                'market_id': market_id,
                'market_title': market_title,
                'wallet_count': wallet_count,
                'min_wallets': min_wallets,
                'total_volume': total_volume,
                'outcome': dominant_outcome,
                'directionality': directionality
            }

        except Exception as e:
            logger.debug(f"Error in _get_burst_pending: {e}")
            return None


# Global service instance
_insider_alerts_service = None


def get_insider_alerts_service() -> Optional[InsiderAlertsService]:
    """Get global insider alerts service instance."""
    return _insider_alerts_service


def set_insider_alerts_service(service: InsiderAlertsService) -> None:
    """Set global insider alerts service instance."""
    global _insider_alerts_service
    _insider_alerts_service = service
