# PUBLIC SHELL VERSION
"""Common utility functions for PolyWhales bot."""
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
POLYMARKET_HOSTS = {'polymarket.com', 'www.polymarket.com'}
POLYMARKET_REF_PARAM = 'r'
POLYMARKET_REF_VALUE = 'PolymarketWhaleAlrts'
POLYMARKET_LOCALE = 'en'
POLYMARKET_BASE_URL = 'https://polymarket.com'
_POLYMARKET_URL_RE = re.compile('https?://[^\\s\\)\\]>]+')
_POLYMARKET_PATH_RE_TEMPLATE = '(?:https?://)?(?:www\\.)?polymarket\\.com/(?:(?:[a-z]{2}(?:-[a-z]{2,4})?)/)*{path_name}/([^/?#\\s\\)\\]>]+)'
_LOCALE_SEGMENT_RE = re.compile('^[a-z]{2}(?:-[a-z]{2,4})?$', re.IGNORECASE)
_PATHS_WITHOUT_LOCALE = {'api', '_next'}

def _localized_polymarket_path(path: str) -> str:
    """Return a Polymarket web path with a stable /en/ prefix."""
    pass

def normalize_polymarket_url(url: str, *, add_ref: bool=True) -> str:
    """
    Normalize Polymarket web URLs to /en/ and append the bot ref parameter.

    This prevents locale auto-redirects such as /ru/ru/event/... for users
    whose browser prefers a non-English Polymarket locale.
    """
    pass

def polymarket_url(path: str='', *, add_ref: bool=True) -> str:
    """Build a normalized Polymarket URL from a site path."""
    pass

def polymarket_event_url(event_slug_or_id: str | None) -> str:
    """Build a normalized Polymarket market/event URL."""
    pass

def polymarket_profile_url(profile_id: str | None) -> str:
    """Build a normalized Polymarket profile URL."""
    pass

def add_polymarket_ref(text: str) -> str:
    """Normalize all Polymarket URLs in text and add the bot ref parameter."""
    pass

def extract_polymarket_event_slug(text: str) -> str | None:
    """Extract an event slug from Polymarket event links with or without locale."""
    pass

def extract_polymarket_profile_id(text: str) -> str | None:
    """Extract a profile id from Polymarket profile links with or without locale."""
    pass

def _extract_polymarket_path_value(text: str, path_name: str) -> str | None:
    pass

def shorten_trader_name(name):
    """
    Shorten trader name:
    1. Remove timestamp suffix (starting with '-') if present.
    2. Truncate long addresses: 0xB0B1Ecb5eD8a22d38Ee89f20b196246005d37507 -> 0xB0B1E...37507
    """
    pass