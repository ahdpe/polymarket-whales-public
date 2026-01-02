import asyncio
import logging
import os
import sys
import fcntl
import time
from services.polymarket import PolymarketService
from services.telegram_service import (
    start_telegram, send_trade_alert, user_filters, 
    get_user_categories, get_default_categories, get_user_lang,
    get_user_probability_filter
)
from core.filters import get_alert_level
from core.categories import detect_category, should_show_trade
from core.localization import get_text, get_trade_level_name, get_trade_level_emoji
from config import FILTERS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default chat ID from env (if set)
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Module-level service reference (set in main())
poly_service = None


def format_position_stats(pos_data):
    """Format position stats line for whale message."""
    if not pos_data:
        return ""
    
    pnl_usd = pos_data.get("pnl_usd", 0)
    pnl_pct = pos_data.get("pnl_percent", 0)
    open_count = pos_data.get("open_count", 0)
    total_value = pos_data.get("total_value", 0)
    
    # Format values (K/M notation for large numbers)
    def fmt_val(v):
        v_abs = abs(v)
        if v_abs >= 1_000_000:
            return f"${v_abs/1_000_000:.1f}M"
        elif v_abs >= 1_000:
            return f"${v_abs/1_000:.1f}K"
        else:
            return f"${v_abs:.0f}"
    
    # Format Open PnL with sign and emoji
    if pnl_usd >= 0:
        open_pnl_str = f"+{fmt_val(pnl_usd)}"
    else:
        open_pnl_str = f"🔻{fmt_val(pnl_usd)}"
    pnl_pct_str = f"({pnl_pct:+.0f}%)" if pnl_pct else "(0%)"
    
    return f"\n📊 Open PnL: {open_pnl_str} {pnl_pct_str}\n💼 Open Positions: {open_count} | Val: {fmt_val(total_value)}"


def format_wallet_age(first_activity_ts):
    """Format wallet age from first activity timestamp."""
    if not first_activity_ts:
        return ""
    
    now = time.time()
    age_seconds = now - first_activity_ts
    
    if age_seconds < 0:
        return ""
    
    # Calculate years, months, days
    days = int(age_seconds / 86400)
    
    if days >= 365:
        years = days // 365
        months = (days % 365) // 30
        if months > 0:
            age_str = f"{years}y {months}mo"
        else:
            age_str = f"{years}y"
    elif days >= 30:
        months = days // 30
        remaining_days = days % 30
        if remaining_days >= 7:
            age_str = f"{months}mo {remaining_days}d"
        else:
            age_str = f"{months}mo"
    elif days >= 1:
        age_str = f"{days}d"
    else:
        hours = int(age_seconds / 3600)
        age_str = f"{hours}h" if hours > 0 else "<1h"
    
    return f"\n🕐 Wallet Age: {age_str}"

