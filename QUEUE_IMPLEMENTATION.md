# Реализация очереди отправки (Шаг 1)

## ✅ Список изменённых файлов

1. **config.py**
   - Добавлены конфиги: `QUEUE_MAX_SIZE`, `WORKER_COUNT`, `GLOBAL_RATE`, `PER_CHAT_RATE`

2. **services/telegram_service.py**
   - Добавлены глобальные переменные для очереди и rate limiters
   - Добавлена функция `enqueue_trade_alert()` - добавляет задачу в очередь
   - Добавлена функция `_queue_worker()` - воркер, обрабатывающий задачи
   - Добавлена функция `_per_chat_rate_limiter_wait()` - per-chat rate limiting
   - Добавлена функция `start_queue_workers()` - запуск воркеров
   - Добавлена функция `stop_queue_workers()` - graceful shutdown
   - Добавлена функция `_log_queue_stats()` - логирование статистики очереди
   - Добавлена функция `_log_mute_stats_periodic()` - периодическое логирование mute stats
   - Изменена функция `start_telegram()` - добавлен запуск очереди
   - Добавлены админ-команды: `/queue_status`, `/queue_clear`
   - Обновлена памятка `/admin` - добавлены команды очереди

3. **main.py**
   - Изменён импорт: добавлен `enqueue_trade_alert`, `stop_queue_workers`
   - Изменена функция `handle_trade()` - строка 468: `send_trade_alert` → `enqueue_trade_alert`
   - Изменена функция `main()` - добавлен вызов `stop_queue_workers()` в finally

4. **requirements.txt**
   - Добавлен `aiolimiter`

---

## 📊 Новые лог-строки

### При старте:
```
INFO - 📤 Queue system started: 3 workers, max_size=10000, global_rate=20/sec, per_chat_rate=0.5/sec
INFO - 📤 Queue worker 1 started
INFO - 📤 Queue worker 2 started
INFO - 📤 Queue worker 3 started
```

### При переполнении очереди:
```
WARNING - QUEUE_FULL dropped=1 queue_size=10000
```

### Статистика очереди (каждую минуту):
```
INFO - 📊 Queue stats: queue_size=X, sent_per_min=Y, dropped_per_min=Z, retryafter_per_min=W, worker_count=3
```

### Статистика мута (каждую минуту):
```
INFO - 📊 Mute stats: muted_count=X, retryafter_per_min=Y, top_muted=[(chat_id, seconds), ...]
```

### При ошибке в воркере:
```
ERROR - ❌ Queue worker 1 error sending to 123456789: <error message>
```

### При остановке:
```
INFO - 📤 Stopping queue workers...
INFO - 📤 Queue emptied, all tasks processed
INFO - 📤 Queue workers stopped
```

---

## 📋 Пример вывода /queue_status

```
**Queue Status:**

**Queue Size:** 42
**Dropped Total:** 5
**Sent Total:** 12345
**Error Total:** 3
**Workers:** 3/3
**Oldest Task Age:** N/A (queue doesn't expose item timestamps)
```

---

## 🔍 Как проверить в логах, что очередь работает

### 1. При старте бота:
Ищите строки:
```
📤 Queue system started: 3 workers, max_size=10000, global_rate=20/sec, per_chat_rate=0.5/sec
📤 Queue worker 1 started
📤 Queue worker 2 started
📤 Queue worker 3 started
```

### 2. При отправке сообщений:
- **До изменений**: в логах сразу появлялись сообщения об отправке
- **После изменений**: сообщения добавляются в очередь, затем обрабатываются воркерами
- Проверьте, что нет прямых вызовов `send_trade_alert` (кроме воркеров)

### 3. Статистика каждую минуту:
Ищите строки:
```
📊 Queue stats: queue_size=X, sent_per_min=Y, dropped_per_min=Z, retryafter_per_min=W, worker_count=3
```

### 4. Проверка rate limiting:
- `queue_size` должен быть небольшим (0-100) при нормальной нагрузке
- `sent_per_min` должен быть ≤ 20 * 60 = 1200 (глобальный лимит)
- Если `dropped_per_min > 0` - очередь переполняется

### 5. Проверка per-chat rate limiting:
- Для одного chat_id не должно быть более 1 сообщения в 2 секунды
- Проверьте логи: между отправками одному chat_id должна быть задержка ≥ 2 секунды

### 6. Проверка graceful shutdown:
При остановке бота (Ctrl+C или kill):
```
📤 Stopping queue workers...
📤 Queue emptied, all tasks processed
📤 Queue workers stopped
```

---

## ⚠️ Важно

1. **Установите aiolimiter**: `pip install aiolimiter` или `pip install -r requirements.txt`

2. **Проверьте конфиги в .env** (опционально):
   ```
   QUEUE_MAX_SIZE=10000
   WORKER_COUNT=3
   GLOBAL_RATE=20
   PER_CHAT_RATE=0.5
   ```

3. **Мониторинг**: Следите за `queue_size` - если он постоянно растёт, возможно нужно увеличить `WORKER_COUNT` или `GLOBAL_RATE`

---

## 🎯 Ожидаемое поведение

- ✅ Сообщения добавляются в очередь мгновенно (не блокируют обработку трейдов)
- ✅ Воркеры обрабатывают очередь с контролируемой скоростью
- ✅ Глобальный лимит: максимум 20 сообщений/сек
- ✅ Per-chat лимит: максимум 1 сообщение/2 сек для одного chat_id
- ✅ При переполнении очереди новые задачи отбрасываются с логом
- ✅ Воркеры не падают при ошибках отправки
- ✅ Graceful shutdown: очередь опустошается перед остановкой
