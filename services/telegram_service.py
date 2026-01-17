# PUBLIC SHELL VERSION
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
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
    pass
_poly_service = None

def set_poly_service(service):
    """Store reference to PolymarketService for report generation."""
    pass

class NoteState(StatesGroup):
    waiting_for_note = State()

class ManualAddState(StatesGroup):
    waiting_for_input = State()

class AgeFilterState(StatesGroup):
    waiting_for_range = State()

class PositionsFilterState(StatesGroup):
    waiting_for_range = State()
MAX_COMMENT_LEN = 240
logger = logging.getLogger(__name__)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
import os
import json
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'user_settings.json')

def load_settings():
    """Load user settings from file."""
    pass

def save_settings():
    """Save user settings to file."""
    pass
(user_filters, user_categories, user_languages, user_statuses, user_usernames, user_probabilities, user_side_types, user_wallet_ages, user_open_positions, bot_enabled) = load_settings()

def is_bot_enabled():
    """Check if bot is enabled (not stopped by admin)."""
    pass

def set_bot_enabled(enabled):
    """Set bot enabled state (admin only)."""
    pass
PROBABILITY_OPTIONS = {'any': None, '1_99': (0.01, 0.99), '5_95': (0.05, 0.95), '10_90': (0.1, 0.9)}

def get_default_categories():
    """Default category preferences - all enabled."""
    pass

def get_default_side_types():
    """Default side type preferences - only BUY and SELL enabled."""
    pass

def ensure_user_exists(chat_id):
    """Ensure user has all necessary settings initialized."""
    pass

def get_user_lang(chat_id):
    """Get user's language preference."""
    pass

def get_language_button_text(current_lang: str) -> str:
    """Get language button text - English always first as primary language."""
    pass

def is_user_active(chat_id):
    """Check if user bot is active (started)."""
    pass

def get_main_keyboard(chat_id):
    """Create persistent keyboard at bottom of chat."""
    pass

def get_filters_keyboard(chat_id):
    """Create keyboard for filters submenu."""
    pass

def get_collapsed_keyboard(chat_id):
    """Create minimal keyboard with only 'Show Menu' button."""
    pass

def get_amount_keyboard(chat_id):
    """Create inline keyboard for amount filter selection."""
    pass

def get_amount_confirm_keyboard(chat_id):
    """Create inline keyboard for $500 filter confirmation."""
    pass

def get_probability_keyboard(chat_id):
    """Create inline keyboard for probability filter selection."""
    pass

def get_age_keyboard(chat_id):
    """Create inline keyboard for wallet age filter selection."""
    pass

def get_positions_keyboard(chat_id):
    """Create inline keyboard for open positions filter selection."""
    pass

def format_age_range(age_filter, lang):
    """Format age filter range for display."""
    pass

def format_positions_range(pos_filter, lang):
    """Format positions filter range for display."""
    pass

def get_categories_keyboard(chat_id):
    """Create inline keyboard for category selection."""
    pass

def get_side_types_keyboard(chat_id):
    """Create inline keyboard for side type selection."""
    pass

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    pass

@dp.message(Command('report'))
async def cmd_report(message: types.Message):
    """Generate and send report on demand (admin only)."""
    pass

@dp.message(Command('amount'))
async def cmd_amount(message: types.Message):
    """Show amount filter menu."""
    pass

@dp.message(Command('categories'))
async def cmd_categories(message: types.Message):
    """Show categories menu."""
    pass

@dp.message(Command('probability'))
async def cmd_probability(message: types.Message):
    """Show probability filter menu."""
    pass

@dp.message(Command('sides'))
async def cmd_sides(message: types.Message):
    """Show side types menu."""
    pass

@dp.message(F.text.in_(['💰 Сумма сделки', '💰 Trade Amount']))
async def btn_amount(message: types.Message):
    """Handle Amount button press."""
    pass

@dp.message(F.text.in_(['📂 Категории', '📂 Categories']))
async def btn_categories(message: types.Message):
    """Handle Categories button press."""
    pass

@dp.message(F.text.in_(['⚖️ Вероятность', '⚖️ Probability']))
async def btn_probability(message: types.Message):
    """Handle Probability button press."""
    pass

