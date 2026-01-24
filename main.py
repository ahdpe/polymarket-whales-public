import asyncio
import logging
import os
import sys
import fcntl
import time
import psutil
from datetime import datetime, time as dt_time, timedelta
import sqlite3
import json
from services.polymarket import PolymarketService
from services.telegram_service import (
    start_telegram, enqueue_trade_alert, user_filters, 
    get_user_categories, get_default_categories, get_user_lang,
    get_user_probability_filter, get_user_side_types,
    get_user_wallet_age_filter, get_user_open_positions_filter,
    send_admin_notification, set_poly_service, set_insider_alerts_service,
    stop_queue_workers
)
from services.report_service import generate_report
from core.filters import get_alert_level
from core.categories import detect_category, should_show_trade
from core.localization import get_text, get_trade_level_name, get_trade_level_emoji, get_trade_level_icon
from core.utils import shorten_trader_name
from config import FILTERS
from storage import saved_whales
from services.twitter_service import get_twitter_service
from services.insider_alerts import InsiderAlertsService, get_insider_alerts_service, set_insider_alerts_service as set_global_insider_alerts_service
from services.status_service import set_start_time as set_status_start_time, set_poly_service as set_status_poly_service, set_insider_service as set_status_insider_service
from services.status_server import start_status_server

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
insider_alerts_service = None

