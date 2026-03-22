# PUBLIC SHELL VERSION
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
DEFAULT_SETTINGS = {'enabled': 'false', 'channel_id': '', 'cooldown_hours': '24', 'cat_sports_enabled': 'true', 'cat_crypto_enabled': 'true', 'cat_other_enabled': 'true', 'probability_min': '0', 'probability_max': '100', 'cluster_enabled': 'false', 'cluster_interval_hours': '2', 'cluster_wallet_age_hours': '24', 'cluster_min_usd': '5000', 'cluster_min_total_usd': '10000', 'cluster_min_wallets': '4', 'cluster_min_direction_pct': '75', 'cluster_side': 'both', 'cluster_include_profiles': 'true', 'cluster_max_positions': '3', 'accumulation_enabled': 'false', 'accumulation_interval_days': '14', 'accumulation_min_usd': '10000', 'accumulation_min_total_usd': '50000', 'accumulation_min_wallets': '3', 'accumulation_wallet_age_hours': '48', 'accumulation_min_direction_pct': '70', 'accumulation_include_profiles': 'true', 'accumulation_max_positions': '3', 'burst_enabled': 'false', 'burst_interval_hours': '1', 'burst_wallet_age_hours': '72', 'burst_min_usd': '1000', 'burst_min_total_usd': '5000', 'burst_min_wallets': '8', 'burst_min_direction_pct': '70', 'burst_include_profiles': 'true', 'burst_max_positions': '3'}

class InsiderAlertsService:
    """Service for detecting and publishing insider trading alerts."""

    def __init__(self):
        """Initialize service and load settings."""
        pass

    def _get_buffer_dict_for_scenario(self, scenario: str) -> Optional[Dict[str, Dict[str, Any]]]:
        pass

    def _set_blocked_reason(self, buffer_dict: Dict[str, Dict[str, Any]], market_id: str, *, code: str, reason: str) -> None:
        """
        Non-invasive: store diagnostics for status UI only.
        Safe to call even if buffer entry doesn't exist.
        """
        pass

    def _clear_blocked_reason(self, buffer_dict: Dict[str, Dict[str, Any]], market_id: str) -> None:
        """Clear diagnostics after successful publish or when no longer relevant."""
        pass

    def set_bot(self, bot):
        """Set bot instance for sending messages."""
        pass

    def set_poly_service(self, poly_service):
        """Set PolymarketService instance for position verification."""
        pass

    async def _run_debounced_scenario_check(self, market_id: str) -> None:
        """Run scenario checks once per market after short quiet period."""
        pass

    def _schedule_scenario_check_debounced(self, market_id: str, category: str) -> None:
        """
        Debounce scenario checks by market_id to reduce repeated heavy checks
        during short trade bursts.
        """
        pass

    def _load_settings(self):
        """Load settings from database or use defaults."""
        pass

    def _save_setting(self, key: str, value: Any):
        """Save a setting to database."""
        pass

    def is_enabled(self) -> bool:
        """Check if insider alerts are globally enabled."""
        pass

    def get_channel_id(self) -> Optional[str]:
        """Get configured Telegram channel ID (env INSIDER_ALERTS_CHANNEL_ID or DB)."""
        pass

    def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """
        Process incoming trade and store if relevant for analysis.
        """
        pass

    async def check_all_markets(self) -> None:
        """Check all active markets for insider patterns (called periodically)."""
        pass

    async def check_scenarios(self, market_id: str, category: str='other') -> None:
        """
        Check all enabled scenarios for a specific market.
        Now async to support position verification before scenario checks.
        """
        pass

    async def _check_and_append_to_existing_alerts(self, market_id: str) -> None:
        """
        Check if there are new unconsumed trades for a market that already has an active
        published alert (on website). If so, fetch them, filter by scenario settings, 
        append to the website DB, and mark as consumed.
        """
        pass

    def _check_cluster(self, market_id: str) -> Optional[Dict[str, Any]]:
        pass

    def _check_accumulation(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Check for slow multi-wallet accumulation pattern."""
        pass

    def _check_burst(self, market_id: str) -> Optional[Dict[str, Any]]:
        pass

    def _calculate_directionality(self, trades: List[Dict]) -> Tuple[str, float]:
        pass

    def _format_alert_message(self, scenario: str, alert_data: Dict[str, Any], shared_wallets: set=None) -> str:
        pass

    def _publish_alert(self, scenario: str, alert_data: Dict[str, Any]) -> None:
        pass

    async def _cleanup_invalid_trades(self, market_id: str) -> None:
        """
        Remove trades from wallets that no longer qualify (too many positions).
        This keeps the buffer clean and allows new qualifying trades to accumulate.
        """
        pass

    def _update_active_buffers_after_cleanup(self, market_id: str, excluded_wallets: set) -> None:
        """Update active buffers after removing invalid wallets."""
        pass

    async def _verify_positions(self, alert_data: Dict[str, Any], scenario: str='CLUSTER') -> Optional[Dict[str, Any]]:
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
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current status and settings for admin command."""
        pass

    def update_setting(self, key: str, value: Any) -> None:
        """Update a setting."""
        pass

    def get_pending_alerts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get markets that are close to triggering alerts but haven't reached threshold yet.
        Returns dict with scenario names as keys and list of pending market info as values.
        """
        pass

    def _get_cluster_pending(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get pending CLUSTER info for a market (if close to threshold)."""
        pass

    def _get_burst_pending(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get pending BURST info for a market (if close to threshold)."""
        pass
_insider_alerts_service = None

def get_insider_alerts_service() -> Optional[InsiderAlertsService]:
    """Get global insider alerts service instance."""
    pass

def set_insider_alerts_service(service: InsiderAlertsService) -> None:
    """Set global insider alerts service instance."""
    pass