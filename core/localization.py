"""Localization strings for PolyWhales bot."""

TRANSLATIONS = {
    'ru': {
        # Start message
        'welcome': "🐋 *Polymarket Whales*\n\nОтслеживаю крупные сделки на Polymarket в реальном времени.\n\n*Возможности:*\n• Уведомления о сделках от $500 до $100,000+\n• Фильтрация по сумме и категориям\n• Ссылки на профиль трейдера\n\nИспользуй кнопки для настройки.",
        
        # Buttons
        'btn_amount': "💰 Сумма сделки",
        'btn_categories': "📂 Категории",
        'btn_probability': "⚖️ Вероятность",
        'btn_start': "▶️ Запустить",
        'btn_stop': "⏸️ Остановить",
        'btn_language': "🇬🇧 EN",
        'btn_about': "ℹ️ О боте",
        
        # Status
        'bot_started': "▶️ **Бот запущен!**\nЯ буду присылать уведомления о сделках.",
        'bot_stopped': "⏸️ **Бот остановлен.**\nУведомления приходить не будут, пока ты снова не запустишь бота.",
        
        # Filter - Amount
        'amount_menu_title': "💰 **Сумма сделки**\n\nВыбери минимальную сумму:",
        'amount_set': "✅ Минимальная сумма установлена: *${min:,}*",
        
        # Filter - Categories  
        'categories_menu_title': "📂 **Категории**\n\nВыбери какие рынки отслеживать:",
        'categories_set': "✅ Категории обновлены: {categories}",
        
        # Filter - Probability
        'probability_menu_title': "⚖️ **Вероятность**\n\nФильтр по вероятности рынка:\n(исключает почти решённые рынки)",
        'probability_set': "✅ Фильтр вероятности: *{range}*",
        'prob_any': "🌐 Любая",
        'prob_1_99': "🟢 1% — 99%",
        'prob_5_95': "🟡 5% — 95%",
        'prob_10_90': "🟠 10% — 90%",
        'filter_toast': "Настройки обновлены!",
        
        # Settings
        'settings_title': "⚙️ **Настройки категорий**\n\nВыбери какие рынки отслеживать:",
        'settings_all': "Все сделки",
        'settings_other': "Всё кроме крипты и спорта",
        'settings_crypto': "💰 Крипто",
        'settings_sports': "⚽ Спорт",
        'settings_done': "✔️ Готово",
        'settings_saved': "✅ **Настройки сохранены!**\n\nАктивные категории: {categories}",
        'settings_toast': "Настройки сохранены!",
        'cat_other': "Остальное",
        'cat_crypto': "Крипто",
        'cat_sports': "Спорт",
        'cat_nothing': "Ничего",
        
        # About
        'about': """*Polymarket Whales* 🐋
Мониторинг крупных сделок на [Polymarket](https://polymarket.com) в реальном времени.

*Функционал:*
• Уведомления о сделках от $500 до $100,000+
• Фильтр минимальной суммы (настраивается пользователем)
• Выбор категорий (Крипто, Спорт, Остальное)
• Фильтр вероятности (исключает почти решённые рынки)

*Классификация объемов:*
🔥 МЕГА КИТ — >$100,000
⚡ СУПЕР КИТ — >$50,000
🐋 КИТ — >$25,000
🦈 АКУЛА — >$10,000
🐬 ДЕЛЬФИН — >$5,000
🐟 РЫБА — >$2,000
🦐 КРЕВЕТКА — >$500

*Метрики в уведомлениях:*
📊 *Open PnL* — PnL открытых позиций (нереализованный)
💼 *Open Positions* — Количество активных позиций (не закрытых)
💵 *Val* — Текущая стоимость всех позиций
🕐 *Wallet Age* — Возраст кошелька (с первой сделки)

*Как определяются категории:*
1. 💰 *Крипто (Crypto)*
Если в названии есть: bitcoin, btc, ethereum, eth, solana, doge, pepe, binance, nft, airdrop и др.
2. ⚽ *Спорт (Sports)*
Если в названии есть: nfl, nba, football, soccer, ufc, f1, lakers, goal и др.

💬 Обратная связь: @Andrey\_Os
💻 [GitHub](https://github.com/ahdpe/PolymarketWhales)

⚡ *ТОП Биржа для торговли:*
[Регистрируйся на Bybit и получи бонусы! 🎁](https://www.bybit.com/invite?ref=JDRKDN)""",
        
        # Trade alerts
        'open_market': "Открыть рынок",
    },
    
    'en': {
        # Start message
        'welcome': "🐋 *Polymarket Whales*\n\nReal-time monitoring of large trades on Polymarket.\n\n*Features:*\n• Trade alerts from $500 to $100,000+\n• Amount and category filters\n• Trader profile links\n\nUse buttons below to configure.",
        
        # Buttons
        'btn_amount': "💰 Trade Amount",
        'btn_categories': "📂 Categories",
        'btn_probability': "⚖️ Probability",
        'btn_start': "▶️ Start",
        'btn_stop': "⏸️ Stop",
        'btn_language': "🇷🇺 RU",
        'btn_about': "ℹ️ About",
        
        # Status
        'bot_started': "▶️ **Bot started!**\nI will send trade alerts.",
        'bot_stopped': "⏸️ **Bot stopped.**\nAlerts are paused until you restart the bot.",
        
        # Filter - Amount
        'amount_menu_title': "💰 **Trade Amount**\n\nSelect minimum amount:",
        'amount_set': "✅ Minimum amount set: *${min:,}*",
        
        # Filter - Categories  
        'categories_menu_title': "📂 **Categories**\n\nSelect which markets to track:",
        'categories_set': "✅ Categories updated: {categories}",
        
        # Filter - Probability
        'probability_menu_title': "⚖️ **Probability**\n\nFilter by market probability:\n(excludes near-resolved markets)",
        'probability_set': "✅ Probability filter: *{range}*",
        'prob_any': "🌐 Any",
        'prob_1_99': "🟢 1% — 99%",
        'prob_5_95': "🟡 5% — 95%",
        'prob_10_90': "🟠 10% — 90%",
        
        # Settings
        'settings_title': "⚙️ **Category Settings**\n\nSelect which markets to track:",
        'settings_all': "All trades",
        'settings_other': "All except crypto & sports",
        'settings_crypto': "💰 Crypto",
        'settings_sports': "⚽ Sports",
        'settings_done': "✔️ Done",
        'settings_saved': "✅ **Settings saved!**\n\nActive categories: {categories}",
        'settings_toast': "Settings saved!",
        'cat_other': "Other",
        'cat_crypto': "Crypto",
        'cat_sports': "Sports",
        'cat_nothing': "None",
        
        # About
        'about': """*Polymarket Whales* 🐋
Real-time monitoring of large trades on [Polymarket](https://polymarket.com).

*Functionality:*
• Trade alerts from $500 to $100,000+
• Customizable amount threshold
• Category selection (Crypto, Sports, Other)
• Probability filter (excludes near-resolved markets)

*Volume classification:*
🔥 MEGA WHALE — >$100,000
⚡ SUPER WHALE — >$50,000
🐋 WHALE — >$25,000
🦈 SHARK — >$10,000
🐬 DOLPHIN — >$5,000
🐟 FISH — >$2,000
🦐 SHRIMP — >$500

*Metric definitions:*
📊 *Open PnL* — PnL of open positions (Unrealized)
💼 *Open Positions* — Count of active positions (not closed)
💵 *Val* — Current value of open positions
🕐 *Wallet Age* — Time since first activity

*Category definitions:*
1. 💰 *Crypto*
Keywords: bitcoin, btc, ethereum, eth, solana, doge, pepe, binance, nft, airdrop, etc.
2. ⚽ *Sports*
Keywords: nfl, nba, football, soccer, ufc, f1, lakers, goal, etc.

💬 Feedback: @Andrey\_Os
💻 [GitHub](https://github.com/ahdpe/PolymarketWhales)

⚡ *Best Exchange to Trade:*
[Join Bybit and get massive bonuses! 🎁](https://www.bybit.com/invite?ref=JDRKDN)""",
        
        # Trade alerts
        'open_market': "Open market",
    }
}