# Memory monitoring
MEMORY_WARNING_THRESHOLD = 85.0  # Percentage
MEMORY_CRITICAL_THRESHOLD = 95.0  # Percentage
MEMORY_CHECK_INTERVAL = 300  # 5 minutes
_last_memory_warning_time = {}  # Track last warning time per threshold level


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
        
        # Variables for cached stats
        pos_data = None
        first_activity_ts = None
        trader_address = trade_data.get('proxyWallet', '') or trade_data.get('maker', '')

        # INSIDER ALERTS: Process FIRST, before any filtering (has own $500 threshold)
        if insider_alerts_service and value_usd >= 500:
            try:
                # Get wallet age and positions early for insider analysis
                if trader_address and poly_service:
                    # Use the global service instance
                    first_activity_ts = await poly_service.get_trader_first_activity(trader_address)
                    pos_data = await poly_service.get_trader_positions(trader_address)
                
                trade_data['market_id'] = trade_data.get('conditionId', '')
                trade_data['first_activity_ts'] = first_activity_ts
                # Store open positions count
                trade_data['open_positions'] = pos_data.get('open_count', 0) if pos_data else 0

                insider_alerts_service.process_trade(trade_data)
            except Exception as ie:
                logger.error(f"Error in insider alerts processing: {ie}")
        
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
        recipients = set() # Set of chat_ids to prevent duplicates

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
        # Returns: (qualified: bool, is_bypass: bool)
        def check_user(chat_id, min_threshold):
             # Check active status FIRST (must be stopped if disabled)
             from services.telegram_service import is_user_active
             if not is_user_active(chat_id):
                 return (False, False)

             # Check if notifications are enabled for this trader (BYPASS ALL FILTERS)
             trader_address = trade_data.get('proxyWallet', '') or trade_data.get('maker', '')
             if trader_address and saved_whales.is_notifications_enabled(chat_id, trader_address):
                 logger.info(f"Notification BYPASS for trader {trader_address} (chat_id: {chat_id})")
                 return (True, True)  # Qualified via bypass

             if value_usd < min_threshold:
                 return (False, False)

             # Check category filter
             user_prefs = get_user_categories(chat_id)
             if not should_show_trade(category, user_prefs):
                 return (False, False)
             
             # Check probability filter
             prob_ranges = get_user_probability_filter(chat_id)
             if prob_ranges:
                 # Check if price is within ANY of the ranges
                 is_in_range = False
                 for min_prob, max_prob in prob_ranges:
                     if min_prob <= price <= max_prob:
                         is_in_range = True
                         break
                 
                 if not is_in_range:
                     return (False, False)
             
             # Check side type filter
             side_types_prefs = get_user_side_types(chat_id)
             if not should_show_side_type(side, trade_data, side_types_prefs):
                 logger.debug(f"Trade filtered by side type: chat_id={chat_id}, side={side}, type={trade_data.get('type')}, prefs={side_types_prefs}")
                 return (False, False)
             
             return (True, False)  # Qualified via filters

        # 1. Check registered users
        bypass_users = set()  # Users receiving via notification bypass
        for chat_id, min_threshold in user_filters.items():
            qualified, is_bypass = check_user(chat_id, min_threshold)
            if qualified:
                recipients.add(chat_id)
                if is_bypass:
                    bypass_users.add(chat_id)
        
        # 2. Check if Twitter wants this trade (independent of Telegram)
        # Use wants_trade (filters only) - post_trade_alert will handle queue/rate limits
        twitter_service = get_twitter_service()
        twitter_wants = False
        twitter_reason = ""
        if twitter_service:
            twitter_wants, twitter_reason = twitter_service.wants_trade(trade_data)
            if not twitter_wants:
                trader_id = trade_data.get('name') or trade_data.get('trader_address', '')[:10]
                logger.info(f"Twitter skipped trade: {twitter_reason} (trader: {trader_id}..., value: ${value_usd:,.0f}, price: {price*100:.1f}%)")
        
        # If no one wants this trade (neither Telegram nor Twitter), stop here!
        if not recipients and not twitter_wants:
            return 
            
        # --- End Optimization ---
        
        emoji = alert_config['emoji']
        # side already defined above
        outcome = trade_data.get('outcome', '')
        trader_address = trade_data.get('proxyWallet', '') or trade_data.get('maker', '')
        trader = trade_data.get('name') or trade_data.get('pseudonym') or trader_address or 'Unknown'
        
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
        # Check if we already fetched them in the Insider Alerts block
        if poly_service and trader_address:
            if pos_data is None:
                pos_data = await poly_service.get_trader_positions(trader_address)
            if first_activity_ts is None:
                first_activity_ts = await poly_service.get_trader_first_activity(trader_address)

        # RE-CHECK TWITTER: Now that we have expensive stats (Age, Positions), 
        # we might qualify for "Insider" Twitter alerts that were skipped initially.
        if twitter_service and not twitter_wants:
            # Inject stats into trade_data
            if pos_data:
                trade_data['open_positions_count'] = pos_data.get('open_count', 999)
            
            if first_activity_ts:
                # Format exactly as Twitter service expects (stripped string)
                raw_age = format_wallet_age(first_activity_ts).replace('\n🕐 Wallet Age: ', '')
                trade_data['wallet_age_str'] = raw_age
            
            # check again
            twitter_wants, new_reason = twitter_service.wants_trade(trade_data)
            if twitter_wants:
                logger.info(f"Twitter ACCEPTED trade after fetching stats (was: {twitter_reason})")
            else:
                # Debug: log why re-check still failed
                logger.info(f"Twitter re-check still rejected: {new_reason} (wallet_age_str={trade_data.get('wallet_age_str')}, pos_count={trade_data.get('open_positions_count')})")

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
             # Check if this is a bypass notification - bypass users skip ALL filters
             is_bypass = chat_id in bypass_users
             
             # Only apply wallet age and positions filters for non-bypass users
             if not is_bypass:
                 # Check wallet age filter (after other filters, data already fetched)
                 age_filter = get_user_wallet_age_filter(chat_id)
                 if age_filter and first_activity_ts:
                     age_days = (time.time() - first_activity_ts) / 86400
                     min_days = age_filter.get('min_days')
                     max_days = age_filter.get('max_days')
                     
                     if min_days is not None and age_days < min_days:
                         continue  # Skip this user
                     if max_days is not None and age_days > max_days:
                         continue  # Skip this user
                 
                 # Check open positions filter (after other filters, data already fetched)
                 positions_filter = get_user_open_positions_filter(chat_id)
                 if positions_filter and pos_data:
                     open_count = pos_data.get('open_count', 0)
                     min_count = positions_filter.get('min_count')
                     max_count = positions_filter.get('max_count')
                     
                     if min_count is not None and open_count < min_count:
                         continue  # Skip this user
                     if max_count is not None and open_count > max_count:
                         continue  # Skip this user
             
             # Localization per user
             lang = get_user_lang(chat_id)
             level_emoji = get_trade_level_emoji(lang, alert_config['min'])
             
             # Check if trader is saved by this user
             is_saved = saved_whales.is_saved(chat_id, trader_address) if trader_address else False
             
             # Shorten trader name/address for display
             display_trader = shorten_trader_name(trader)
             trader_text = f"[{display_trader}]({trader_url})" if trader_url else display_trader
             

             
             # Format side_display - skip price % for SPLIT/MERGE/REDEEM
             if is_split or is_merge or is_redeem:
                 side_line = f"{side_display}\n"
             else:
                 side_line = f"{side_display} @ {price_pct:.1f}%\n"
             
             # Add bypass indicator (is_bypass already defined at start of loop)
             bypass_indicator = " 🔔" if is_bypass else ""
             
             msg = (
                f"{cat_emoji} [{market_title[:80]}]({market_url})\n"
                f"{side_line}"
                f"💵 {money_text}\n"
                f"{level_emoji} {trader_text}{bypass_indicator}{position_stats_line}{wallet_age_line}\n"
            )
             # Get level icon for button
             level_icon = get_trade_level_icon(alert_config['min'])
             if is_bypass:
                 logger.info(
                     f"Sending BYPASS alert to chat_id={chat_id} "
                     f"trader={trader_address[:10]}... value=${value_usd:,.0f} "
                     f"market={market_title[:50]}"
                 )
             await enqueue_trade_alert(chat_id, msg, whale_key=whale_key, is_saved=is_saved, level_icon=level_icon)
        
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
                'wallet_age_str': format_wallet_age(first_activity_ts).replace('\n🕐 Wallet Age: ', '') if first_activity_ts else '',
                'open_positions_count': pos_data.get('open_count', 999) if pos_data else 999
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

