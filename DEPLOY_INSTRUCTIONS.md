# Инструкция по деплою Auto-Mute системы

## 1. Подготовка конфигурации

Добавьте в `.env` файл (или создайте, если его нет):

```bash
# Auto-mute configuration
RETRY_SHORT_MAX=10
MUTE_DURATIONS=3600,21600,86400
FAIL_STREAK_MUTE_THRESHOLD=3
HOTFIX_CHAT_ID=1580869819
HOTFIX_THRESHOLD=60
HOTFIX_MUTE=86400
```

## 2. Команды для деплоя на Vultr

### Шаг 1: Подключение к серверу
```bash
ssh root@your-vultr-ip
```

### Шаг 2: Переход в директорию проекта
```bash
cd /root/PolymarketWhales
```

### Шаг 3: Обновление кода (если используете git)
```bash
git pull origin master
# или просто обновите файлы вручную
```

### Шаг 4: Проверка конфигурации
```bash
# Убедитесь, что .env содержит нужные параметры
cat .env | grep -E "RETRY_SHORT_MAX|MUTE_DURATIONS|FAIL_STREAK|HOTFIX"
```

### Шаг 5: Создание директории для данных (если не существует)
```bash
mkdir -p data
```

### Шаг 6: Перезапуск бота
```bash
# Если используете systemd
sudo systemctl restart polymarket-bot

# Или если запускаете напрямую
pkill -f "python.*main.py"
nohup python3 main.py > bot_output.log 2>&1 &
```

### Шаг 7: Проверка логов (первые 5 минут)
```bash
# Следите за логами в реальном времени
tail -f bot_output.log | grep -E "MUTED|MUTED_SKIP|RETRY_AFTER|Mute stats|Loaded mute state"

# Или просто все логи
tail -f bot_output.log
```

## 3. Что вы должны увидеть в логах в первые 5 минут

### При старте:
```
INFO - Loaded mute state: X muted, Y streaks
INFO - Starting Telegram Bot Polling...
```

### Если chat_id 1580869819 получает TelegramRetryAfter:
```
WARNING - 🔇 MUTED chat_id=1580869819 retry_after=XXXXs mute_for=86400s (hotfix)
```

### При попытке отправить замученному пользователю:
```
INFO - 🔇 MUTED_SKIP chat_id=1580869819 seconds_left=XXXXX
```

### Статистика (каждую минуту):
```
INFO - 📊 Mute stats: muted_count=X, retryafter_per_min=Y, top_muted=[(1580869819, XXXXX), ...]
```

### Очистка памяти (каждый час):
```
INFO - 🧹 Cleaned up X old mute state entries
```

## 4. Проверка работы

### Проверка состояния мута:
```bash
# Через Telegram бота (от владельца)
/mute_status
```

### Проверка файла состояния:
```bash
cat data/mute_state.json
```

### Проверка, что 1580869819 замучен:
```bash
grep "1580869819" data/mute_state.json
```

## 5. Админ-команды

После деплоя вы можете использовать следующие команды в Telegram:

- `/mute_status` - показать статистику мута (top muted, muted_count, retryafter_per_min)
- `/unmute <chat_id>` - снять мут вручную
- `/mute <chat_id> [hours]` - замутить пользователя вручную (по умолчанию 1 час)

Примеры:
```
/mute_status
/unmute 1580869819
/mute 123456789 24
```

## 6. Мониторинг после деплоя

### Проверка, что RetryAfter упал:
```bash
# До деплоя должно быть много записей
grep -c "Flood limit for 1580869819" bot_output.log

# После деплоя должно быть только MUTED и MUTED_SKIP
grep "1580869819" bot_output.log | tail -20
```

### Проверка производительности:
```bash
# Считаем MUTED_SKIP (должно быть много)
grep -c "MUTED_SKIP" bot_output.log

# Считаем MUTED (должно быть несколько)
grep -c "MUTED chat_id" bot_output.log

# Проверяем, что нет длительных sleep
grep "sleep" bot_output.log | tail -10
```

## 7. Ожидаемый результат

После деплоя вы должны увидеть:

1. ✅ **Меньше Flood limit ошибок** - вместо сотен ошибок в минуту будут только MUTED и MUTED_SKIP
2. ✅ **chat_id 1580869819 замучен** - в `data/mute_state.json` и в логах
3. ✅ **Статистика каждую минуту** - "Mute stats" с информацией о замученных
4. ✅ **Быстрая работа бота** - нет блокировок на тысячи секунд
5. ✅ **Автоматическая очистка** - старые записи удаляются каждый час

## 8. Troubleshooting

### Если бот не запускается:
```bash
# Проверьте логи
tail -50 bot_output.log

# Проверьте синтаксис Python
python3 -m py_compile services/telegram_service.py config.py
```

### Если mute_state.json не создается:
```bash
# Проверьте права на директорию
ls -la data/
chmod 755 data/
```

### Если конфиг не загружается:
```bash
# Проверьте .env файл
cat .env

# Проверьте, что python-dotenv установлен
pip3 list | grep dotenv
```

## 9. Откат (если нужно)

Если что-то пошло не так:

```bash
# Остановите бота
sudo systemctl stop polymarket-bot
# или
pkill -f "python.*main.py"

# Удалите mute_state.json (опционально)
rm data/mute_state.json

# Откатите изменения в коде
git checkout HEAD~1 services/telegram_service.py config.py

# Запустите снова
sudo systemctl start polymarket-bot
```