# Trade level names per language
TRADE_LEVELS = {
    'ru': {
        20000: "Кит",
        10000: "Акула",
        5000: "Дельфин",
        1000: "Рыба",
        100: "Креветка",
    },
    'en': {
        20000: "Whale",
        10000: "Shark",
        5000: "Dolphin",
        1000: "Fish",
        100: "Shrimp",
    }
}

# Trade level emojis with localized text
TRADE_LEVEL_EMOJIS = {
    'ru': {
        100000: "🔥 МЕГА КИТ",
        50000: "⚡ СУПЕР КИТ", 
        25000: "🐋 КИТ",
        10000: "🦈 АКУЛА",
        5000: "🐬 ДЕЛЬФИН",
        2000: "🐟 РЫБА",
        500: "🦐 КРЕВЕТКА",
    },
    'en': {
        100000: "🔥 MEGA WHALE",
        50000: "⚡ SUPER WHALE",
        25000: "🐋 WHALE",
        10000: "🦈 SHARK",
        5000: "🐬 DOLPHIN",
        2000: "🐟 FISH",
        500: "🦐 SHRIMP",
    }
}


def get_text(lang: str, key: str, **kwargs) -> str:
    """Get localized text."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def get_trade_level_name(lang: str, min_value: int) -> str:
    """Get localized trade level name."""
    return TRADE_LEVELS.get(lang, TRADE_LEVELS['ru']).get(min_value, "")


def get_trade_level_emoji(lang: str, min_value: int) -> str:
    """Get localized trade level emoji with text (e.g. '🐬 DOLPHIN')."""
    levels = TRADE_LEVEL_EMOJIS.get(lang, TRADE_LEVEL_EMOJIS['ru'])
    return levels.get(min_value, levels.get(500, "🦐"))
