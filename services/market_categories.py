# PUBLIC SHELL VERSION
"""Non-blocking Gamma metadata cache for detailed market categories."""
import asyncio
import logging
import os
import re
import time
from typing import Iterable
from urllib.parse import quote
logger = logging.getLogger(__name__)
GAMMA_EVENTS_URL = 'https://gamma-api.polymarket.com/events'
GAMMA_MARKETS_URL = 'https://gamma-api.polymarket.com/markets'
GAMMA_EVENT_BY_SLUG_URL = 'https://gamma-api.polymarket.com/events/slug'

def _normalize_signal(value) -> str:
    """Normalize Gamma labels, slugs and series values to one stable form."""
    pass

def _normalize_market_title(value) -> str:
    """Normalize a title for exact, case-insensitive Combo leg lookups."""
    pass

def _merge_title_signals(target: dict, title, signals) -> None:
    pass

def _add_object_signals(target: set[str], item, fields) -> None:
    pass

def extract_event_category_signals(event: dict) -> frozenset[str]:
    """Collect authoritative tags and series metadata from one Gamma event."""
    pass

def extract_market_category_signals(market: dict) -> frozenset[str]:
    """Collect market tags plus metadata inherited from its parent events."""
    pass

def build_events_query_params(page: int, page_size: int) -> dict:
    """Prioritize active, high-volume events that can produce whale alerts."""
    pass

def _env_bool(name: str, default: bool=False) -> bool:
    pass

def build_category_maps(events: Iterable[dict]):
    """Build immutable-style lookup maps from a Gamma events payload."""
    pass

def build_market_title_map(events: Iterable[dict]) -> dict:
    """Map exact event and market titles to their official Gamma signals."""
    pass

def build_market_category_maps(markets: Iterable[dict]):
    """Build cache additions from an on-demand Gamma markets response."""
    pass

class MarketCategoryMetadataCache:
    """Periodically refresh active Gamma events without blocking alert delivery."""

    def __init__(self):
        pass

    def get_tags(self, event_slug: str='', condition_id: str='') -> frozenset[str]:
        pass

    def get_combo_leg_tags(self, combo_title: str):
        """Return official signals for each Combo leg using exact title matches."""
        pass

    def _merge_maps(self, event_map: dict, condition_map: dict) -> None:
        pass

    async def _fetch_missing(self, event_slug: str, condition_id: str) -> bool:
        pass

    async def get_tags_or_fetch(self, event_slug: str='', condition_id: str='') -> frozenset[str]:
        """Return cached metadata, resolving only cache misses through Gamma."""
        pass

    async def refresh(self) -> bool:
        pass

    async def run_periodically(self):
        pass
_market_category_cache = MarketCategoryMetadataCache()

def get_market_category_cache() -> MarketCategoryMetadataCache:
    pass