async def handle_trade(trade_data):
    """
    Callback for when a trade is received from Data API.
    """
    try:
        price = float(trade_data.get('price', 0))
        size = float(trade_data.get('size', 0))
        value_usd = price * size
        
        # Get alert level for this trade size
        alert_config = get_alert_level(value_usd)
        
        if not alert_config:
            return  # Trade too small for any alert
        
        # Detect category - use both slug and eventSlug for better detection
        market_title = trade_data.get('title', 'Unknown Market')
        slug = trade_data.get('slug', '')
        event_slug = trade_data.get('eventSlug', '')
        
        # Build market URL early (needed for category detection)
        market_url = f"https://polymarket.com/event/{event_slug}" if event_slug else ""
        
        # Also check for sports-specific URL pattern if available from API
        api_url = trade_data.get('url', '') or trade_data.get('marketUrl', '')
        
        category = detect_category(market_title, f"{slug} {event_slug}", url=api_url or market_url)

        # --- OPTIMIZATION: Identify recipients BEFORE triggering expensive API calls ---
        recipients = [] # List of (chat_id, localized_level_emoji, localized_level_name, localized_lang)

        # Helper to check if a user qualifies
        def check_user(chat_id, min_threshold):
             if value_usd < min_threshold:
                 return False

             # Check active status
             from services.telegram_service import is_user_active
             if not is_user_active(chat_id):
                 return False

             # Check category filter
             user_prefs = get_user_categories(chat_id)
             if not should_show_trade(category, user_prefs):
                 return False
             
             # Check probability filter
             prob_range = get_user_probability_filter(chat_id)
             if prob_range:
                 min_prob, max_prob = prob_range
                 if price < min_prob or price > max_prob:
                     return False
             
             return True

        # 1. Check registered users
        for chat_id, min_threshold in user_filters.items():
            if check_user(chat_id, min_threshold):
                recipients.append(chat_id)
        
        # 2. Check default chat ID (if not already included)
        if DEFAULT_CHAT_ID:
            try:
                default_id = int(DEFAULT_CHAT_ID)
                if default_id not in user_filters and default_id not in recipients:
                     # Use default lowest threshold for fallback
                     min_threshold = FILTERS[-1]['min']
                     if check_user(default_id, min_threshold):
                         recipients.append(default_id)
            except ValueError:
                pass

        # If no one wants this trade, stop here!
        if not recipients:
            return 
            
        # --- End Optimization ---
        
        emoji = alert_config['emoji']
        side = trade_data.get('side', 'UNKNOWN')
        outcome = trade_data.get('outcome', '')
        trader = trade_data.get('name') or trade_data.get('pseudonym', 'Unknown')
        trader_address = trade_data.get('proxyWallet', '') or trade_data.get('maker', '')
        
        # Color for side + outcome
        # 🟢 Green = BUY Yes, 🔴 Red = BUY No, 🔵 Blue = SELL
        if side == "SELL":
            side_emoji = "🔵"
        elif outcome.lower() == "yes":
            side_emoji = "🟢"
        else:
            side_emoji = "🔴"
        
        # Category emoji
        cat_emoji = {"crypto": "💰", "sports": "⚽", "other": "📌"}.get(category, "")
        
        trader_url = f"https://polymarket.com/profile/{trader_address}" if trader_address else ""
        
        # Price as percentage (Polymarket prices are 0-1)
        price_pct = price * 100
        
        # Fetch trader positions and first activity (cached, async)
        # We only do this NOW because we know at least one person will see it.
        pos_data = None
        first_activity_ts = None
        if poly_service and trader_address:
            pos_data = await poly_service.get_trader_positions(trader_address)
            first_activity_ts = await poly_service.get_trader_first_activity(trader_address)
        position_stats_line = format_position_stats(pos_data)
        wallet_age_line = format_wallet_age(first_activity_ts)
        
        # Money display logic
        if side == 'BUY':
            money_text = f"*${value_usd:,.0f}* → ${size:,.0f}"
        else:
            money_text = f"*${value_usd:,.0f}*"

        # Header logic
        is_series = trade_data.get('is_aggregate', False) and trade_data.get('series_fills', 1) > 1
        if is_series:
            fills = trade_data.get('series_fills', 0)
            side_display = f"⚡ *Series {side} {outcome}* ({fills} fills)"
        else:
            side_display = f"{side_emoji} *{side} {outcome}*"

        # Send to all recipients
        for chat_id in recipients:
             # Localization per user
             lang = get_user_lang(chat_id)
             level_emoji = get_trade_level_emoji(lang, alert_config['min'])
             
             trader_text = f"[{trader}]({trader_url})" if trader_url else trader
             
             msg = (
                f"{cat_emoji} [{market_title[:80]}]({market_url})\n"
                f"{side_display} @ {price_pct:.1f}%\n"
                f"💵 {money_text}\n"
                f"{level_emoji} {trader_text}{position_stats_line}{wallet_age_line}"
            )
             await send_trade_alert(chat_id, msg)
                    
    except Exception as e:
        logger.error(f"Error handling trade: {e}")

def single_instance_check():
    """Ensure only one instance of the bot is running."""
    lock_file = '/tmp/polymarket_whales.lock'
    try:
        fp = open(lock_file, 'w')
        # Try to acquire an exclusive lock without blocking
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fp
    except IOError:
        print("Another instance is already running. Exiting.")
        sys.exit(1)

async def main():
    # Ensure single instance
    lock_handle = single_instance_check()

    # Start Telegram in background
    tg_task = asyncio.create_task(start_telegram())
    
    # Start Polymarket Service
    global poly_service
    poly_service = PolymarketService()
    
    logger.info("Starting PolyWhales...")
    logger.info("Using Polymarket Data API for whale trades...")
    
    # Run Polymarket trade polling (uses POLL_INTERVAL from polymarket.py)
    await poly_service.poll_trades(handle_trade)
    
    await tg_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
