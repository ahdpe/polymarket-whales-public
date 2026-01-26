from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
import asyncio
import logging
import hashlib
import time
import re
from datetime import datetime
import html

# Try to import aiolimiter, fallback if not available
_aiolimiter_available = False
try:
    from aiolimiter import AsyncLimiter
    import aiolimiter
    _aiolimiter_available = True
    _aiolimiter_version = getattr(aiolimiter, '__version__', 'unknown')
except ImportError:
    AsyncLimiter = None
    _aiolimiter_version = None
from config import (
    TELEGRAM_BOT_TOKEN, FILTERS, OWNER_ID,
    RETRY_SHORT_MAX, MUTE_DURATIONS, FAIL_STREAK_MUTE_THRESHOLD,
    HOTFIX_CHAT_ID, HOTFIX_THRESHOLD, HOTFIX_MUTE,
    QUEUE_MAX_SIZE, WORKER_COUNT, GLOBAL_RATE, PER_CHAT_RATE
)
from core.localization import get_text
from core.utils import shorten_trader_name
from storage import saved_whales
from services.report_service import generate_report

# Global reference to PolymarketService instance (set during startup)
_poly_service = None

def set_poly_service(service):
    """Store reference to PolymarketService for report generation."""
    global _poly_service
    _poly_service = service

# Global reference to InsiderAlertsService (set during startup)
_insider_alerts_service = None

def set_insider_alerts_service(service):
    """Store reference to InsiderAlertsService for admin commands."""
    global _insider_alerts_service
    _insider_alerts_service = service
    # Set bot reference for publishing alerts
    if service:
        service.set_bot(bot)

# FSM States for note input
class NoteState(StatesGroup):
    waiting_for_note = State()

# FSM States for manual trader addition
class ManualAddState(StatesGroup):
    waiting_for_input = State()

# FSM States for age and positions filter input
class AgeFilterState(StatesGroup):
    waiting_for_range = State()

class PositionsFilterState(StatesGroup):
    waiting_for_range = State()

class ProbabilityFilterState(StatesGroup):
    waiting_for_range = State()

# Max comment length
MAX_COMMENT_LEN = 240

logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Settings file path
import os
import json
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'user_settings.json')

def load_settings():
    """Load user settings from file."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to int
                filters = {int(k): v for k, v in data.get('filters', {}).items()}
                categories = {int(k): v for k, v in data.get('categories', {}).items()}
                languages = {int(k): v for k, v in data.get('languages', {}).items()}
                statuses = {int(k): v for k, v in data.get('statuses', {}).items()}
                usernames = {int(k): v for k, v in data.get('usernames', {}).items()}
                probabilities = {int(k): v for k, v in data.get('probabilities', {}).items()}
                side_types = {int(k): v for k, v in data.get('side_types', {}).items()}
                wallet_ages = {int(k): v for k, v in data.get('wallet_ages', {}).items()}
                open_positions = {int(k): v for k, v in data.get('open_positions', {}).items()}
                blocked_users = {int(k): v for k, v in data.get('blocked_users', {}).items()}  # Track blocked users
                bot_enabled = data.get('bot_enabled', True)  # Default: enabled
                return filters, categories, languages, statuses, usernames, probabilities, side_types, wallet_ages, open_positions, blocked_users, bot_enabled
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
    return {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, True  # Default: enabled

def save_settings():
    """Save user settings to file."""
    try:
        data = {
            'filters': {str(k): v for k, v in user_filters.items()},
            'categories': {str(k): v for k, v in user_categories.items()},
            'languages': {str(k): v for k, v in user_languages.items()},
            'statuses': {str(k): v for k, v in user_statuses.items()},
            'usernames': {str(k): v for k, v in user_usernames.items()},
            'probabilities': {str(k): v for k, v in user_probabilities.items()},
            'side_types': {str(k): v for k, v in user_side_types.items()},
            'wallet_ages': {str(k): v for k, v in user_wallet_ages.items()},
            'open_positions': {str(k): v for k, v in user_open_positions.items()},
            'blocked_users': {str(k): v for k, v in blocked_users.items()},  # Save blocked users
            'bot_enabled': bot_enabled
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

# Load settings on startup
user_filters, user_categories, user_languages, user_statuses, user_usernames, user_probabilities, user_side_types, user_wallet_ages, user_open_positions, blocked_users, bot_enabled = load_settings()

# Auto-mute structures for problematic chat_ids
muted_until = {}  # dict[int, float] - chat_id -> unix timestamp until muted
fail_streak = {}  # dict[int, int] - consecutive failures per chat_id
mute_level = {}  # dict[int, int] - mute escalation level (0/1/2/3)
last_fail_reason = {}  # dict[int, str] - for diagnostics
last_mute_time = {}  # dict[int, float] - timestamp of last mute (for 24h reset logic)

# Mute state file path
MUTE_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'mute_state.json')

def load_mute_state():
    """Load mute state from file."""
    try:
        if os.path.exists(MUTE_STATE_FILE):
            with open(MUTE_STATE_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to int
                muted_until.update({int(k): v for k, v in data.get('muted_until', {}).items()})
                fail_streak.update({int(k): v for k, v in data.get('fail_streak', {}).items()})
                mute_level.update({int(k): v for k, v in data.get('mute_level', {}).items()})
                last_mute_time.update({int(k): v for k, v in data.get('last_mute_time', {}).items()})
                logger.info(f"Loaded mute state: {len(muted_until)} muted, {len(fail_streak)} streaks")
    except Exception as e:
        logger.error(f"Error loading mute state: {e}")

def save_mute_state():
    """Save mute state to file (atomic write)."""
    try:
        # Ensure data directory exists
        os.makedirs(os.path.dirname(MUTE_STATE_FILE), exist_ok=True)
        
        # Prepare data
        data = {
            'muted_until': {str(k): v for k, v in muted_until.items()},
            'fail_streak': {str(k): v for k, v in fail_streak.items()},
            'mute_level': {str(k): v for k, v in mute_level.items()},
            'last_mute_time': {str(k): v for k, v in last_mute_time.items()},
        }
        
        # Atomic write: write to temp file, then rename
        temp_file = MUTE_STATE_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(data, f)
        os.replace(temp_file, MUTE_STATE_FILE)
    except Exception as e:
        logger.error(f"Error saving mute state: {e}")

def load_mute_state():
    """Load mute state from file."""
    try:
        if os.path.exists(MUTE_STATE_FILE):
            with open(MUTE_STATE_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to int
                muted_until.update({int(k): v for k, v in data.get('muted_until', {}).items()})
                fail_streak.update({int(k): v for k, v in data.get('fail_streak', {}).items()})
                mute_level.update({int(k): v for k, v in data.get('mute_level', {}).items()})
                last_mute_time.update({int(k): v for k, v in data.get('last_mute_time', {}).items()})
                logger.info(f"Loaded mute state: {len(muted_until)} muted, {len(fail_streak)} streaks")
    except Exception as e:
        logger.error(f"Error loading mute state: {e}")

def save_mute_state():
    """Save mute state to file (atomic write)."""
    try:
        # Ensure data directory exists
        os.makedirs(os.path.dirname(MUTE_STATE_FILE), exist_ok=True)
        
        # Prepare data
        data = {
            'muted_until': {str(k): v for k, v in muted_until.items()},
            'fail_streak': {str(k): v for k, v in fail_streak.items()},
            'mute_level': {str(k): v for k, v in mute_level.items()},
            'last_mute_time': {str(k): v for k, v in last_mute_time.items()},
        }
        
        # Atomic write: write to temp file, then rename
        temp_file = MUTE_STATE_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(data, f)
        os.replace(temp_file, MUTE_STATE_FILE)
    except Exception as e:
        logger.error(f"Error saving mute state: {e}")

def cleanup_mute_state():
    """Clean up old mute state entries to prevent memory bloat."""
    now = time.time()
    cleaned = 0
    
    # Remove expired mutes and zero streaks older than 24h
    for chat_id in list(muted_until.keys()):
        if now > muted_until[chat_id] + 86400:  # 24h after mute expired
            muted_until.pop(chat_id, None)
            if fail_streak.get(chat_id, 0) == 0:
                fail_streak.pop(chat_id, None)
                mute_level.pop(chat_id, None)
                last_mute_time.pop(chat_id, None)
                last_fail_reason.pop(chat_id, None)
                cleaned += 1
    
    if cleaned > 0:
        logger.info(f"🧹 Cleaned up {cleaned} old mute state entries")
        save_mute_state()

# Mute duration constants (loaded from config)
# MUTE_DURATIONS imported from config

# Statistics tracking
_stats_lock = asyncio.Lock()
_stats_reset_time = time.time()

# Queue system for sending alerts
alert_queue = None  # Will be initialized in start_telegram()
worker_tasks = []  # List of worker tasks for graceful shutdown
queue_stats = {
    'sent_total': 0,
    'dropped_total': 0,
    'error_total': 0,
    'sent_per_min': 0,
    'dropped_per_min': 0,
    'retryafter_min': 0,  # Changed from retryafter_per_min to retryafter_min
}
_queue_stats_lock = asyncio.Lock()
_queue_stats_reset_time = time.time()

# Track oldest task age
_queue_oldest_enqueued = None  # Timestamp of oldest task in queue
_queue_oldest_lock = asyncio.Lock()  # Lock for oldest tracking

# Track queue lag warnings
_queue_lag_warn_count = 0  # Consecutive minutes with lag > 120s

# Rate limiters
global_rate_limiter = None  # Will be initialized in start_telegram()
_per_chat_next_send = {}  # dict[chat_id, float] - next allowed send time
_per_chat_lock = asyncio.Lock()  # Lock for per_chat_next_send

# Queue enabled flag
_queue_enabled = False

def is_bot_enabled():
    """Check if bot is enabled (not stopped by admin)."""
    return bot_enabled

def set_bot_enabled(enabled):
    """Set bot enabled state (admin only)."""
    global bot_enabled
    bot_enabled = enabled
    save_settings()

# Probability filter options: (min, max) or None for any
PROBABILITY_OPTIONS = {
    'any': None,
    '1_99': (0.01, 0.99),
    '5_95': (0.05, 0.95),
    '10_90': (0.10, 0.90),
}

def get_default_categories():
    """Default category preferences - all enabled."""
    return {'all': False, 'other': True, 'crypto': True, 'sports': False}

def get_default_side_types():
    """Default side type preferences - only BUY and SELL enabled."""
    return {'all': False, 'BUY': True, 'SELL': True, 'SPLIT': False, 'MERGE': False, 'REDEEM': False}

def ensure_user_exists(chat_id):
    """Ensure user has all necessary settings initialized."""
    chat_id = int(chat_id) # Strict type coercion
    
    # If user sends a message, they're not blocked anymore - remove from blocked list
    if chat_id in blocked_users:
        logger.info(f"✅ User {chat_id} unblocked the bot (sent a message)")
        del blocked_users[chat_id]
        save_settings()
    
    if chat_id not in user_filters:
        logger.info(f"Initialized filters for new/reset user {chat_id}")
        user_filters[chat_id] = 50000  # Default to $50k
    
    if chat_id not in user_categories:
        logger.info(f"Initialized categories for new/reset user {chat_id}")
        user_categories[chat_id] = get_default_categories()
        
    if chat_id not in user_languages:
        user_languages[chat_id] = 'en'  # Default: English
        
    if chat_id not in user_statuses:
        user_statuses[chat_id] = False  # Default: Stopped (user must start manually)
    
    if chat_id not in user_probabilities:
        user_probabilities[chat_id] = '1_99'  # Default: 1-99% probability filter
    
    if chat_id not in user_side_types:
        logger.info(f"Initialized side types for new/reset user {chat_id}")
        user_side_types[chat_id] = get_default_side_types()
    
    if chat_id not in user_wallet_ages:
        user_wallet_ages[chat_id] = {'min_days': None, 'max_days': None}  # Default: unlimited
    
    if chat_id not in user_open_positions:
        user_open_positions[chat_id] = {'min_count': None, 'max_count': None}  # Default: unlimited

def get_user_lang(chat_id):
    """Get user's language preference."""
    return user_languages.get(chat_id, 'en')

def get_language_button_text(current_lang: str) -> str:
    """Get language button text - English always first as primary language."""
    # English is primary, always show first
    return "🇬🇧 / 🇷🇺"

def is_user_active(chat_id):
    """Check if user bot is active (started)."""
    return user_statuses.get(chat_id, False)  # Default False (Stopped)

def get_main_keyboard(chat_id):
    """Create persistent keyboard at bottom of chat."""
    lang = get_user_lang(chat_id)
    active = is_user_active(chat_id)
    
    # Toggle button text
    btn_toggle = get_text(lang, 'btn_stop') if active else get_text(lang, 'btn_start')
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=btn_toggle),
             KeyboardButton(text=get_text(lang, 'btn_filters')),
             KeyboardButton(text=get_text(lang, 'btn_saved'))]
        ],
        resize_keyboard=True
    )

def get_filters_keyboard(chat_id):
    """Create keyboard for filters submenu."""
    lang = get_user_lang(chat_id)
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(lang, 'btn_amount')),
             KeyboardButton(text=get_text(lang, 'btn_categories')),
             KeyboardButton(text=get_text(lang, 'btn_probability'))],
            [KeyboardButton(text=get_text(lang, 'btn_sides')),
             KeyboardButton(text=get_text(lang, 'btn_age')),
             KeyboardButton(text=get_text(lang, 'btn_positions'))],
            [KeyboardButton(text=get_text(lang, 'btn_back'))]
        ],
        resize_keyboard=True
    )

def get_collapsed_keyboard(chat_id):
    """Create minimal keyboard with only 'Show Menu' button."""
    lang = get_user_lang(chat_id)
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(lang, 'btn_show_menu'))]
        ],
        resize_keyboard=True
    )

