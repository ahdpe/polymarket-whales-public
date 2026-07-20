# PUBLIC SHELL VERSION
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, TelegramObject
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
import aiohttp
from urllib.parse import quote
_aiolimiter_available = False
try:
    from aiolimiter import AsyncLimiter
    import aiolimiter
    _aiolimiter_available = True
    _aiolimiter_version = getattr(aiolimiter, '__version__', 'unknown')
except ImportError:
    AsyncLimiter = None
    _aiolimiter_version = None
from config import TELEGRAM_BOT_TOKEN, FILTERS, OWNER_ID, RETRY_SHORT_MAX, MUTE_DURATIONS, FAIL_STREAK_MUTE_THRESHOLD, HOTFIX_CHAT_ID, HOTFIX_THRESHOLD, HOTFIX_MUTE, QUEUE_MAX_SIZE, WORKER_COUNT, GLOBAL_RATE, PER_CHAT_RATE
from core.localization import get_text
from core.categories import DETAILED_CATEGORY_OPTIONS, get_allowed_detailed_categories
from core.utils import add_polymarket_ref, extract_polymarket_event_slug, extract_polymarket_profile_id, polymarket_event_url, polymarket_profile_url, shorten_trader_name
from storage import saved_whales
from storage import saved_markets
from services.report_service import generate_report
from services.market_timeframe import TIMEFRAME_FILTER_OPTIONS
DATA_API_URL = 'https://data-api.polymarket.com'
_poly_service = None

def set_poly_service(service):
    """Store reference to PolymarketService for report generation."""
    pass
_insider_alerts_service = None

def set_insider_alerts_service(service):
    """Store reference to InsiderAlertsService for admin commands."""
    pass

class NoteState(StatesGroup):
    waiting_for_note = State()

class ManualAddState(StatesGroup):
    waiting_for_input = State()

class MarketManualAddState(StatesGroup):
    waiting_for_input = State()

class AgeFilterState(StatesGroup):
    waiting_for_range = State()

class PositionsFilterState(StatesGroup):
    waiting_for_range = State()

class ProbabilityFilterState(StatesGroup):
    waiting_for_range = State()
MAX_COMMENT_LEN = 240
DEFAULT_MIN_MARKET_TIMEFRAME_MINUTES = 15
logger = logging.getLogger(__name__)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
_last_telegram_incoming_ts: float = 0.0
_prev_webhook_pending_count: int | None = None
_telegram_health_boot_ts: float = 0.0
_admin_health_alert_ts: dict[str, float] = {}
_HEALTH_ALERT_COOLDOWN_SEC = 6 * 3600
_HEALTH_WATCHDOG_INTERVAL_SEC = 600
_HEALTH_WARMUP_SEC = 900
_HEALTH_SILENCE_SEC = 20 * 60
_HEALTH_PENDING_GROWTH_MIN = 18
_queue_zero_sent_streak: int = 0