async def monitor_memory():
    """Monitor memory usage and send alerts to admin if threshold exceeded."""
    global _last_memory_warning_time
    
    while True:
        try:
            # Get memory usage
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Get system memory info
            system_memory = psutil.virtual_memory()
            system_memory_percent = system_memory.percent
            
            # Use the higher of process or system memory
            current_percent = max(memory_percent, system_memory_percent)
            
            now = time.time()
            warning_sent = False
            
            # Check critical threshold (95%)
            if current_percent >= MEMORY_CRITICAL_THRESHOLD:
                last_warn = _last_memory_warning_time.get('critical', 0)
                # Send warning max once per hour
                if now - last_warn >= 3600:
                    memory_mb = memory_info.rss / 1024 / 1024
                    system_total_gb = system_memory.total / 1024 / 1024 / 1024
                    system_used_gb = system_memory.used / 1024 / 1024 / 1024
                    
                    message = (
                        f"🚨 **CRITICAL: High Memory Usage**\n\n"
                        f"Process memory: {memory_mb:.1f} MB ({memory_percent:.1f}%)\n"
                        f"System memory: {system_used_gb:.1f} GB / {system_total_gb:.1f} GB ({system_memory_percent:.1f}%)\n"
                        f"**Current usage: {current_percent:.1f}%**\n\n"
                        f"⚠️ Bot may become unstable!"
                    )
                    await send_admin_notification(message)
                    _last_memory_warning_time['critical'] = now
                    warning_sent = True
                    logger.warning(f"CRITICAL memory usage: {current_percent:.1f}%")
            
            # Check warning threshold (85%)
            elif current_percent >= MEMORY_WARNING_THRESHOLD:
                last_warn = _last_memory_warning_time.get('warning', 0)
                # Send warning max once per 2 hours
                if now - last_warn >= 7200:
                    memory_mb = memory_info.rss / 1024 / 1024
                    system_total_gb = system_memory.total / 1024 / 1024 / 1024
                    system_used_gb = system_memory.used / 1024 / 1024 / 1024
                    
                    message = (
                        f"⚠️ **Memory Usage Warning**\n\n"
                        f"Process memory: {memory_mb:.1f} MB ({memory_percent:.1f}%)\n"
                        f"System memory: {system_used_gb:.1f} GB / {system_total_gb:.1f} GB ({system_memory_percent:.1f}%)\n"
                        f"**Current usage: {current_percent:.1f}%**\n\n"
                        f"Consider monitoring or restarting the bot."
                    )
                    await send_admin_notification(message)
                    _last_memory_warning_time['warning'] = now
                    warning_sent = True
                    logger.warning(f"High memory usage: {current_percent:.1f}%")
            
            # If memory dropped below warning threshold, reset warning timers
            if current_percent < MEMORY_WARNING_THRESHOLD:
                if 'warning' in _last_memory_warning_time:
                    del _last_memory_warning_time['warning']
                if 'critical' in _last_memory_warning_time:
                    del _last_memory_warning_time['critical']
            
            if not warning_sent:
                logger.debug(f"Memory check: {current_percent:.1f}% (OK)")
            
        except Exception as e:
            logger.error(f"Error in memory monitoring: {e}")
        
        await asyncio.sleep(MEMORY_CHECK_INTERVAL)


