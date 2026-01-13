from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import hashlib
from config import TELEGRAM_BOT_TOKEN, FILTERS, OWNER_ID
from core.localization import get_text
from storage import saved_whales
from services.report_service import generate_report


def shorten_trader_name(name):
    """
    Shorten trader name:
    1. Remove timestamp suffix (starting with '-') if present.
    2. Truncate long addresses: 0xB0B1Ecb5eD8a22d38Ee89f20b196246005d37507 -> 0xB0B1E...37507
    """
    if not name:
        return "Unknown"
    
    # Check if it looks like a wallet address (starts with 0x)
    clean_name = name
    if name.startswith("0x"):
        # Split by '-' to remove potential timestamp suffix
        parts = name.split('-')
        clean_name = parts[0]
        
        # If it's a long wallet address, truncate it
        if len(clean_name) > 15:
            return f"{clean_name[:7]}...{clean_name[-5:]}"
            
    return clean_name

# Global reference to PolymarketService instance (set during startup)
_poly_service = None

def set_poly_service(service):
    """Store reference to PolymarketService for report generation."""
    global _poly_service
    _poly_service = service

# FSM States for note input
class NoteState(StatesGroup):
    waiting_for_note = State()

# FSM States for age and positions filter input
class AgeFilterState(StatesGroup):
    waiting_for_range = State()

class PositionsFilterState(StatesGroup):
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
                bot_enabled = data.get('bot_enabled', True)  # Default: enabled
                return filters, categories, languages, statuses, usernames, probabilities, side_types, wallet_ages, open_positions, bot_enabled
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
    return {}, {}, {}, {}, {}, {}, {}, {}, {}, True  # Default: enabled

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
            'bot_enabled': bot_enabled
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

# Load settings on startup
user_filters, user_categories, user_languages, user_statuses, user_usernames, user_probabilities, user_side_types, user_wallet_ages, user_open_positions, bot_enabled = load_settings()

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
    return {'all': True, 'other': True, 'crypto': True, 'sports': True}

def get_default_side_types():
    """Default side type preferences - only BUY and SELL enabled."""
    return {'all': False, 'BUY': True, 'SELL': True, 'SPLIT': False, 'MERGE': False, 'REDEEM': False}

def ensure_user_exists(chat_id):
    """Ensure user has all necessary settings initialized."""
    chat_id = int(chat_id) # Strict type coercion
    
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
        resize_keyboard=True,
        is_persistent=True
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
        resize_keyboard=True,
        is_persistent=True
    )

def get_collapsed_keyboard(chat_id):
    """Create minimal keyboard with only 'Show Menu' button."""
    lang = get_user_lang(chat_id)
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(lang, 'btn_show_menu'))]
        ],
        resize_keyboard=True,
        is_persistent=True
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
    for key, label in options:
        text = f"✅ {label}" if key == current else label
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"prob_{key}")])
    
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
    prob_text = get_text(lang, f'prob_{prob_key}')
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
        await message.answer(get_text(lang, 'saved_empty'))


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
        
    text = "\n".join(lines)
    
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
        
        # Done Button
        done_text = "✅ Готово" if lang == 'ru' else "✅ Done"
        buttons.append([InlineKeyboardButton(text=done_text, callback_data=f"aq_mode:view:{page}")])
        
    else:
        # View Mode: [ Edit List ] [ Clear All ]
        edit_text = "✏️ Редакт" if lang == 'ru' else "✏️ Edit List"
        clear_text = "🗑 Очистить" if lang == 'ru' else "🗑 Clear All"
        
        action_row = [
            InlineKeyboardButton(text=edit_text, callback_data=f"aq_mode:edit:{page}"),
            InlineKeyboardButton(text=clear_text, callback_data=f"clearall")
        ]
        buttons.append(action_row)
        
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
        # Empty
        await message.answer(get_text(lang, 'saved_empty'))


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
    """Handle click on already saved button."""
    lang = get_user_lang(callback.message.chat.id)
    await callback.answer(get_text(lang, 'saved_btn'))


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

@dp.callback_query(F.data.startswith("prob_"))
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

def get_user_min_threshold(chat_id):
    """Get user's minimum threshold. Return default if not set."""
    return user_filters.get(chat_id, FILTERS[-1]['min'])

def get_user_categories(chat_id):
    """Get user's category preferences."""
    return user_categories.get(chat_id, get_default_categories())

