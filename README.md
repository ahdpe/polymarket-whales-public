# Polymarket Whales Bot 🐋

[🇷🇺 Русский](#-русский) | [🇬🇧 English](#-english)

---

## 🇷🇺 Русский

Telegram-бот для отслеживания крупных сделок ("китов") на [Polymarket](https://polymarket.com) в режиме реального времени.

### Возможности

- 📊 **Мониторинг сделок** от $500 до $100,000+
- 💰 **Фильтр по сумме** — выбери минимальный порог
- 📂 **Фильтр по категориям** — Крипто, Спорт, Остальное
- ⚖️ **Фильтр вероятности** — исключает почти решённые рынки (99.9%)
- 🌐 **Двуязычный интерфейс** — Русский / English
- 🔗 **Ссылки на профиль трейдера** и рынок
- 📈 **Расширенная аналитика:** Open PnL, активные позиции, возраст кошелька

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
  - Сторона (BUY/SELL)
  - Исход (YES/NO/Outcome Index)
- **Окно времени:** Сделки собираются в течение **60 секунд** с момента первой части.
- **Порог срабатывания:** Если сумма серии превышает **$500**, она считается значимой и передается на отправку.

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
  - **Язык:** Русский или Английский
- **Интерфейс:**
  - `💰 Сумма сделки` — выбор минимального порога
  - `📂 Категории` — выбор категорий рынков
  - `⚖️ Вероятность` — фильтр по вероятности
  - `▶️ Запустить / ⏸️ Остановить` — переключатель уведомлений
- **Уведомления:** Присылает сообщение с:
  - Эмодзи категории (💰, ⚽, 📌) и названием рынка
  - Типом сделки (Покупка/Продажа) и ценой
  - Суммой сделки (для серий пишет "Series X fills")
  - Уровнем "кита" и ссылкой на трейдера
  - Статистикой (PnL, Pos, Age)

#### 5. Администрирование
- `/stats` — статистика бота (только для владельца)
- `/users` — список пользователей
- `/broadcast <сообщение>` — рассылка всем пользователям
- `/cache` — просмотр кэша возраста кошельков
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
```

Запуск:
```bash
python main.py
```

---

## 🇬🇧 English

Telegram bot for real-time tracking of large trades ("whales") on [Polymarket](https://polymarket.com).

### Features

- 📊 **Trade monitoring** from $500 to $100,000+
- 💰 **Amount filter** — choose minimum threshold
- 📂 **Category filter** — Crypto, Sports, Other
- ⚖️ **Probability filter** — excludes near-resolved markets (99.9%)
- 🌐 **Bilingual interface** — Russian / English
- 🔗 **Links to trader profile** and market
- 📈 **Advanced Analytics:** Open PnL, Active Positions, Wallet Age

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
- **Grouping:** Same wallet, market, side, outcome.
- **Time window:** **60 seconds** aggregation window.
- **Trigger:** Series sum > **$500**.

#### 3. Deduplication and Persistence
- **Database:** Local **SQLite** (`data/trades.db`) stores processed trade keys.
- **Cache:** 10,000 most recent trades in RAM.
- **Cleanup:** Records > 72h are deleted.

#### 4. Telegram Bot (TelegramService)
- **Filters:** Amount, Category, Probability, Language.
- **Interface:** Persistent menu for easy configuration.
- **Alerts:** Rich messages with emojis, links, and trader stats.

#### 5. Administration
- `/stats` — bot statistics (owner only)
- `/users` — user list
- `/broadcast <message>` — broadcast to all users
- `/cache` — inspect wallet age cache
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
```

Run:
```bash
python main.py
```

---

## Tech Stack

- **Language:** Python 3.10+
- **Libraries:** aiogram, aiohttp, sqlite3
- **Config:** `.env` (tokens), `user_settings.json` (user preferences)

## License

MIT
