from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton
)
import logging
from config import TELEGRAM_BOT_TOKEN, FILTERS, OWNER_ID
from core.localization import get_text, get_trade_level_name

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
                return filters, categories, languages, statuses, usernames, probabilities
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
    return {}, {}, {}, {}, {}, {}

def save_settings():
    """Save user settings to file."""
    try:
        data = {
            'filters': {str(k): v for k, v in user_filters.items()},
            'categories': {str(k): v for k, v in user_categories.items()},
            'languages': {str(k): v for k, v in user_languages.items()},
            'statuses': {str(k): v for k, v in user_statuses.items()},
            'usernames': {str(k): v for k, v in user_usernames.items()},
            'probabilities': {str(k): v for k, v in user_probabilities.items()}
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

# Load settings on startup
user_filters, user_categories, user_languages, user_statuses, user_usernames, user_probabilities = load_settings()

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
        user_languages[chat_id] = 'ru'
        
    if chat_id not in user_statuses:
        user_statuses[chat_id] = True
    
    if chat_id not in user_probabilities:
        user_probabilities[chat_id] = 'any'  # Default: no probability filter

def get_user_lang(chat_id):
    """Get user's language preference."""
    return user_languages.get(chat_id, 'ru')

def is_user_active(chat_id):
    """Check if user bot is active (started)."""
    return user_statuses.get(chat_id, True)  # Default True (Active)

def get_main_keyboard(chat_id):
    """Create persistent keyboard at bottom of chat."""
    lang = get_user_lang(chat_id)
    active = is_user_active(chat_id)
    
    # Toggle button text
    btn_toggle = get_text(lang, 'btn_stop') if active else get_text(lang, 'btn_start')
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(lang, 'btn_amount')),
             KeyboardButton(text=get_text(lang, 'btn_categories')),
             KeyboardButton(text=get_text(lang, 'btn_probability'))],
            [KeyboardButton(text=btn_toggle),
             KeyboardButton(text=get_text(lang, 'btn_language')),
             KeyboardButton(text=get_text(lang, 'btn_about'))]
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

@dp.message(F.text.in_(["🇬🇧 EN", "🇷🇺 RU"]))
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
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("filter_"))
async def callback_filter(callback: CallbackQuery):
    """Handle filter amount selection."""
    chat_id = callback.message.chat.id
    ensure_user_exists(chat_id)
    lang = get_user_lang(chat_id)
    min_value = int(callback.data.replace("filter_", ""))
    
    user_filters[chat_id] = min_value
    save_settings()
    
    # Show confirmation and refresh keyboard
    await callback.answer(get_text(lang, 'filter_toast'))
    await callback.message.edit_text(
        get_text(lang, 'amount_set', min=min_value),
        parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} set filter to ${min_value}")

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

def is_user_active(chat_id):
    """Check if user is active."""
    return user_statuses.get(chat_id, True)


# ============ ADMIN COMMANDS (Owner Only) ============

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show bot statistics (owner only)."""
    if message.chat.id != OWNER_ID:
        return  # Silently ignore non-owners
    
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


async def start_telegram():
    logger.info("Starting Telegram Bot Polling...")
    await dp.start_polling(bot)

async def send_trade_alert(chat_id, message_text):
    if not chat_id:
        return
    try:
        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