class _LastIncomingUpdateMiddleware(BaseMiddleware):
    """Фиксирует время последнего update, дошедшего до диспетчера."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        pass
dp.update.outer_middleware(_LastIncomingUpdateMiddleware())

def _health_alert_ready(key: str) -> bool:
    pass

async def _telegram_polling_health_watchdog():
    """Периодически проверяет webhook/pending и при подозрении шлёт OWNER_ID."""
    pass
import os
import json
import shutil
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'user_settings.json')
SETTINGS_BACKUP_FILE = SETTINGS_FILE + '.bak'
DETAILED_CATEGORIES_ENABLED = os.getenv('DETAILED_CATEGORIES_ENABLED', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}

def _decode_settings(data):
    """Convert persisted JSON settings into the in-memory representation."""
    pass

def load_settings():
    """Load user settings from file."""
    pass

def save_settings():
    """Save user settings to file."""
    pass
user_filters, user_categories, user_languages, user_statuses, user_usernames, user_probabilities, user_side_types, user_wallet_ages, user_open_positions, user_min_market_timeframes, user_category_refinements, blocked_users, bot_enabled = load_settings()

def apply_default_market_timeframe_filter() -> None:
    """Backfill the default timeframe filter for users created before the setting existed."""
    pass
apply_default_market_timeframe_filter()
user_menu_state = {}

def set_menu_state(chat_id: int, state: str) -> None:
    pass

def get_menu_state(chat_id: int) -> str:
    pass
muted_until = {}
fail_streak = {}
mute_level = {}
last_fail_reason = {}
last_mute_time = {}
MUTE_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'mute_state.json')

def load_mute_state():
    """Load mute state from file."""
    pass

def save_mute_state():
    """Save mute state to file (atomic write)."""
    pass

def cleanup_mute_state():
    """Clean up old mute state entries to prevent memory bloat."""
    pass
_stats_lock = asyncio.Lock()
_stats_reset_time = time.time()
alert_queue = None
worker_tasks = []
queue_stats = {'sent_total': 0, 'dropped_total': 0, 'error_total': 0, 'skipped_prequeue_total': 0, 'skipped_worker_gate_total': 0, 'sent_per_min': 0, 'dropped_per_min': 0, 'skipped_prequeue_per_min': 0, 'skipped_worker_gate_per_min': 0, 'retryafter_min': 0, 'requeued_total': 0, 'requeued_per_min': 0}
_queue_stats_lock = asyncio.Lock()
_queue_stats_reset_time = time.time()
_queue_oldest_enqueued = None
_queue_oldest_lock = asyncio.Lock()
_queue_lag_warn_count = 0
global_rate_limiter = None
_per_chat_next_send = {}
_per_chat_lock = asyncio.Lock()
_queue_enabled = False

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

def format_market_timeframe_filter(value: int | None, lang: str) -> str:
    """Format market timeframe filter for display."""
    pass

def get_market_timeframe_keyboard(chat_id):
    """Create inline keyboard for minimum market timeframe selection."""
    pass

def format_age_range(age_filter, lang):
    """Format age filter range for display."""
    pass

def format_positions_range(pos_filter, lang):
    """Format positions filter range for display."""
    pass

def _get_category_parent_state(chat_id, parent):
    """Return off/full/partial plus the effective child count."""
    pass

def _format_category_selection(chat_id, lang):
    """Format every category with a distinct icon and tri-state selection."""
    pass

def get_categories_keyboard(chat_id):
    """Create inline keyboard for category selection."""
    pass
_DETAILED_PARENT_LABELS = {'sports': {'ru': '🏆 Спорт', 'en': '🏆 Sports'}, 'crypto': {'ru': '💰 Крипто', 'en': '💰 Crypto'}, 'other': {'ru': '🗂 Остальное', 'en': '🗂 Other'}}
_DETAILED_CATEGORY_LABELS = {'sports.combo': {'ru': '🎟 Combo', 'en': '🎟 Combo'}, 'sports.esports': {'ru': '🎮 Esports', 'en': '🎮 Esports'}, 'sports.soccer': {'ru': '⚽ Футбол', 'en': '⚽ Soccer'}, 'sports.basketball': {'ru': '🏀 Баскетбол', 'en': '🏀 Basketball'}, 'sports.american_football': {'ru': '🏈 Амер. футбол', 'en': '🏈 American football'}, 'sports.baseball': {'ru': '⚾ Бейсбол', 'en': '⚾ Baseball'}, 'sports.hockey': {'ru': '🏒 Хоккей', 'en': '🏒 Hockey'}, 'sports.tennis': {'ru': '🎾 Теннис', 'en': '🎾 Tennis'}, 'sports.combat': {'ru': '🥊 Единоборства', 'en': '🥊 Combat sports'}, 'sports.motorsport': {'ru': '🏎️ Автоспорт', 'en': '🏎️ Motorsport'}, 'sports.golf': {'ru': '⛳ Гольф', 'en': '⛳ Golf'}, 'sports.cricket': {'ru': '🏏 Крикет', 'en': '🏏 Cricket'}, 'sports.other': {'ru': '🏅 Другой спорт', 'en': '🏅 Other sports'}, 'crypto.bitcoin': {'ru': '🟠 Bitcoin', 'en': '🟠 Bitcoin'}, 'crypto.ethereum': {'ru': '🔷 Ethereum', 'en': '🔷 Ethereum'}, 'crypto.solana': {'ru': '🟣 Solana', 'en': '🟣 Solana'}, 'crypto.other_assets': {'ru': '🪙 Другие активы', 'en': '🪙 Other assets'}, 'crypto.prices': {'ru': '📈 Цены и Up/Down', 'en': '📈 Prices and Up/Down'}, 'crypto.launches': {'ru': '🚀 Запуски и FDV', 'en': '🚀 Launches and FDV'}, 'crypto.regulation': {'ru': '⚖️ Регулирование', 'en': '⚖️ Regulation'}, 'crypto.defi_nft': {'ru': '🧩 DeFi и NFT', 'en': '🧩 DeFi and NFT'}, 'crypto.other': {'ru': '💠 Другое крипто', 'en': '💠 Other crypto'}, 'other.politics': {'ru': '🗳️ Политика', 'en': '🗳️ Politics'}, 'other.geopolitics': {'ru': '🌍 Геополитика', 'en': '🌍 Geopolitics'}, 'other.economy': {'ru': '📊 Экономика', 'en': '📊 Economy'}, 'other.entertainment': {'ru': '🎬 Развлечения', 'en': '🎬 Entertainment'}, 'other.science_tech': {'ru': '🔬 Наука и технологии', 'en': '🔬 Science and tech'}, 'other.weather': {'ru': '🌦️ Погода', 'en': '🌦️ Weather'}, 'other.business': {'ru': '💼 Бизнес', 'en': '💼 Business'}, 'other.other': {'ru': '🗂️ Остальное', 'en': '🗂️ Everything else'}}

def _detail_label(detail_id, lang):
    pass

def _parent_label(parent, lang):
    pass

def _get_chat_refinements(chat_id):
    pass

def _get_saved_detailed_selection(chat_id, parent):
    """Return a meaningful saved subset, including one parked while full/off."""
    pass

def _get_detailed_editor_selection(chat_id, parent):
    """Resolve the checkboxes shown when editing a detailed category."""
    pass

def get_detailed_categories_menu_keyboard(chat_id):
    """Create the compact top-level detailed category menu."""
    pass

def get_detailed_parent_keyboard(chat_id, parent):
    """Create a two-column selector for one detailed category parent."""
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

@dp.message(Command('tlgrm_prob'))
async def cmd_tlgrm_prob(message: types.Message):
    """
    Handle /tlgrm_prob command (GLOBAL Insider Alerts filter).
    Usage:
    - /tlgrm_prob 10 90 (sets range 10-90%)
    - /tlgrm_prob 0 (resets to 0-100%)
    """
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

@dp.message(F.text.in_(['⏱ Длительность рынка', '⏱ Market Duration']))
async def btn_market_timeframe(message: types.Message):
    """Handle market timeframe filter button press."""
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

@dp.message(Command('reset'))
async def cmd_reset(message: types.Message):
    """Reset all user settings to default."""
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

@dp.message(Command('markets'))
async def cmd_markets(message: types.Message):
    """Command to show saved markets list."""
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
MARKETS_PAGE_SIZE = 10

def get_markets_list(chat_id, page=0, edit_mode=False):
    """
    Generate text list and keyboard for Saved Markets.
    Supports View Mode and Edit Mode.
    """
    pass

@dp.message(lambda message: message.text in [get_text('ru', 'btn_saved_markets'), get_text('en', 'btn_saved_markets')])
async def btn_saved_markets(message: types.Message):
    """Handle Saved Markets button press - Show List View."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('mk_mode:'))