@dp.message(Command('age'))
@dp.message(F.text.in_(['🕐 Возраст', '🕐 Age']))
async def btn_age(message: types.Message):
    """Handle Age button press - show age filter menu."""
    pass

@dp.message(Command('positions'))
@dp.message(F.text.in_(['💼 Позиции', '💼 Positions']))
async def btn_positions(message: types.Message):
    """Handle Positions button press - show positions filter menu."""
    pass

@dp.message(F.text.in_(['🔄 Типы событий', '🔄 Event Types']))
async def btn_sides(message: types.Message):
    """Handle Side Types button press."""
    pass

def format_current_filters(chat_id):
    """Format current filter settings for display."""
    pass

@dp.message(F.text.in_(['⚙️ Фильтры', '⚙️ Filters']))
async def btn_filters(message: types.Message):
    """Handle Filters button press - show filters submenu."""
    pass

@dp.message(Command('back'))
@dp.message(F.text.in_(['⬅️ Назад', '⬅️ Back']))
async def btn_back(message: types.Message):
    """Handle Back button press - return to main menu."""
    pass

@dp.message(F.text.in_(['▶️ Запустить', '▶️ Start', '⏸️ Остановить', '⏸️ Stop']))
async def btn_start_stop(message: types.Message):
    """Handle Start/Stop toggle button."""
    pass

@dp.message(F.text.in_(['🇬🇧 / 🇷🇺']))
async def btn_language(message: types.Message):
    """Handle Language toggle button."""
    pass

@dp.message(F.text.in_(['ℹ️ О боте', 'ℹ️ About']))
async def btn_about(message: types.Message):
    """Handle About button press."""
    pass

@dp.message(F.text.in_(['⬇️ Скрыть меню', '⬇️ Hide Menu']))
async def btn_hide_menu(message: types.Message):
    """Handle 'Hide Menu' button."""
    pass

@dp.message(F.text.in_(['⬆️ Показать меню', '⬆️ Show Menu']))
async def btn_show_menu(message: types.Message):
    """Handle 'Show Menu' button."""
    pass

@dp.message(Command('menu'))
async def cmd_menu(message: types.Message):
    """Command to show menu."""
    pass

@dp.message(Command('about'))
async def cmd_about(message: types.Message):
    """Command to show about info."""
    pass

@dp.message(Command('lang'))
async def cmd_lang(message: types.Message):
    """Command to toggle language."""
    pass

@dp.message(Command('hide'))
async def cmd_hide(message: types.Message):
    """Command to hide menu."""
    pass

@dp.message(Command('stop'))
async def cmd_stop(message: types.Message):
    """Command to toggle bot state (start/stop alerts)."""
    pass

@dp.message(Command('filters'))
async def cmd_filters(message: types.Message):
    """Command to show filters menu."""
    pass

@dp.message(Command('saved'))
async def cmd_saved(message: types.Message):
    """Command to show saved traders list."""
    pass
AQUARIUM_PAGE_SIZE = 10

def get_aquarium_list(chat_id, page=0, edit_mode=False):
    """
    Generate text list and keyboard for Aquarium.
    Supports View Mode and Edit Mode.
    """
    pass

@dp.message(lambda message: message.text in [get_text('ru', 'btn_saved'), get_text('en', 'btn_saved')])
async def btn_saved(message: types.Message):
    """Handle Aquarium button press - Show List View."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('aq_mode:'))
async def callback_aquarium_mode(callback_query: types.CallbackQuery):
    """Toggle View/Edit Mode."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('aq_page:'))
async def callback_aquarium_page(callback_query: types.CallbackQuery):
    """Navigate Aquarium List pages."""
    pass

@dp.callback_query(F.data.startswith('save:'))
async def callback_save(callback: CallbackQuery):
    """Handle save trader callback."""
    pass

@dp.callback_query(F.data.startswith('saved:'))
async def callback_already_saved(callback: CallbackQuery):
    """Handle click on already saved button."""
    pass

class NoteState(StatesGroup):
    waiting_for_note = State()

