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
    get_user_probability_filter, get_user_side_types
)
from core.filters import get_alert_level
from core.categories import detect_category, should_show_trade
from core.localization import get_text, get_trade_level_name, get_trade_level_emoji, get_trade_level_icon
from config import FILTERS
from storage import saved_whales
from services.twitter_service import get_twitter_service

# Configure logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO, 
    format=log_format,
    handlers=[
        logging.StreamHandler(),  # Keep stderr for systemd/journal
        logging.FileHandler('bot_output.log', mode='a', encoding='utf-8')  # Also write to file
    ]
)
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
    # Check if bot is enabled (admin can stop/start bot)
    from services.telegram_service import is_bot_enabled
    if not is_bot_enabled():
        return  # Bot is stopped by admin, skip processing
    
    try:
        price = float(trade_data.get('price', 0))
        size = float(trade_data.get('size', 0))
        # For activities, value_usd might already be set
        value_usd = trade_data.get('value_usd')
        if value_usd is None:
            value_usd = price * size
        else:
            value_usd = float(value_usd)
        
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
        
        # Add category to trade_data for Twitter filter
        trade_data['category'] = category

        # Get side early (needed for side type filter)
        side = trade_data.get('side', 'UNKNOWN')

        # --- OPTIMIZATION: Identify recipients BEFORE triggering expensive API calls ---
        recipients = [] # List of (chat_id, localized_level_emoji, localized_level_name, localized_lang)

        # Helper function to check if side type should be shown
        def should_show_side_type(side, trade_data, side_types_prefs):
            """Check if trade side type matches user preferences."""
            if side_types_prefs.get('all', True):
                return True
            
            side_upper = side.upper() if side else 'UNKNOWN'
            # Check for Split
            is_split = side_upper == 'SPLIT' or trade_data.get('type', '').upper() == 'SPLIT'
            if is_split:
                return side_types_prefs.get('SPLIT', False)
            
            # Check for Merge
            is_merge = side_upper == 'MERGE' or trade_data.get('type', '').upper() == 'MERGE'
            if is_merge:
                return side_types_prefs.get('MERGE', False)
            
            # Check for Redeem
            is_redeem = side_upper == 'REDEEM' or trade_data.get('type', '').upper() == 'REDEEM'
            if is_redeem:
                return side_types_prefs.get('REDEEM', False)
            
            # Check BUY and SELL
            if side_upper == 'BUY':
                return side_types_prefs.get('BUY', False)
            elif side_upper == 'SELL':
                return side_types_prefs.get('SELL', False)
            
            # Unknown side type - show by default if all is enabled, otherwise hide
            return side_types_prefs.get('all', True)

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
             
             # Check side type filter
             side_types_prefs = get_user_side_types(chat_id)
             if not should_show_side_type(side, trade_data, side_types_prefs):
                 logger.debug(f"Trade filtered by side type: chat_id={chat_id}, side={side}, type={trade_data.get('type')}, prefs={side_types_prefs}")
                 return False
             
             return True

        # 1. Check registered users
        for chat_id, min_threshold in user_filters.items():
            if check_user(chat_id, min_threshold):
                recipients.append(chat_id)
        
        # 2. Check if Twitter wants this trade (independent of Telegram)
        # Use wants_trade (filters only) - post_trade_alert will handle queue/rate limits
        twitter_service = get_twitter_service()
        twitter_wants = twitter_service and twitter_service.wants_trade(trade_data)[0]
        
        # If no one wants this trade (neither Telegram nor Twitter), stop here!
        if not recipients and not twitter_wants:
            return 
            
        # --- End Optimization ---
        
        emoji = alert_config['emoji']
        # side already defined above
        outcome = trade_data.get('outcome', '')
        trader = trade_data.get('name') or trade_data.get('pseudonym', 'Unknown')
        trader_address = trade_data.get('proxyWallet', '') or trade_data.get('maker', '')
        
        # Check if this is a Split position
        is_split = side.upper() == 'SPLIT' or trade_data.get('type', '').upper() == 'SPLIT'
        
        # Check if this is a Merge position
        is_merge = side.upper() == 'MERGE' or trade_data.get('type', '').upper() == 'MERGE'
        
        # Check if this is a Redeem position
        is_redeem = side.upper() == 'REDEEM' or trade_data.get('type', '').upper() == 'REDEEM'
        
        # Color for side + outcome
        # 🟢 Green = BUY Yes, 🔴 Red = BUY No, 🔵 Blue = SELL, ⚪ Split, ↔️ Merge, 🟣 Purple = Redeem
        if is_split:
            side_emoji = "⚪"
        elif is_merge:
            side_emoji = "↔️"
        elif is_redeem:
            side_emoji = "🟣"
        elif side == "SELL":
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
        if is_split:
            # For Split, show total value (split creates both YES and NO positions)
            money_text = f"*${value_usd:,.0f}* (YES + NO)"
        elif is_merge:
            # For Merge, show value (merge combines YES+NO back to USDC)
            money_text = f"*${value_usd:,.0f}* (YES + NO → USDC)"
        elif is_redeem:
            # For Redeem, show redeemed value
            money_text = f"*${value_usd:,.0f}*"
        elif side == 'BUY':
            money_text = f"*${value_usd:,.0f}* → ${size:,.0f}"
        else:
            money_text = f"*${value_usd:,.0f}*"

        # Header logic
        is_series = trade_data.get('is_aggregate', False) and trade_data.get('series_fills', 1) > 1
        if is_split:
            # Split creates both YES and NO positions
            side_display = f"{side_emoji} *SPLIT* (YES + NO)"
        elif is_merge:
            # Merge combines YES+NO back to USDC
            side_display = f"{side_emoji} *MERGE* (YES + NO → USDC)"
        elif is_redeem:
            # Redeem is when a position is redeemed (market resolved)
            side_display = f"{side_emoji} *REDEEM {outcome}*"
        elif is_series:
            fills = trade_data.get('series_fills', 0)
            side_display = f"🟡 *Series {side} {outcome}* ({fills} fills)"
        else:
            side_display = f"{side_emoji} *{side} {outcome}*"

        # Get whale_key for saved traders feature (with trader name and level icon)
        level_icon = get_trade_level_icon(alert_config['min'])
        whale_key = saved_whales.get_or_create_key(trader_address, name=trader, level_icon=level_icon) if trader_address else None
        
        # Send to all recipients
        for chat_id in recipients:
             # Localization per user
             lang = get_user_lang(chat_id)
             level_emoji = get_trade_level_emoji(lang, alert_config['min'])
             
             # Check if trader is saved by this user
             is_saved = saved_whales.is_saved(chat_id, trader_address) if trader_address else False
             
             trader_text = f"[{trader}]({trader_url})" if trader_url else trader
             
             # Format side_display - skip price % for SPLIT/MERGE/REDEEM
             if is_split or is_merge or is_redeem:
                 side_line = f"{side_display}\n"
             else:
                 side_line = f"{side_display} @ {price_pct:.1f}%\n"
             
             msg = (
                f"{cat_emoji} [{market_title[:80]}]({market_url})\n"
                f"{side_line}"
                f"💵 {money_text}\n"
                f"{level_emoji} {trader_text}{position_stats_line}{wallet_age_line}\n"
            )
             # Get level icon for button
             level_icon = get_trade_level_icon(alert_config['min'])
             await send_trade_alert(chat_id, msg, whale_key=whale_key, is_saved=is_saved, level_icon=level_icon)
        
        # Post to Twitter (if enabled and trade is big enough)
        if twitter_wants:
            # Prepare trade data for Twitter
            twitter_data = {
                'title': market_title,
                'market_url': market_url,
                'side': side,
                'outcome': outcome,
                'price': price,
                'size': size,
                'category': category,  # For category filter
                'trader_address': trader_address,
                'trader_name': trader,  # Full trader name if available
                'level_name': alert_config.get('name', 'WHALE'),
                'position_stats': pos_data,
                'wallet_age_str': format_wallet_age(first_activity_ts).replace('\n🕐 Wallet Age: ', '') if first_activity_ts else ''
            }
            await twitter_service.post_trade_alert(twitter_data)
                    
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
    
    # Initialize saved whales DB
    saved_whales.init_db()

    # Start Telegram in background
    tg_task = asyncio.create_task(start_telegram())
    
    # Start Polymarket Service
    global poly_service
    poly_service = PolymarketService()
    
    logger.info("Starting PolyWhales...")
    logger.info("Using Polymarket Data API for whale trades...")
    
    # Run Polymarket trade polling (uses POLL_INTERVAL from polymarket.py)
    trade_polling_task = asyncio.create_task(poly_service.poll_trades(handle_trade))
    # SPLIT/MERGE/REDEEM activity polling (enabled)
    activity_polling_task = asyncio.create_task(poly_service.poll_activities(handle_trade))
    
    # Start Twitter queue processor (if Twitter is configured)
    twitter_service = get_twitter_service()
    twitter_queue_task = None
    if twitter_service and twitter_service.is_configured:
        twitter_queue_task = asyncio.create_task(twitter_service.process_queue_periodically(interval=60))
    
    # Wait for all tasks
    tasks = [trade_polling_task, activity_polling_task, tg_task]
    if twitter_queue_task:
        tasks.append(twitter_queue_task)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
