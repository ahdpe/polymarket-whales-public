"""Localization strings for PolyWhales bot."""

TRANSLATIONS = {
    'ru': {
        # Start message
        'welcome': "🐋 *Polymarket Whale Alerts*\n\nКрупные сделки на [Polymarket](https://polymarket.com?via=PolymarketWhaleAlerts) — в реальном времени.\n\n*Что умеет бот:*\n• 🔔 Уведомления от $500 до $100,000+\n• 🎯 Фильтры: сумма, категории, вероятность, типы, возраст, позиции\n• 📊 Аналитика: PnL, возраст кошелька, открытые позиции\n• 🔗 Быстрые ссылки на профили\n• ⭐ Трейдеры — сохранённые трейдеры, заметки и уведомления об их сделках ($500+)\n• ⭐ Маркеты — сохранённые маркеты с отдельными уведомлениями ($500+)\n• 🚫 Игнор — скрытие сигналов от выбранных трейдеров или маркетов\n\nДля настройки уведомлений нажми кнопку ⚙️ **Фильтры** в меню ниже.",
        
        # Buttons
        'btn_filters': "⚙️ Фильтры",
        'btn_amount': "💰 Сумма сделки",
        'btn_categories': "📂 Категории",
        'btn_probability': "⚖️ Вероятность",
        'btn_sides': "🔄 Типы событий",
        'btn_start': "▶️ Запустить",
        'btn_stop': "⏸️ Остановить",
        'btn_language': "🇬🇧 EN",
        'btn_about': "ℹ️ О боте",
        'btn_hide_menu': "⬇️ Скрыть меню",
        'btn_show_menu': "⬆️ Показать меню",
        'btn_back': "⬅️ Назад",
        'btn_saved': "⭐ Трейдеры",
        'btn_saved_markets': "⭐ Маркеты",
        'menu_hidden': "✅ Меню скрыто. Нажмите 'Показать меню' чтобы вернуть его.",
        'menu_shown': "✅ Меню показано.",
        
        # Status
        'bot_started': "▶️ **Бот запущен!**\nЯ буду присылать уведомления о сделках.",
        'bot_stopped': "⏸️ **Бот остановлен.**\nУведомления приходить не будут, пока ты снова не запустишь бота.",
        
        # Filter - Amount
        'amount_menu_title': "💰 **Сумма сделки**\n\nВыбери минимальную сумму:",
        'amount_set': "✅ Минимальная сумма установлена: *${min:,}*",
        'amount_warning_title': "⚠️ Много сделок",
        'amount_warning_text': "Порог $500 без дополнительных фильтров приведёт к большому количеству алертов.\nВключить $500 всё равно?",
        'amount_confirm_yes': "✅ Да, включить",
        'amount_confirm_no': "❌ Нет, отмена",
        
        # Filter - Categories  
        'categories_menu_title': "📂 **Категории**\n\nВыбери какие рынки отслеживать:",
        'categories_set': "✅ Категории обновлены: {categories}",
        
        # Filter - Probability
        'probability_menu_title': "⚖️ **Вероятность**\n\nФильтр по вероятности рынка:\n(исключает почти решённые рынки)",
        'probability_set': "✅ Фильтр вероятности: *{range}*",
        
        # Filter - Side Types
        'sides_menu_title': "🔄 **Типы событий**\n\nВыбери какие типы сделок отслеживать:",
        'sides_set': "✅ Типы событий обновлены: {sides}",
        'filters_menu_title': "⚙️ **Фильтры**\n\nВыбери настройку:",
        'side_all': "Все события",
        'side_buy': "🟢 BUY",
        'side_sell': "🔵 SELL",
        'side_split': "⚪ SPLIT",
        'side_merge': "↔️ MERGE",
        'side_redeem': "🟣 REDEEM",
        'side_nothing': "Ничего",
        'prob_any': "🌐 Любая",
        'prob_1_99': "🟢 1% — 99%",
        'prob_5_95': "🟡 5% — 95%",
        'prob_10_90': "🟠 10% — 90%",
        'prob_custom': "📝 Настроить интервал",
        'prob_set': "✅ Фильтр вероятности: *{range}*",
        'prob_prompt': "**Введите диапазон в процентах:**\nФормат: мин-макс\nПримеры:\n• 20-80 (от 20% до 80%)\n• 0-5, 95-100 (редкие или верняки)\n• 0-100 (сбросить)",
        'prob_invalid': "❌ Неверный формат. Примеры: `20-80` или `0-5, 95-100`\n\nНажмите кнопку снова, чтобы повторить ввод.",
        'filter_toast': "Настройки обновлены!",
        
        # Filter - Wallet Age
        'btn_age': "🕐 Возраст",
        'age_menu_title': "🕐 **Возраст кошелька**\n\n🧪 *Тестовый режим* — возможны неточности\n\nФильтр по возрасту кошелька трейдера:",
        'age_any': "🌐 Любой",
        'age_custom': "📝 Настроить интервал",
        'age_set': "✅ Фильтр возраста: *{range}*",
        'age_prompt': "**Введите диапазон в днях:**\nФормат: мин-макс\nПримеры:\n• 7-365 (от 7 дней до 1 года)\n• 30- (от 30 дней)\n• -90 (до 90 дней)\n• 0 (сбросить)",
        'age_invalid': "❌ Неверный формат. Примеры: `7-365` или `30-` или `-90`\n\nНажмите кнопку снова, чтобы повторить ввод.",
        'days': "дн.",
        'current': "Текущее",
        
        # Filter - Open Positions
        'btn_positions': "💼 Позиции",
        'pos_menu_title': "💼 **Количество позиций**\n\nФильтр по количеству открытых позиций:",
        'pos_any': "🌐 Любой",
        'pos_custom': "📝 Настроить интервал",
        'pos_set': "✅ Фильтр позиций: *{range}*",
        'pos_prompt': "**Введите диапазон:**\nФормат: мин-макс\nПримеры:\n• 5-50 (от 5 до 50 позиций)\n• 10- (от 10 позиций)\n• -20 (до 20 позиций)\n• 0 (сбросить)",
        'pos_invalid': "❌ Неверный формат. Примеры: `5-50` или `10-` или `-20`\n\nНажмите кнопку снова, чтобы повторить ввод.",
        
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
        'about': """*Polymarket Whale Alerts* 🐋
Мониторинг крупных сделок на [Polymarket](https://polymarket.com?via=PolymarketWhaleAlerts) в реальном времени.

*Функционал:*
• 🔔 Уведомления о сделках от $500 до $100,000+
• 💰 Фильтр минимальной суммы (настраивается пользователем)
• 📂 Выбор категорий (Крипто, Спорт, Остальное)
• ⚖️ Фильтр вероятности (исключает почти решённые рынки)
• 🔄 Фильтр типов событий (BUY, SELL, SPLIT, MERGE, REDEEM)
• 🕐 Фильтр возраста кошелька (по дням, мин-макс)
• 💼 Фильтр количества позиций (мин-макс)
• ⭐ Трейдеры (сохранять, уведомлять, игнорировать)
• ⭐ Маркеты (сохранять, уведомлять, игнорировать)

*Классификация объемов:*
🔥 МЕГА КИТ — >$100,000
⚡ СУПЕР КИТ — >$50,000
🐋 КИТ — >$25,000
🦈 АКУЛА — >$10,000
🐬 ДЕЛЬФИН — >$5,000
🐟 РЫБА — >$2,000
🦐 КРЕВЕТКА — >$500

*Типы событий:*
🟢 BUY — покупка
🔵 SELL — продажа
⚪ SPLIT — разделение на YES+NO
↔️ MERGE — объединение YES+NO → USDC
🟣 REDEEM — выкуп при разрешении рынка

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
📢 @PMInsiderSignals — сигналы о нетипичной скоординированной активности свежих кошельков на Polymarket.
🌐 https://polymarketwhales.online/ — активные сигналы, буфер до публикации и причины непубликации в канал.
🐦 [Twitter/X](https://x.com/PolyMrktWhales)

💝 *Поддержать проект:*
ERC-20: `0x53676559a4ac7fd8e19c79eef51e27622791bd45`

""",
        
        # Trade alerts

        
        # Saved Traders
        'save_btn': "Сохранить трейдера",
        'saved_btn': "✅ Сохранено",
        'note_btn': "💬 Коммент",
        'saved_list_title': "⭐ **Трейдеры**\n\n",
        'saved_list_header': "⭐ Трейдеры\n🔔 - уведомления включены (все сделки $500+)\n🔕 - только по общим фильтрам\n🚫 - скрыт из алертов\n",
        'saved_empty': "Список пуст. Сохраняй трейдеров из алертов!",
        'saved_deleted': "🗑 Трейдер удалён",
        'saved_added': "⭐ Трейдер сохранён!",
        'note_prompt': "💬 Введи комментарий к трейдеру (макс. 240 символов):\n\nОтправь \"–\" чтобы удалить комментарий.",
        'note_saved': "✅ Комментарий сохранён",
        'note_too_long': "❌ Слишком длинный! Макс. 240 символов. Попробуй ещё раз:",
        'note_removed': "✅ Комментарий удалён",
        'page_info': "Стр. {page}/{total}",
        'notif_on': "🔔 Вкл",
        'notif_off': "🔕 Выкл",
        'notif_all_on': "🔔 Все",
        'notif_all_off': "🔕 Все",
        'notif_enabled': "🔔 Уведомления включены (без фильтров)",
        'notif_disabled': "🔕 Уведомления выключены (по общим фильтрам)",
        'saved_cleared': "🗑 Все трейдеры удалены",
        
        # Ignore
        'ignore_trader_btn': "🚫 Трейдер",
        'ignore_market_btn': "🚫 Маркет",
        'ignored_trader_added': "🛑 Трейдер в игноре",
        'ignored_market_added': "🛑 Маркет в игноре",
        'state_ignore': "🛑 Игнор",
        'state_notify': "🔔 Активен",

        # Saved Markets
        'market_track_btn': "💾 Сохранить маркет",
        'market_saved_btn': "✅ В списке",
        'markets_list_header': "⭐ Маркеты\n🔔 - уведомления включены (все сделки $500+, фильтр типов событий)\n🔕 - только по общим фильтрам\n🚫 - скрыт из алертов\n",
        'markets_empty': "Список пуст. Добавляй маркеты из алертов или вручную!",
        'market_added': "✅ Маркет добавлен!",
        'market_deleted': "🗑 Маркет удалён",
        'markets_cleared': "🗑 Все маркеты удалены",
        'market_exists': "ℹ️ Этот маркет уже в списке.",
        'market_notif_on': "🔔 Вкл",
        'market_notif_off': "🔕 Выкл",
        'market_notif_all_on': "🔔 Все",
        'market_notif_all_off': "🔕 Все",
        'market_notif_enabled': "🔔 Уведомления включены (все сделки $500+, с учётом типов)",
        'market_notif_disabled': "🔕 Уведомления выключены (по общим фильтрам)",
        'market_manual_add_btn': "➕ Добавить",
        'market_manual_add_prompt': "✍️ Отправьте ссылку на маркет Polymarket:\n\nПример:\n• `https://polymarket.com/event/...`",
        'market_manual_add_invalid': "❌ Неверный формат. Отправьте ссылку на маркет вида `https://polymarket.com/event/...`\n\nНажмите ➕ снова, чтобы повторить.",
        'market_manual_add_exists': "ℹ️ Этот маркет уже в списке.",
        'market_manual_add_success': "✅ Маркет добавлен!",
        'market_manual_add_cancel': "❌ Отмена",
        
        # Manual add
        'manual_add_btn': "➕ Добавить",
        'manual_add_prompt': "✍️ Отправьте ссылку на профиль Polymarket или адрес кошелька трейдера:\n\nПример:\n• `https://polymarket.com/profile/0x123...`\n• `0x1234567890abcdef...`",
        'manual_add_invalid': "❌ Неверный формат. Отправьте ссылку на профиль или адрес кошелька (0x...)\n\nНажмите ➕ снова, чтобы повторить.",
        'manual_add_exists': "ℹ️ Этот трейдер уже в списке.",
        'manual_add_success': "✅ Трейдер добавлен в список!",
        'manual_add_cancel': "❌ Отмена",
        'reset_done': "🔄 **Настройки сброшены!**\nВсе фильтры вернулись к значениям по умолчанию.",
    },
    
    'en': {
        # Start message
        'welcome': "🐋 *Polymarket Whale Alerts*\n\nLarge trades on [Polymarket](https://polymarket.com?via=PolymarketWhaleAlerts) — in real-time.\n\n*What the bot can do:*\n• 🔔 Alerts from $500 to $100,000+\n• 🎯 Filters: amount, categories, probability, types, age, positions\n• 📊 Analytics: PnL, wallet age, open positions\n• 🔗 Quick links to profiles\n• ⭐ Traders — saved traders, notes and notifications about their trades ($500+)\n• ⭐ Markets — saved markets with personal notifications ($500+)\n• 🚫 Ignore traders/markets — hide signals from selected traders or markets\n\nTo configure alerts, press the ⚙️ **Filters** button in the menu below.",
        
        # Buttons
        'btn_filters': "⚙️ Filters",
        'btn_amount': "💰 Trade Amount",
        'btn_categories': "📂 Categories",
        'btn_probability': "⚖️ Probability",
        'btn_sides': "🔄 Event Types",
        'btn_start': "▶️ Start",
        'btn_stop': "⏸️ Stop",
        'btn_language': "🇷🇺 RU",
        'btn_about': "ℹ️ About",
        'btn_hide_menu': "⬇️ Hide Menu",
        'btn_show_menu': "⬆️ Show Menu",
        'btn_back': "⬅️ Back",
        'btn_saved': "⭐ Traders",
        'btn_saved_markets': "⭐ Markets",
        'menu_hidden': "✅ Menu hidden. Press 'Show Menu' to restore it.",
        'menu_shown': "✅ Menu shown.",
        
        # Status
        'bot_started': "▶️ **Bot started!**\nI will send trade alerts.",
        'bot_stopped': "⏸️ **Bot stopped.**\nAlerts are paused until you restart the bot.",
        
        # Filter - Amount
        'amount_menu_title': "💰 **Trade Amount**\n\nSelect minimum amount:",
        'amount_set': "✅ Minimum amount set: *${min:,}*",
        'amount_warning_title': "⚠️ Many Trades",
        'amount_warning_text': "A $500 threshold without additional filters will result in a large number of alerts.\nEnable $500 anyway?",
        'amount_confirm_yes': "✅ Yes, enable",
        'amount_confirm_no': "❌ No, cancel",
        
        # Filter - Categories  
        'categories_menu_title': "📂 **Categories**\n\nSelect which markets to track:",
        'categories_set': "✅ Categories updated: {categories}",
        
        # Filter - Probability
        'probability_menu_title': "⚖️ **Probability**\n\nFilter by market probability:\n(excludes near-resolved markets)",
        'probability_set': "✅ Probability filter: *{range}*",
        
        # Filter - Side Types
        'sides_menu_title': "🔄 **Event Types**\n\nSelect which trade types to track:",
        'sides_set': "✅ Event types updated: {sides}",
        'filters_menu_title': "⚙️ **Filters**\n\nSelect setting:",
        'side_all': "All events",
        'side_buy': "🟢 BUY",
        'side_sell': "🔵 SELL",
        'side_split': "⚪ SPLIT",
        'side_merge': "↔️ MERGE",
        'side_redeem': "🟣 REDEEM",
        'side_nothing': "None",
        'prob_any': "🌐 Any",
        'prob_1_99': "🟢 1% — 99%",
        'prob_5_95': "🟡 5% — 95%",
        'prob_10_90': "🟠 10% — 90%",
        'prob_custom': "📝 Set interval",
        'prob_set': "✅ Probability filter: *{range}*",
        'prob_prompt': "**Enter range in %:**\nFormat: min-max\nExamples:\n• 20-80 (20% to 80%)\n• 0-5, 95-100 (rare or certain)\n• 0-100 (reset)",
        'prob_invalid': "❌ Invalid format. Examples: `20-80` or `0-5, 95-100`\n\nPress the button again to retry.",
        'filter_toast': "Settings updated!",
        
        # Filter - Wallet Age
        'btn_age': "🕐 Age",
        'age_menu_title': "🕐 **Wallet Age**\n\n🧪 *Beta mode* — may have inaccuracies\n\nFilter by trader wallet age:",
        'age_any': "🌐 Any",
        'age_custom': "📝 Set interval",
        'age_set': "✅ Age filter: *{range}*",
        'age_prompt': "**Enter range in days:**\nFormat: min-max\nExamples:\n• 7-365 (7 days to 1 year)\n• 30- (from 30 days)\n• -90 (up to 90 days)\n• 0 (reset)",
        'age_invalid': "❌ Invalid format. Examples: `7-365` or `30-` or `-90`\n\nPress the button again to retry.",
        'days': "days",
        'current': "Current",
        
        # Filter - Open Positions
        'btn_positions': "💼 Positions",
        'pos_menu_title': "💼 **Open Positions**\n\nFilter by number of open positions:",
        'pos_any': "🌐 Any",
        'pos_custom': "📝 Set interval",
        'pos_set': "✅ Positions filter: *{range}*",
        'pos_prompt': "**Enter range:**\nFormat: min-max\nExamples:\n• 5-50 (5 to 50 positions)\n• 10- (from 10 positions)\n• -20 (up to 20 positions)\n• 0 (reset)",
        'pos_invalid': "❌ Invalid format. Examples: `5-50` or `10-` or `-20`\n\nPress the button again to retry.",
        
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
        'about': """*Polymarket Whale Alerts* 🐋
Real-time monitoring of large trades on [Polymarket](https://polymarket.com?via=PolymarketWhaleAlerts).

*Functionality:*
• 🔔 Trade alerts from $500 to $100,000+
• 💰 Customizable amount threshold
• 📂 Category selection (Crypto, Sports, Other)
• ⚖️ Probability filter (excludes near-resolved markets)
• 🔄 Event type filter (BUY, SELL, SPLIT, MERGE, REDEEM)
• 🕐 Wallet age filter (in days, min-max range)
• 💼 Open positions filter (min-max range)
• ⭐ Traders (Save traders, notify, ignore)
• ⭐ Markets (Save markets, notify, ignore)

*Volume classification:*
🔥 MEGA WHALE — >$100,000
⚡ SUPER WHALE — >$50,000
🐋 WHALE — >$25,000
🦈 SHARK — >$10,000
🐬 DOLPHIN — >$5,000
🐟 FISH — >$2,000
🦐 SHRIMP — >$500

*Event types:*
🟢 BUY — purchase
🔵 SELL — sale
⚪ SPLIT — split into YES+NO
↔️ MERGE — merge YES+NO → USDC
🟣 REDEEM — redeem on market resolution

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
📢 @PMInsiderSignals — signals of atypical coordinated activity of fresh wallets on Polymarket.
🌐 https://polymarketwhales.online/ — active signals, pre-publish buffer, and reasons why a signal is not yet posted to the channel.
🐦 [Twitter/X](https://x.com/PolyMrktWhales)

💝 *Support the project:*
ERC-20: `0x53676559a4ac7fd8e19c79eef51e27622791bd45`

""",
        
        # Trade alerts

        
        # Saved Traders
        'save_btn': "Save Trader",
        'saved_btn': "✅ Saved",
        'note_btn': "💬 Note",
        'saved_list_title': "⭐ **Traders**\n\n",
        'saved_list_header': "⭐ Traders\n🔔 - notifications enabled (all trades $500+)\n🔕 - general filters only\n🚫 - hidden from alerts\n",
        'saved_empty': "Empty list. Save traders from alerts!",
        'saved_deleted': "🗑 Trader removed",
        'saved_added': "⭐ Trader saved!",
        'note_prompt': "💬 Enter note for trader (max 240 chars):\n\nSend \"–\" to remove note.",
        'note_saved': "✅ Note saved",
        'note_too_long': "❌ Too long! Max 240 characters. Try again:",
        'note_removed': "✅ Note removed",
        'page_info': "Page {page}/{total}",
        'notif_on': "🔔 On",
        'notif_off': "🔕 Off",
        'notif_all_on': "🔔 All",
        'notif_all_off': "🔕 All",
        'notif_enabled': "🔔 Notifications enabled (bypassing filters)",
        'notif_disabled': "🔕 Notifications disabled (using general filters)",
        'saved_cleared': "🗑 All traders removed",
        
        # Ignore
        'ignore_trader_btn': "🚫 Trader",
        'ignore_market_btn': "🚫 Market",
        'ignored_trader_added': "🛑 Trader ignored",
        'ignored_market_added': "🛑 Market ignored",
        'state_ignore': "🛑 Ignored",
        'state_notify': "🔔 Active",

        # Saved Markets
        'market_track_btn': "💾 Save Market",
        'market_saved_btn': "✅ Tracking",
        'markets_list_header': "⭐ Markets\n🔔 - notifications enabled (all trades $500+, event types filter)\n🔕 - general filters only\n🚫 - hidden from alerts\n",
        'markets_empty': "Empty list. Track markets from alerts or add manually!",
        'market_added': "✅ Market added!",
        'market_deleted': "🗑 Market removed",
        'markets_cleared': "🗑 All markets removed",
        'market_exists': "ℹ️ This market is already in the list.",
        'market_notif_on': "🔔 On",
        'market_notif_off': "🔕 Off",
        'market_notif_all_on': "🔔 All",
        'market_notif_all_off': "🔕 All",
        'market_notif_enabled': "🔔 Notifications enabled (all trades $500+, event types applied)",
        'market_notif_disabled': "🔕 Notifications disabled (general filters only)",
        'market_manual_add_btn': "➕ Add",
        'market_manual_add_prompt': "✍️ Send a Polymarket market link:\n\nExample:\n• `https://polymarket.com/event/...`",
        'market_manual_add_invalid': "❌ Invalid format. Send a link like `https://polymarket.com/event/...`\n\nPress ➕ again to retry.",
        'market_manual_add_exists': "ℹ️ This market is already in the list.",
        'market_manual_add_success': "✅ Market added!",
        'market_manual_add_cancel': "❌ Cancel",
        
        # Manual add
        'manual_add_btn': "➕ Add",
        'manual_add_prompt': "✍️ Send a Polymarket profile link or trader wallet address:\n\nExample:\n• `https://polymarket.com/profile/0x123...`\n• `0x1234567890abcdef...`",
        'manual_add_invalid': "❌ Invalid format. Send a profile link or wallet address (0x...)\n\nPress ➕ again to retry.",
        'manual_add_exists': "ℹ️ This trader is already in the list.",
        'manual_add_success': "✅ Trader added to the list!",
        'manual_add_cancel': "❌ Cancel",
        'reset_done': "🔄 **Settings reset!**\nAll filters have been restored to default values.",
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


def get_trade_level_icon(min_value: int) -> str:
    """Get just the emoji for the trade level."""
    # Mapping of threshold to emoji (same as TRADE_LEVEL_EMOJIS keys)
    icons = {
        100000: "🔥",
        50000: "⚡",
        25000: "🐋",
        10000: "🦈",
        5000: "🐬",
        2000: "🐟",
        500: "🦐",
    }
    return icons.get(min_value, "🦐")


def get_trade_level_emoji(lang: str, min_value: int) -> str:
    """Get localized trade level emoji with text (e.g. '🐬 DOLPHIN')."""
    levels = TRADE_LEVEL_EMOJIS.get(lang, TRADE_LEVEL_EMOJIS['ru'])
    return levels.get(min_value, levels.get(500, "🦐"))