@dp.callback_query(lambda c: c.data and c.data.startswith('note:'))
async def callback_note(callback: types.CallbackQuery, state: FSMContext):
    """Handle note button - start FSM for note input."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('edit:'))
async def callback_edit(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle edit note button."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('delete:'))
async def callback_delete(callback: types.CallbackQuery):
    """Handle delete from saved."""
    pass

@dp.callback_query(lambda c: c.data == 'clearall')
async def callback_clear_all(callback: types.CallbackQuery):
    """Ask for confirmation before clearing all."""
    pass

@dp.callback_query(lambda c: c.data == 'confirm_clear')
async def callback_confirm_clear(callback: types.CallbackQuery):
    """Execute clear all."""
    pass

@dp.callback_query(lambda c: c.data == 'cancel_clear')
async def callback_cancel_clear(callback: types.CallbackQuery):
    """Cancel clear all - ensure return to list."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('toggle_notif:'))
async def callback_toggle_notif(callback: types.CallbackQuery):
    """Toggle notifications for a saved trader."""
    pass

@dp.callback_query(F.data == 'noop')
async def callback_noop(callback: CallbackQuery):
    """Handle noop callback (page info button)."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('manual_add:'))
async def callback_manual_add(callback: types.CallbackQuery, state: FSMContext):
    """Handle manual add button - start FSM for trader input."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('cancel_manual_add:'))
async def callback_cancel_manual_add(callback: types.CallbackQuery, state: FSMContext):
    """Cancel manual add operation."""
    pass

@dp.message(ManualAddState.waiting_for_input)
async def process_manual_add_input(message: types.Message, state: FSMContext):
    """Handle manual add text input from FSM."""
    pass

@dp.message(NoteState.waiting_for_note)
async def process_note_input(message: types.Message, state: FSMContext):
    """Handle note text input from FSM."""
    pass

@dp.callback_query(F.data.startswith('filter_'))
async def callback_filter(callback: CallbackQuery):
    """Handle filter amount selection."""
    pass

@dp.callback_query(F.data == 'confirm_filter_500')
async def callback_confirm_filter_500(callback: CallbackQuery):
    """Handle confirmation for $500 filter."""
    pass

@dp.callback_query(F.data == 'cancel_filter_500')
async def callback_cancel_filter_500(callback: CallbackQuery):
    """Handle cancellation for $500 filter - return to amount menu."""
    pass

@dp.callback_query(F.data.startswith('prob_'))
async def callback_probability(callback: CallbackQuery):
    """Handle probability filter selection."""
    pass

@dp.callback_query(F.data == 'age_any')
async def callback_age_any(callback: CallbackQuery):
    """Handle age filter 'any' selection."""
    pass

@dp.callback_query(F.data == 'age_custom')
async def callback_age_custom(callback: CallbackQuery, state: FSMContext):
    """Handle age filter 'custom' selection - start FSM."""
    pass

@dp.message(AgeFilterState.waiting_for_range)
async def process_age_range(message: types.Message, state: FSMContext):
    """Process age range input from user."""
    pass

@dp.callback_query(F.data == 'pos_any')
async def callback_positions_any(callback: CallbackQuery):
    """Handle positions filter 'any' selection."""
    pass

@dp.callback_query(F.data == 'pos_custom')
async def callback_positions_custom(callback: CallbackQuery, state: FSMContext):
    """Handle positions filter 'custom' selection - start FSM."""
    pass

@dp.message(PositionsFilterState.waiting_for_range)
async def process_positions_range(message: types.Message, state: FSMContext):
    """Process positions range input from user."""
    pass

@dp.callback_query(F.data.startswith('cat_'))
async def callback_category(callback: CallbackQuery):
    """Handle category toggle callback."""
    pass

@dp.callback_query(F.data.startswith('side_'))
async def callback_side_type(callback: CallbackQuery):
    """Handle side type toggle callback."""
    pass

def get_user_min_threshold(chat_id):
    """Get user's minimum threshold. Return default if not set."""
    pass

def get_user_categories(chat_id):
    """Get user's category preferences."""
    pass

def get_user_probability_filter(chat_id):
    """Get user's probability filter setting. Returns (min, max) tuple or None."""
    pass

def get_user_side_types(chat_id):
    """Get user's side type preferences."""
    pass