async def callback_markets_mode(callback_query: types.CallbackQuery):
    """Toggle View/Edit Mode for Markets."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('mk_page:'))
async def callback_markets_page(callback_query: types.CallbackQuery):
    """Navigate Saved Markets pages."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('mk_delete:'))
async def callback_market_delete(callback: types.CallbackQuery):
    """Handle delete from saved markets."""
    pass

@dp.callback_query(lambda c: c.data == 'mk_clearall')
async def callback_markets_clear_all(callback: types.CallbackQuery):
    """Ask for confirmation before clearing all markets."""
    pass

@dp.callback_query(lambda c: c.data == 'mk_confirm_clear')
async def callback_markets_confirm_clear(callback: types.CallbackQuery):
    """Execute clear all markets."""
    pass

@dp.callback_query(lambda c: c.data == 'mk_cancel_clear')
async def callback_markets_cancel_clear(callback: types.CallbackQuery):
    """Cancel clear all markets."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('mk_toggle:'))
async def callback_market_toggle_notif(callback: types.CallbackQuery):
    """Toggle notifications/state for a saved market.
    
    Cycle: 🔕 off → 🔔 on → 🚫 ignore → 🔕 off (back to start)
    """
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('mk_toggle_all:'))
async def callback_market_toggle_all(callback: types.CallbackQuery):
    """Toggle notifications for all saved markets."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('market_manual_add:'))