def get_amount_keyboard(chat_id):
    """Create inline keyboard for amount filter selection."""
    lang = get_user_lang(chat_id)
    current_min = user_filters.get(chat_id, 50000)  # Default $50k
    
    buttons = []
    
    for f in FILTERS:
        # Use localized emoji based on language
        emoji = f.get('emoji_en', f['emoji']) if lang == 'en' else f['emoji']
        text = f"{emoji} >${f['min']:,}"
        if f['min'] == current_min:
            text = f"✅ {text}"
            
        btn = InlineKeyboardButton(text=text, callback_data=f"filter_{f['min']}")
        buttons.append([btn])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_amount_confirm_keyboard(chat_id):
    """Create inline keyboard for $500 filter confirmation."""
    lang = get_user_lang(chat_id)
    buttons = [
        [InlineKeyboardButton(
            text=get_text(lang, 'amount_confirm_yes'),
            callback_data="confirm_filter_500"
        )],
        [InlineKeyboardButton(
            text=get_text(lang, 'amount_confirm_no'),
            callback_data="cancel_filter_500"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_probability_keyboard(chat_id):
    """Create inline keyboard for probability filter selection."""
    lang = get_user_lang(chat_id)
    current = user_probabilities.get(chat_id, 'any')
    
    options = [
        ('any', get_text(lang, 'prob_any')),
        ('1_99', get_text(lang, 'prob_1_99')),
        ('5_95', get_text(lang, 'prob_5_95')),
        ('10_90', get_text(lang, 'prob_10_90')),
    ]
    
    buttons = []
    standard_keys = [opt[0] for opt in options]
    
    for key, label in options:
        text = f"✅ {label}" if key == current else label
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"prob_{key}")])
    
    # Custom button
    custom_text = get_text(lang, 'prob_custom')
    if current not in standard_keys:
        custom_text = f"✅ {current.replace('_', '-')}%"
        
    buttons.append([InlineKeyboardButton(text=custom_text, callback_data="prob_custom")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_age_keyboard(chat_id):
    """Create inline keyboard for wallet age filter selection."""
    lang = get_user_lang(chat_id)
    current = user_wallet_ages.get(chat_id, {'min_days': None, 'max_days': None})
    
    # Check if filter is set (not unlimited)
    is_unlimited = current.get('min_days') is None and current.get('max_days') is None
    
    buttons = []
    
    # "Any" option
    any_text = get_text(lang, 'age_any')
    if is_unlimited:
        any_text = f"✅ {any_text}"
    buttons.append([InlineKeyboardButton(text=any_text, callback_data="age_any")])
    
    # "Set interval" option
    custom_text = get_text(lang, 'age_custom')
    if not is_unlimited:
        custom_text = f"✅ {custom_text}"
    buttons.append([InlineKeyboardButton(text=custom_text, callback_data="age_custom")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_positions_keyboard(chat_id):
    """Create inline keyboard for open positions filter selection."""
    lang = get_user_lang(chat_id)
    current = user_open_positions.get(chat_id, {'min_count': None, 'max_count': None})
    
    # Check if filter is set (not unlimited)
    is_unlimited = current.get('min_count') is None and current.get('max_count') is None
    
    buttons = []
    
    # "Any" option
    any_text = get_text(lang, 'pos_any')
    if is_unlimited:
        any_text = f"✅ {any_text}"
    buttons.append([InlineKeyboardButton(text=any_text, callback_data="pos_any")])
    
    # "Set interval" option
    custom_text = get_text(lang, 'pos_custom')
    if not is_unlimited:
        custom_text = f"✅ {custom_text}"
    buttons.append([InlineKeyboardButton(text=custom_text, callback_data="pos_custom")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_age_range(age_filter, lang):
    """Format age filter range for display."""
    min_days = age_filter.get('min_days')
    max_days = age_filter.get('max_days')
    
    if min_days is None and max_days is None:
        return get_text(lang, 'age_any')
    
    days_text = get_text(lang, 'days')
    
    if min_days is not None and max_days is not None:
        return f"{int(min_days)}-{int(max_days)} {days_text}"
    elif min_days is not None:
        return f">={int(min_days)} {days_text}"
    elif max_days is not None:
        return f"<={int(max_days)} {days_text}"
    
    return get_text(lang, 'age_any')

def format_positions_range(pos_filter, lang):
    """Format positions filter range for display."""
    min_count = pos_filter.get('min_count')
    max_count = pos_filter.get('max_count')
    
    if min_count is None and max_count is None:
        return get_text(lang, 'pos_any')
    
    if min_count is not None and max_count is not None:
        return f"{int(min_count)}-{int(max_count)}"
    elif min_count is not None:
        return f">={int(min_count)}"
    elif max_count is not None:
        return f"<={int(max_count)}"
    
    return get_text(lang, 'pos_any')


def get_categories_keyboard(chat_id):
    """Create inline keyboard for category selection."""
    lang = get_user_lang(chat_id)
    prefs = user_categories.get(chat_id, get_default_categories())
    
    def check(key):
        return "✅" if prefs.get(key, True) else "⬜"
    
    buttons = [
        [InlineKeyboardButton(
            text=f"{check('all')} {get_text(lang, 'settings_all')}",
            callback_data="cat_all"
        )],
        [InlineKeyboardButton(
            text=f"{check('other')} {get_text(lang, 'settings_other')}",
            callback_data="cat_other"
        )],
        [InlineKeyboardButton(
            text=f"{check('crypto')} {get_text(lang, 'settings_crypto')}",
            callback_data="cat_crypto"
        )],
        [InlineKeyboardButton(
            text=f"{check('sports')} {get_text(lang, 'settings_sports')}",
            callback_data="cat_sports"
        )],
        [InlineKeyboardButton(
            text=get_text(lang, 'settings_done'),
            callback_data="cat_done"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_side_types_keyboard(chat_id):
    """Create inline keyboard for side type selection."""
    lang = get_user_lang(chat_id)
    prefs = user_side_types.get(chat_id, get_default_side_types())
    
    def check(key):
        return "✅" if prefs.get(key, True) else "⬜"
    
    buttons = [
        [InlineKeyboardButton(
            text=f"{check('all')} {get_text(lang, 'side_all')}",
            callback_data="side_all"
        )],
        [InlineKeyboardButton(
            text=f"{check('BUY')} {get_text(lang, 'side_buy')}",
            callback_data="side_BUY"
        )],
        [InlineKeyboardButton(
            text=f"{check('SELL')} {get_text(lang, 'side_sell')}",
            callback_data="side_SELL"
        )],
        [InlineKeyboardButton(
            text=f"{check('SPLIT')} {get_text(lang, 'side_split')}",
            callback_data="side_SPLIT"
        )],
        [InlineKeyboardButton(
            text=f"{check('MERGE')} {get_text(lang, 'side_merge')}",
            callback_data="side_MERGE"
        )],
        [InlineKeyboardButton(
            text=f"{check('REDEEM')} {get_text(lang, 'side_redeem')}",
            callback_data="side_REDEEM"
        )],
        [InlineKeyboardButton(
            text=get_text(lang, 'settings_done'),
            callback_data="side_done"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    # Save username/name
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    user_usernames[chat_id] = username
    
    ensure_user_exists(chat_id)
    # Force active on start command
    user_statuses[chat_id] = True
    save_settings()
    
    lang = get_user_lang(chat_id)
    await message.answer(
        get_text(lang, 'welcome', chat_id=chat_id),
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(chat_id)
    )
    logger.info(f"User started bot. Chat ID: {chat_id}")

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    """Generate and send report on demand (admin only)."""
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return  # Only owner can request reports
    
    # Send "Generating report..." message
    status_msg = await message.answer("⏳ Генерирую отчет...")
    
    try:
        report = generate_report(_poly_service)
        await message.answer(report, parse_mode="HTML")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error in /report command: {e}")
        await message.answer(f"❌ Ошибка генерации отчета: {e}")

@dp.message(Command("amount"))
async def cmd_amount(message: types.Message):
    """Show amount filter menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
        
    await message.answer(
        get_text(lang, 'amount_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_amount_keyboard(chat_id)
    )

@dp.message(Command("categories"))
async def cmd_categories(message: types.Message):
    """Show categories menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
        
    await message.answer(
        get_text(lang, 'categories_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_categories_keyboard(chat_id)
    )

@dp.message(Command("probability"))
async def cmd_probability(message: types.Message):
    """Show probability filter menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
        
    await message.answer(
        get_text(lang, 'probability_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_probability_keyboard(chat_id)
    )

@dp.message(Command("tlgrm_prob"))
async def cmd_tlgrm_prob(message: types.Message):
    """
    Handle /tlgrm_prob command (GLOBAL Insider Alerts filter).
    Usage:
    - /tlgrm_prob 10 90 (sets range 10-90%)
    - /tlgrm_prob 0 (resets to 0-100%)
    """
    if message.chat.id != OWNER_ID:
        return
        
    if not _insider_alerts_service:
        await message.answer("❌ Service not initialized")
        return
        
    # Get arguments
    args = message.text.replace("/tlgrm_prob", "", 1).strip()
    
    if not args:
        # Show current setting
        status = _insider_alerts_service.get_status()
        p_min = status.get('probability_min', '0')
        p_max = status.get('probability_max', '100')
        await message.answer(f"📊 Global Insider Probability: **{p_min}% - {p_max}%**", parse_mode="Markdown")
        return
        
    if args == "0" or args.lower() == "any":
        _insider_alerts_service.update_setting('probability_min', '0')
        _insider_alerts_service.update_setting('probability_max', '100')
        await message.answer("✅ Global Insider Probability reset to **0% - 100%**", parse_mode="Markdown")
        return
        
    try:
        valid_ranges = parse_probability_ranges(args)
        if not valid_ranges or len(valid_ranges) > 1:
            raise ValueError("Only single range supported for global filter")
            
        r = valid_ranges[0]
        _insider_alerts_service.update_setting('probability_min', str(r[0]))
        _insider_alerts_service.update_setting('probability_max', str(r[1]))
        
        await message.answer(
            f"✅ Global Insider Probability set to **{r[0]}% - {r[1]}%**",
            parse_mode="Markdown"
        )
        
    except ValueError as e:
        await message.answer(f"❌ Invalid format. Use: `/tlgrm_prob 10 90`", parse_mode="Markdown")

@dp.message(Command("sides"))
async def cmd_sides(message: types.Message):
    """Show side types menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
        
    await message.answer(
        get_text(lang, 'sides_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_side_types_keyboard(chat_id)
    )

# Text handlers for bottom keyboard buttons
@dp.message(F.text.in_(["💰 Сумма сделки", "💰 Trade Amount"]))
async def btn_amount(message: types.Message):
    """Handle Amount button press."""
    await cmd_amount(message)

@dp.message(F.text.in_(["📂 Категории", "📂 Categories"]))
async def btn_categories(message: types.Message):
    """Handle Categories button press."""
    await cmd_categories(message)

@dp.message(F.text.in_(["⚖️ Вероятность", "⚖️ Probability"]))
async def btn_probability(message: types.Message):
    """Handle Probability button press."""
    await cmd_probability(message)

@dp.message(Command("age"))
@dp.message(F.text.in_(["🕐 Возраст", "🕐 Age"]))
async def btn_age(message: types.Message):
    """Handle Age button press - show age filter menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'age_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_age_keyboard(chat_id)
    )

@dp.message(Command("positions"))
@dp.message(F.text.in_(["💼 Позиции", "💼 Positions"]))
async def btn_positions(message: types.Message):
    """Handle Positions button press - show positions filter menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'pos_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_positions_keyboard(chat_id)
    )

@dp.message(F.text.in_(["🔄 Типы событий", "🔄 Event Types"]))
async def btn_sides(message: types.Message):
    """Handle Side Types button press."""
    await cmd_sides(message)

def format_current_filters(chat_id):
    """Format current filter settings for display."""
    lang = get_user_lang(chat_id)
    lines = []
    
    # 1. Amount
    amount = user_filters.get(chat_id, 50000)
    lines.append(f"💰 {'Сумма' if lang == 'ru' else 'Amount'}: ≥${amount:,}")
    
    # 2. Categories
    cats = user_categories.get(chat_id, get_default_categories())
    if cats.get('all'):
        cats_text = get_text(lang, 'settings_all')
    else:
        enabled = []
        if cats.get('crypto'):
            enabled.append(get_text(lang, 'cat_crypto'))
        if cats.get('sports'):
            enabled.append(get_text(lang, 'cat_sports'))
        if cats.get('other'):
            enabled.append(get_text(lang, 'cat_other'))
        cats_text = ", ".join(enabled) if enabled else get_text(lang, 'cat_nothing')
    lines.append(f"📂 {'Категории' if lang == 'ru' else 'Categories'}: {cats_text}")
    
    # 3. Probability
    prob_key = user_probabilities.get(chat_id, '1_99')
    if prob_key in PROBABILITY_OPTIONS:
        prob_text = get_text(lang, f'prob_{prob_key}')
    else:
        # Custom range
        # Format "min_max,min_max" -> "min-max%, min-max%"
        parts = prob_key.split(',')
        formatted_parts = [p.replace('_', '-') + '%' for p in parts]
        prob_text = ", ".join(formatted_parts)
    lines.append(f"⚖️ {'Вероятность' if lang == 'ru' else 'Probability'}: {prob_text}")
    
    # 4. Side types
    sides = user_side_types.get(chat_id, get_default_side_types())
    if sides.get('all'):
        sides_text = get_text(lang, 'side_all')
    else:
        enabled = []
        if sides.get('BUY'):
            enabled.append("BUY")
        if sides.get('SELL'):
            enabled.append("SELL")
        if sides.get('SPLIT'):
            enabled.append("SPLIT")
        if sides.get('MERGE'):
            enabled.append("MERGE")
        if sides.get('REDEEM'):
            enabled.append("REDEEM")
        sides_text = ", ".join(enabled) if enabled else get_text(lang, 'side_nothing')
    lines.append(f"🔄 {'События' if lang == 'ru' else 'Events'}: {sides_text}")
    
    # 5. Wallet Age
    age_filter = user_wallet_ages.get(chat_id, {'min_days': None, 'max_days': None})
    age_text = format_age_range(age_filter, lang)
    lines.append(f"🕐 {'Возраст' if lang == 'ru' else 'Age'}: {age_text}")
    
    # 6. Open Positions
    pos_filter = user_open_positions.get(chat_id, {'min_count': None, 'max_count': None})
    pos_text = format_positions_range(pos_filter, lang)
    lines.append(f"💼 {'Позиции' if lang == 'ru' else 'Positions'}: {pos_text}")
    
    return "\n".join(lines)


@dp.message(F.text.in_(["⚙️ Фильтры", "⚙️ Filters"]))
async def btn_filters(message: types.Message):
    """Handle Filters button press - show filters submenu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    current_filters = format_current_filters(chat_id)
    title = "⚙️ *Фильтры*" if lang == 'ru' else "⚙️ *Filters*"
    subtitle = "📋 *Текущие настройки:*" if lang == 'ru' else "📋 *Current settings:*"
    
    msg_text = f"{title}\n\n{subtitle}\n{current_filters}"
    
    await message.answer(
        msg_text,
        parse_mode="Markdown",
        reply_markup=get_filters_keyboard(chat_id)
    )

@dp.message(Command("back"))
@dp.message(F.text.in_(["⬅️ Назад", "⬅️ Back"]))
async def btn_back(message: types.Message):
    """Handle Back button press - return to main menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'menu_shown'),
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(F.text.in_(["▶️ Запустить", "▶️ Start", "⏸️ Остановить", "⏸️ Stop"]))
async def btn_start_stop(message: types.Message):
    """Handle Start/Stop toggle button."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    active = is_user_active(chat_id)
    
    # Toggle state
    new_state = not active
    user_statuses[chat_id] = new_state
    save_settings()
    
    msg_key = 'bot_started' if new_state else 'bot_stopped'
    
    await message.answer(
        get_text(lang, msg_key),
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(F.text.in_(["🇬🇧 / 🇷🇺"]))
async def btn_language(message: types.Message):
    """Handle Language toggle button."""
    chat_id = message.chat.id
    current_lang = get_user_lang(chat_id)
    
    # Toggle language
    new_lang = 'en' if current_lang == 'ru' else 'ru'
    user_languages[chat_id] = new_lang
    save_settings()
    
    await message.answer(
        get_text(new_lang, 'welcome', chat_id=chat_id),
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(F.text.in_(["ℹ️ О боте", "ℹ️ About"]))
async def btn_about(message: types.Message):
    """Handle About button press."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'about'),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@dp.message(F.text.in_(["⬇️ Скрыть меню", "⬇️ Hide Menu"]))
async def btn_hide_menu(message: types.Message):
    """Handle 'Hide Menu' button."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'menu_hidden'),
        reply_markup=get_collapsed_keyboard(chat_id)
    )

@dp.message(F.text.in_(["⬆️ Показать меню", "⬆️ Show Menu"]))
async def btn_show_menu(message: types.Message):
    """Handle 'Show Menu' button."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'menu_shown'),
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    """Command to show menu."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'menu_shown'),
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    """Command to show about info."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'about'),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    """Command to toggle language."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    current_lang = get_user_lang(chat_id)
    
    # Toggle language
    new_lang = 'en' if current_lang == 'ru' else 'ru'
    user_languages[chat_id] = new_lang
    save_settings()
    
    await message.answer(
        get_text(new_lang, 'welcome', chat_id=chat_id),
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Reset all user settings to default."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    # Reset all filters and settings
    user_filters.pop(chat_id, None)
    user_categories.pop(chat_id, None)
    user_probabilities.pop(chat_id, None)
    user_side_types.pop(chat_id, None)
    user_wallet_ages.pop(chat_id, None)
    user_open_positions.pop(chat_id, None)
    # Note: We do NOT reset language or bot enabled status
    
    save_settings()
    
    await message.answer(get_text(lang, 'reset_done'), parse_mode="Markdown")
    logger.info(f"User {chat_id} reset settings to default")

@dp.message(Command("hide"))
async def cmd_hide(message: types.Message):
    """Command to hide menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    await message.answer(
        get_text(lang, 'menu_hidden'),
        reply_markup=get_collapsed_keyboard(chat_id)
    )

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    """Command to toggle bot state (start/stop alerts)."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    active = is_user_active(chat_id)
    
    # Toggle state
    new_state = not active
    user_statuses[chat_id] = new_state
    save_settings()
    
    msg_key = 'bot_started' if new_state else 'bot_stopped'
    
    await message.answer(
        get_text(lang, msg_key),
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(chat_id)
    )

@dp.message(Command("filters"))
async def cmd_filters(message: types.Message):
    """Command to show filters menu."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    current_filters = format_current_filters(chat_id)
    title = "⚙️ *Фильтры*" if lang == 'ru' else "⚙️ *Filters*"
    subtitle = "📋 *Текущие настройки:*" if lang == 'ru' else "📋 *Current settings:*"
    
    msg_text = f"{title}\n\n{subtitle}\n{current_filters}"
    
    await message.answer(
        msg_text,
        parse_mode="Markdown",
        reply_markup=get_filters_keyboard(chat_id)
    )

@dp.message(Command("saved"))
async def cmd_saved(message: types.Message):
    """Command to show saved traders list."""
    chat_id = message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    text, reply_markup = get_aquarium_list(chat_id, 0)
    
    if text:
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        # Empty list - show add button
        add_text = get_text(lang, 'manual_add_btn')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=add_text, callback_data="manual_add:0:view")]
        ])
        await message.answer(get_text(lang, 'saved_empty'), reply_markup=keyboard)


# ============ SAVED TRADERS HANDLERS (LIST + EDIT MODE) ============

AQUARIUM_PAGE_SIZE = 10

def get_aquarium_list(chat_id, page=0, edit_mode=False):
    """
    Generate text list and keyboard for Aquarium.
    Supports View Mode and Edit Mode.
    """
    lang = get_user_lang(chat_id)
    offset = page * AQUARIUM_PAGE_SIZE
    saved = saved_whales.list_saved(chat_id, offset=offset, limit=AQUARIUM_PAGE_SIZE)
    total = saved_whales.count_saved(chat_id)
    
    if not saved and page > 0:
        return get_aquarium_list(chat_id, page - 1, edit_mode)
    
    if not saved:
        return None, None

    # Build Text List (Same for both modes)
    lines = []
    for i, item in enumerate(saved):
        idx = offset + i + 1
        whale_id = item['whale_id'] # Needed for logic but not display
        # Get whale_data by whale_id to ensure we get the correct key and data
        whale_data = saved_whales.get_whale_data_by_id(whale_id)
        key = whale_data.get('key') if whale_data else hashlib.sha1(whale_id.encode()).hexdigest()[:10]
        
        name = item.get('name')
        if not name and whale_data: name = whale_data.get('name')
        display_name = name if name else whale_id
        # Shorten address if it's a wallet ID
        display_name = shorten_trader_name(display_name)
        
        # Escape markdown symbols in name
        safe_name = display_name.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
        
        icon = item.get('level_icon')
        if not icon and whale_data: icon = whale_data.get('level_icon')
        icon = icon or "🦐"

        profile_url = f"https://polymarket.com/profile/{whale_id}"
        link = f"[{safe_name}]({profile_url})"
        
        comment = item.get('comment')
        # Escape comment too just in case
        if comment:
            safe_comment = comment.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
            comment_part = f" 💬 {safe_comment}"
        else:
            comment_part = ""
        
        notif_status = " 🔔" if item.get('notifications_enabled') else " 🔕"
        line = f"*{idx}.* {icon} {link}{notif_status}{comment_part}"
        lines.append(line)
        
    # Add header and join lines
    header = get_text(lang, 'saved_list_header')
    text = header + "\n" + "\n".join(lines)
    
    # Build Keyboard
    buttons = []
    
    if edit_mode:
        # Edit Mode: Rows of [ ✏️ N name ] [ ❌ N name ]
        for i, item in enumerate(saved):
            local_num = offset + i + 1
            whale_id = item['whale_id']
            # Get whale_data by whale_id to ensure we get the correct key and data
            whale_data = saved_whales.get_whale_data_by_id(whale_id)
            key = whale_data.get('key') if whale_data else hashlib.sha1(whale_id.encode()).hexdigest()[:10]
            
            # Get trader name (truncate for button text)
            name = item.get('name')
            if not name and whale_data:
                name = whale_data.get('name')
            if not name:
                name = whale_id[:8]
            # Truncate name for button (max ~10 chars)
            short_name = name[:10] if len(name) > 10 else name
            
            notif_enabled = bool(item.get('notifications_enabled'))
            notif_btn_text = get_text(lang, 'notif_on' if notif_enabled else 'notif_off')
            
            btn_row = [
                InlineKeyboardButton(text=f"✏️ {local_num} {short_name}", callback_data=f"edit:{key}:{page}:1"),
                InlineKeyboardButton(text=notif_btn_text, callback_data=f"toggle_notif:{key}:{page}:1"),
                InlineKeyboardButton(text=f"❌ {local_num}", callback_data=f"delete:{key}:{page}:1")
            ]
            buttons.append(btn_row)
        
        # Add manually button + Done Button
        add_text = get_text(lang, 'manual_add_btn')
        done_text = "✅ Готово" if lang == 'ru' else "✅ Done"
        mode_str = "edit" if edit_mode else "view"
        buttons.append([
            InlineKeyboardButton(text=add_text, callback_data=f"manual_add:{page}:{mode_str}"),
            InlineKeyboardButton(text=done_text, callback_data=f"aq_mode:view:{page}")
        ])
        
    else:
        # View Mode: [ Edit List ] [ Clear All ]
        edit_text = "✏️ Редакт" if lang == 'ru' else "✏️ Edit List"
        clear_text = "🗑 Очистить" if lang == 'ru' else "🗑 Clear All"
        
        action_row = [
            InlineKeyboardButton(text=edit_text, callback_data=f"aq_mode:edit:{page}"),
            InlineKeyboardButton(text=clear_text, callback_data=f"clearall")
        ]
        buttons.append(action_row)
        
        # Add manually button
        add_text = get_text(lang, 'manual_add_btn')
        buttons.append([InlineKeyboardButton(text=add_text, callback_data=f"manual_add:{page}:view")])
        
        # Navigation row (Only view mode needs pagination? Or both?)
        # Let's show pagination in both, but actions differ.
        # Actually user requested specific buttons for Edit Mode.
        # If list > 5, we need pagination in Edit Mode too to delete items on page 2.
    
    # Pagination row (Common for both, logic adapts)
    total_pages = max(1, (total + AQUARIUM_PAGE_SIZE - 1) // AQUARIUM_PAGE_SIZE)
    if total_pages > 1:
        nav_row = []
        mode_str = "edit" if edit_mode else "view"
        
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"aq_page:{page-1}:{mode_str}"))
        
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"aq_page:{page+1}:{mode_str}"))
            
        buttons.append(nav_row)
        
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)





@dp.message(lambda message: message.text in [get_text('ru', 'btn_saved'), get_text('en', 'btn_saved')])
async def btn_saved(message: types.Message):
    """Handle Aquarium button press - Show List View."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    text, reply_markup = get_aquarium_list(chat_id, 0)
    
    if text:
        # Send list
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        # Empty list - show add button
        add_text = get_text(lang, 'manual_add_btn')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=add_text, callback_data="manual_add:0:view")]
        ])
        await message.answer(get_text(lang, 'saved_empty'), reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith('aq_mode:'))
async def callback_aquarium_mode(callback_query: types.CallbackQuery):
    """Toggle View/Edit Mode."""
    chat_id = callback_query.message.chat.id
    try:
        parts = callback_query.data.split(':')
        mode = parts[1] # 'view' or 'edit'
        page = int(parts[2])
        
        is_edit = (mode == 'edit')
        text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
        
        if text:
            from contextlib import suppress
            with suppress(Exception):
                await callback_query.message.edit_text(
                    text, 
                    reply_markup=reply_markup, 
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
    except ValueError:
        pass
    await callback_query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith('aq_page:'))
async def callback_aquarium_page(callback_query: types.CallbackQuery):
    """Navigate Aquarium List pages."""
    chat_id = callback_query.message.chat.id
    try:
        parts = callback_query.data.split(':')
        page = int(parts[1])
        mode = parts[2] if len(parts) > 2 else 'view'
        
        is_edit = (mode == 'edit')
        text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
        
        if text:
            # Edit message to show list
            from contextlib import suppress
            with suppress(Exception):
                await callback_query.message.edit_text(
                    text, 
                    reply_markup=reply_markup, 
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
    except ValueError:
        pass
    await callback_query.answer()






@dp.callback_query(F.data.startswith("save:"))
async def callback_save(callback: CallbackQuery):
    """Handle save trader callback."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    key = callback.data.replace("save:", "")
    whale_id = saved_whales.get_whale_id(key)
    
    if not whale_id:
        await callback.answer("Error: trader not found")
        return
    
    if saved_whales.is_saved(chat_id, whale_id):
        await callback.answer(get_text(lang, 'saved_btn'))
        return
    
    # Get name and icon from whale_keys and save
    whale_data = saved_whales.get_whale_data(key)
    name = whale_data['name'] if whale_data else None
    level_icon = whale_data.get('level_icon') if whale_data else None
    
    saved_whales.save(chat_id, whale_id, name=name, level_icon=level_icon)
    await callback.answer(get_text(lang, 'saved_added'))
    
    # Update button in message to show "Saved"
    try:
        old_keyboard = callback.message.reply_markup
        if old_keyboard:
            new_buttons = []
            for row in old_keyboard.inline_keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data == f"save:{key}":
                        new_row.append(InlineKeyboardButton(
                            text=get_text(lang, 'saved_btn'),
                            callback_data=f"saved:{key}"
                        ))
                    else:
                        new_row.append(btn)
                new_buttons.append(new_row)
            await callback.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons)
            )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("saved:"))
async def callback_already_saved(callback: CallbackQuery):
    """Handle click on already saved button.

    Toggle: remove from favorites and switch button back to "To Favorites".
    """
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)

    key = callback.data.replace("saved:", "")
    whale_id = saved_whales.get_whale_id(key)

    if not whale_id:
        await callback.answer("Error: trader not found")
        return

    # If trader is saved – delete from favorites
    if saved_whales.is_saved(chat_id, whale_id):
        saved_whales.delete(chat_id, whale_id)
        await callback.answer(get_text(lang, 'saved_deleted'))
    else:
        # Fallback: if по какой‑то причине не сохранён, просто показать тултип
        await callback.answer(get_text(lang, 'save_btn'))
        return

    # Обновляем кнопку в сообщении: "Saved" -> "To Favorites"
    try:
        old_keyboard = callback.message.reply_markup
        if old_keyboard:
            # Попробуем взять иконку уровня, чтобы восстановить исходный текст кнопки
            whale_data = saved_whales.get_whale_data(key) or saved_whales.get_whale_data_by_id(whale_id)
            level_icon = whale_data.get('level_icon') if whale_data and whale_data.get('level_icon') else "🦐"

            new_buttons = []
            for row in old_keyboard.inline_keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data == f"saved:{key}":
                        new_row.append(InlineKeyboardButton(
                            text=f"{level_icon} {get_text(lang, 'save_btn')}",
                            callback_data=f"save:{key}"
                        ))
                    else:
                        new_row.append(btn)
                new_buttons.append(new_row)

            await callback.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons)
            )
    except Exception:
        # Если не получилось обновить клавиатуру — просто игнорируем, логика удаления уже отработала
        pass


# ============ NOTE FSM HANDLERS ============

class NoteState(StatesGroup):
    waiting_for_note = State()

@dp.callback_query(lambda c: c.data and c.data.startswith("note:"))
async def callback_note(callback: types.CallbackQuery, state: FSMContext):
    """Handle note button - start FSM for note input."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    parts = callback.data.split(':')
    key = parts[1] if len(parts) > 1 else callback.data.replace("note:", "")
    
    whale_id = saved_whales.get_whale_id(key)
    if not whale_id:
        await callback.answer("Error: trader not found")
        return
    
    # Check if we need to save first? (e.g. from alert directly)
    if not saved_whales.is_saved(chat_id, whale_id):
        # We need to fetch whale data, but callback doesn't have it easily.
        # Fallback: just save id
        # Try to get level from whale_keys - use whale_id to get correct data
        whale_data = saved_whales.get_whale_data_by_id(whale_id)
        name = whale_data.get('name') if whale_data else None
        level_icon = whale_data.get('level_icon') if whale_data else None
        saved_whales.save(chat_id, whale_id, name=name, level_icon=level_icon)
    
    await state.set_state(NoteState.waiting_for_note)
    
    # Store page/mode info to return to correct state
    # Parts format from edit button: edit:key:page:edit_mode
    page = 0
    edit_mode = 0
    if len(parts) > 2:
        try:
            page = int(parts[2])
        except ValueError: pass
    if len(parts) > 3:
        try:
            edit_mode = int(parts[3])
        except ValueError: pass
        
    await state.update_data(whale_id=whale_id, whale_key=key, page=page, edit_mode=edit_mode)
    
    await callback.answer()
    await callback.message.answer(
        get_text(lang, 'note_prompt'),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data and c.data.startswith('edit:'))
async def callback_edit(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle edit note button."""
    # Format: edit:key:page:edit_mode
    await callback_note(callback_query, state)





@dp.callback_query(lambda c: c.data and c.data.startswith("delete:"))
async def callback_delete(callback: types.CallbackQuery):
    """Handle delete from saved."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    parts = callback.data.split(':')
    key = parts[1]
    # Format: delete:key:page:edit_mode
    page = int(parts[2]) if len(parts) > 2 else 0
    edit_mode = int(parts[3]) if len(parts) > 3 else 0
    
    whale_id = saved_whales.get_whale_id(key)
    
    if not whale_id:
        await callback.answer("Error: trader not found")
        return
    
    saved_whales.delete(chat_id, whale_id)
    await callback.answer(get_text(lang, 'saved_deleted'))
    
    # Refresh View
    is_edit = bool(edit_mode)
    text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
    
    if text:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        # Totally empty
        await callback.message.edit_text(get_text(lang, 'saved_empty'))


@dp.callback_query(lambda c: c.data == "clearall")
async def callback_clear_all(callback: types.CallbackQuery):
    """Ask for confirmation before clearing all."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    confirm_text = "Внимание! Вы точно хотите удалить ВСЕХ сохраненных трейдеров?" if lang == 'ru' else "Warning! Are you sure you want to delete ALL saved traders?"
    
    yes_text = "✅ Да, удалить всё" if lang == 'ru' else "✅ Yes, delete all"
    no_text = "❌ Отмена" if lang == 'ru' else "❌ Cancel"
    
    buttons = [
        [InlineKeyboardButton(text=yes_text, callback_data="confirm_clear")],
        [InlineKeyboardButton(text=no_text, callback_data="cancel_clear")]
    ]
    
    await callback.message.edit_text(confirm_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@dp.callback_query(lambda c: c.data == "confirm_clear")
async def callback_confirm_clear(callback: types.CallbackQuery):
    """Execute clear all."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    saved_whales.clear_all(chat_id)
    await callback.answer(get_text(lang, 'saved_cleared'))
    await callback.message.edit_text(get_text(lang, 'saved_empty'))


@dp.callback_query(lambda c: c.data == "cancel_clear")
async def callback_cancel_clear(callback: types.CallbackQuery):
    """Cancel clear all - ensure return to list."""
    chat_id = callback.message.chat.id
    # Go back to page 0
    text, reply_markup = get_aquarium_list(chat_id, 0)
    if text:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        # Should usually not happen if we cancelled, unless list was empty?
        # If empty, show empty message
        lang = get_user_lang(chat_id)
        await callback.message.edit_text(get_text(lang, 'saved_empty'))
    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("toggle_notif:"))
async def callback_toggle_notif(callback: types.CallbackQuery):
    """Toggle notifications for a saved trader."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    parts = callback.data.split(':')
    key = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    edit_mode = int(parts[3]) if len(parts) > 3 else 0
    
    whale_id = saved_whales.get_whale_id(key)
    if not whale_id:
        await callback.answer("Error: trader not found")
        return
    
    new_state = saved_whales.toggle_notifications(chat_id, whale_id)
    
    msg_key = 'notif_enabled' if new_state else 'notif_disabled'
    await callback.answer(get_text(lang, msg_key))
    
    # Refresh View
    is_edit = bool(edit_mode)
    text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
    
    if text:
        from contextlib import suppress
        with suppress(Exception):
            await callback.message.edit_text(
                text, 
                reply_markup=reply_markup, 
                parse_mode="Markdown", 
                disable_web_page_preview=True
            )


@dp.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    """Handle noop callback (page info button)."""
    await callback.answer()


# ============ MANUAL ADD TRADER HANDLERS ============

@dp.callback_query(lambda c: c.data and c.data.startswith("manual_add:"))
async def callback_manual_add(callback: types.CallbackQuery, state: FSMContext):
    """Handle manual add button - start FSM for trader input."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    parts = callback.data.split(':')
    page = int(parts[1]) if len(parts) > 1 else 0
    mode = parts[2] if len(parts) > 2 else 'view'
    
    await state.set_state(ManualAddState.waiting_for_input)
    await state.update_data(page=page, mode=mode)
    
    # Show cancel button
    cancel_text = get_text(lang, 'manual_add_cancel')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cancel_text, callback_data=f"cancel_manual_add:{page}:{mode}")]
    ])
    
    await callback.answer()
    await callback.message.answer(
        get_text(lang, 'manual_add_prompt'),
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("cancel_manual_add:"))
async def callback_cancel_manual_add(callback: types.CallbackQuery, state: FSMContext):
    """Cancel manual add operation."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    await state.clear()
    
    parts = callback.data.split(':')
    page = int(parts[1]) if len(parts) > 1 else 0
    mode = parts[2] if len(parts) > 2 else 'view'
    is_edit = (mode == 'edit')
    
    # Delete the prompt message
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Show updated list
    text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
    if text:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        add_text = get_text(lang, 'manual_add_btn')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=add_text, callback_data="manual_add:0:view")]
        ])
        await callback.message.answer(get_text(lang, 'saved_empty'), reply_markup=keyboard)
    
    await callback.answer()


@dp.message(ManualAddState.waiting_for_input)
async def process_manual_add_input(message: types.Message, state: FSMContext):
    """Handle manual add text input from FSM."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    text = message.text.strip() if message.text else ""
    
    # Parse input - extract wallet address
    wallet = None
    
    # Try polymarket URL
    if "polymarket.com/profile/" in text:
        parts = text.split("polymarket.com/profile/")
        if len(parts) > 1:
            wallet = parts[1].split("?")[0].split("/")[0].strip()
    
    # Try direct wallet format (0x...)
    elif text.startswith("0x"):
        # Extract just the address part (42 chars for Ethereum)
        wallet = text[:42] if len(text) >= 42 else text
    
    # Validate
    if not wallet or not wallet.startswith("0x") or len(wallet) < 40:
        await message.answer(get_text(lang, 'manual_add_invalid'))
        
        # Exit FSM and return to list
        data = await state.get_data()
        page = data.get('page', 0)
        mode = data.get('mode', 'view')
        is_edit = (mode == 'edit')
        await state.clear()
        
        text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
        if text:
            await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            add_text = get_text(lang, 'manual_add_btn')
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=add_text, callback_data="manual_add:0:view")]
            ])
            await message.answer(get_text(lang, 'saved_empty'), reply_markup=keyboard)
        return
    
    # Normalize wallet (lowercase for consistency)
    wallet = wallet.lower()
    
    # Check if already saved
    if saved_whales.is_saved(chat_id, wallet):
        await message.answer(get_text(lang, 'manual_add_exists'))
        await state.clear()
        
        # Return to list
        data = await state.get_data()
        page = data.get('page', 0)
        mode = data.get('mode', 'view')
        is_edit = (mode == 'edit')
        
        text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
        if text:
            await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
        return
    
    # Create key for the wallet and save
    saved_whales.get_or_create_key(wallet)
    saved_whales.save(chat_id, wallet)
    
    await message.answer(get_text(lang, 'manual_add_success'))
    
    # Clear state and return to list
    data = await state.get_data()
    page = data.get('page', 0)
    mode = data.get('mode', 'view')
    is_edit = (mode == 'edit')
    await state.clear()
    
    text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
    if text:
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)


@dp.message(NoteState.waiting_for_note)
async def process_note_input(message: types.Message, state: FSMContext):
    """Handle note text input from FSM."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    
    data = await state.get_data()
    whale_id = data.get('whale_id')
    
    if not whale_id:
        await state.clear()
        return
    
    text = message.text.strip() if message.text else ""
    
    # Check for remove signal
    if text in ("-", "–", "—", ""):
        saved_whales.set_comment(chat_id, whale_id, None)
        await message.answer(get_text(lang, 'note_removed'))
    else:
        # Check length
        if len(text) > MAX_COMMENT_LEN:
            await message.answer(get_text(lang, 'note_too_long'))
            return  # Stay in FSM state
        
        # Save comment
        saved_whales.set_comment(chat_id, whale_id, text)
        await message.answer(get_text(lang, 'note_saved'))
    
    # Common exit logic: Clear state and return to list
    await state.clear()
    
    # Return to Aquarium View
    page = data.get('page', 0)
    edit_mode = data.get('edit_mode', 0)
    is_edit = bool(edit_mode)
    
    text, reply_markup = get_aquarium_list(chat_id, page, edit_mode=is_edit)
    if text:
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)


@dp.callback_query(F.data.startswith("filter_"))
async def callback_filter(callback: CallbackQuery):
    """Handle filter amount selection."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    min_value = int(callback.data.replace("filter_", ""))
    
    # If user selects $500, show warning confirmation
    if min_value == 500:
        await callback.answer()
        warning_text = (
            f"*{get_text(lang, 'amount_warning_title')}*\n\n"
            f"{get_text(lang, 'amount_warning_text')}"
        )
        await callback.message.edit_text(
            warning_text,
            parse_mode="Markdown",
            reply_markup=get_amount_confirm_keyboard(chat_id)
        )
        return
    
    # For other amounts, apply immediately
    user_filters[chat_id] = min_value
    save_settings()
    
    # Show confirmation and refresh keyboard
    await callback.answer(get_text(lang, 'filter_toast'))
    await callback.message.edit_text(
        get_text(lang, 'amount_set', min=min_value),
        parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} set filter to ${min_value}")


@dp.callback_query(F.data == "confirm_filter_500")
async def callback_confirm_filter_500(callback: CallbackQuery):
    """Handle confirmation for $500 filter."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    # Apply $500 filter
    user_filters[chat_id] = 500
    save_settings()
    
    await callback.answer(get_text(lang, 'filter_toast'))
    await callback.message.edit_text(
        get_text(lang, 'amount_set', min=500),
        parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} confirmed and set filter to $500")


@dp.callback_query(F.data == "cancel_filter_500")
async def callback_cancel_filter_500(callback: CallbackQuery):
    """Handle cancellation for $500 filter - return to amount menu."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    await callback.answer()
    await callback.message.edit_text(
        get_text(lang, 'amount_menu_title'),
        parse_mode="Markdown",
        reply_markup=get_amount_keyboard(chat_id)
    )
    logger.info(f"User {chat_id} cancelled $500 filter selection")

@dp.callback_query(F.data.startswith("prob_") & (F.data != "prob_custom"))
async def callback_probability(callback: CallbackQuery):
    """Handle probability filter selection."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    prob_key = callback.data.replace("prob_", "")
    
    user_probabilities[chat_id] = prob_key
    save_settings()
    
    # Get display text for the selected range
    range_text = get_text(lang, f'prob_{prob_key}')
    
    await callback.answer(get_text(lang, 'filter_toast'))
    await callback.message.edit_text(
        get_text(lang, 'probability_set', range=range_text),
        parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} set probability filter to {prob_key}")

@dp.callback_query(F.data == "prob_custom")
async def callback_prob_custom(callback: CallbackQuery, state: FSMContext):
    """Handle custom probability filter selection."""
    chat_id = callback.message.chat.id
    lang = get_user_lang(chat_id)
    
    current_key = user_probabilities.get(chat_id, 'any')
    if current_key == 'any':
        current_text = get_text(lang, 'prob_any')
    elif current_key in PROBABILITY_OPTIONS:
        current_text = get_text(lang, f'prob_{current_key}')
    else:
        current_text = f"{current_key.replace('_', '-')} %"
    
    await state.set_state(ProbabilityFilterState.waiting_for_range)
    
    await callback.answer()
    await callback.message.edit_text(
        get_text(lang, 'prob_prompt') + f"\n\n*{get_text(lang, 'current')}:* {current_text}",
        parse_mode="Markdown"
    )

def parse_probability_ranges(text):
    """
    Parse probability ranges from string.
    Supports:
    - Multiple ranges: "0-5, 95-100"
    - Space/underscore as separator: "20 80", "20_80"
    - Single ranges: "20-80"
    """
    text = text.strip()
    if not text:
        return None
        
    raw_ranges = text.split(',')
    valid_ranges = []
    
    for rng in raw_ranges:
        clean_text = rng.strip().replace(" ", "-").replace("_", "-")
        if not clean_text:
            continue
            
        parts = clean_text.split("-")
        
        if len(parts) != 2:
            raise ValueError
            
        min_v = int(parts[0])
        max_v = int(parts[1])
        
        if min_v < 0 or max_v > 100 or min_v > max_v:
            raise ValueError # Invalid range
            
        valid_ranges.append((min_v, max_v))
        
    if not valid_ranges:
        return None
        
    return valid_ranges

@dp.message(ProbabilityFilterState.waiting_for_range)
async def process_prob_custom_input(message: types.Message, state: FSMContext):
    """Process custom probability range input."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    text = message.text.strip()
    
    if text == "0" or text == "0-100":
        user_probabilities[chat_id] = 'any'
        save_settings()
        await state.clear()
        await message.answer(get_text(lang, 'filter_toast'))
        # Show updated menu
        await cmd_probability(message)
        return

    try:
        valid_ranges = parse_probability_ranges(text)
        if not valid_ranges:
            raise ValueError
            
        # Format as stored key "min_max,min_max"
        prob_key = ",".join([f"{r[0]}_{r[1]}" for r in valid_ranges])
        
        user_probabilities[chat_id] = prob_key
        save_settings()
        await state.clear()
        
        # Format display text
        range_texts = [f"{r[0]}% — {r[1]}%" for r in valid_ranges]
        range_text = ", ".join(range_texts)
        
        await message.answer(
            get_text(lang, 'prob_set', range=range_text),
            parse_mode="Markdown"
        )
        # Reshow menu
        await cmd_probability(message)
        
    except ValueError:
        await message.answer(
            get_text(lang, 'prob_invalid'),
            parse_mode="Markdown"
        )
        await state.clear()

@dp.callback_query(F.data == "age_any")
async def callback_age_any(callback: CallbackQuery):
    """Handle age filter 'any' selection."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    user_wallet_ages[chat_id] = {'min_days': None, 'max_days': None}
    save_settings()
    
    await callback.answer(get_text(lang, 'filter_toast'))
    await callback.message.edit_text(
        get_text(lang, 'age_set', range=get_text(lang, 'age_any')),
        parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} set age filter to unlimited")

@dp.callback_query(F.data == "age_custom")
async def callback_age_custom(callback: CallbackQuery, state: FSMContext):
    """Handle age filter 'custom' selection - start FSM."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    current = user_wallet_ages.get(chat_id, {'min_days': None, 'max_days': None})
    current_text = format_age_range(current, lang)
    
    await callback.answer()
    await callback.message.edit_text(
        get_text(lang, 'age_prompt') + f"\n\n*{get_text(lang, 'current')}:* {current_text}",
        parse_mode="Markdown"
    )
    
    await state.set_state(AgeFilterState.waiting_for_range)
    await state.update_data(chat_id=chat_id)

@dp.message(AgeFilterState.waiting_for_range)
async def process_age_range(message: types.Message, state: FSMContext):
    """Process age range input from user."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    text = message.text.strip()
    
    # Reset filter if user sends "0" or "any"
    if text.lower() in ['0', 'any', 'любой', 'неограничено']:
        user_wallet_ages[chat_id] = {'min_days': None, 'max_days': None}
        save_settings()
        await message.answer(
            get_text(lang, 'age_set', range=get_text(lang, 'age_any')),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Parse range: "min-max", "min-", "-max", or just "min"
    try:
        min_days = None
        max_days = None
        
        if '-' in text:
            parts = text.split('-')
            if len(parts) == 2:
                min_part = parts[0].strip()
                max_part = parts[1].strip()
                
                if min_part:
                    min_days = float(min_part)
                if max_part:
                    max_days = float(max_part)
        else:
            # Single number means minimum
            min_days = float(text)
        
        if min_days is not None and min_days < 0:
            raise ValueError("Negative days")
        if max_days is not None and max_days < 0:
            raise ValueError("Negative days")
        if min_days is not None and max_days is not None and min_days > max_days:
            raise ValueError("Min > Max")
        
        user_wallet_ages[chat_id] = {'min_days': min_days, 'max_days': max_days}
        save_settings()
        
        range_text = format_age_range(user_wallet_ages[chat_id], lang)
        await message.answer(
            get_text(lang, 'age_set', range=range_text),
            parse_mode="Markdown"
        )
        logger.info(f"User {chat_id} set age filter to {min_days}-{max_days} days")
        
    except (ValueError, TypeError):
        await message.answer(
            get_text(lang, 'age_invalid'),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    await state.clear()

@dp.callback_query(F.data == "pos_any")
async def callback_positions_any(callback: CallbackQuery):
    """Handle positions filter 'any' selection."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    user_open_positions[chat_id] = {'min_count': None, 'max_count': None}
    save_settings()
    
    await callback.answer(get_text(lang, 'filter_toast'))
    await callback.message.edit_text(
        get_text(lang, 'pos_set', range=get_text(lang, 'pos_any')),
        parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} set positions filter to unlimited")

@dp.callback_query(F.data == "pos_custom")
async def callback_positions_custom(callback: CallbackQuery, state: FSMContext):
    """Handle positions filter 'custom' selection - start FSM."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    
    current = user_open_positions.get(chat_id, {'min_count': None, 'max_count': None})
    current_text = format_positions_range(current, lang)
    
    await callback.answer()
    await callback.message.edit_text(
        get_text(lang, 'pos_prompt') + f"\n\n*{get_text(lang, 'current')}:* {current_text}",
        parse_mode="Markdown"
    )
    
    await state.set_state(PositionsFilterState.waiting_for_range)
    await state.update_data(chat_id=chat_id)

@dp.message(PositionsFilterState.waiting_for_range)
async def process_positions_range(message: types.Message, state: FSMContext):
    """Process positions range input from user."""
    chat_id = message.chat.id
    lang = get_user_lang(chat_id)
    text = message.text.strip()
    
    # Reset filter if user sends "0" or "any"
    if text.lower() in ['0', 'any', 'любой', 'неограничено']:
        user_open_positions[chat_id] = {'min_count': None, 'max_count': None}
        save_settings()
        await message.answer(
            get_text(lang, 'pos_set', range=get_text(lang, 'pos_any')),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Parse range: "min-max", "min-", "-max", or just "min"
    try:
        min_count = None
        max_count = None
        
        if '-' in text:
            parts = text.split('-')
            if len(parts) == 2:
                min_part = parts[0].strip()
                max_part = parts[1].strip()
                
                if min_part:
                    min_count = int(float(min_part))  # Allow float but convert to int
                if max_part:
                    max_count = int(float(max_part))
        else:
            # Single number means minimum
            min_count = int(float(text))
        
        if min_count is not None and min_count < 0:
            raise ValueError("Negative count")
        if max_count is not None and max_count < 0:
            raise ValueError("Negative count")
        if min_count is not None and max_count is not None and min_count > max_count:
            raise ValueError("Min > Max")
        
        user_open_positions[chat_id] = {'min_count': min_count, 'max_count': max_count}
        save_settings()
        
        range_text = format_positions_range(user_open_positions[chat_id], lang)
        await message.answer(
            get_text(lang, 'pos_set', range=range_text),
            parse_mode="Markdown"
        )
        logger.info(f"User {chat_id} set positions filter to {min_count}-{max_count}")
        
    except (ValueError, TypeError):
        await message.answer(
            get_text(lang, 'pos_invalid'),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    await state.clear()

@dp.callback_query(F.data.startswith("cat_"))
async def callback_category(callback: CallbackQuery):
    """Handle category toggle callback."""
    chat_id = int(callback.message.chat.id)
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    category = callback.data.replace("cat_", "")
    
    prefs = user_categories[chat_id]
    
    if category == "done":
        # Close settings
        save_settings()
        
        # Get active categories text
        enabled = [k for k, v in prefs.items() if v and k != 'all']
        labels = {
            'other': get_text(lang, 'cat_other'),
            'crypto': get_text(lang, 'cat_crypto'),
            'sports': get_text(lang, 'cat_sports')
        }
        enabled_text = ", ".join(labels.get(k, k) for k in enabled) if enabled else get_text(lang, 'cat_nothing')
        
        await callback.answer(get_text(lang, 'filter_toast'))
        await callback.message.edit_text(
            get_text(lang, 'categories_set', categories=enabled_text),
            parse_mode="Markdown"
        )
        return
    
    if category == "all":
        # Toggle all
        new_state = not prefs.get('all', True)
        prefs['all'] = new_state
        prefs['other'] = new_state
        prefs['crypto'] = new_state
        prefs['sports'] = new_state
    else:
        # Toggle individual category
        prefs[category] = not prefs.get(category, True)
        prefs['all'] = prefs.get('other', False) and prefs.get('crypto', False) and prefs.get('sports', False)
    
    user_categories[chat_id] = prefs
    
    # Save settings on EVERY click to avoid state loss/desync
    save_settings()
    
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=get_categories_keyboard(chat_id))
    except Exception as e:
        # Avoid error if keyboard is identical
        pass

@dp.callback_query(F.data.startswith("side_"))
async def callback_side_type(callback: CallbackQuery):
    """Handle side type toggle callback."""
    chat_id = int(callback.message.chat.id)
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    side_type = callback.data.replace("side_", "")
    
    prefs = user_side_types[chat_id]
    
    if side_type == "done":
        # Close settings
        save_settings()
        
        # Get active side types text
        enabled = [k for k, v in prefs.items() if v and k != 'all']
        labels = {
            'BUY': get_text(lang, 'side_buy'),
            'SELL': get_text(lang, 'side_sell'),
            'SPLIT': get_text(lang, 'side_split'),
            'MERGE': get_text(lang, 'side_merge'),
            'REDEEM': get_text(lang, 'side_redeem')
        }
        enabled_text = ", ".join(labels.get(k, k) for k in enabled) if enabled else get_text(lang, 'side_nothing')
        
        await callback.answer(get_text(lang, 'filter_toast'))
        await callback.message.edit_text(
            get_text(lang, 'sides_set', sides=enabled_text),
            parse_mode="Markdown"
        )
        return
    
    if side_type == "all":
        # Toggle all
        new_state = not prefs.get('all', True)
        prefs['all'] = new_state
        prefs['BUY'] = new_state
        prefs['SELL'] = new_state
        prefs['SPLIT'] = new_state
        prefs['MERGE'] = new_state
        prefs['REDEEM'] = new_state
    else:
        # Toggle individual side type
        prefs[side_type] = not prefs.get(side_type, True)
        prefs['all'] = prefs.get('BUY', False) and prefs.get('SELL', False) and prefs.get('SPLIT', False) and prefs.get('MERGE', False) and prefs.get('REDEEM', False)
    
    user_side_types[chat_id] = prefs
    
    # Save settings on EVERY click to avoid state loss/desync
    save_settings()
    
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=get_side_types_keyboard(chat_id))
    except Exception as e:
        # Avoid error if keyboard is identical
        pass

# Global catch-all handler for unhandled callback queries (MUST be last - after all specific handlers)
@dp.callback_query()
async def callback_query_catch_all(callback: CallbackQuery):
    """Catch-all handler for unhandled callback queries - logs for debugging."""
    try:
        logger.warning(f"⚠️ Unhandled callback_query: data='{callback.data}' from chat_id={callback.message.chat.id}")
        await callback.answer("⚠️ Кнопка не обработана", show_alert=False)
    except Exception as e:
        logger.error(f"Error in callback_query_catch_all: {e}")

def get_user_min_threshold(chat_id):
    """Get user's minimum threshold. Return default if not set."""
    return user_filters.get(chat_id, FILTERS[-1]['min'])

def get_user_categories(chat_id):
    """Get user's category preferences."""
    return user_categories.get(chat_id, get_default_categories())

def get_user_probability_filter(chat_id):
    """Get user's probability filter setting. Returns LIST of (min, max) tuples or None."""
    prob_key = user_probabilities.get(chat_id, 'any')
    
    # Standard option?
    if prob_key in PROBABILITY_OPTIONS:
        val = PROBABILITY_OPTIONS[prob_key]
        return [val] if val else None
        
    # Custom option? "min_max" or "min_max,min_max"
    try:
        ranges = []
        # Split by comma for multiple ranges
        parts_list = prob_key.split(',')
        
        for part in parts_list:
            part = part.strip()
            if "_" in part:
                p = part.split("_")
                if len(p) == 2:
                    # Convert 1-99 integer range to 0.01-0.99 float range
                    ranges.append((int(p[0])/100.0, int(p[1])/100.0))
        
        if ranges:
            return ranges
            
    except Exception:
        pass
        
    return None

def get_user_side_types(chat_id):
    """Get user's side type preferences."""
    return user_side_types.get(chat_id, get_default_side_types())

def get_user_wallet_age_filter(chat_id):
    """Get user's wallet age filter. Returns dict with min_days and max_days (or None)."""
    return user_wallet_ages.get(chat_id, {'min_days': None, 'max_days': None})

def get_user_open_positions_filter(chat_id):
    """Get user's open positions filter. Returns dict with min_count and max_count (or None)."""
    return user_open_positions.get(chat_id, {'min_count': None, 'max_count': None})

def is_user_active(chat_id):
    """Check if user is active."""
    return user_statuses.get(chat_id, True)


# ============ ADMIN COMMANDS (Owner Only) ============

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Show admin commands cheatsheet (owner only)."""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Нет доступа")
        return
    
    # Build plain text message
    msg_lines = [
        "🔐 === Команды администратора ===",
        "",
        "🤖 === Управление ботом ===",
        "/bot_stop — остановить отправку алертов",
        "/bot_start — возобновить отправку алертов",
        "",
        "📊 === Статистика ===",
        "/stats — статистика бота",
        "/users — список пользователей",
        "/cache — кэш возраста кошельков",
        "/report — полный отчет о системе",
        "",
        "📢 === Рассылка ===",
        "/broadcast <текст> — отправить всем",
        "",
        "🔇 === Auto-Mute ===",
        "/mute_status — показать статистику мута (muted_count, retryafter_per_min, top_muted 5)",
        "/mute <chat_id> [hours] — вручную замутить пользователя (пример: /mute 123456789 24)",
        "/unmute <chat_id> — размутить пользователя (пример: /unmute 123456789)",
        "",
        "📤 === Queue ===",
        "/queue_status — статистика очереди (queue_size, dropped_total, sent_total, workers)",
        "/queue_clear — очистить очередь (экстренно)",
        "",
        "🐦 === Twitter ===",
        "/twitter — все настройки и статус",
        "/twitter_on / off — вкл/выкл",
        "/twitter_min 25000 — минимум $",
        "/twitter_ins_min 20000 — мин. для инсайдеров",
        "/twitter_age_ins 2 — макс. возраст инсайдера",
        "/twitter_pos_ins 3 — макс. позиций инсайдера",
        "/twitter_interval 25 — интервал мин",
        "/twitter_prob 1_99 — вероятность",
        "/twitter_sell on — SELL сигналы",
        "/twitter_split on — SPLIT сигналы",
        "/twitter_merge on — MERGE сигналы",
        "/twitter_redeem on — REDEEM сигналы",
        "/twitter_cat crypto on — категории",
        "",
        "🕵️ === Insider Alerts ===",
        "/tlgrm — статус и все настройки",
        "/tlgrm_prob 10 90 — фильтр вероятности",
        "/tlgrm_pending — ожидающие алерты",
        "/tlgrm_on / off — глобально вкл/выкл",
        "/tlgrm_channel -100... — ID канала",
        "",
        "=== Категории ===",
        "/tlgrm_cat crypto on",
        "/tlgrm_cat sports on",
        "/tlgrm_cat other on",
        "",
        "=== CLUSTER (Simultaneous entries) ===",
        "/tlgrm_cluster on/off",
        "/tlgrm_cluster_show / reset",
        "/tlgrm_cluster_interval 2 — окно (ч)",
        "/tlgrm_cluster_min 5000 — мин. объём ($)",
        "/tlgrm_cluster_total 10000 — мин. общий объём ($)",
        "/tlgrm_cluster_wallets 4 — мин. кошельков",
        "/tlgrm_cluster_wallet_age 24 — макс. возраст (ч)",
        "/tlgrm_cluster_side both — buy/sell/both",
        "/tlgrm_cluster_direction 75 — направленность (%)",
        "/tlgrm_cluster_profiles on — показывать участников",
        "/tlgrm_cluster_pos 3 — макс. открытых позиций",
        "",
        "=== ACCUMULATION (Slow multi-wallet accumulation) ===",
        "/tlgrm_accumulation on/off",
        "/tlgrm_accumulation_show / reset",
        "/tlgrm_accumulation_interval 14 — окно (дней)",
        "/tlgrm_accumulation_min 10000 — мин. размер ($)",
        "/tlgrm_accumulation_total 50000 — мин. общий объём ($)",
        "/tlgrm_accumulation_wallets 3 — мин. кошельков",
        "/tlgrm_accumulation_age 48 — макс. возраст (ч)",
        "/tlgrm_accumulation_profiles on — показывать участников",
        "/tlgrm_accumulation_pos 3 — макс. открытых позиций",
        "/tlgrm_accumulation_direction 70 — направленность (%)",
        "",
        "=== BURST (Small wallets surge) ===",
        "/tlgrm_burst on/off",
        "/tlgrm_burst_show / reset",
        "/tlgrm_burst_interval 1 — окно (ч)",
        "/tlgrm_burst_min 1000 — мин. размер ($)",
        "/tlgrm_burst_total 5000 — мин. общий объём ($)",
        "/tlgrm_burst_wallets 8 — мин. кошельков",
        "/tlgrm_burst_age 72 — макс. возраст (ч)",
        "/tlgrm_burst_profiles on — показывать участников",
        "/tlgrm_burst_pos 3 — макс. открытых позиций",
        "/tlgrm_burst_direction 70 — направленность (%)",
        "",
        "👤 === Пользовательские ===",
        "/reset — сброс своих фильтров",
        "",
        "ℹ️ Эта памятка: /admin",
    ]
    
    msg = "\n".join(msg_lines)
    
    # Split message into chunks by lines (max 3500 chars per chunk)
    max_chunk_size = 3500
    chunks = []
    if len(msg) > max_chunk_size:
        current_chunk = []
        current_size = 0
        
        for line in msg_lines:
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
    else:
        chunks = [msg]
    
    # Send chunks as plain text (no parse_mode)
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk = f"(Часть {i+1}/{len(chunks)})\n\n{chunk}"
        
        # Debug: log last 300 chars before sending to catch parsing issues
        if i == len(chunks) - 1:  # Only log for last chunk
            last_300 = chunk[-300:] if len(chunk) > 300 else chunk
            logger.info(f"DEBUG /admin: sending chunk {i+1}/{len(chunks)}, last 300 chars: {repr(last_300)}")
        
        await message.answer(chunk)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show bot statistics (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    # Bot status
    bot_status = "▶️ Включен" if is_bot_enabled() else "⏸️ Остановлен"
    
    total_users = len(user_filters)
    active_users = sum(1 for uid in user_statuses if user_statuses.get(uid, True))
    
    # Calculate paused vs blocked
    blocked_count = len(blocked_users)
    # Paused = inactive users who are NOT blocked
    paused_users = total_users - active_users - blocked_count
    
    # Filter distribution
    filter_dist = {}
    for uid, threshold in user_filters.items():
        filter_dist[threshold] = filter_dist.get(threshold, 0) + 1
    
    # Category preferences
    crypto_on = sum(1 for uid in user_categories if user_categories[uid].get('crypto', True))
    sports_on = sum(1 for uid in user_categories if user_categories[uid].get('sports', True))
    other_on = sum(1 for uid in user_categories if user_categories[uid].get('other', True))
    
    # Language distribution
    ru_users = sum(1 for uid in user_languages if user_languages.get(uid, 'ru') == 'ru')
    en_users = total_users - ru_users
    
    msg = f"""📊 **Статистика бота**

🤖 **Статус:** {bot_status}

👥 **Пользователи:** {total_users}
▶️ Активных: {active_users}
⏸️ На паузе: {paused_users}
🛑 Заблокировали: {blocked_count}

💰 **Фильтры по сумме:**
"""
    for f in FILTERS:
        count = filter_dist.get(f['min'], 0)
        msg += f"  {f['emoji']}: {count}\n"
    
    msg += f"""
📂 **Категории:**
💰 Крипто вкл: {crypto_on}
⚽ Спорт вкл: {sports_on}
📌 Остальное вкл: {other_on}

🌐 **Язык:**
🇷🇺 RU: {ru_users}
🇬🇧 EN: {en_users}
"""
    
    await message.answer(msg, parse_mode="Markdown")


@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    """List all users as a text file (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    if not user_filters:
        await message.answer("📭 Пока нет пользователей.")
        return
    
    import io
    
    # Build file content
    lines = ["Username | Status | Threshold | Language"]
    lines.append("=" * 50)
    
    for uid in user_filters.keys():
        threshold = user_filters.get(uid, 100)
        if uid in blocked_users:
            status = "🛑 Blocked"
        elif user_statuses.get(uid, True):
            status = "▶️ Active"
        else:
            status = "⏸️ Paused"
        lang = user_languages.get(uid, 'ru').upper()
        username = user_usernames.get(uid, f"ID:{uid}")
        
        lines.append(f"@{username} | {status} | ${threshold:,} | {lang}")
    
    content = "\n".join(lines)
    
    # Create file in memory and send
    file = io.BytesIO(content.encode('utf-8'))
    file.name = "users_list.txt"
    
    from aiogram.types import BufferedInputFile
    doc = BufferedInputFile(file.getvalue(), filename="users_list.txt")
    
    await message.answer_document(doc, caption=f"👥 Всего пользователей: {len(user_filters)}")



@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    """Broadcast message to all users (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    # Get message text after /broadcast command
    text = message.text.replace("/broadcast", "", 1).strip()
    
    if not text:
        await message.answer("❌ Использование: `/broadcast <сообщение>`", parse_mode="Markdown")
        return
    
    # Send to all users
    sent = 0
    failed = 0
    
    for chat_id in user_filters.keys():
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {chat_id}: {e}")
            failed += 1
    
    await message.answer(f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")


@dp.message(Command("mute_status"))
async def cmd_mute_status(message: types.Message):
    """Show mute statistics (owner only)."""
    if message.from_user is None or message.from_user.id != OWNER_ID:
        await message.answer("❌ Нет доступа")
        return
    
    now = time.time()
    muted_list = []
    for cid, mute_until_ts in muted_until.items():
        if now < mute_until_ts:
            secs_left = mute_until_ts - now
            until_iso = datetime.fromtimestamp(mute_until_ts).strftime("%Y-%m-%d %H:%M:%S")
            level = mute_level.get(cid, 0)
            reason = last_fail_reason.get(cid, "unknown")
            streak = fail_streak.get(cid, 0)
            username = user_usernames.get(cid, f"ID:{cid}")
            muted_list.append((cid, secs_left, until_iso, reason, streak, level, username))
    
    muted_list.sort(key=lambda x: x[1], reverse=True)
    top_muted = muted_list[:10]
    
    # Get retryafter count from queue_stats
    async with _queue_stats_lock:
        retryafter_count = queue_stats.get('retryafter_min', 0)
    
    try:
        msg = f"""**Mute Statistics:**
        
**Currently Muted:** {len(muted_list)}
**RetryAfter (last min):** {retryafter_count}

**Top Muted Users:**
"""
        if top_muted:
            for cid, secs_left, until_iso, reason, streak, level, username in top_muted:
                hours = int(secs_left // 3600)
                mins = int((secs_left % 3600) // 60)
                # Escape special Markdown characters in username and reason
                safe_username = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                safe_reason = str(reason).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                msg += f"• `{cid}` (@{safe_username}): {hours}h {mins}m left, until {until_iso}, reason={safe_reason}, streak={streak}, level={level}\n"
        else:
            msg += "None"
        
        await message.answer(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cmd_mute_status: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при получении статистики мута: {e}")

@dp.message(Command("queue_status"))
async def cmd_queue_status(message: types.Message):
    """Show queue statistics (owner only)."""
    if message.chat.id != OWNER_ID:
        await message.answer("❌ Нет доступа")
        return
    
    queue_size = alert_queue.qsize() if alert_queue else 0
    
    async with _queue_stats_lock:
        dropped_total = queue_stats['dropped_total']
        sent_total = queue_stats['sent_total']
        error_total = queue_stats['error_total']
    
    # Get age statistics
    oldest_age_sec, avg_age_sec = await _get_queue_age_stats()
    
    age_info = "Queue empty"
    if oldest_age_sec is not None:
        age_info = f"{int(oldest_age_sec)}s"
        if avg_age_sec is not None:
            age_info += f" (avg: {int(avg_age_sec)}s)"
    
    msg = f"""**Queue Status:**

**Queue Size:** {queue_size}
**Dropped Total:** {dropped_total}
**Sent Total:** {sent_total}
**Error Total:** {error_total}
**Workers:** {len(worker_tasks)}/{WORKER_COUNT}
**Oldest Task Age:** {age_info}
"""
    await message.answer(msg, parse_mode="Markdown")

@dp.message(Command("queue_clear"))
async def cmd_queue_clear(message: types.Message):
    """Clear queue (owner only)."""
    if message.chat.id != OWNER_ID:
        await message.answer("❌ Нет доступа")
        return
    
    if not alert_queue:
        await message.answer("❌ Queue not initialized")
        return
    
    cleared = 0
    while not alert_queue.empty():
        try:
            alert_queue.get_nowait()
            alert_queue.task_done()
            cleared += 1
        except asyncio.QueueEmpty:
            break
    
    await message.answer(f"✅ Queue cleared: {cleared} tasks removed", parse_mode="Markdown")
    logger.warning(f"🗑️ Queue cleared by admin: {cleared} tasks removed")

@dp.message(Command("unmute"))
async def cmd_unmute(message: types.Message):
    """Unmute a user (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: `/unmute <chat_id>`", parse_mode="Markdown")
        return
    
    try:
        chat_id = int(parts[1])
        muted_until.pop(chat_id, None)
        fail_streak.pop(chat_id, None)
        mute_level.pop(chat_id, None)
        last_mute_time.pop(chat_id, None)
        last_fail_reason.pop(chat_id, None)
        save_mute_state()
        await message.answer(f"✅ Unmuted user `{chat_id}`", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Invalid chat_id")

@dp.message(Command("mute"))
async def cmd_mute(message: types.Message):
    """Manually mute a user (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: `/mute <chat_id> [hours]`\nDefault: 1 hour", parse_mode="Markdown")
        return
    
    try:
        chat_id = int(parts[1])
        hours = int(parts[2]) if len(parts) > 2 else 1
        mute_seconds = hours * 3600
        
        _apply_mute(chat_id, "manual_admin", mute_seconds=mute_seconds)
        await message.answer(f"✅ Muted user `{chat_id}` for {hours} hour(s)", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Invalid chat_id or hours")

@dp.message(Command("cache"))
async def cmd_cache(message: types.Message):
    """Show wallet age cache stats (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.polymarket import get_wallet_age_cache
    
    cache = get_wallet_age_cache()
    count = len(cache)
    
    if count == 0:
        await message.answer("📭 Кэш возраста кошельков пуст.")
        return
        
    msg = f"📂 **Wallet Age Cache ({count})**\n\n"
    
    # Show last 10 entries
    keys = list(cache.keys())[-10:]
    now = __import__('time').time()
    
    for k in keys:
        entry = cache[k]
        age_days = (now - entry['first_ts']) / 86400
        cached_min = (now - entry['cached_at']) / 60
        msg += f"`{k[:6]}...`: Age {age_days:.1f}d (cached {cached_min:.1f}m ago)\n"
        
    if count > 10:
        msg += f"\n... и ещё {count - 10} записей."
        
    await message.answer(msg, parse_mode="Markdown")


@dp.message(Command("bot_stop"))
async def cmd_bot_stop(message: types.Message):
    """Stop bot alerts (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    set_bot_enabled(False)
    logger.info(f"Bot alerts stopped by admin (chat_id: {message.chat.id})")
    await message.answer("⏸️ **Бот остановлен**\n\nВсе алерты временно отключены. Используйте `/bot_start` для возобновления.", parse_mode="Markdown")


@dp.message(Command("bot_start"))
async def cmd_bot_start(message: types.Message):
    """Start bot alerts (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    set_bot_enabled(True)
    logger.info(f"Bot alerts started by admin (chat_id: {message.chat.id})")
    await message.answer("▶️ **Бот запущен**\n\nОтправка алертов возобновлена.", parse_mode="Markdown")


# ============ TWITTER ADMIN COMMANDS ============

@dp.message(Command("twitter"))
async def cmd_twitter(message: types.Message):
    """Show Twitter settings and commands (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import (
        get_twitter_settings, get_twitter_service, is_twitter_enabled,
        is_twitter_paused, get_seconds_until_next_tweet,
        get_twitter_interval, get_twitter_probability_range,
        is_twitter_sell_allowed, is_twitter_split_allowed,
        is_twitter_merge_allowed, is_twitter_redeem_allowed,
        get_twitter_categories, get_tweets_in_last_24h, MAX_TWEETS_PER_24H
    )
    
    settings = get_twitter_settings()
    service = get_twitter_service()
    
    enabled_str = "✅ Включен" if settings.get('enabled', True) else "❌ Выключен"
    min_usd = settings.get('min_alert_usd', 25000)
    configured_str = "✅ Настроен" if service else "❌ Нет ключей"
    
    # Check pause status
    paused, pause_secs = is_twitter_paused()
    if paused:
        pause_mins = pause_secs // 60
        pause_str = f"⛔ ПАУЗА (403): {pause_mins} мин"
    else:
        pause_str = "✅ Нет паузы"
    
    # Check 24h rolling window limit
    tweets_count = get_tweets_in_last_24h()
    wait_secs = get_seconds_until_next_tweet()
    if wait_secs > 0:
        wait_mins = wait_secs // 60
        wait_hours = wait_mins // 60
        if tweets_count >= MAX_TWEETS_PER_24H:
            rate_str = f"⛔ Лимит: {tweets_count}/{MAX_TWEETS_PER_24H} (след. слот через {wait_hours}h{wait_mins%60}m)"
        else:
            rate_str = f"⏳ След. твит: {wait_mins} мин"
    else:
        rate_str = f"✅ Готов ({tweets_count}/{MAX_TWEETS_PER_24H} за 24ч)"
    
    # Filters
    interval = get_twitter_interval()
    p_min, p_max = get_twitter_probability_range()
    prob_filter = f"{p_min}% - {p_max}%"
    sell_allowed = "✅" if is_twitter_sell_allowed() else "❌"
    split_allowed = "✅" if is_twitter_split_allowed() else "❌"
    merge_allowed = "✅" if is_twitter_merge_allowed() else "❌"
    redeem_allowed = "✅" if is_twitter_redeem_allowed() else "❌"
    cats = get_twitter_categories()
    cats_str = ", ".join([k for k, v in cats.items() if v]) or "нет"
    
    msg = f"""🐦 Twitter Settings

{configured_str}
{enabled_str}

Фильтры:
💰 Минимум: ${min_usd:,}
🕵️ Инсайдер мин: ${settings.get('min_alert_insider_usd', 20000):,}
🕵️ Инсайдер возраст: <={settings.get('max_insider_age_days', 2.0)}d
🕵️ Инсайдер позиций: <={settings.get('max_insider_positions', 3)}
📊 Вероятность: {prob_filter}
📈 SELL: {sell_allowed}
⚪ SPLIT: {split_allowed}
↔️ MERGE: {merge_allowed}
🟣 REDEEM: {redeem_allowed}
📂 Категории: {cats_str}
⏱ Интервал: {interval} мин

Статус:
{pause_str}
{rate_str}

Команды:
/twitter_on, /twitter_off
/twitter_min 25000
/twitter_ins_min 20000
/twitter_age_ins 2
/twitter_pos_ins 3
/twitter_interval 25
/twitter_prob 1 99
/twitter_sell on
/twitter_split on
/twitter_merge on
/twitter_redeem on
/twitter_cat crypto on
"""
    await message.answer(msg)


@dp.message(Command("twitter_on"))
async def cmd_twitter_on(message: types.Message):
    """Enable Twitter posting (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_enabled
    set_twitter_enabled(True)
    await message.answer("✅ Twitter постинг включен.")


@dp.message(Command("twitter_off"))
async def cmd_twitter_off(message: types.Message):
    """Disable Twitter posting (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_enabled
    set_twitter_enabled(False)
    await message.answer("❌ Twitter постинг выключен.")


@dp.message(Command("twitter_ins_min"))
async def cmd_twitter_ins_min(message: types.Message):
    """Set Twitter minimum amount for Insider tweets."""
    logger = logging.getLogger(__name__)
    logger.info(f"twitter_ins_min called by chat_id={message.chat.id}, text={message.text}")
    
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        logger.warning(f"twitter_ins_min: chat_id {chat_id} != OWNER_ID {OWNER_ID}")
        return
    
    from services import twitter_service

    try:
        args = message.text.split()
        if len(args) < 2:
            current = twitter_service.get_twitter_insider_min()
            await message.answer(
                f"ℹ️ Current Insider Min: ${current:,}\n"
                f"Usage: /twitter_ins_min <amount>\n"
                f"Example: /twitter_ins_min 15000"
            )
            return
        
        amount_str = args[1].lower().replace('k', '000').replace('$', '').replace(',', '')
        amount = int(float(amount_str))
        
        twitter_service.set_twitter_insider_min(amount)
        await message.answer(f"✅ Twitter Insider Min set to ${amount:,}")
        
    except ValueError:
        await message.answer("❌ Invalid amount format")
    except Exception as e:
        logger.error(f"Error setting twitter insider min: {e}")
        await message.answer(f"❌ Error: {e}")


@dp.message(Command("twitter_min"))
async def cmd_twitter_min(message: types.Message):
    """Set minimum USD for Twitter alerts (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_min_alert
    
    # Parse amount from command
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `/twitter_min 50000`", parse_mode="Markdown")
        return
    
    try:
        min_usd = int(parts[1].replace(",", "").replace("$", ""))
        set_twitter_min_alert(min_usd)
        await message.answer(f"✅ Twitter минимум установлен: ${min_usd:,}")
    except ValueError:
        await message.answer("❌ Укажите число, например: `/twitter_min 50000`", parse_mode="Markdown")


@dp.message(Command("twitter_age_ins"))
async def cmd_twitter_age_ins(message: types.Message):
    """Set Twitter max wallet age (days) for Insider tweets."""
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
    
    try:
        from services import twitter_service
        args = message.text.split()
        if len(args) < 2:
            current = twitter_service.get_twitter_insider_max_age()
            await message.answer(
                f"ℹ️ Current Insider Max Age: {current} days\n"
                f"Usage: /twitter_age_ins <days>\n"
                f"Example: /twitter_age_ins 5"
            )
            return
        
        days = float(args[1])
        if days < 0:
            raise ValueError("Negative days")
            
        twitter_service.set_twitter_insider_max_age(days)
        await message.answer(f"✅ Twitter Insider Max Age set to {days} days")
        
    except ValueError:
        await message.answer("❌ Invalid days format (must be number >= 0)")
    except Exception as e:
        logger.error(f"Error setting twitter insider age: {e}")
        await message.answer(f"❌ Error: {e}")


@dp.message(Command("twitter_pos_ins"))
async def cmd_twitter_pos_ins(message: types.Message):
    """Set Twitter max positions needed for Insider tweets."""
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
    
    try:
        from services import twitter_service
        args = message.text.split()
        if len(args) < 2:
            current = twitter_service.get_twitter_insider_max_positions()
            await message.answer(
                f"ℹ️ Current Insider Max Positions: {current}\n"
                f"Usage: /twitter_pos_ins <count>\n"
                f"Example: /twitter_pos_ins 3"
            )
            return
        
        count = int(args[1])
        if count < 0:
            raise ValueError("Negative count")
            
        twitter_service.set_twitter_insider_max_positions(count)
        await message.answer(f"✅ Twitter Insider Max Positions set to {count}")
        
    except ValueError:
        await message.answer("❌ Invalid count format (must be integer >= 0)")
    except Exception as e:
        logger.error(f"Error setting twitter insider positions: {e}")
        await message.answer(f"❌ Error: {e}")


@dp.message(Command("twitter_interval"))
async def cmd_twitter_interval(message: types.Message):
    """Set interval between tweets in minutes (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_interval, get_twitter_interval
    
    parts = message.text.split()
    if len(parts) < 2:
        current = get_twitter_interval()
        await message.answer(f"⏱ Текущий интервал: {current} мин\nИспользование: `/twitter_interval 25`", parse_mode="Markdown")
        return
    
    try:
        minutes = int(parts[1])
        if minutes < 1:
            await message.answer("❌ Минимальный интервал: 1 минута")
            return
        set_twitter_interval(minutes)
        await message.answer(f"✅ Twitter интервал установлен: {minutes} мин")
    except ValueError:
        await message.answer("❌ Укажите число минут, например: `/twitter_interval 25`", parse_mode="Markdown")


@dp.message(Command("twitter_prob"))
async def cmd_twitter_prob(message: types.Message):
    """Set probability filter for Twitter (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_probability_range, get_twitter_probability_range
    
    parts = message.text.replace("/twitter_prob", "", 1).strip()
    
    if not parts:
        p_min, p_max = get_twitter_probability_range()
        await message.answer(
            f"📊 Текущий фильтр: {p_min}% - {p_max}%\n\n"
            "Использование: `/twitter_prob <min> <max>`\n"
            "Пример: `/twitter_prob 10 80`",
            parse_mode="Markdown"
        )
        return
    
    try:
        valid_ranges = parse_probability_ranges(parts)
        if not valid_ranges or len(valid_ranges) > 1:
            raise ValueError("Only single range supported for Twitter filter")
            
        r = valid_ranges[0]
        set_twitter_probability_range(r[0], r[1])
        await message.answer(f"✅ Twitter фильтр вероятности: {r[0]}% - {r[1]}%")
        
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте: `/twitter_prob 10 90`", parse_mode="Markdown")


@dp.message(Command("twitter_sell"))
async def cmd_twitter_sell(message: types.Message):
    """Toggle SELL signals for Twitter (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_sell_allowed, is_twitter_sell_allowed
    
    parts = message.text.split()
    if len(parts) < 2:
        current = is_twitter_sell_allowed()
        status = "✅ включены" if current else "❌ выключены"
        await message.answer(
            f"📈 SELL сигналы: {status}\n\n"
            "Использование:\n"
            "`/twitter_sell on` — включить\n"
            "`/twitter_sell off` — выключить",
            parse_mode="Markdown"
        )
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true', 'да']:
        set_twitter_sell_allowed(True)
        await message.answer("✅ Twitter SELL сигналы включены")
    elif arg in ['off', '0', 'no', 'false', 'нет']:
        set_twitter_sell_allowed(False)
        await message.answer("❌ Twitter SELL сигналы выключены")
    else:
        await message.answer("❌ Используйте: `/twitter_sell on` или `/twitter_sell off`", parse_mode="Markdown")


@dp.message(Command("twitter_split"))
async def cmd_twitter_split(message: types.Message):
    """Toggle SPLIT signals for Twitter (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_split_allowed, is_twitter_split_allowed
    
    parts = message.text.split()
    if len(parts) < 2:
        current = is_twitter_split_allowed()
        status = "✅ включены" if current else "❌ выключены"
        await message.answer(
            f"⚪ SPLIT сигналы: {status}\n\n"
            "Использование:\n"
            "`/twitter_split on` — включить\n"
            "`/twitter_split off` — выключить",
            parse_mode="Markdown"
        )
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true', 'да']:
        set_twitter_split_allowed(True)
        await message.answer("✅ Twitter SPLIT сигналы включены")
    elif arg in ['off', '0', 'no', 'false', 'нет']:
        set_twitter_split_allowed(False)
        await message.answer("❌ Twitter SPLIT сигналы выключены")
    else:
        await message.answer("❌ Используйте: `/twitter_split on` или `/twitter_split off`", parse_mode="Markdown")


@dp.message(Command("twitter_redeem"))
async def cmd_twitter_redeem(message: types.Message):
    """Toggle REDEEM signals for Twitter (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_redeem_allowed, is_twitter_redeem_allowed
    
    parts = message.text.split()
    if len(parts) < 2:
        current = is_twitter_redeem_allowed()
        status = "✅ включены" if current else "❌ выключены"
        await message.answer(
            f"🟣 REDEEM сигналы: {status}\n\n"
            "Использование:\n"
            "`/twitter_redeem on` — включить\n"
            "`/twitter_redeem off` — выключить",
            parse_mode="Markdown"
        )
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true', 'да']:
        set_twitter_redeem_allowed(True)
        await message.answer("✅ Twitter REDEEM сигналы включены")
    elif arg in ['off', '0', 'no', 'false', 'нет']:
        set_twitter_redeem_allowed(False)
        await message.answer("❌ Twitter REDEEM сигналы выключены")
    else:
        await message.answer("❌ Используйте: `/twitter_redeem on` или `/twitter_redeem off`", parse_mode="Markdown")


@dp.message(Command("twitter_merge"))
async def cmd_twitter_merge(message: types.Message):
    """Toggle MERGE signals for Twitter (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_merge_allowed, is_twitter_merge_allowed
    
    parts = message.text.split()
    if len(parts) < 2:
        current = is_twitter_merge_allowed()
        status = "✅ включены" if current else "❌ выключены"
        await message.answer(
            f"↔️ MERGE сигналы: {status}\n\n"
            "Использование:\n"
            "`/twitter_merge on` — включить\n"
            "`/twitter_merge off` — выключить",
            parse_mode="Markdown"
        )
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true', 'да']:
        set_twitter_merge_allowed(True)
        await message.answer("✅ Twitter MERGE сигналы включены")
    elif arg in ['off', '0', 'no', 'false', 'нет']:
        set_twitter_merge_allowed(False)
        await message.answer("❌ Twitter MERGE сигналы выключены")
    else:
        await message.answer("❌ Используйте: `/twitter_merge on` или `/twitter_merge off`", parse_mode="Markdown")


@dp.message(Command("twitter_cat"))
async def cmd_twitter_cat(message: types.Message):
    """Set category filters for Twitter (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    from services.twitter_service import set_twitter_category, get_twitter_categories
    
    parts = message.text.split()
    if len(parts) < 3:
        cats = get_twitter_categories()
        crypto_st = "✅" if cats.get('crypto', True) else "❌"
        sports_st = "✅" if cats.get('sports', True) else "❌"
        other_st = "✅" if cats.get('other', True) else "❌"
        
        await message.answer(
            f"📂 **Категории Twitter:**\n"
            f"{crypto_st} crypto\n"
            f"{sports_st} sports\n"
            f"{other_st} other\n\n"
            "Использование:\n"
            "`/twitter_cat crypto on`\n"
            "`/twitter_cat sports off`\n"
            "`/twitter_cat all on` — все вкл/выкл",
            parse_mode="Markdown"
        )
        return
    
    category = parts[1].lower()
    action = parts[2].lower()
    
    if category not in ['crypto', 'sports', 'other', 'all']:
        await message.answer("❌ Категории: crypto, sports, other, all")
        return
    
    enabled = action in ['on', '1', 'yes', 'true', 'да']
    if set_twitter_category(category, enabled):
        status = "включена" if enabled else "выключена"
        await message.answer(f"✅ Twitter категория {category}: {status}")
    else:
        await message.answer("❌ Ошибка установки категории")


# ============ INSIDER ALERTS ADMIN COMMANDS ============

@dp.message(Command("tlgrm"))
async def cmd_tlgrm(message: types.Message):
    """Show Insider Alerts status and settings (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        await message.answer("❌ Insider Alerts Service not initialized")
        return
    
    # Wrap get_status() in timeout to prevent hanging on DB locks
    try:
        import asyncio
        # Run synchronous get_status() in executor with timeout
        loop = asyncio.get_event_loop()
        status = await asyncio.wait_for(
            loop.run_in_executor(None, _insider_alerts_service.get_status),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        await message.answer("❌ Timeout getting status (database may be busy). Try again later.")
        logger.warning("cmd_tlgrm: get_status() timed out after 5s")
        return
    except Exception as e:
        await message.answer(f"❌ Error getting status: {str(e)[:200]}")
        logger.error(f"cmd_tlgrm: get_status() error: {e}", exc_info=True)
        return
    enabled_str = "✅ Enabled" if status['enabled'] else "❌ Disabled"
    channel = status.get('channel_id') or '(not set)'
    
    p_min = status.get('probability_min', '0')
    p_max = status.get('probability_max', '100')
    prob_text = f"{p_min}% - {p_max}%"

    msg = f"""🕵️ **Telegram Insider Alerts**

Status: {enabled_str}
Channel ID: `{channel}`
Probability: `{prob_text}`

**Categories:**
"""
    
    # Categories
    cats = status.get('categories', {})
    sports_st = "✅" if cats.get('Sports', 'true') == 'true' else "❌"
    crypto_st = "✅" if cats.get('Crypto', 'true') == 'true' else "❌"
    other_st = "✅" if cats.get('Other', 'true') == 'true' else "❌"
    
    msg += f"""  {sports_st} Sports
  {crypto_st} Crypto
  {other_st} Other

**Scenarios:**
"""
    
    # CLUSTER
    c = status['scenarios']['CLUSTER']
    c_enabled = "✅" if c['enabled'] == 'true' else "❌"
    msg += f"""
{c_enabled} **CLUSTER** (Fresh wallets entering simultaneously)
  • Interval: {c['interval']}h
  • Max wallet age: {c['max_age']}h
  • Min trade size: ${c['min_usd']}
  • Min total volume: ${c['min_total']}
  • Min wallets: {c['min_wallets']}
  • Min directionality: {c['min_dir']}%
  • Side filter: {c['side']}
  • Max positions: {c['max_pos']}
  • Show profiles: {c['profiles']}
"""
    
    # ACCUMULATION
    r = status['scenarios']['ACCUMULATION']
    r_enabled = "✅" if r['enabled'] == 'true' else "❌"
    msg += f"""
{r_enabled} **ACCUMULATION** (Slow multi-wallet accumulation)
  • Interval: {r['interval']}d
  • Max wallet age: {r['max_age']}h
  • Min trade size: ${r['min_usd']}
  • Min total volume: ${r.get('min_total', 'N/A')}
  • Min wallets: {r.get('min_wallets', 'N/A')}
  • Min directionality: {r['min_dir']}%
  • Max positions: {r['max_pos']}
  • Show profiles: {r['profiles']}
"""
    
    # BURST
    b = status['scenarios']['BURST']
    b_enabled = "✅" if b['enabled'] == 'true' else "❌"
    msg += f"""
{b_enabled} **BURST** (Sudden surge of small wallets)
  • Interval: {b['interval']}h
  • Max wallet age: {b['max_age']}h
  • Min trade size: ${b['min_usd']}
  • Min total volume: ${b['min_total']}
  • Min wallets: {b['min_wallets']}
  • Min directionality: {b['min_dir']}%
  • Max positions: {b['max_pos']}
  • Show profiles: {b['profiles']}
"""

    
    # Stats
    stats = status['stats']
    msg += f"""
**Database:**
  • Trades stored: {stats['trades_stored']}
  • Alerts published: {stats['alerts_published']}

**Commands:** `/admin` for full list
"""
    
    await message.answer(msg, parse_mode="Markdown")


@dp.message(Command("tlgrm_pending"))
async def cmd_tlgrm_pending(message: types.Message):
    """Show pending alerts close to threshold (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        await message.answer("❌ Service not initialized")
        return
    
    pending = _insider_alerts_service.get_pending_alerts()
    
    cluster_list = pending.get('CLUSTER', [])
    burst_list = pending.get('BURST', [])
    
    if not cluster_list and not burst_list:
        await message.answer("📊 **Pending Alerts:** None\n\nNo markets are close to triggering alerts.", parse_mode="Markdown")
        return
    
    msg = "📊 **Pending Insider Alerts**\n\n"
    
    if cluster_list:
        min_w = cluster_list[0]['min_wallets'] if cluster_list else 4
        msg += f"🔸 **CLUSTER** (min_wallets={min_w}):\n"
        for p in cluster_list[:10]:  # Limit to 10
            title = p['market_title'][:30] + "..." if len(p['market_title']) > 30 else p['market_title']
            msg += f"  • {title}: {p['wallet_count']}/{p['min_wallets']} wallets, ${p['total_volume']:,.0f}, {p['directionality']:.0f}% {p['outcome']}\n"
        if len(cluster_list) > 10:
            msg += f"  • ...and {len(cluster_list) - 10} more\n"
        msg += "\n"
    
    if burst_list:
        min_w = burst_list[0]['min_wallets'] if burst_list else 8
        msg += f"🔸 **BURST** (min_wallets={min_w}):\n"
        for p in burst_list[:10]:
            title = p['market_title'][:30] + "..." if len(p['market_title']) > 30 else p['market_title']
            msg += f"  • {title}: {p['wallet_count']}/{p['min_wallets']} wallets, ${p['total_volume']:,.0f}, {p['directionality']:.0f}% {p['outcome']}\n"
        if len(burst_list) > 10:
            msg += f"  • ...and {len(burst_list) - 10} more\n"
        msg += "\n"
    
    total = len(cluster_list) + len(burst_list)
    msg += f"**Total pending:** {total} markets"
    
    await message.answer(msg, parse_mode="Markdown")


@dp.message(Command("tlgrm_on"))
async def cmd_tlgrm_on(message: types.Message):
    """Enable Insider Alerts globally (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        await message.answer("❌ Service not initialized")
        return
    
    _insider_alerts_service.update_setting('enabled', 'true')
    await message.answer("✅ Insider Alerts **enabled**", parse_mode="Markdown")


@dp.message(Command("tlgrm_off"))
async def cmd_tlgrm_off(message: types.Message):
    """Disable Insider Alerts globally (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        await message.answer("❌ Service not initialized")
        return
    
    _insider_alerts_service.update_setting('enabled', 'false')
    await message.answer("❌ Insider Alerts **disabled**", parse_mode="Markdown")


@dp.message(Command("tlgrm_channel"))
async def cmd_tlgrm_channel(message: types.Message):
    """Set Telegram channel ID for insider alerts (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        await message.answer("❌ Service not initialized")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.get_channel_id() or '(not set)'
        await message.answer(
            f"📡 Current channel: `{current}`\n\n"
            "Usage: `/tlgrm_channel <id>`\n"
            "Example: `/tlgrm_channel -1001234567890`",
            parse_mode="Markdown"
        )
        return
    
    channel_id = parts[1]
    _insider_alerts_service.update_setting('channel_id', channel_id)
    await message.answer(f"✅ Channel ID set to: `{channel_id}`", parse_mode="Markdown")


# CLUSTER commands
@dp.message(Command("tlgrm_cluster"))
async def cmd_tlgrm_cluster(message: types.Message):
    """Toggle CLUSTER scenario (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        status = _insider_alerts_service.get_status()['scenarios']['CLUSTER']
        enabled_str = "✅ enabled" if status['enabled'] else "❌ disabled"
        await message.answer(f"CLUSTER: {enabled_str}\nUsage: `/tlgrm_cluster on|off`", parse_mode="Markdown")
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true']:
        _insider_alerts_service.update_setting('cluster_enabled', 'true')
        await message.answer("✅ CLUSTER scenario enabled")
    elif arg in ['off', '0', 'no', 'false']:
        _insider_alerts_service.update_setting('cluster_enabled', 'false')
        await message.answer("❌ CLUSTER scenario disabled")
    else:
        await message.answer("Usage: `/tlgrm_cluster on|off`", parse_mode="Markdown")


@dp.message(Command("tlgrm_cluster_interval"))
async def cmd_tlgrm_cluster_interval(message: types.Message):
    """Set CLUSTER interval in hours (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('cluster_interval_hours', '2')
        await message.answer(f"Current: {current}h\nUsage: `/tlgrm_cluster_interval <hours>`", parse_mode="Markdown")
        return
    
    try:
        hours = float(parts[1])
        _insider_alerts_service.update_setting('cluster_interval_hours', str(hours))
        await message.answer(f"✅ CLUSTER interval: {hours}h")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_cluster_wallet_age"))
async def cmd_tlgrm_cluster_wallet_age(message: types.Message):
    """Set CLUSTER max wallet age in hours (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('cluster_wallet_age_hours', '24')
        await message.answer(f"Current: {current}h\nUsage: `/tlgrm_cluster_wallet_age <hours>`", parse_mode="Markdown")
        return
    
    try:
        hours = float(parts[1])
        _insider_alerts_service.update_setting('cluster_wallet_age_hours', str(hours))
        await message.answer(f"✅ CLUSTER max wallet age: {hours}h")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_cluster_min"))
async def cmd_tlgrm_cluster_min(message: types.Message):
    """Set CLUSTER minimum volume in USD (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('cluster_min_usd', '5000')
        await message.answer(f"Current: ${current}\nUsage: `/tlgrm_cluster_min <usd>`", parse_mode="Markdown")
        return
    
    try:
        usd = float(parts[1].replace(',', '').replace('$', ''))
        _insider_alerts_service.update_setting('cluster_min_usd', str(usd))
        await message.answer(f"✅ CLUSTER min volume: ${usd:,.0f}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_cluster_wallets"))
async def cmd_tlgrm_cluster_wallets(message: types.Message):
    """Set CLUSTER minimum wallet count (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('cluster_min_wallets', '4')
        await message.answer(f"Current: {current}\nUsage: `/tlgrm_cluster_wallets <count>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        _insider_alerts_service.update_setting('cluster_min_wallets', str(count))
        await message.answer(f"✅ CLUSTER min wallets: {count}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_cluster_direction"))
async def cmd_tlgrm_cluster_direction(message: types.Message):
    """Set CLUSTER minimum directionality % (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('cluster_min_direction_pct', '75')
        await message.answer(f"Current: {current}%\nUsage: `/tlgrm_cluster_direction <percent>`", parse_mode="Markdown")
        return
    
    try:
        pct = float(parts[1].replace('%', ''))
        _insider_alerts_service.update_setting('cluster_min_direction_pct', str(pct))
        await message.answer(f"✅ CLUSTER min directionality: {pct}%")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_cluster_pos"))
async def cmd_tlgrm_cluster_pos(message: types.Message):
    """Set CLUSTER maximum open positions (owner only)."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('cluster_max_positions', '3')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_cluster_pos <count>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        _insider_alerts_service.update_setting('cluster_max_positions', str(count))
        await message.answer(f"✅ CLUSTER max positions: {count}")
    except ValueError:
        await message.answer("❌ Invalid number")


# ACCUMULATION commands
@dp.message(Command("tlgrm_accumulation"))
async def cmd_tlgrm_accumulation(message: types.Message):
    """Toggle ACCUMULATION scenario (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        status = _insider_alerts_service.get_status()['scenarios']['ACCUMULATION']
        enabled_str = "✅ enabled" if status['enabled'] else "❌ disabled"
        await message.answer(f"ACCUMULATION: {enabled_str}\nUsage: `/tlgrm_accumulation on|off`", parse_mode="Markdown")
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true']:
        _insider_alerts_service.update_setting('accumulation_enabled', 'true')
        await message.answer("✅ ACCUMULATION scenario enabled")
    elif arg in ['off', '0', 'no', 'false']:
        _insider_alerts_service.update_setting('accumulation_enabled', 'false')
        await message.answer("❌ ACCUMULATION scenario disabled")
    else:
        await message.answer("Usage: `/tlgrm_accumulation on|off`", parse_mode="Markdown")


@dp.message(Command("tlgrm_accumulation_interval"))
async def cmd_tlgrm_accumulation_interval(message: types.Message):
    """Set ACCUMULATION interval window in days (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('accumulation_interval_days', '14')
        await message.answer(f"Current: {current} days\nUsage: `/tlgrm_accumulation_interval <days>`", parse_mode="Markdown")
        return
    
    try:
        days = float(parts[1])
        _insider_alerts_service.update_setting('accumulation_interval_days', str(days))
        await message.answer(f"✅ ACCUMULATION interval: {days} days")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_accumulation_min"))
async def cmd_tlgrm_accumulation_min(message: types.Message):
    """Set ACCUMULATION minimum trade size in USD (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('accumulation_min_usd', '10000')
        await message.answer(f"Current: ${current}\nUsage: `/tlgrm_accumulation_min <usd>`", parse_mode="Markdown")
        return
    
    try:
        usd = float(parts[1].replace(',', '').replace('$', ''))
        _insider_alerts_service.update_setting('accumulation_min_usd', str(usd))
        await message.answer(f"✅ ACCUMULATION min trade size: ${usd:,.0f}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_accumulation_total"))
async def cmd_tlgrm_accumulation_total(message: types.Message):
    """Set ACCUMULATION minimum total volume in USD (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('accumulation_min_total_usd', '50000')
        await message.answer(f"Current: ${current}\nUsage: `/tlgrm_accumulation_total <usd>`", parse_mode="Markdown")
        return
    
    try:
        usd = float(parts[1].replace(',', '').replace('$', ''))
        _insider_alerts_service.update_setting('accumulation_min_total_usd', str(usd))
        await message.answer(f"✅ ACCUMULATION min total volume: ${usd:,.0f}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_accumulation_wallets"))
async def cmd_tlgrm_accumulation_wallets(message: types.Message):
    """Set ACCUMULATION minimum wallets count (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('accumulation_min_wallets', '3')
        await message.answer(f"Current: {current}\nUsage: `/tlgrm_accumulation_wallets <count>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        _insider_alerts_service.update_setting('accumulation_min_wallets', str(count))
        await message.answer(f"✅ ACCUMULATION min wallets: {count}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_accumulation_pos"))
async def cmd_tlgrm_accumulation_pos(message: types.Message):
    """Set ACCUMULATION maximum open positions (owner only)."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('accumulation_max_positions', '3')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_accumulation_pos <count>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        _insider_alerts_service.update_setting('accumulation_max_positions', str(count))
        await message.answer(f"✅ ACCUMULATION max positions: {count}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_accumulation_direction"))
async def cmd_tlgrm_accumulation_direction(message: types.Message):
    """Set ACCUMULATION minimum directionality % (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('accumulation_min_direction_pct', '70')
        await message.answer(f"Current: {current}%\nUsage: `/tlgrm_accumulation_direction <percent>`", parse_mode="Markdown")
        return
    
    try:
        pct = float(parts[1].replace('%', ''))
        _insider_alerts_service.update_setting('accumulation_min_direction_pct', str(pct))
        await message.answer(f"✅ ACCUMULATION min directionality: {pct}%")
    except ValueError:
        await message.answer("❌ Invalid number")


# BURST commands
@dp.message(Command("tlgrm_burst"))
async def cmd_tlgrm_burst(message: types.Message):
    """Toggle BURST scenario (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        status = _insider_alerts_service.get_status()['scenarios']['BURST']
        enabled_str = "✅ enabled" if status['enabled'] else "❌ disabled"
        await message.answer(f"BURST: {enabled_str}\nUsage: `/tlgrm_burst on|off`", parse_mode="Markdown")
        return
    
    arg = parts[1].lower()
    if arg in ['on', '1', 'yes', 'true']:
        _insider_alerts_service.update_setting('burst_enabled', 'true')
        await message.answer("✅ BURST scenario enabled")
    elif arg in ['off', '0', 'no', 'false']:
        _insider_alerts_service.update_setting('burst_enabled', 'false')
        await message.answer("❌ BURST scenario disabled")
    else:
        await message.answer("Usage: `/tlgrm_burst on|off`", parse_mode="Markdown")


@dp.message(Command("tlgrm_burst_interval"))
async def cmd_tlgrm_burst_interval(message: types.Message):
    """Set BURST interval in hours (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('burst_interval_hours', '1')
        await message.answer(f"Current: {current}h\nUsage: `/tlgrm_burst_interval <hours>`", parse_mode="Markdown")
        return
    
    try:
        hours = float(parts[1])
        _insider_alerts_service.update_setting('burst_interval_hours', str(hours))
        await message.answer(f"✅ BURST interval: {hours}h")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_burst_min"))
async def cmd_tlgrm_burst_min(message: types.Message):
    """Set BURST minimum trade size in USD (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('burst_min_usd', '1000')
        await message.answer(f"Current: ${current}\nUsage: `/tlgrm_burst_min <usd>`", parse_mode="Markdown")
        return
    
    try:
        usd = float(parts[1].replace(',', '').replace('$', ''))
        _insider_alerts_service.update_setting('burst_min_usd', str(usd))
        await message.answer(f"✅ BURST min trade size: ${usd:,.0f}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_burst_wallets"))
async def cmd_tlgrm_burst_wallets(message: types.Message):
    """Set BURST minimum wallet count (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('burst_min_wallets', '8')
        await message.answer(f"Current: {current}\nUsage: `/tlgrm_burst_wallets <count>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        _insider_alerts_service.update_setting('burst_min_wallets', str(count))
        await message.answer(f"✅ BURST min wallets: {count}")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_burst_direction"))
async def cmd_tlgrm_burst_direction(message: types.Message):
    """Set BURST minimum directionality % (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    
    if not _insider_alerts_service:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        current = _insider_alerts_service.settings.get('burst_min_direction_pct', '70')
        await message.answer(f"Current: {current}%\nUsage: `/tlgrm_burst_direction <percent>`", parse_mode="Markdown")
        return
    
    try:
        pct = float(parts[1].replace('%', ''))
        _insider_alerts_service.update_setting('burst_min_direction_pct', str(pct))
        await message.answer(f"✅ BURST min directionality: {pct}%")
    except ValueError:
        await message.answer("❌ Invalid number")


@dp.message(Command("tlgrm_burst_pos"))
async def cmd_tlgrm_burst_pos(message: types.Message):
    """Set BURST maximum open positions (owner only)."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('burst_max_positions', '3')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_burst_pos <count>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        _insider_alerts_service.update_setting('burst_max_positions', str(count))
        await message.answer(f"✅ BURST max positions: {count}")
    except ValueError:
        await message.answer("❌ Invalid number")

@dp.message(Command("tlgrm_cat"))
async def cmd_tlgrm_cat(message: types.Message):
    """Set category enabled status (owner only)."""
    if message.chat.id != OWNER_ID:
        return
    if not _insider_alerts_service:
        return

    parts = message.text.split()
    if len(parts) < 3:
        status = _insider_alerts_service.get_status()['categories']
        msg = "📂 **Categories:**\n"
        for k, v in status.items():
            icon = "✅" if v == 'true' else "❌"
            msg += f"{icon} {k}\n"
        
        msg += "\nUsage: `/tlgrm_cat <sport/crypto/other> on|off`"
        await message.answer(msg, parse_mode="Markdown")
        return

    cat = parts[1].lower()
    val = parts[2].lower()
    
    if cat not in ['sports', 'crypto', 'other']:
        await message.answer("❌ Invalid category. Use: sports, crypto, other")
        return

    enabled = 'true' if val in ['on', 'true', '1', 'yes'] else 'false'
    key = f"cat_{cat}_enabled"
    _insider_alerts_service.update_setting(key, enabled)
    
    await message.answer(f"✅ Category **{cat}** set to {enabled}")


# Extended CLUSTER Commands
@dp.message(Command("tlgrm_cluster_side"))
async def cmd_tlgrm_cluster_side(message: types.Message):
    """Set CLUSTER side filter (buy/sell/both)."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('cluster_side', 'both')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_cluster_side buy|sell|both`", parse_mode="Markdown")
        return
        
    side = parts[1].lower()
    if side not in ['buy', 'sell', 'both']:
        await message.answer("❌ Invalid side. Use: buy, sell, both")
        return
        
    _insider_alerts_service.update_setting('cluster_side', side)
    await message.answer(f"✅ CLUSTER side filter set to: {side}")

@dp.message(Command("tlgrm_cluster_total"))
async def cmd_tlgrm_cluster_total(message: types.Message):
    """Set CLUSTER min total volume."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('cluster_min_total_usd', '10000')
        await message.answer(f"Current: ${curr}\nUsage: `/tlgrm_cluster_total <usd>`", parse_mode="Markdown")
        return
        
    try:
        usd = float(parts[1].replace(',', '').replace('$', ''))
        _insider_alerts_service.update_setting('cluster_min_total_usd', str(usd))
        await message.answer(f"✅ CLUSTER min total volume: ${usd:,.0f}")
    except ValueError:
        await message.answer("❌ Invalid number")

@dp.message(Command("tlgrm_cluster_profiles"))
async def cmd_tlgrm_cluster_profiles(message: types.Message):
    """Toggle displaying profiles in CLUSTER alerts."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return

    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('cluster_include_profiles', 'true')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_cluster_profiles on|off`", parse_mode="Markdown")
        return

    arg = parts[1].lower()
    val = 'true' if arg in ['on', 'true', '1', 'yes'] else 'false'
    _insider_alerts_service.update_setting('cluster_include_profiles', val)
    await message.answer(f"✅ CLUSTER include profiles: {val}")

@dp.message(Command("tlgrm_cluster_show"))
async def cmd_tlgrm_cluster_show(message: types.Message):
    """Show detailed CLUSTER settings."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    s = _insider_alerts_service.settings
    msg = f"""**CLUSTER Configuration:**
Enabled: {s.get('cluster_enabled')}
Interval: {s.get('cluster_interval_hours')}h
Max Wallet Age: {s.get('cluster_wallet_age_hours')}h
Min Wallet Size: ${s.get('cluster_min_usd')}
Min Total Vol: ${s.get('cluster_min_total_usd')}
Min Wallets: {s.get('cluster_min_wallets')}
Min Directionality: {s.get('cluster_min_direction_pct')}%
Side Filter: {s.get('cluster_side')}
Show Profiles: {s.get('cluster_include_profiles')}
"""
    await message.answer(msg, parse_mode="Markdown")

@dp.message(Command("tlgrm_cluster_reset"))
async def cmd_tlgrm_cluster_reset(message: types.Message):
    """Reset CLUSTER settings to default."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    defaults = {
        'cluster_interval_hours': '2',
        'cluster_wallet_age_hours': '24',
        'cluster_min_usd': '5000',
        'cluster_min_total_usd': '10000',
        'cluster_min_wallets': '4',
        'cluster_min_direction_pct': '75',
        'cluster_side': 'both',
        'cluster_include_profiles': 'true'
    }
    for k, v in defaults.items():
        _insider_alerts_service.update_setting(k, v)
        
    await message.answer("✅ CLUSTER settings reset to defaults.")


# Extended BURST Commands
@dp.message(Command("tlgrm_burst_age"))
async def cmd_tlgrm_burst_age(message: types.Message):
    """Set BURST max wallet age."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('burst_wallet_age_hours', '72')
        await message.answer(f"Current: {curr}h\nUsage: `/tlgrm_burst_age <hours>`", parse_mode="Markdown")
        return
        
    try:
        hours = float(parts[1])
        _insider_alerts_service.update_setting('burst_wallet_age_hours', str(hours))
        await message.answer(f"✅ BURST max wallet age: {hours}h")
    except ValueError:
        await message.answer("❌ Invalid number")

@dp.message(Command("tlgrm_burst_total"))
async def cmd_tlgrm_burst_total(message: types.Message):
    """Set BURST min total volume."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('burst_min_total_usd', '5000')
        await message.answer(f"Current: ${curr}\nUsage: `/tlgrm_burst_total <usd>`", parse_mode="Markdown")
        return
        
    try:
        usd = float(parts[1].replace(',', '').replace('$', ''))
        _insider_alerts_service.update_setting('burst_min_total_usd', str(usd))
        await message.answer(f"✅ BURST min total volume: ${usd:,.0f}")
    except ValueError:
        await message.answer("❌ Invalid number")

@dp.message(Command("tlgrm_burst_profiles"))
async def cmd_tlgrm_burst_profiles(message: types.Message):
    """Toggle displaying profiles in BURST alerts."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return

    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('burst_include_profiles', 'true')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_burst_profiles on|off`", parse_mode="Markdown")
        return

    arg = parts[1].lower()
    val = 'true' if arg in ['on', 'true', '1', 'yes'] else 'false'
    _insider_alerts_service.update_setting('burst_include_profiles', val)
    await message.answer(f"✅ BURST include profiles: {val}")

@dp.message(Command("tlgrm_burst_show"))
async def cmd_tlgrm_burst_show(message: types.Message):
    """Show detailed BURST settings."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    s = _insider_alerts_service.settings
    msg = f"""**BURST Configuration:**
Enabled: {s.get('burst_enabled')}
Interval: {s.get('burst_interval_hours')}h
Max Wallet Age: {s.get('burst_wallet_age_hours')}h
Min Wallet Size: ${s.get('burst_min_usd')}
Min Total Vol: ${s.get('burst_min_total_usd')}
Min Wallets: {s.get('burst_min_wallets')}
Min Directionality: {s.get('burst_min_direction_pct')}%
Show Profiles: {s.get('burst_include_profiles')}
"""
    await message.answer(msg, parse_mode="Markdown")

@dp.message(Command("tlgrm_burst_reset"))
async def cmd_tlgrm_burst_reset(message: types.Message):
    """Reset BURST settings to default."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    defaults = {
        'burst_interval_hours': '1',
        'burst_wallet_age_hours': '72',
        'burst_min_usd': '1000',
        'burst_min_total_usd': '5000',
        'burst_min_wallets': '8',
        'burst_min_direction_pct': '70',
        'burst_include_profiles': 'true'
    }
    for k, v in defaults.items():
        _insider_alerts_service.update_setting(k, v)
        
    await message.answer("✅ BURST settings reset to defaults.")


# Extended ACCUMULATION Commands
@dp.message(Command("tlgrm_accumulation_age"))
async def cmd_tlgrm_accumulation_age(message: types.Message):
    """Set ACCUMULATION max wallet age."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('accumulation_wallet_age_hours', '48')
        await message.answer(f"Current: {curr}h\nUsage: `/tlgrm_accumulation_age <hours>`", parse_mode="Markdown")
        return
        
    try:
        hours = float(parts[1])
        _insider_alerts_service.update_setting('accumulation_wallet_age_hours', str(hours))
        await message.answer(f"✅ ACCUMULATION max wallet age: {hours}h")
    except ValueError:
        await message.answer("❌ Invalid number")

@dp.message(Command("tlgrm_accumulation_profiles"))
async def cmd_tlgrm_accumulation_profiles(message: types.Message):
    """Toggle displaying profiles in ACCUMULATION alerts."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return

    parts = message.text.split()
    if len(parts) < 2:
        curr = _insider_alerts_service.settings.get('accumulation_include_profiles', 'true')
        await message.answer(f"Current: {curr}\nUsage: `/tlgrm_accumulation_profiles on|off`", parse_mode="Markdown")
        return

    arg = parts[1].lower()
    val = 'true' if arg in ['on', 'true', '1', 'yes'] else 'false'
    _insider_alerts_service.update_setting('accumulation_include_profiles', val)
    await message.answer(f"✅ ACCUMULATION include profiles: {val}")

@dp.message(Command("tlgrm_accumulation_show"))
async def cmd_tlgrm_accumulation_show(message: types.Message):
    """Show detailed ACCUMULATION settings."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    s = _insider_alerts_service.settings
    msg = f"""**ACCUMULATION Configuration:**
Enabled: {s.get('accumulation_enabled')}
Interval: {s.get('accumulation_interval_days')}d
Max Wallet Age: {s.get('accumulation_wallet_age_hours')}h
Min Trade Size: ${s.get('accumulation_min_usd')}
Min Total Volume: ${s.get('accumulation_min_total_usd')}
Min Wallets: {s.get('accumulation_min_wallets')}
Min Directionality: {s.get('accumulation_min_direction_pct')}%
Max Positions: {s.get('accumulation_max_positions')}
Show Profiles: {s.get('accumulation_include_profiles')}
"""
    await message.answer(msg, parse_mode="Markdown")

@dp.message(Command("tlgrm_accumulation_reset"))
async def cmd_tlgrm_accumulation_reset(message: types.Message):
    """Reset ACCUMULATION settings to default."""
    if message.chat.id != OWNER_ID: return
    if not _insider_alerts_service: return
    
    defaults = {
        'accumulation_interval_days': '14',
        'accumulation_min_usd': '10000',
        'accumulation_min_total_usd': '50000',
        'accumulation_min_wallets': '3',
        'accumulation_wallet_age_hours': '48',
        'accumulation_min_direction_pct': '70',
        'accumulation_include_profiles': 'true',
        'accumulation_max_positions': '3'
    }
    for k, v in defaults.items():
        _insider_alerts_service.update_setting(k, v)
        
    await message.answer("✅ ACCUMULATION settings reset to defaults.")




async def send_admin_notification(message: str, parse_mode="HTML"):
    """Send notification message to bot owner/admin."""
    try:
        if OWNER_ID:
            await bot.send_message(
                chat_id=OWNER_ID,
                text=message,
                parse_mode=parse_mode
            )
            logger.info("Admin notification sent")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

async def start_telegram():
    try:
        logger.info("Starting Telegram Bot Polling...")
        # Load mute state on startup
        load_mute_state()
        logger.info("Mute state loaded")
        
        # Start queue system
        start_queue_workers()
        logger.info("Queue workers started")
        
        # Start periodic cleanup task
        asyncio.create_task(_periodic_cleanup())
        logger.info("Periodic cleanup task started")
        
        logger.info("Starting dp.start_polling()...")
        # Add heartbeat task to monitor polling health
        async def polling_heartbeat():
            """Log heartbeat every 5 minutes to confirm polling is alive."""
            while True:
                await asyncio.sleep(300)  # 5 minutes
                logger.info("💓 Telegram polling heartbeat - still alive")
        asyncio.create_task(polling_heartbeat())
        
        await dp.start_polling(bot)
        logger.info("dp.start_polling() completed (should not happen normally)")
    except Exception as e:
        logger.error(f"CRITICAL: Error in start_telegram(): {e}", exc_info=True)
        raise

async def _periodic_cleanup():
    """Periodic cleanup of mute state (every hour)."""
    while True:
        await asyncio.sleep(3600)  # 1 hour
        cleanup_mute_state()


def get_trade_alert_keyboard(lang: str, whale_key: str, is_saved: bool, level_icon: str = "🦐"):
    """Create inline keyboard for trade alerts."""
    if is_saved:
        save_text = get_text(lang, 'saved_btn')
        save_callback = f"saved:{whale_key}"
    else:
        # Use dynamic level icon + "To Aquarium" text
        save_text = f"{level_icon} {get_text(lang, 'save_btn')}"
        save_callback = f"save:{whale_key}"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=save_text, callback_data=save_callback),
            InlineKeyboardButton(text=get_text(lang, 'note_btn'), callback_data=f"note:{whale_key}"),
        ]
    ])


def _get_mute_duration(chat_id: int) -> int:
    """Get mute duration based on escalation level."""
    level = mute_level.get(chat_id, 0)
    if level == 0:
        level = 1  # First mute
    if level > 3:
        level = 3
    return MUTE_DURATIONS[level]

def _apply_mute(chat_id: int, reason: str, mute_seconds: int = None):
    """Apply mute to chat_id."""
    now = time.time()
    
    # Escalate level if needed (reset if 24h passed since last mute)
    current_level = mute_level.get(chat_id, 0)
    last_mute = last_mute_time.get(chat_id, 0)
    if now - last_mute > 86400:  # 24 hours passed
        mute_level[chat_id] = 1
    else:
        mute_level[chat_id] = min(current_level + 1, 3)
    
    # Determine mute duration (use provided or calculate from level)
    if mute_seconds is None:
        mute_seconds = _get_mute_duration(chat_id)
    
    muted_until[chat_id] = now + mute_seconds
    last_mute_time[chat_id] = now
    last_fail_reason[chat_id] = reason
    
    # Save state after applying mute
    save_mute_state()
    
    return mute_seconds

def _is_muted(chat_id: int) -> tuple[bool, float]:
    """Check if chat_id is muted. Returns (is_muted, seconds_left)."""
    if chat_id not in muted_until:
        return False, 0.0
    
    now = time.time()
    mute_until = muted_until[chat_id]
    
    if now < mute_until:
        return True, mute_until - now
    else:
        # Mute expired, clean up
        muted_until.pop(chat_id, None)
        return False, 0.0

async def _log_mute_stats():
    """Log mute statistics (called periodically)."""
    global _stats_reset_time
    
    async with _stats_lock:
        now = time.time()
        # Count currently muted users
        muted_list = []
        for cid, mute_until_ts in list(muted_until.items()):
            if now < mute_until_ts:
                muted_list.append((cid, mute_until_ts - now))
            else:
                # Clean up expired mutes
                muted_until.pop(cid, None)
        
        muted_count = len(muted_list)
        
        # Get top muted chat_ids
        muted_list.sort(key=lambda x: x[1], reverse=True)
        top_muted = muted_list[:5]
        
        # Get retryafter count from queue_stats
        async with _queue_stats_lock:
            retryafter_count = queue_stats.get('retryafter_min', 0)
        
        logger.info(
            f"📊 Mute stats: muted_count={muted_count}, "
            f"retryafter_per_min={retryafter_count}, "
            f"top_muted={[(cid, int(secs)) for cid, secs in top_muted]}"
        )
        
        _stats_reset_time = now

async def enqueue_trade_alert(chat_id, message_text, whale_key: str = None, is_saved: bool = False, level_icon: str = "🦐"):
    """
    Add trade alert to queue for sending.
    Returns immediately (fire-and-forget).
    Falls back to direct send if queue is disabled.
    """
    if not chat_id:
        return
    
    # Fallback to direct send if queue is disabled
    if not _queue_enabled or alert_queue is None:
        await send_trade_alert(chat_id, message_text, whale_key, is_saved, level_icon)
        return
    
    enqueued_at = time.time()
    task = {
        'chat_id': chat_id,
        'message_text': message_text,
        'whale_key': whale_key,
        'is_saved': is_saved,
        'level_icon': level_icon,
        'enqueued_at': enqueued_at,
    }
    
    # Update oldest task tracking
    async with _queue_oldest_lock:
        global _queue_oldest_enqueued
        if _queue_oldest_enqueued is None or enqueued_at < _queue_oldest_enqueued:
            _queue_oldest_enqueued = enqueued_at
    
    try:
        alert_queue.put_nowait(task)
    except asyncio.QueueFull:
        # Drop new task and log
        async with _queue_stats_lock:
            queue_stats['dropped_total'] += 1
            queue_stats['dropped_per_min'] += 1
        
        logger.warning(f"QUEUE_FULL dropped=1 queue_size={alert_queue.qsize()}")
        return

async def _per_chat_rate_limiter_wait(chat_id: int):
    """Wait if needed to respect per-chat rate limit."""
    async with _per_chat_lock:
        now = time.time()
        next_send = _per_chat_next_send.get(chat_id, 0)
        delay = max(0, next_send - now)
        _per_chat_next_send[chat_id] = now + delay + (1.0 / PER_CHAT_RATE)
    
    if delay > 0:
        await asyncio.sleep(delay)

async def _queue_worker(worker_id: int):
    """Worker that processes tasks from the queue."""
    logger.info(f"📤 Queue worker {worker_id} started")
    
    while True:
        try:
            # Get task from queue (blocks until available)
            task = await alert_queue.get()
            
            chat_id = task['chat_id']
            message_text = task['message_text']
            whale_key = task.get('whale_key')
            is_saved = task.get('is_saved', False)
            level_icon = task.get('level_icon', '🦐')
            enqueued_at = task.get('enqueued_at', time.time())
            
            # Update oldest task tracking (this task is being processed)
            # If this was the oldest task, we need to find the new oldest
            # Since we can't peek into queue, we reset and let next enqueue set it
            async with _queue_oldest_lock:
                global _queue_oldest_enqueued
                if _queue_oldest_enqueued == enqueued_at:
                    # This was the oldest, reset to None (will be updated by next enqueue)
                    _queue_oldest_enqueued = None
                    # If queue is not empty, we can't know the new oldest without peeking
                    # So we'll wait for next enqueue to set it, or it will be None until then
            
            # Apply rate limiters
            if global_rate_limiter:
                await global_rate_limiter.acquire()
            await _per_chat_rate_limiter_wait(chat_id)
            
            # Send the alert
            try:
                await send_trade_alert(chat_id, message_text, whale_key, is_saved, level_icon)
                
                # Update stats on success
                async with _queue_stats_lock:
                    queue_stats['sent_total'] += 1
                    queue_stats['sent_per_min'] += 1
                    
            except Exception as e:
                # Log error and update stats
                logger.error(f"❌ Queue worker {worker_id} error sending to {chat_id}: {e}")
                async with _queue_stats_lock:
                    queue_stats['error_total'] += 1
            
            # Mark task as done
            alert_queue.task_done()
            
        except asyncio.CancelledError:
            logger.info(f"📤 Queue worker {worker_id} cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Queue worker {worker_id} unexpected error: {e}")
            # Continue processing

async def _get_queue_age_stats():
    """Get oldest and average age of tasks in queue."""
    if not alert_queue or alert_queue.empty():
        return None, None
    
    # We can't peek into queue, so we use tracked oldest
    async with _queue_oldest_lock:
        oldest_enqueued = _queue_oldest_enqueued
    
    if oldest_enqueued is None:
        return None, None
    
    now = time.time()
    oldest_age_sec = now - oldest_enqueued
    
    # For avg_age, we estimate based on queue size and processing rate
    # This is an approximation since we can't access queue items
    queue_size = alert_queue.qsize()
    if queue_size > 1:
        # Estimate: tasks are distributed evenly, so avg is roughly half of oldest
        avg_age_sec = oldest_age_sec / 2
    else:
        avg_age_sec = oldest_age_sec
    
    return oldest_age_sec, avg_age_sec

async def _log_queue_stats():
    """Periodically log queue statistics."""
    global _queue_stats_reset_time, _queue_lag_warn_count
    
    while True:
        await asyncio.sleep(60)  # Every minute
        
        try:
            async with _queue_stats_lock:
                queue_size = alert_queue.qsize() if alert_queue else 0
                oldest_age_sec, avg_age_sec = await _get_queue_age_stats()
                
                age_info = ""
                if oldest_age_sec is not None:
                    age_info = f", oldest_age_sec={int(oldest_age_sec)}"
                    if avg_age_sec is not None:
                        age_info += f", avg_age_sec={int(avg_age_sec)}"
                
                # Check for warnings
                warnings = []
                
                # WARN_QUEUE_DROPS if dropped_per_min > 0
                if queue_stats.get('dropped_per_min', 0) > 0:
                    warnings.append("WARN_QUEUE_DROPS")
                
                # WARN_QUEUE_LAG if oldest_age_sec > 120s for 3 consecutive minutes
                if oldest_age_sec is not None and oldest_age_sec > 120:
                    _queue_lag_warn_count += 1
                    if _queue_lag_warn_count >= 3:
                        warnings.append("WARN_QUEUE_LAG")
                else:
                    _queue_lag_warn_count = 0  # Reset counter if lag is resolved
                
                warn_info = ""
                if warnings:
                    warn_info = f", warnings=[{', '.join(warnings)}]"
                
                retryafter_count = queue_stats.get('retryafter_min', 0)
                
                logger.info(
                    f"📊 Queue stats: queue_size={queue_size}{age_info}, "
                    f"sent_per_min={queue_stats.get('sent_per_min', 0)}, "
                    f"dropped_per_min={queue_stats.get('dropped_per_min', 0)}, "
                    f"retryafter_per_min={retryafter_count}, "
                    f"worker_count={len(worker_tasks)}{warn_info}"
                )
                
                # Reset per-minute counters
                queue_stats['sent_per_min'] = 0
                queue_stats['dropped_per_min'] = 0
                queue_stats['retryafter_min'] = 0
                _queue_stats_reset_time = time.time()
        except Exception as e:
            import traceback
            logger.error(f"❌ Error in _log_queue_stats(): {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)  # Short sleep before retry

def start_queue_workers():
    """Start queue workers and initialize queue."""
    global alert_queue, global_rate_limiter, worker_tasks, _queue_enabled
    
    # Check if aiolimiter is available
    if not _aiolimiter_available:
        logger.error(
            "❌ CRITICAL: aiolimiter not installed! Queue system disabled.\n"
            "Install with: pip install aiolimiter\n"
            "Falling back to direct send (no rate limiting)."
        )
        _queue_enabled = False
        return
    
    logger.info(f"✅ aiolimiter version: {_aiolimiter_version}")
    
    # Initialize queue
    alert_queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
    
    # Initialize global rate limiter
    global_rate_limiter = AsyncLimiter(GLOBAL_RATE, 1)
    
    # Start workers
    worker_tasks = []
    for i in range(WORKER_COUNT):
        task = asyncio.create_task(_queue_worker(i + 1))
        worker_tasks.append(task)
    
    # Start stats logging (includes both queue and mute stats)
    asyncio.create_task(_log_queue_stats())
    asyncio.create_task(_log_mute_stats_periodic())
    
    _queue_enabled = True
    logger.info(f"📤 Queue system started: {WORKER_COUNT} workers, max_size={QUEUE_MAX_SIZE}, global_rate={GLOBAL_RATE}/sec, per_chat_rate={PER_CHAT_RATE}/sec")

async def _log_mute_stats_periodic():
    """Periodically log mute statistics (called from queue system)."""
    while True:
        await asyncio.sleep(60)  # Every minute
        await _log_mute_stats()

async def stop_queue_workers():
    """Stop queue workers gracefully."""
    global worker_tasks
    
    if not alert_queue or not worker_tasks:
        return
    
    logger.info("📤 Stopping queue workers...")
    
    # Wait for queue to empty (with timeout)
    try:
        await asyncio.wait_for(alert_queue.join(), timeout=10.0)
        logger.info("📤 Queue emptied, all tasks processed")
    except asyncio.TimeoutError:
        logger.warning("📤 Queue join timeout (10s), cancelling workers")
    
    # Cancel all workers
    for task in worker_tasks:
        if not task.done():
            task.cancel()
    
    # Wait for cancellation
    if worker_tasks:
        await asyncio.gather(*worker_tasks, return_exceptions=True)
    
    worker_tasks = []
    logger.info("📤 Queue workers stopped")

async def send_trade_alert(chat_id, message_text, whale_key: str = None, is_saved: bool = False, level_icon: str = "🦐"):
    """
    Send trade alert with robust error handling (RetryAfter) and auto-mute for problematic users.
    """
    if not chat_id:
        return
    
    # A) Check if muted before any sending attempt
    is_muted, seconds_left = _is_muted(chat_id)
    if is_muted:
        until_ts = muted_until.get(chat_id, time.time())
        until_iso = datetime.fromtimestamp(until_ts).strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"🔇 MUTED_SKIP chat_id={chat_id} seconds_left={int(seconds_left)} until_iso={until_iso}")
        return  # Skip sending, return immediately
        
    lang = get_user_lang(chat_id)
    reply_markup = None
    if whale_key:
        reply_markup = get_trade_alert_keyboard(lang, whale_key, is_saved, level_icon)

    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            # B) Success - reset fail streak and optionally reset mute level
            fail_streak[chat_id] = 0
            last_fail_reason.pop(chat_id, None)
            
            # Reset mute level if 24 hours passed since last mute and no errors
            now = time.time()
            last_mute = last_mute_time.get(chat_id, 0)
            if now - last_mute > 86400:  # 24 hours
                mute_level.pop(chat_id, None)
                save_mute_state()  # Save state after reset
            
            # Optional: log success (can be less frequent)
            if attempt > 0:
                logger.info(f"✅ SEND_OK chat_id={chat_id} after_retry={attempt}")
            return  # Success, exit function
            
        except TelegramRetryAfter as e:
            # C) Handle TelegramRetryAfter
            async with _queue_stats_lock:
                queue_stats['retryafter_min'] += 1
            
            wait_time = e.retry_after
            
            # Hotfix for problematic chat_id
            if chat_id == HOTFIX_CHAT_ID and wait_time > HOTFIX_THRESHOLD:
                mute_seconds = _apply_mute(chat_id, f"hotfix_retryafter_{wait_time}s", mute_seconds=HOTFIX_MUTE)
                until_ts = muted_until.get(chat_id, time.time())
                until_iso = datetime.fromtimestamp(until_ts).strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"🔇 MUTED chat_id={chat_id} retry_after={wait_time}s mute_for={mute_seconds}s until_iso={until_iso} (hotfix)")
                return
            
            if wait_time <= RETRY_SHORT_MAX:
                # Short retry - attempt once
                logger.warning(f"⚠️ RETRY_AFTER short chat_id={chat_id} retry_after={wait_time}s attempt={attempt+1}")
                await asyncio.sleep(wait_time)
                # Loop will continue and retry
            else:
                # Long retry - mute immediately
                mute_seconds = _apply_mute(chat_id, f"retryafter_{wait_time}s")
                until_ts = muted_until.get(chat_id, time.time())
                until_iso = datetime.fromtimestamp(until_ts).strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"🔇 MUTED chat_id={chat_id} retry_after={wait_time}s mute_for={mute_seconds}s until_iso={until_iso}")
                return  # Don't retry, user is muted
            
        except TelegramForbiddenError:
            # User blocked the bot or account deactivated
            logger.info(f"🛑 User {chat_id} blocked the bot/deactivated. Auto-stopping.")
            try:
                if user_statuses.get(chat_id):
                    user_statuses[chat_id] = False
                # Mark as blocked (with timestamp)
                blocked_users[chat_id] = int(time.time())
                save_settings()
            except Exception as e2:
                logger.error(f"Error auto-stopping user {chat_id}: {e2}")
            return  # Stop trying
            
        except Exception as e:
            # D) Other errors - track streak
            fail_streak[chat_id] = fail_streak.get(chat_id, 0) + 1
            streak = fail_streak[chat_id]
            error_str = str(e)
            last_fail_reason[chat_id] = error_str
            
            logger.warning(f"⚠️ SEND_FAIL chat_id={chat_id} streak={streak} error={error_str}")
            
            if streak >= FAIL_STREAK_MUTE_THRESHOLD:
                # Mute after 3 consecutive failures
                mute_seconds = _apply_mute(chat_id, "consecutive_failures")
                until_ts = muted_until.get(chat_id, time.time())
                until_iso = datetime.fromtimestamp(until_ts).strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"🔇 MUTED chat_id={chat_id} reason=consecutive_failures mute_for={mute_seconds}s until_iso={until_iso}")
                return  # Stop trying
            
            # Continue retrying if streak < 3
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Brief delay before retry

