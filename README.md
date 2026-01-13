# Polymarket Whale Alerts 🐋

[🇷🇺 Русский](#-русский) | [🇬🇧 English](#-english)

---

## 🇷🇺 Русский

Telegram-бот для отслеживания крупных сделок ("китов") на [Polymarket](https://polymarket.com) в режиме реального времени.

### Возможности

- 📊 **Мониторинг сделок** от $500 до $100,000+
- 💰 **Фильтр по сумме** — выбери минимальный порог
- 📂 **Фильтр по категориям** — Крипто, Спорт, Остальное
- ⚖️ **Фильтр вероятности** — исключает почти решённые рынки (99.9%)
- 🔄 **Фильтр типов событий** — выбирай какие сделки отслеживать: BUY, SELL, SPLIT, MERGE, REDEEM
- 🕐 **Фильтр возраста кошелька** — фильтр по возрасту кошелька трейдера (в днях, мин-макс)
- 💼 **Фильтр количества позиций** — фильтр по количеству открытых позиций (мин-макс)
- 🌐 **Двуязычный интерфейс** — Русский / English
- 🔗 **Ссылки на профиль трейдера** и рынок
- 📈 **Расширенная аналитика:** Open PnL, активные позиции, возраст кошелька
- ⭐ **Избранное:** Сохранение интересных трейдеров с их текущим "уровнем" (🦐-🔥) + **🔔 Уведомления** (персональная подписка на трейдера)
- 🐦 **Twitter интеграция** — автоматическая публикация крупных сделок в Twitter/X

### Классификация объёмов

| Эмодзи | Уровень | Сумма |
|--------|---------|-------|
| 🔥 | Мега Кит | >$100,000 |
| ⚡ | Супер Кит | >$50,000 |
| 🐋 | Кит | >$25,000 |
| 🦈 | Акула | >$10,000 |
| 🐬 | Дельфин | >$5,000 |
| 🐟 | Рыба | >$2,000 |
| 🦐 | Креветка | >$500 |

### Новые метрики и точность данных

#### Аналитика трейдера
В каждом уведомлении теперь доступна статистика:
- 📊 **Open PnL**: Нереализованная прибыль/убыток по открытым позициям.
- 💼 **Open Positions**: Количество и стоимость активных (не закрытых) позиций.
- 🕐 **Wallet Age**: Возраст кошелька с момента первой активности.

#### Точный возраст кошелька (PolygonScan + Proxy)
Polymarket API часто обрезает историю сделок для активных трейдеров. Чтобы возраст определялся точно:
1. **Интеграция с блокчейном:** Если история короткая, бот проверяет данные напрямую в PolygonScan (требуется API Key).
2. **Поддержка Proxy-кошельков:** Бот умеет определять возраст даже для смарт-кошельков (Gnosis Safe / Proxy), проверяя переводы токенов ERC20/ERC1155.
3. **Кэширование:** Найденный возраст запоминается на **7 дней**, чтобы экономить лимиты API.

### Принцип работы

#### 1. Получение данных (PolymarketService)
- **Источник:** Бот использует публичный **Polymarket Data API** (`data-api.polymarket.com`).
- **Метод:** Бот **опрашивает (polling)** API каждые **3 секунды**.
- **Фильтрация на входе:** Запрашиваются только сделки типа `CASH` на сумму от **$10** (чтобы захватить даже мелкие части крупных ордеров).

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
  - **Вероятность:** Любая, 1%-99%, 5%-95%, 10%-90%
  - **Типы событий:** BUY, SELL, SPLIT, MERGE, REDEEM
  - **Возраст кошелька:** Фильтр по возрасту кошелька трейдера в днях (мин-макс диапазон, по умолчанию неограничено). ⚠️ Тестовый режим — возможны неточности.
  - **Количество позиций:** Фильтр по количеству открытых позиций (мин-макс диапазон, по умолчанию неограничено)
  - **Язык:** Русский или Английский
- **Интерфейс:**
  - `⚙️ Фильтры` — подменю со всеми настройками фильтров:
    - **Строка 1:** `💰 Сумма сделки`, `📂 Категории`, `⚖️ Вероятность`
    - **Строка 2:** `🔄 Типы событий`, `🕐 Возраст`, `💼 Позиции`
    - **Строка 3:** `⬅️ Назад`
  - **Настройка фильтров возраста и позиций:**
    - Выберите "🌐 Любой" для неограниченного фильтра
    - Или "📝 Настроить интервал" для ввода диапазона
    - Формат: `мин-макс` (например: `7-365`), `мин-` (от минимума), `-макс` (до максимума), или `0` (сбросить)
  - `▶️ Запустить / ⏸️ Остановить` — переключатель уведомлений
  - `⭐ Избранное` — список сохранённых трейдеров
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
- `/saved` — Список избранных китов
- `/about` — Информация о боте
- `/lang` — Переключение языка (🇬🇧 / 🇷🇺)
- `/hide` — Скрыть клавиатуру меню
- `/menu` — Показать клавиатуру меню

**Настройки фильтров:**
- `/amount` — Фильтр суммы
- `/categories` — Фильтр категорий
- `/probability` — Фильтр вероятности
- `/sides` — Фильтр типов событий
- `/age` — Фильтр возраста кошелька
- `/positions` — Фильтр открытых позиций
- `/back` — Назад в главное меню

#### 6. Twitter Интеграция
Бот может автоматически публиковать крупные сделки в Twitter/X:
- **Настройки:** Минимальная сумма, интервал между твитами, фильтры по вероятности и категориям
- **Фильтры типов событий:** Управление публикацией BUY, SELL, SPLIT, MERGE, REDEEM (по умолчанию только BUY)
- **Защита от блокировок:** Минимальный интервал 25 минут, пауза 6 часов при 403 ошибке
- **Форматирование:** Английский язык, без эмодзи в названиях уровней, специальное форматирование
- **Команды:** 
  - `/twitter` — все настройки и статус
  - `/twitter_on`, `/twitter_off` — вкл/выкл постинг
  - `/twitter_min 25000` — минимум в долларах
  - `/twitter_interval 25` — интервал между твитами (минуты)
  - `/twitter_prob 1_99` — фильтр вероятности
  - `/twitter_sell on/off` — SELL сигналы
  - `/twitter_split on/off` — SPLIT сигналы
  - `/twitter_merge on/off` — MERGE сигналы
  - `/twitter_redeem on/off` — REDEEM сигналы
  - `/twitter_cat crypto on/off` — фильтры категорий

#### 7. Администрирование
- `/stats` — статистика бота (только для владельца)
- `/users` — список пользователей
- `/broadcast <сообщение>` — рассылка всем пользователям
- `/cache` — просмотр кэша возраста кошельков
- `/report` — полный отчет о системе
- `/admin` — памятка со всеми административными командами

#### 8. Архитектура "Избранного" (Saved Traders)
Реализация списка избранных трейдеров оптимизирована для работы с ограничениями Telegram API:
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

### Установка

```bash
git clone https://github.com/ahdpe/PolymarketWhales.git
cd PolymarketWhales
pip install -r requirements.txt
```

Создайте `.env` файл:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
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

### Features

- 📊 **Trade monitoring** from $500 to $100,000+
- 💰 **Amount filter** — choose minimum threshold
- 📂 **Category filter** — Crypto, Sports, Other
- ⚖️ **Probability filter** — excludes near-resolved markets (99.9%)
- 🔄 **Event type filter** — choose which trades to track: BUY, SELL, SPLIT, MERGE, REDEEM
- 🕐 **Wallet age filter** — filter by trader wallet age (in days, min-max range)
- 💼 **Open positions filter** — filter by number of open positions (min-max range)
- 🌐 **Bilingual interface** — Russian / English
- 🔗 **Links to trader profile** and market
- 📈 **Advanced Analytics:** Open PnL, Active Positions, Wallet Age
- ⭐ **Favorites:** Save interesting traders with their current "level" (🦐-🔥) + **🔔 Notifications** (subscribe to specific trader)
- 🐦 **Twitter integration** — automatic posting of large trades to Twitter/X

### Volume Classification

| Emoji | Level | Amount |
|-------|-------|--------|
| 🔥 | Mega Whale | >$100,000 |
| ⚡ | Super Whale | >$50,000 |
| 🐋 | Whale | >$25,000 |
| 🦈 | Shark | >$10,000 |
| 🐬 | Dolphin | >$5,000 |
| 🐟 | Fish | >$2,000 |
| 🦐 | Shrimp | >$500 |

### New Metrics & Data Accuracy

#### Trader Analytics
Every alert includes detailed stats:
- 📊 **Open PnL**: Floating profit/loss on open positions.
- 💼 **Open Positions**: Count and total value of active positions.
- 🕐 **Wallet Age**: Time since the very first activity.

#### Accurate Wallet Age (PolygonScan + Proxy)
Polymarket API often truncates activity history for high-frequency traders. For accuracy:
1. **Blockchain Integration:** If history seems short, the bot queries PolygonScan directly (requires API Key).
2. **Proxy Wallet Support:** Correctly identifies age even for Smart Wallets (Gnosis/Proxy) by checking ERC20/ERC1155 transfers.
3. **Caching:** Wallet age is cached for **7 days** to minimize API usage.

### How It Works

#### 1. Data Fetching (PolymarketService)
- **Source:** Uses public **Polymarket Data API** (`data-api.polymarket.com`).
- **Method:** Polls the API every **3 seconds**.
- **Input filtering:** Only `CASH` type trades from **$10** are requested.

#### 2. Processing and Aggregation
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

#### 3. Deduplication and Persistence
- **Database:** Local **SQLite** (`data/trades.db`) stores processed trade keys.
- **Cache:** 10,000 most recent trades in RAM.
- **Cleanup:** Records > 72h are deleted.

#### 4. Telegram Bot (TelegramService)
- **Filters:** Amount, Category, Probability, Event Types (BUY/SELL/SPLIT/MERGE/REDEEM), Wallet Age, Open Positions, Language.
- **Interface:** Compact menu with "⚙️ Filters" submenu for all filter settings:
  - **Row 1:** Amount, Categories, Probability
  - **Row 2:** Event Types, Wallet Age, Open Positions
  - **Row 3:** Back
- **Filter Details:**
  - **Wallet Age:** Filter by trader wallet age in days (min-max range, default: unlimited). ⚠️ Beta mode - may have inaccuracies.
    - Format: `min-max` (e.g., `7-365`), `min-` (from minimum), `-max` (up to maximum), or `0` (reset)
  - **Open Positions:** Filter by number of open positions (min-max range, default: unlimited).
    - Format: `min-max` (e.g., `5-50`), `min-` (from minimum), `-max` (up to maximum), or `0` (reset)
- **Alerts:** Rich messages with emojis, links, and trader stats:
  - Color-coded trade types: 🟢 BUY Yes, 🔴 BUY No, 🔵 SELL, ⚪ SPLIT, ↔️ MERGE, 🟣 REDEEM

#### 5. Commands

**Main:**
- `/start` — Start bot
- `/stop` — Toggle alerts ON/OFF (same as ▶️/⏸️ button)
- `/filters` — Filter settings menu
- `/saved` — Saved whales list
- `/about` — About bot info
- `/lang` — Switch language (🇬🇧 / 🇷🇺)
- `/hide` — Hide menu keyboard
- `/menu` — Show menu keyboard

**Filter Settings:**
- `/amount` — Amount filter
- `/categories` — Category filter
- `/probability` — Probability filter
- `/sides` — Event types filter
- `/age` — Wallet age filter
- `/positions` — Open positions filter
- `/back` — Back to main menu

#### 6. Twitter Integration
The bot can automatically post large trades to Twitter/X:
- **Settings:** Minimum amount, tweet interval, probability and category filters
- **Event type filters:** Control posting of BUY, SELL, SPLIT, MERGE, REDEEM (only BUY enabled by default)
- **Anti-spam protection:** 25-minute minimum interval, 6-hour pause on 403 errors
- **Formatting:** English only, no emojis in tier names, special formatting rules
- **Commands:**
  - `/twitter` — all settings and status
  - `/twitter_on`, `/twitter_off` — enable/disable posting
  - `/twitter_min 25000` — minimum amount in USD
  - `/twitter_interval 25` — interval between tweets (minutes)
  - `/twitter_prob 1_99` — probability filter
  - `/twitter_sell on/off` — SELL signals
  - `/twitter_split on/off` — SPLIT signals
  - `/twitter_merge on/off` — MERGE signals
  - `/twitter_redeem on/off` — REDEEM signals
  - `/twitter_cat crypto on/off` — category filters

#### 7. Administration
- `/stats` — bot statistics (owner only)
- `/users` — user list
- `/broadcast <message>` — broadcast to all users
- `/cache` — inspect wallet age cache
- `/report` — full system status report
- `/admin` — admin commands cheatsheet

#### 8. Favorites Architecture (Saved Traders)
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

### Installation

```bash
git clone https://github.com/ahdpe/PolymarketWhales.git
cd PolymarketWhales
pip install -r requirements.txt
```

Create `.env` file:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
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