def get_user_probability_filter(chat_id):
    """Get user's probability filter setting. Returns (min, max) tuple or None."""
    prob_key = user_probabilities.get(chat_id, 'any')
    return PROBABILITY_OPTIONS.get(prob_key, None)

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
    if message.chat.id != OWNER_ID:
        return
    
    msg = """🔐 **Команды администратора**

🤖 **Управление ботом:**
`/bot_stop` — остановить отправку алертов
`/bot_start` — возобновить отправку алертов

📊 **Статистика:**
`/stats` — статистика бота
`/users` — список пользователей
`/cache` — кэш возраста кошельков
`/report` — полный отчет о системе

📢 **Рассылка:**
`/broadcast <текст>` — отправить всем

🐦 **Twitter:**
`/twitter` — все настройки и статус
`/twitter_on` / `off` — вкл/выкл
`/twitter_min 25000` — минимум $
`/twitter_interval 25` — интервал мин
`/twitter_prob 1_99` — вероятность
`/twitter_sell on` — SELL сигналы
`/twitter_split on` — SPLIT сигналы
`/twitter_merge on` — MERGE сигналы
`/twitter_redeem on` — REDEEM сигналы
`/twitter_cat crypto on` — категории

ℹ️ Эта памятка: `/admin`
"""
    await message.answer(msg, parse_mode="Markdown")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show bot statistics (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    # Bot status
    bot_status = "▶️ Включен" if is_bot_enabled() else "⏸️ Остановлен"
    
    total_users = len(user_filters)
    active_users = sum(1 for uid in user_statuses if user_statuses.get(uid, True))
    paused_users = total_users - active_users
    
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
    """List all users (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
    if not user_filters:
        await message.answer("📭 Пока нет пользователей.")
        return
    
    msg = "👥 **Список пользователей:**\n\n"
    for uid in list(user_filters.keys())[:50]:  # Limit to 50
        threshold = user_filters.get(uid, 100)
        status = "▶️" if user_statuses.get(uid, True) else "⏸️"
        lang = user_languages.get(uid, 'ru').upper()
        
        # Escape markdown characters in username to avoid breaking the message
        # We need to escape: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
        # For Telegram MarkdownV2 usually just _ * [ ] ( ) ~ ` > # + - = | { } . !
        # But here valid implementation for standard Markdown or MarkdownV2 is needed.
        # The bot uses parse_mode="Markdown" (Legacy) based on existing code.
        # Legacy Markdown only needs escaping for: _ * ` [
        
        raw_username = user_usernames.get(uid, "—")
        safe_username = str(raw_username).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
        
        msg += f"@{safe_username} | {status} | ${threshold:,} | {lang}\n"
    
    if len(user_filters) > 50:
        msg += f"\n... и ещё {len(user_filters) - 50} пользователей"
    
    try:
        await message.answer(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error sending /users list: {e}")
        await message.answer("❌ Ошибка при отправке списка пользователей. Проверьте логи.")


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
        get_twitter_interval, get_twitter_probability_filter,
        is_twitter_sell_allowed, is_twitter_split_allowed, is_twitter_merge_allowed, is_twitter_redeem_allowed,
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
    prob_filter = get_twitter_probability_filter()
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
/twitter_interval 25
/twitter_prob 1_99
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
    
    from services.twitter_service import set_twitter_probability_filter, get_twitter_probability_filter
    
    parts = message.text.split()
    if len(parts) < 2:
        current = get_twitter_probability_filter()
        await message.answer(
            f"📊 Текущий фильтр: {current}\n\n"
            "Использование: `/twitter_prob <фильтр>`\n"
            "Фильтры:\n"
            "• `any` — все сигналы\n"
            "• `1_99` — 1-99%\n"
            "• `5_95` — 5-95%\n"
            "• `10_90` — 10-90%",
            parse_mode="Markdown"
        )
        return
    
    filter_key = parts[1].lower()
    if set_twitter_probability_filter(filter_key):
        await message.answer(f"✅ Twitter фильтр вероятности: {filter_key}")
    else:
        await message.answer("❌ Неверный фильтр. Доступные: any, 1_99, 5_95, 10_90")


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
    logger.info("Starting Telegram Bot Polling...")
    await dp.start_polling(bot)


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


async def send_trade_alert(chat_id, message_text, whale_key: str = None, is_saved: bool = False, level_icon: str = "🦐"):
    """Send trade alert with optional inline keyboard for saving traders."""
    if not chat_id:
        return
    try:
        lang = get_user_lang(chat_id)
        reply_markup = None
        
        if whale_key:
            reply_markup = get_trade_alert_keyboard(lang, whale_key, is_saved, level_icon)
        
        await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