async def callback_market_manual_add(callback: types.CallbackQuery, state: FSMContext):
    """Handle manual add button for markets."""
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('cancel_market_manual_add:'))
async def callback_cancel_market_manual_add(callback: types.CallbackQuery, state: FSMContext):
    """Cancel manual add operation for markets."""
    pass

def _extract_event_slug(text: str) -> str | None:
    pass

async def _fetch_market_title_by_slug(slug: str) -> str | None:
    pass

@dp.message(MarketManualAddState.waiting_for_input)
async def process_market_manual_add_input(message: types.Message, state: FSMContext):
    """Handle manual add text input for markets."""
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
    """Handle click on already saved button.

    Toggle: remove from favorites and switch button back to "To Favorites".
    """
    pass

@dp.callback_query(F.data.startswith('market_save:'))
async def callback_market_save(callback: CallbackQuery):
    """Handle save market callback."""
    pass

@dp.callback_query(F.data.startswith('market_saved:'))
async def callback_market_saved(callback: CallbackQuery):
    """Handle click on already saved market button (remove)."""
    pass

@dp.callback_query(F.data.startswith('ign_trader:'))
async def callback_ignore_trader(callback: CallbackQuery):
    """Handle ignore trader callback - upsert with state='ignore'."""
    pass

@dp.callback_query(F.data.startswith('ign_market:'))
async def callback_ignore_market(callback: CallbackQuery):
    """Handle ignore market callback - upsert with state='ignore'."""
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
    """Toggle notifications/state for a saved trader.
    
    Cycle: 🔕 off → 🔔 on → 🚫 ignore → 🔕 off (back to start)
    """
    pass

@dp.callback_query(lambda c: c.data and c.data.startswith('toggle_notif_all:'))
async def callback_toggle_notif_all(callback: types.CallbackQuery):
    """Toggle notifications for all saved traders."""
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

@dp.callback_query(F.data.startswith('prob_') & (F.data != 'prob_custom'))
async def callback_probability(callback: CallbackQuery):
    """Handle probability filter selection."""
    pass

@dp.callback_query(F.data == 'prob_custom')
async def callback_prob_custom(callback: CallbackQuery, state: FSMContext):
    """Handle custom probability filter selection."""
    pass

def parse_probability_ranges(text):
    """
    Parse probability ranges from string.
    Supports:
    - Multiple ranges: "0-5, 95-100"
    - Space/underscore as separator: "20 80", "20_80"
    - Single ranges: "20-80"
    """
    pass

@dp.message(ProbabilityFilterState.waiting_for_range)
async def process_prob_custom_input(message: types.Message, state: FSMContext):
    """Process custom probability range input."""
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

@dp.callback_query(F.data.startswith('tf_'))
async def callback_market_timeframe(callback: CallbackQuery):
    """Handle minimum market timeframe selection."""
    pass

@dp.callback_query(F.data.startswith('cat_'))
async def callback_category(callback: CallbackQuery):
    """Handle category toggle callback."""
    pass

def _save_parent_refinement(chat_id, parent, allowed):
    """Persist a detailed subset; all/none collapse back to binary mode."""
    pass

@dp.callback_query(F.data.startswith('dcat_'))
async def callback_detailed_category(callback: CallbackQuery):
    """Handle optional detailed category navigation and selections."""
    pass

