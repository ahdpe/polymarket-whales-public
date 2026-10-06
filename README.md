# PUBLIC SHELL REPOSITORY
> This is a public demonstration shell. Core logic is stripped.

# Polymarket Whale Alerts 🐋

[🇷🇺 Русский](#-русский) | [🇬🇧 English](#-english)

---

## 🇷🇺 Русский

Telegram-бот для отслеживания крупных сделок ("китов") на [Polymarket](https://polymarket.com) в режиме реального времени.

### 🌐 Веб-сайт

**[polymarketwhales.online](https://polymarketwhales.online)** — публичная страница с live-сигналами и whale-трейдами:
- 📡 **[Signals & Patterns](https://polymarketwhales.online/public)** — лента сигналов о поведенческих паттернах (кластеры, накопления, всплески объёмов)
- 🐋 **[Whale Trades](https://polymarketwhales.online/whale-trades)** — live-поток крупных BUY-ордеров от $10K+ с PnL, позициями и возрастом кошелька

### Возможности

- 📊 **Мониторинг сделок** от $500 до $100,000+
- 💰 **Фильтр по сумме** — выбери минимальный порог
- 📂 **Категории и подкатегории** — общий выбор Крипто, Спорт, Остальное и детальная настройка отдельных типов рынков
- ⚖️ **Фильтр вероятности** — исключает почти решённые рынки (99.9%)
- 🔄 **Фильтр типов событий** — выбирай какие сделки отслеживать: BUY, SELL, SPLIT, MERGE, REDEEM
- ⏱ **Фильтр длительности рынка** — скрывает короткие рынки, если в названии или slug удаётся распознать таймфрейм
- 🕐 **Фильтр возраста кошелька** — фильтр по возрасту кошелька трейдера (в днях, мин-макс)
- 💼 **Фильтр количества позиций** — фильтр по количеству открытых позиций (мин-макс)
- 🌐 **Двуязычный интерфейс** — Русский / English
- 🔗 **Ссылки на профиль трейдера** и рынок
- 📈 **Расширенная аналитика:** Portfolio PnL, портфель, возраст кошелька и сделки
- ⭐ **Трейдеры:** Сохранение трейдеров с их текущим "уровнем" (🦐-🔥) + **🔔 Уведомления** и **🚫 Игнор** (персональная подписка или скрытие сигналов)
- ⭐ **Маркеты:** Сохранение маркетов + **🔔 Уведомления** и **🚫 Игнор** по маркету (все сделки $500+, с учётом фильтра типов событий)
- 🐦 **Twitter интеграция** — автоматическая публикация крупных сделок в Twitter/X

### Обратная связь и поддержка

📢 [Feedback](https://t.me/polymarketwhales_feedback) | 💻 [GitHub](https://github.com/ahdpe/polymarket-whales-public) | 🐦 [Twitter](https://x.com/polywhales_bot)

💝 **Поддержать проект:**  
ERC-20: `0x53676559a4ac7fd8e19c79eef51e27622791bd45`

### Классификация объёмов

| Эмодзи | Уровень | Сумма |
|--------|---------|-------|
| 🔥 | Мега Кит | >$100,000 |
| ⚡ | Супер Кит | >$50,000 |
| 🐋 | Кит | >$25,000 |
| 🦈 | Акула | >$10,000 |
| 🐬 | Дельфин | >$5,000 |
| 🐟 | Рыба | >$2,000 |
| 🐙 | Осьминог | >$1,000 |
| 🦐 | Креветка | >$500 |

### Новые метрики и точность данных

#### Аналитика трейдера
В каждом уведомлении теперь доступна статистика:
- 💵 **Paid → Max payout**: Сумма покупки и максимальная выплата при выигрыше.
- 💵 **Received**: Сумма, полученная при продаже.
- 📊 **Portfolio PnL**: Нереализованная прибыль/убыток по всем открытым позициям кошелька.
- 💼 **Portfolio**: Количество и стоимость активных (не закрытых) позиций.
- 🕐 **Wallet Age**: Возраст кошелька с момента первой активности.
- 🕐 **Trade**: Сколько времени прошло с момента сделки (показывается от 1 минуты).

#### Точный возраст кошелька
Polymarket Data API часто обрезает историю активных трейдеров. Поэтому бот:
1. **Сначала использует дату создания публичного профиля Polymarket** из Gamma API.
2. **Проверяет полную историю активности и PolygonScan как резервные источники**, когда это возможно.
3. **Не показывает ложный молодой возраст**, если доступная история явно обрезана.
4. **Кэширует подтверждённый результат на 7 дней**, чтобы уменьшить нагрузку на API.

### Принцип работы

#### 1. Получение данных (PolymarketService)
- **Источник:** Бот использует публичный **Polymarket Data API** (`data-api.polymarket.com`).
- **Метод:** Бот **опрашивает (polling)** API каждые **3 секунды**.
- **Фильтрация на входе:** Запрашиваются только сделки типа `CASH` на сумму от **$10** (чтобы захватить даже мелкие части крупных ордеров).
- **Задержка источника:** Polymarket Data API иногда публикует сделки с задержкой в несколько минут. В такие моменты алерты тоже могут приходить не мгновенно — это ограничение источника данных, а не ошибка бота.

#### 2. Обработка и Агрегация (Aggregation)
Одна крупная сделка на Polymarket часто разбивается на множество мелких исполнений (fills). Чтобы не спамить уведомлениями о каждой части, бот собирает их в серии.
- **Группировка:** Сделки объединяются в серию, если совпадают:
  - Кошелек трейдера
  - Рынок (Condition ID)
  - Сторона (BUY/SELL/SPLIT/MERGE/REDEEM)
  - Исход (YES/NO/Outcome Index)
- **Типы событий:** Бот поддерживает все типы сделок Polymarket:
  - **BUY/SELL** — обычные покупки и продажи
  - **SPLIT** — разделение позиции на YES и NO одновременно
  - **MERGE** — объединение YES и NO позиций обратно в USDC
  - **REDEEM** — выкуп позиций при разрешении рынка
- **Окно времени:** Сделки собираются в течение **60 секунд** с момента первой части.
- **Порог срабатывания:** Если сумма серии превышает **$500**, она считается значимой и передается на отправку.
- **Оптимизация:** Тяжелые запросы к API (PnL, Pos, Age) выполняются **только** если сделка проходит фильтры хотя бы одного активного пользователя.

#### 3. Дедупликация и Хранение (Persistence)
Чтобы избежать повторных уведомлений (например, при перезапуске):
- **База данных:** Используется локальная база **SQLite** (`data/trades.db`), где хранятся уникальные ключи всех обработанных сделок.
- **Кэш:** В оперативной памяти держится список последних 10,000 сделок (LRU Cache).
- **Очистка:** Старые записи (старше 72 часов) автоматически удаляются из базы.

#### 4. Telegram Бот (TelegramService)
Бот взаимодействует с пользователями и рассылает уведомления.
- **Персонализация:** Каждый пользователь может настроить свои фильтры:
  - **Минимальная сумма:** от $500 до $100,000
  - **Категории:** Крипто, Спорт, Остальное (определяются по ключевым словам)
  - **Вероятность:** Любая, 1%-99%, 5%-95%, или **свой диапазон** (20-80%)
  - **Типы событий:** BUY, SELL, SPLIT, MERGE, REDEEM
  - **Длительность рынка:** по умолчанию ≥15m; варианты Off, ≥15m, ≥30m, ≥60m, ≥240m. Если длительность не распознана, алерт не скрывается
  - **Возраст кошелька:** Фильтр по возрасту кошелька трейдера в днях (мин-макс диапазон, по умолчанию неограничено). ⚠️ Тестовый режим — возможны неточности.
  - **Количество позиций:** Фильтр по количеству открытых позиций (мин-макс диапазон, по умолчанию неограничено)
  - **Язык:** Русский или Английский
- **Интерфейс:**
  - `⚙️ Фильтры` — подменю со всеми настройками фильтров:
    - **Строка 1:** `💰 Сумма сделки`, `📂 Категории`, `⚖️ Вероятность`
    - **Строка 2:** `🔄 Типы событий`, `🕐 Возраст`, `💼 Позиции`
    - **Строка 3:** `⏱ Длительность рынка`, `▶️ Запустить / ⏸️ Остановить`, `⬅️ Назад`
  - **Настройка фильтров:**
    - Для **вероятности**, **возраста** и **позиций** доступен ввод произвольного диапазона нажатием "📝 Настроить интервал".
    - Формат: `мин-макс` (например: `7-365`), `мин-` (от минимума), `-макс` (до максимума), или `0` (сбросить)
  - `▶️ Запустить / ⏸️ Остановить` — переключатель уведомлений
  - `⭐ Трейдеры` — список сохранённых трейдеров
  - `⭐ Маркеты` — список сохранённых маркетов
- **Уведомления:** Присылает сообщение с:
  - Эмодзи категории (💰, ⚽, 📌) и названием рынка
  - Типом сделки (BUY/SELL/SPLIT/MERGE/REDEEM) с цветовыми индикаторами:
    - 🟢 BUY Yes, 🔴 BUY No, 🔵 SELL, ⚪ SPLIT, ↔️ MERGE, 🟣 REDEEM
  - Суммой сделки (для серий пишет "Series X fills")
  - Уровнем "кита" и ссылкой на трейдера
  - Статистикой (PnL, Pos, Age)

#### 5. Команды

**Основные:**
- `/start` — Запуск бота
- `/stop` — Вкл/Выкл уведомления (аналог кнопки ▶️/⏸️)
- `/filters` — Меню настроек фильтров
- `/saved` — Список сохранённых трейдеров
- `/markets` — Список сохранённых маркетов
- `/about` — Информация о боте
- `/lang` — Переключение языка (🇬🇧 / 🇷🇺)
- `/hide` — Скрыть клавиатуру меню
- `/menu` — Показать клавиатуру меню
- `/reset` — Сброс всех фильтров по умолчанию

**Настройки фильтров:**
- `/amount` — Фильтр суммы
- `/categories` — Фильтр категорий
- `/probability` — Фильтр вероятности
- `/sides` — Фильтр типов событий
- `/age` — Фильтр возраста кошелька
- `/positions` — Фильтр открытых позиций
- `/back` — Назад в главное меню

#### 6. Архитектура "Трейдеров" (Saved Traders)
Реализация списка сохранённых трейдеров оптимизирована для работы с ограничениями Telegram API:
1. **Компактные ключи (Callback Data):**
   - Telegram ограничивает `callback_data` до 64 байт.
   - Полные адреса кошельков (42 символа) + префикс команды часто превышают лимит.
   - **Решение:** Используется таблица `whale_keys`, где хеш `SHA1(wallet_address)[:10]` мапится на полный адрес. В кнопках передается только короткий хеш.
2. **Оптимизация производительности:**
   - Данные для отображения списка (имя, иконка уровня) кэшируются в БД в момент сохранения.
   - Это позволяет рендерить списки мгновенно без запросов к Polymarket API.
3. **Хранение данных (SQLite):**
   - `saved_whales`: Связь `user_id` <-> `whale_id` + комментарий пользователя.
   - `whale_keys`: Общая таблица метаданных (адрес, имя, уровень).
4. **Персональные уведомления (Bell Feature):**
   - Возможность включить уведомления (🔔) для конкретного трейдера.
   - Такие уведомления **игнорируют общие фильтры** (сумма, категория, вероятность) и приходят всегда.

#### 7. Архитектура "Маркетов" (Saved Markets)
Реализация списка сохранённых маркетов:
1. **Компактные ключи (Callback Data):**
   - Используется таблица `market_keys`, где `SHA1(market_ref)[:10]` мапится на market_id/slug.
2. **Хранение данных (SQLite):**
   - `saved_markets`: Связь `user_id` <-> `market_ref` + флаг уведомлений.
3. **Персональные уведомления по рынку:**
   - При включении (🔔) приходят **все сделки $500+** на этом рынке, с учётом фильтра типов событий пользователя.

# Опционально (для точного возраста кошельков)
POLYGONSCAN_API_KEY=your_polygonscan_key
# Опционально (для Twitter интеграции)
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
```

Запуск:
```bash
python main.py
```
> **Важно:** Убедитесь, что запущена только **одна** копия бота. Запуск нескольких экземпляров приведет к дублированию уведомлений и ошибкам фильтрации.

---

## 🇬🇧 English

Telegram bot for real-time tracking of large trades ("whales") on [Polymarket](https://polymarket.com).

### 🌐 Website

**[polymarketwhales.online](https://polymarketwhales.online)** — public page with live signals and whale trades:
- 📡 **[Signals & Patterns](https://polymarketwhales.online/public)** — behavioral intelligence feed (clusters, accumulations, volume bursts)
- 🐋 **[Whale Trades](https://polymarketwhales.online/whale-trades)** — live feed of $10K+ BUY orders with PnL, positions, and wallet age

### Features

- 📊 **Trade monitoring** from $500 to $100,000+
- 💰 **Amount filter** — choose minimum threshold
- 📂 **Categories and subcategories** — broad Crypto, Sports, Other selection plus detailed market-type controls
- ⚖️ **Probability filter** — excludes near-resolved markets (99.9%)
- 🔄 **Event type filter** — choose which trades to track: BUY, SELL, SPLIT, MERGE, REDEEM
- ⏱ **Market duration filter** — hides short markets when a timeframe can be recognized in the title or slug
- 🕐 **Wallet age filter** — filter by trader wallet age (in days, min-max range)
- 💼 **Open positions filter** — filter by number of open positions (min-max range)
- 🌐 **Bilingual interface** — Russian / English
- 🔗 **Links to trader profile** and market
- 📈 **Advanced Analytics:** Portfolio PnL, Portfolio, Wallet Age, Trade Age
- ⭐ **Traders:** Save traders with their current "level" (🦐-🔥) + **🔔 Notifications** and **🚫 Ignore** (subscribe to or hide signals)
- ⭐ **Markets:** Save markets + **🔔 Notifications** and **🚫 Ignore** per market (all trades $500+, event types filter applied)
- 🐦 **Twitter integration** — automatic posting of large trades to Twitter/X

### Feedback and Support

📢 [Feedback](https://t.me/polymarketwhales_feedback) | 💻 [GitHub](https://github.com/ahdpe/polymarket-whales-public) | 🐦 [Twitter](https://x.com/polywhales_bot)

💝 **Support the project:**  
ERC-20: `0x53676559a4ac7fd8e19c79eef51e27622791bd45`

### Volume Classification

| Emoji | Level | Amount |
|-------|-------|--------|
| 🔥 | Mega Whale | >$100,000 |
| ⚡ | Super Whale | >$50,000 |
| 🐋 | Whale | >$25,000 |
| 🦈 | Shark | >$10,000 |
| 🐬 | Dolphin | >$5,000 |
| 🐟 | Fish | >$2,000 |
| 🐙 | Octopus | >$1,000 |
| 🦐 | Shrimp | >$500 |

### New Metrics & Data Accuracy

#### Trader Analytics
Every alert includes detailed stats:
- 💵 **Paid → Max payout**: Purchase cost and maximum payout if the outcome wins.
- 💵 **Received**: Amount received from a sale.
- 📊 **Portfolio PnL**: Unrealized profit/loss across all open wallet positions.
- 💼 **Portfolio**: Count and total value of active positions.
- 🕐 **Wallet Age**: Time since the very first activity.
- 🕐 **Trade**: Time elapsed since the trade (shown from 1 minute).

#### Accurate Wallet Age
The Polymarket Data API often truncates active traders' history. The bot therefore:
1. **Uses the public Polymarket profile creation date** from the Gamma API first.
2. **Checks complete activity history and PolygonScan as fallbacks** when available.
3. **Leaves age unknown instead of showing a falsely young wallet** when history is clearly truncated.
4. **Caches confirmed results for 7 days** to reduce API load.

### How It Works

#### 8. Data Fetching (PolymarketService)
- **Source:** Uses public **Polymarket Data API** (`data-api.polymarket.com`).
- **Method:** Polls the API every **3 seconds**.
- **Input filtering:** Only `CASH` type trades from **$10** are requested.
- **Source delay:** The Polymarket Data API can publish trades with a delay of a few minutes. When this happens, alerts may not be instant — this is a data-source limitation, not a bot error.

#### 9. Processing and Aggregation
A single large trade is often split into multiple fills. To avoid spam, the bot groups them:
- **Grouping:** Same wallet, market, side (BUY/SELL/SPLIT/MERGE/REDEEM), outcome.
- **Event types:** The bot supports all Polymarket trade types:
  - **BUY/SELL** — regular purchases and sales
  - **SPLIT** — splitting a position into YES and NO simultaneously
  - **MERGE** — merging YES and NO positions back into USDC
  - **REDEEM** — redeeming positions when market resolves
- **Time window:** **60 seconds** aggregation window.
- **Trigger:** Series sum > **$500**.
- **Optimization:** Expensive API calls (PnL, Pos, Age) are deferred and only executed if the trade matches at least one active user's filters.

#### 10. Deduplication and Persistence
- **Database:** Local **SQLite** (`data/trades.db`) stores processed trade keys.
- **Cache:** 10,000 most recent trades in RAM.
- **Cleanup:** Records > 72h are deleted.

#### 11. Telegram Bot (TelegramService)
- **Filters:** Amount, Category, Probability (Presets or Custom Range), Event Types, Market Duration, Wallet Age, Open Positions, Language.
- **Interface:** Compact menu with "⚙️ Filters" submenu for all filter settings:
  - **Row 1:** Amount, Categories, Probability
  - **Row 2:** Event Types, Wallet Age, Open Positions
  - **Row 3:** Market Duration, Start/Stop, Back
  - **Buttons:** Start/Stop, ⭐ Traders, ⭐ Markets
- **Filter Details:**
  - **Market Duration:** default ≥15m; options Off, ≥15m, ≥30m, ≥60m, ≥240m. If the duration is not recognized, the alert is not hidden.
  - **Wallet Age:** Filter by trader wallet age in days (min-max range, default: unlimited). ⚠️ Beta mode - may have inaccuracies.
    - Format: `min-max` (e.g., `7-365`), `min-` (from minimum), `-max` (up to maximum), or `0` (reset)
  - **Open Positions:** Filter by number of open positions (min-max range, default: unlimited).
    - Format: `min-max` (e.g., `5-50`), `min-` (from minimum), `-max` (up to maximum), or `0` (reset)
- **Alerts:** Rich messages with emojis, links, and trader stats:
  - Color-coded trade types: 🟢 BUY Yes, 🔴 BUY No, 🔵 SELL, ⚪ SPLIT, ↔️ MERGE, 🟣 REDEEM

#### 12. Commands

**Main:**
- `/start` — Start bot
- `/stop` — Toggle alerts ON/OFF (same as ▶️/⏸️ button)
- `/filters` — Filter settings menu
- `/saved` — Saved traders list
- `/markets` — Saved markets list
- `/about` — About bot info
- `/lang` — Switch language (🇬🇧 / 🇷🇺)
- `/hide` — Hide menu keyboard
- `/menu` — Show menu keyboard
- `/reset` — Reset all filters to default

**Filter Settings:**
- `/amount` — Amount filter
- `/categories` — Category filter
- `/probability` — Probability filter
- `/sides` — Event types filter
- `/age` — Wallet age filter
- `/positions` — Open positions filter
- `/back` — Back to main menu

#### 13. Traders Architecture (Saved Traders)
The saved traders implementation is optimized for Telegram API constraints:
1. **Compact Keys (Callback Data):**
   - Telegram limits `callback_data` to 64 bytes.
   - Full wallet addresses (42 chars) + action prefixes often exceed this limit.
   - **Solution:** We use a `whale_keys` table mapping `SHA1(wallet_address)[:10]` to the full address. Buttons only carry this short hash.
2. **Performance Optimization:**
   - Display data (name, level icon) is cached in the DB at the time of saving.
   - This allows instant list rendering without Polymarket API calls.
3. **Data Storage (SQLite):**
   - `saved_whales`: Maps `user_id` <-> `whale_id` + user comment.
   - `whale_keys`: Shared metadata table (address, name, level).
4. **Direct Notifications (Bell Feature):**
   - Toggle notifications (🔔) for specific saved traders.
   - These alerts **bypass general filters** (amount, category, probability) and are always delivered.

#### 14. Markets Architecture (Saved Markets)
Saved markets implementation:
1. **Compact Keys (Callback Data):**
   - Uses `market_keys` table mapping `SHA1(market_ref)[:10]` to market_id/slug.
2. **Data Storage (SQLite):**
   - `saved_markets`: Maps `user_id` <-> `market_ref` + notifications flag.
3. **Market Notifications:**
   - When enabled (🔔), all trades **$500+** on that market are delivered, with user event-type filter applied.

# Optional (for accurate wallet age)
POLYGONSCAN_API_KEY=your_polygonscan_key
# Optional (for Twitter integration)
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
```

Run:
```bash
python main.py
```
> **Important:** Ensure only **one** instance of the bot is running. Multiple instances will cause duplicate alerts and broken filtering.

---

## Tech Stack

- **Language:** Python 3.10+
- **Libraries:** aiogram, aiohttp, sqlite3
- **Config:** `.env` (tokens), `user_settings.json` (user preferences)

## License

MIT