async def daily_report_scheduler():
    """Schedule daily report at 12:00."""
    while True:
        try:
            now = datetime.now()
            # Calculate next 12:00
            target_time = dt_time(12, 0)
            
            if now.time() < target_time:
                # Today at 12:00
                next_report = datetime.combine(now.date(), target_time)
            else:
                # Tomorrow at 12:00
                next_report = datetime.combine(now.date() + timedelta(days=1), target_time)
            
            wait_seconds = (next_report - now).total_seconds()
            
            logger.info(f"Next daily report scheduled for {next_report.strftime('%Y-%m-%d %H:%M:%S')} (in {wait_seconds/3600:.1f} hours)")
            
            await asyncio.sleep(wait_seconds)
            
            # Generate and send report
            report = generate_report(poly_service)
            await send_admin_notification(report)
            logger.info("Daily report sent")
            
        except Exception as e:
            logger.error(f"Error in daily report scheduler: {e}")
            # Wait 1 hour before retry on error
            await asyncio.sleep(3600)

async def check_insider_scenarios_periodically():
    """Check for insider patterns every 5 minutes."""
    while True:
        try:
            if insider_alerts_service:
                await insider_alerts_service.check_all_markets()
        except Exception as e:
            logger.error(f"Error checking insider scenarios: {e}")
        
        await asyncio.sleep(300)  # 5 minutes

async def start_insider_collector():
    """Start all background tasks and return list of tasks."""
    tasks = []
    
    # Start Telegram in background
    tg_task = asyncio.create_task(start_telegram())
    tasks.append(tg_task)
    
    # Start Polymarket Service
    global poly_service
    poly_service = PolymarketService()
    
    # Store reference in telegram service for /report command
    set_poly_service(poly_service)
    
    # Store reference in status service for dashboard
    set_status_poly_service(poly_service)
    
    # Initialize Insider Alerts Service
    global insider_alerts_service
    insider_alerts_service = InsiderAlertsService()
    insider_alerts_service.set_poly_service(poly_service)  # For position verification before alerts
    # Pass bot reference (after telegram starts, we'll set it in telegram_service.py)
    set_global_insider_alerts_service(insider_alerts_service)
    set_insider_alerts_service(insider_alerts_service)  # For telegram_service.py commands
    set_status_insider_service(insider_alerts_service)  # For status dashboard
    logger.info("Insider alerts service initialized")
    
    logger.info("Starting PolyWhales...")
    logger.info("Using Polymarket Data API for whale trades...")
    
    # Run Polymarket trade polling (uses POLL_INTERVAL from polymarket.py)
    trade_polling_task = asyncio.create_task(poly_service.poll_trades(handle_trade))
    tasks.append(trade_polling_task)
    
    # SPLIT/MERGE/REDEEM activity polling (enabled)
    activity_polling_task = asyncio.create_task(poly_service.poll_activities(handle_trade))
    tasks.append(activity_polling_task)
    
    # Start Twitter queue processor (if Twitter is configured)
    twitter_service = get_twitter_service()
    if twitter_service and twitter_service.is_configured:
        twitter_queue_task = asyncio.create_task(twitter_service.process_queue_periodically(interval=60))
        tasks.append(twitter_queue_task)
    
    # Start insider alerts scenario checker
    if insider_alerts_service:
        insider_check_task = asyncio.create_task(check_insider_scenarios_periodically())
        tasks.append(insider_check_task)
        logger.info("Insider alerts scenario checker started")
    
    # Start memory monitoring
    memory_monitor_task = asyncio.create_task(monitor_memory())
    tasks.append(memory_monitor_task)
    logger.info("Memory monitoring started")
    
    # Start daily report scheduler
    daily_report_task = asyncio.create_task(daily_report_scheduler())
    tasks.append(daily_report_task)
    logger.info("Daily report scheduler started")
    
    return tasks

async def main():
    # Ensure single instance
    lock_handle = single_instance_check()
    
    # Set bot start time for uptime tracking
    set_status_start_time(time.time())
    
    # Initialize saved whales DB
    saved_whales.init_db()
    
    # Start status dashboard server
    status_port = int(os.getenv("STATUS_PORT", "5000"))
    if os.getenv("STATUS_ENABLED", "true").lower() != "false":
        start_status_server(port=status_port)
        logger.info(f"Status dashboard available at http://0.0.0.0:{status_port}")

    # Start all background tasks
    tasks = await start_insider_collector()
    
    # Wait for all tasks with proper cleanup
    try:
        await asyncio.gather(*tasks)
    finally:
        # Stop queue workers gracefully
        await stop_queue_workers()
        
        # Cleanup: cancel all tasks
        for task in tasks:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("All tasks cancelled and cleaned up")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
