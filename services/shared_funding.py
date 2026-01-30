"""
Shared Funding Detection Module for Telegram Insider Alerts.

Isolated module that analyzes funding sources of wallets in insider alerts
to detect potential coordination (multiple wallets funded from same source).

This module ONLY enriches Telegram messages with tags.
It does NOT affect signal generation or filtering.
"""
import logging
import time
import random
import aiohttp
from typing import Dict, Set, List, Optional, Any

from config import POLYGONSCAN_API_KEY

logger = logging.getLogger(__name__)

# ============ CONSTANTS ============

# Minimum funding amount to consider (in USD equivalent)
MIN_FUNDING_USD = 300

# Cache TTL for funding sources (7 days)
FUNDING_CACHE_TTL = 7 * 24 * 3600

# Contract check cache (permanent - contracts don't change)
CONTRACT_CACHE_TTL = 30 * 24 * 3600  # 30 days

# Thresholds for shared funding detection by scenario type
SHARED_THRESHOLDS = {
    'CLUSTER': 3,
    'ACCUMULATION': 2,
    'BURST': 4
}

# Minimum coverage: at least 60% of wallets must have funding source determined
MIN_COVERAGE_PCT = 0.6

# Known stablecoin contract addresses (lowercase)
USDC_POLYGON = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"  # Native USDC
USDC_BRIDGED = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"  # USDC.e (bridged)
USDT_POLYGON = "0xc2132d05d31c914a87c6611c10748aeb04b58e8f"


# ============ CACHE ============

_funding_cache: Dict[str, Dict[str, Any]] = {}
# Format: {wallet: {"source": "0x...", "is_contract": bool, "cached_at": timestamp}}

_contract_cache: Dict[str, bool] = {}
# Format: {address: is_contract}


# ============ HELPER FUNCTIONS ============

def _get_api_key() -> Optional[str]:
    """Get a random API key if multiple are configured."""
    if not POLYGONSCAN_API_KEY:
        return None
    if isinstance(POLYGONSCAN_API_KEY, list):
        return random.choice(POLYGONSCAN_API_KEY)
    return POLYGONSCAN_API_KEY


async def _is_contract(address: str, session: aiohttp.ClientSession) -> bool:
    """
    Check if an address is a contract or EOA.
    Uses getsourcecode endpoint - contracts have code, EOAs don't.
    """
    address_lower = address.lower()
    
    # Check cache first
    if address_lower in _contract_cache:
        return _contract_cache[address_lower]
    
    api_key = _get_api_key()
    if not api_key:
        return False  # Assume EOA if no API key
    
    try:
        url = (
            f"https://api.etherscan.io/v2/api"
            f"?chainid=137&module=contract&action=getsourcecode"
            f"&address={address}&apikey={api_key}"
        )
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return False
            
            data = await resp.json()
            
            # If result has ABI or source code, it's a contract
            if data.get("status") == "1" and data.get("result"):
                result = data["result"][0] if isinstance(data["result"], list) else data["result"]
                # Contracts have ABI, EOAs don't
                is_contract = bool(result.get("ABI") and result["ABI"] != "Contract source code not verified")
                _contract_cache[address_lower] = is_contract
                return is_contract
            
            # No result means EOA
            _contract_cache[address_lower] = False
            return False
            
    except Exception as e:
        logger.debug(f"Error checking contract status for {address[:10]}...: {e}")
        return False