def get_user_wallet_age_filter(chat_id):
    """Get user's wallet age filter. Returns dict with min_days and max_days (or None)."""
    pass

def get_user_open_positions_filter(chat_id):
    """Get user's open positions filter. Returns dict with min_count and max_count (or None)."""
    pass

def is_user_active(chat_id):
    """Check if user is active."""
    pass

@dp.message(Command('admin'))
async def cmd_admin(message: types.Message):
    """Show admin commands cheatsheet (owner only)."""
    pass

@dp.message(Command('stats'))
async def cmd_stats(message: types.Message):
    """Show bot statistics (owner only)."""
    pass

@dp.message(Command('users'))
async def cmd_users(message: types.Message):
    """List all users as a text file (owner only)."""
    pass

@dp.message(Command('broadcast'))
async def cmd_broadcast(message: types.Message):
    """Broadcast message to all users (owner only)."""
    pass

@dp.message(Command('cache'))
async def cmd_cache(message: types.Message):
    """Show wallet age cache stats (owner only)."""
    pass

@dp.message(Command('bot_stop'))
async def cmd_bot_stop(message: types.Message):
    """Stop bot alerts (owner only)."""
    pass

@dp.message(Command('bot_start'))
async def cmd_bot_start(message: types.Message):
    """Start bot alerts (owner only)."""
    pass

@dp.message(Command('twitter'))
async def cmd_twitter(message: types.Message):
    """Show Twitter settings and commands (owner only)."""
    pass

@dp.message(Command('twitter_on'))
async def cmd_twitter_on(message: types.Message):
    """Enable Twitter posting (owner only)."""
    pass

@dp.message(Command('twitter_off'))
async def cmd_twitter_off(message: types.Message):
    """Disable Twitter posting (owner only)."""
    pass

@dp.message(Command('twitter_ins_min'))
async def cmd_twitter_ins_min(message: types.Message):
    """Set Twitter minimum amount for Insider tweets."""
    pass

@dp.message(Command('twitter_min'))
async def cmd_twitter_min(message: types.Message):
    """Set minimum USD for Twitter alerts (owner only)."""
    pass

@dp.message(Command('twitter_age_ins'))
async def cmd_twitter_age_ins(message: types.Message):
    """Set Twitter max wallet age (days) for Insider tweets."""
    pass

@dp.message(Command('twitter_pos_ins'))
async def cmd_twitter_pos_ins(message: types.Message):
    """Set Twitter max positions needed for Insider tweets."""
    pass

@dp.message(Command('twitter_interval'))
async def cmd_twitter_interval(message: types.Message):
    """Set interval between tweets in minutes (owner only)."""
    pass

@dp.message(Command('twitter_prob'))
async def cmd_twitter_prob(message: types.Message):
    """Set probability filter for Twitter (owner only)."""
    pass

@dp.message(Command('twitter_sell'))
async def cmd_twitter_sell(message: types.Message):
    """Toggle SELL signals for Twitter (owner only)."""
    pass

@dp.message(Command('twitter_split'))
async def cmd_twitter_split(message: types.Message):
    """Toggle SPLIT signals for Twitter (owner only)."""
    pass

@dp.message(Command('twitter_redeem'))
async def cmd_twitter_redeem(message: types.Message):
    """Toggle REDEEM signals for Twitter (owner only)."""
    pass

@dp.message(Command('twitter_merge'))
async def cmd_twitter_merge(message: types.Message):
    """Toggle MERGE signals for Twitter (owner only)."""
    pass

@dp.message(Command('twitter_cat'))
async def cmd_twitter_cat(message: types.Message):
    """Set category filters for Twitter (owner only)."""
    pass

async def send_admin_notification(message: str, parse_mode='HTML'):
    """Send notification message to bot owner/admin."""
    pass

async def start_telegram():
    pass

def get_trade_alert_keyboard(lang: str, whale_key: str, is_saved: bool, level_icon: str='🦐'):
    """Create inline keyboard for trade alerts."""
    pass

async def send_trade_alert(chat_id, message_text, whale_key: str=None, is_saved: bool=False, level_icon: str='🦐'):
    """Send trade alert with optional inline keyboard for saving traders."""
    pass