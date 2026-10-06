# PUBLIC SHELL VERSION
"""Market timeframe parsing and filtering helpers."""
from __future__ import annotations
import re
from typing import Any
TIMEFRAME_FILTER_OPTIONS: tuple[int | None, ...] = (None, 15, 30, 60, 240)
_TOKEN_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = ((re.compile('(?<![a-z0-9])5\\s*m(?![a-z0-9])', re.IGNORECASE), 5), (re.compile('(?<![a-z0-9])15\\s*m(?![a-z0-9])', re.IGNORECASE), 15), (re.compile('(?<![a-z0-9])30\\s*m(?![a-z0-9])', re.IGNORECASE), 30), (re.compile('(?<![a-z0-9])1\\s*h(?![a-z0-9])', re.IGNORECASE), 60), (re.compile('(?<![a-z0-9])4\\s*h(?![a-z0-9])', re.IGNORECASE), 240), (re.compile('(?<![a-z0-9])1\\s*d(?![a-z0-9])', re.IGNORECASE), 1440), (re.compile('(?<![a-z0-9])1\\s*w(?![a-z0-9])', re.IGNORECASE), 10080), (re.compile('(?<![a-z0-9])5[-_\\s]*minute(?:s)?(?![a-z0-9])', re.IGNORECASE), 5), (re.compile('(?<![a-z0-9])15[-_\\s]*minute(?:s)?(?![a-z0-9])', re.IGNORECASE), 15), (re.compile('(?<![a-z0-9])30[-_\\s]*minute(?:s)?(?![a-z0-9])', re.IGNORECASE), 30), (re.compile('(?<![a-z0-9])1[-_\\s]*hour(?:s)?(?![a-z0-9])', re.IGNORECASE), 60), (re.compile('(?<![a-z0-9])4[-_\\s]*hour(?:s)?(?![a-z0-9])', re.IGNORECASE), 240), (re.compile('(?<![a-z0-9])daily(?![a-z0-9])', re.IGNORECASE), 1440), (re.compile('(?<![a-z0-9])weekly(?![a-z0-9])', re.IGNORECASE), 10080))

def parse_market_timeframe_minutes(event_slug: Any=None, slug: Any=None, title: Any=None) -> int | None:
    """Return a market timeframe in minutes, if one can be recognized.

    Search order is eventSlug/event_slug, then market slug, then title. Unknown
    formats deliberately return None so caller can fail open.
    """
    pass

def should_block_market_timeframe(threshold_minutes: int | None, event_slug: Any=None, slug: Any=None, title: Any=None) -> tuple[bool, int | None]:
    """Return (should_block, recognized_timeframe_minutes)."""
    pass