async def _get_funding_source(wallet: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """
    Get the funding source for a wallet.
    
    Strategy:
    1. Primary: Look for USDC/USDT incoming transfers (tokentx)
    2. Fallback: Look for native MATIC transfers (txlist)
    
    Returns: {"source": "0x...", "is_contract": bool, "amount": float} or None
    """
    wallet_lower = wallet.lower()
    now = time.time()
    
    # Check cache
    cached = _funding_cache.get(wallet_lower)
    if cached and (now - cached.get("cached_at", 0) < FUNDING_CACHE_TTL):
        return cached
    
    api_key = _get_api_key()
    if not api_key:
        logger.debug("No PolygonScan API key configured for shared funding check")
        return None
    
    funding_source = None
    
    try:
        # Primary: Token transfers (USDC/USDT)
        url = (
            f"https://api.etherscan.io/v2/api"
            f"?chainid=137&module=account&action=tokentx"
            f"&address={wallet}&startblock=0&endblock=99999999"
            f"&page=1&offset=100&sort=asc&apikey={api_key}"
        )
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                
                if data.get("status") == "1" and data.get("result"):
                    for tx in data["result"]:
                        # Only incoming transfers to this wallet
                        if tx.get("to", "").lower() != wallet_lower:
                            continue
                        
                        # Check if it's a stablecoin
                        contract = tx.get("contractAddress", "").lower()
                        if contract not in [USDC_POLYGON, USDC_BRIDGED, USDT_POLYGON]:
                            continue
                        
                        # Calculate value (6 decimals for USDC/USDT)
                        try:
                            value = float(tx.get("value", 0)) / 1e6
                        except (ValueError, TypeError):
                            continue
                        
                        if value >= MIN_FUNDING_USD:
                            source_addr = tx.get("from", "")
                            if source_addr:
                                is_contract = await _is_contract(source_addr, session)
                                funding_source = {
                                    "source": source_addr.lower(),
                                    "is_contract": is_contract,
                                    "amount": value,
                                    "cached_at": now
                                }
                                break
        
        # Fallback: Native MATIC transfers
        if funding_source is None:
            url = (
                f"https://api.etherscan.io/v2/api"
                f"?chainid=137&module=account&action=txlist"
                f"&address={wallet}&startblock=0&endblock=99999999"
                f"&page=1&offset=100&sort=asc&apikey={api_key}"
            )
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    if data.get("status") == "1" and data.get("result"):
                        for tx in data["result"]:
                            # Only incoming transfers
                            if tx.get("to", "").lower() != wallet_lower:
                                continue
                            
                            # Calculate value (18 decimals for MATIC)
                            try:
                                value_wei = float(tx.get("value", 0))
                                # Approximate MATIC price ~$0.50
                                value_usd = (value_wei / 1e18) * 0.5
                            except (ValueError, TypeError):
                                continue
                            
                            if value_usd >= MIN_FUNDING_USD * 0.5:  # Lower threshold for native
                                source_addr = tx.get("from", "")
                                if source_addr:
                                    is_contract = await _is_contract(source_addr, session)
                                    funding_source = {
                                        "source": source_addr.lower(),
                                        "is_contract": is_contract,
                                        "amount": value_usd,
                                        "cached_at": now
                                    }
                                    break
        
        # Cache result (even if None - prevents repeated failed lookups)
        if funding_source:
            _funding_cache[wallet_lower] = funding_source
        else:
            # Cache negative result for shorter time
            _funding_cache[wallet_lower] = {"source": None, "cached_at": now}
        
        return funding_source
        
    except Exception as e:
        logger.debug(f"Error getting funding source for {wallet[:10]}...: {e}")
        return None


# ============ MAIN ANALYSIS FUNCTION ============

async def analyze_shared_funding(scenario: str, wallets: List[str]) -> Dict[str, Any]:
    """
    Analyze wallets for shared funding sources.
    
    Args:
        scenario: Signal type ('CLUSTER', 'ACCUMULATION', 'BURST')
        wallets: List of wallet addresses to analyze
    
    Returns:
        {
            "shared_wallets": set of wallet addresses that share funding source,
            "has_shared": bool indicating if shared funding was detected,
            "shared_sources": list of source addresses (EOA) that funded multiple wallets
        }
    """
    result = {
        "shared_wallets": set(),
        "has_shared": False,
        "shared_sources": []  # List of source addresses that funded multiple wallets
    }
    
    if not wallets or len(wallets) < 2:
        return result
    
    threshold = SHARED_THRESHOLDS.get(scenario.upper(), 3)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get funding sources for all wallets
            funding_sources: Dict[str, str] = {}  # wallet -> funding source (EOA only)
            
            for wallet in wallets:
                funding = await _get_funding_source(wallet, session)
                
                if funding and funding.get("source") and not funding.get("is_contract"):
                    # Only use EOA funding sources for shared detection
                    funding_sources[wallet.lower()] = funding["source"]
            
            # Check coverage
            coverage = len(funding_sources) / len(wallets)
            if coverage < MIN_COVERAGE_PCT:
                logger.debug(
                    f"Shared funding: insufficient coverage {coverage:.0%} "
                    f"({len(funding_sources)}/{len(wallets)} wallets)"
                )
                return result
            
            # Group wallets by funding source
            source_to_wallets: Dict[str, List[str]] = {}
            for wallet, source in funding_sources.items():
                if source not in source_to_wallets:
                    source_to_wallets[source] = []
                source_to_wallets[source].append(wallet)
            
            # Find groups meeting threshold
            shared_wallets: Set[str] = set()
            shared_sources: List[str] = []
            for source, wallets_from_source in source_to_wallets.items():
                if len(wallets_from_source) >= threshold:
                    shared_wallets.update(wallets_from_source)
                    shared_sources.append(source)  # Add source address
                    logger.info(
                        f"Shared funding detected: {len(wallets_from_source)} wallets "
                        f"from source {source[:10]}..."
                    )
            
            if shared_wallets:
                result["shared_wallets"] = shared_wallets
                result["has_shared"] = True
                result["shared_sources"] = shared_sources  # Return list of source addresses
        
    except Exception as e:
        logger.error(f"Error in shared funding analysis: {e}")
    
    return result


def get_funding_cache_stats() -> Dict[str, int]:
    """Get cache statistics for monitoring."""
    return {
        "funding_cache_size": len(_funding_cache),
        "contract_cache_size": len(_contract_cache)
    }