@dp.callback_query(F.data.startswith('side_'))
async def callback_side_type(callback: CallbackQuery):
    """Handle side type toggle callback."""
    pass

@dp.callback_query()
async def callback_query_catch_all(callback: CallbackQuery):
    """Catch-all handler for unhandled callback queries - logs for debugging."""
    pass

def get_user_min_threshold(chat_id):
    """Get user's minimum threshold. Return default if not set."""
    pass

def get_user_categories(chat_id):
    """Get user's category preferences."""
    pass

def get_user_category_refinements(chat_id):
    """Get optional detailed category preferences without mutating defaults."""
    pass

def get_user_probability_filter(chat_id):
    """Get user's probability filter setting. Returns LIST of (min, max) tuples or None."""
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

def get_user_min_market_timeframe(chat_id):
    """Get user's minimum market timeframe filter in minutes, or None if off."""
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

@dp.message(Command('mute_status'))
async def cmd_mute_status(message: types.Message):
    """Show mute statistics (owner only)."""
    pass

@dp.message(Command('queue_status'))
async def cmd_queue_status(message: types.Message):
    """Show queue statistics (owner only)."""
    pass

@dp.message(Command('queue_clear'))
async def cmd_queue_clear(message: types.Message):
    """Clear queue (owner only)."""
    pass

@dp.message(Command('unmute'))
async def cmd_unmute(message: types.Message):
    """Unmute a user (owner only)."""
    pass

@dp.message(Command('mute'))
async def cmd_mute(message: types.Message):
    """Manually mute a user (owner only)."""
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

@dp.message(Command('twitter_delay'))
async def cmd_twitter_delay(message: types.Message):
    """Set delay between trade and Twitter signal (in minutes, owner only)."""
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

@dp.message(Command('tlgrm'))
async def cmd_tlgrm(message: types.Message):
    """Show Insider Alerts status and settings (owner only)."""
    pass

@dp.message(Command('tlgrm_pending'))
async def cmd_tlgrm_pending(message: types.Message):
    """Show pending alerts close to threshold (owner only)."""
    pass

@dp.message(Command('tlgrm_on'))
async def cmd_tlgrm_on(message: types.Message):
    """Enable Insider Alerts globally (owner only)."""
    pass

@dp.message(Command('tlgrm_off'))
async def cmd_tlgrm_off(message: types.Message):
    """Disable Insider Alerts globally (owner only)."""
    pass

@dp.message(Command('tlgrm_channel'))
async def cmd_tlgrm_channel(message: types.Message):
    """Set Telegram channel ID for insider alerts (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster'))
async def cmd_tlgrm_cluster(message: types.Message):
    """Toggle CLUSTER scenario (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_interval'))
async def cmd_tlgrm_cluster_interval(message: types.Message):
    """Set CLUSTER interval in hours (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_wallet_age'))
async def cmd_tlgrm_cluster_wallet_age(message: types.Message):
    """Set CLUSTER max wallet age in hours (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_min'))
async def cmd_tlgrm_cluster_min(message: types.Message):
    """Set CLUSTER minimum volume in USD (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_wallets'))
async def cmd_tlgrm_cluster_wallets(message: types.Message):
    """Set CLUSTER minimum wallet count (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_direction'))
async def cmd_tlgrm_cluster_direction(message: types.Message):
    """Set CLUSTER minimum directionality % (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_pos'))
async def cmd_tlgrm_cluster_pos(message: types.Message):
    """Set CLUSTER maximum open positions (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation'))
async def cmd_tlgrm_accumulation(message: types.Message):
    """Toggle ACCUMULATION scenario (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation_interval'))
async def cmd_tlgrm_accumulation_interval(message: types.Message):
    """Set ACCUMULATION interval window in days (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation_min'))
async def cmd_tlgrm_accumulation_min(message: types.Message):
    """Set ACCUMULATION minimum trade size in USD (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation_total'))
async def cmd_tlgrm_accumulation_total(message: types.Message):
    """Set ACCUMULATION minimum total volume in USD (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation_wallets'))
async def cmd_tlgrm_accumulation_wallets(message: types.Message):
    """Set ACCUMULATION minimum wallets count (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation_pos'))
async def cmd_tlgrm_accumulation_pos(message: types.Message):
    """Set ACCUMULATION maximum open positions (owner only)."""
    pass

@dp.message(Command('tlgrm_accumulation_direction'))
async def cmd_tlgrm_accumulation_direction(message: types.Message):
    """Set ACCUMULATION minimum directionality % (owner only)."""
    pass

@dp.message(Command('tlgrm_burst'))
async def cmd_tlgrm_burst(message: types.Message):
    """Toggle BURST scenario (owner only)."""
    pass

@dp.message(Command('tlgrm_burst_interval'))
async def cmd_tlgrm_burst_interval(message: types.Message):
    """Set BURST interval in hours (owner only)."""
    pass

@dp.message(Command('tlgrm_burst_min'))
async def cmd_tlgrm_burst_min(message: types.Message):
    """Set BURST minimum trade size in USD (owner only)."""
    pass

@dp.message(Command('tlgrm_burst_wallets'))
async def cmd_tlgrm_burst_wallets(message: types.Message):
    """Set BURST minimum wallet count (owner only)."""
    pass

@dp.message(Command('tlgrm_burst_direction'))
async def cmd_tlgrm_burst_direction(message: types.Message):
    """Set BURST minimum directionality % (owner only)."""
    pass

@dp.message(Command('tlgrm_burst_pos'))
async def cmd_tlgrm_burst_pos(message: types.Message):
    """Set BURST maximum open positions (owner only)."""
    pass

@dp.message(Command('tlgrm_cat'))
async def cmd_tlgrm_cat(message: types.Message):
    """Set category enabled status (owner only)."""
    pass

@dp.message(Command('tlgrm_cluster_side'))
async def cmd_tlgrm_cluster_side(message: types.Message):
    """Set CLUSTER side filter (buy/sell/both)."""
    pass

@dp.message(Command('tlgrm_cluster_total'))
async def cmd_tlgrm_cluster_total(message: types.Message):
    """Set CLUSTER min total volume."""
    pass

@dp.message(Command('tlgrm_cluster_profiles'))
async def cmd_tlgrm_cluster_profiles(message: types.Message):
    """Toggle displaying profiles in CLUSTER alerts."""
    pass

@dp.message(Command('tlgrm_position_tracker'))
async def cmd_tlgrm_position_tracker(message: types.Message):
    """Enable/disable optional insider position tracker mode."""
    pass

@dp.message(Command('tlgrm_position_tracker_sold'))
async def cmd_tlgrm_position_tracker_sold(message: types.Message):
    """Control removal of sold-out wallets from insider buffer."""
    pass

@dp.message(Command('tlgrm_cluster_show'))
async def cmd_tlgrm_cluster_show(message: types.Message):
    """Show detailed CLUSTER settings."""
    pass

@dp.message(Command('tlgrm_cluster_reset'))
async def cmd_tlgrm_cluster_reset(message: types.Message):
    """Reset CLUSTER settings to default."""
    pass

@dp.message(Command('tlgrm_burst_age'))
async def cmd_tlgrm_burst_age(message: types.Message):
    """Set BURST max wallet age."""
    pass

@dp.message(Command('tlgrm_burst_total'))
async def cmd_tlgrm_burst_total(message: types.Message):
    """Set BURST min total volume."""
    pass

@dp.message(Command('tlgrm_burst_profiles'))
async def cmd_tlgrm_burst_profiles(message: types.Message):
    """Toggle displaying profiles in BURST alerts."""
    pass

@dp.message(Command('tlgrm_burst_show'))
async def cmd_tlgrm_burst_show(message: types.Message):
    """Show detailed BURST settings."""
    pass

@dp.message(Command('tlgrm_burst_reset'))
async def cmd_tlgrm_burst_reset(message: types.Message):
    """Reset BURST settings to default."""
    pass

@dp.message(Command('tlgrm_accumulation_age'))
async def cmd_tlgrm_accumulation_age(message: types.Message):
    """Set ACCUMULATION max wallet age."""
    pass

@dp.message(Command('tlgrm_accumulation_profiles'))
async def cmd_tlgrm_accumulation_profiles(message: types.Message):
    """Toggle displaying profiles in ACCUMULATION alerts."""
    pass

@dp.message(Command('tlgrm_accumulation_show'))
async def cmd_tlgrm_accumulation_show(message: types.Message):
    """Show detailed ACCUMULATION settings."""
    pass

@dp.message(Command('tlgrm_accumulation_reset'))
async def cmd_tlgrm_accumulation_reset(message: types.Message):
    """Reset ACCUMULATION settings to default."""
    pass

async def send_admin_notification(message: str, parse_mode='HTML'):
    """Send notification message to bot owner/admin."""
    pass

async def start_telegram():
    pass

async def _periodic_cleanup():
    """Periodic cleanup of mute state (every hour)."""
    pass

def get_trade_alert_keyboard(lang: str, whale_key: str, is_saved: bool, level_icon: str='🦐', market_key: str | None=None, is_market_saved: bool=False, is_trader_ignored: bool=False, is_market_ignored: bool=False):
    """Create inline keyboard for trade alerts."""
    pass

def _get_mute_duration(chat_id: int) -> int:
    """Get mute duration based on escalation level."""
    pass

def _apply_mute(chat_id: int, reason: str, mute_seconds: int=None):
    """Apply mute to chat_id."""
    pass

def _is_muted(chat_id: int) -> tuple[bool, float]:
    """Check if chat_id is muted. Returns (is_muted, seconds_left)."""
    pass

async def _clear_muted_chat_queue(chat_id: int):
    """Background helper: clear queued alerts for newly muted chat."""
    pass

def _can_enqueue_or_send(chat_id: int, value_usd: float | None=None, bypass_filters: bool=False) -> bool:
    """Fast eligibility gate used before queueing and before worker rate-limit wait."""
    pass

async def _log_mute_stats():
    """Log mute statistics (called periodically)."""
    pass

async def clear_pending_alert_queue(chat_id: int | None=None) -> int:
    """
    Remove pending Telegram alert tasks from queue.
    If chat_id is provided, only tasks for that user are removed.
    """
    pass

def _get_per_chat_delay(chat_id: int) -> float:
    """
    Check how long to wait for per-chat rate limit WITHOUT updating state.
    Returns seconds to wait (0 if ready).
    """
    pass

async def _reserve_per_chat_slot(chat_id: int, delay_threshold: float=0.5) -> float:
    """
    Reserve a slot for sending. 
    If delay > delay_threshold, DO NOT reserve and return delay (so caller can requeue).
    If delay <= delay_threshold, reserve and return delay (caller must wait).
    """
    pass

async def enqueue_trade_alert(chat_id, message_text, whale_key: str=None, is_saved: bool=False, level_icon: str='🦐', market_key: str | None=None, is_market_saved: bool=False, value_usd: float | None=None, bypass_filters: bool=False):
    """
    Add trade alert to queue for sending.
    Returns immediately (fire-and-forget).
    Falls back to direct send if queue is disabled.
    """
    pass

async def _per_chat_rate_limiter_wait(chat_id: int):
    """Wait if needed to respect per-chat rate limit."""
    pass

async def _queue_worker(worker_id: int):
    """Worker that processes tasks from the queue."""
    pass

async def _get_queue_age_stats():
    """Get oldest and average age of tasks in queue."""
    pass

async def _log_queue_stats():
    """Periodically log queue statistics."""
    pass

def start_queue_workers():
    """Start queue workers and initialize queue."""
    pass

async def _log_mute_stats_periodic():
    """Periodically log mute statistics (called from queue system)."""
    pass

async def stop_queue_workers():
    """Stop queue workers gracefully."""
    pass

async def send_trade_alert(chat_id, message_text, whale_key: str=None, is_saved: bool=False, level_icon: str='🦐', market_key: str | None=None, is_market_saved: bool=False, value_usd: float | None=None, bypass_filters: bool=False) -> bool:
    """
    Send trade alert with robust error handling (RetryAfter) and auto-mute for problematic users.
    """
    pass