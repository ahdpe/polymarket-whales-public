# Чек-лист теста очереди на проде

## 📋 Что проверить в логах в первые 5 минут

### 1. При старте бота (первые секунды):

**Успешный запуск с aiolimiter:**
```
INFO - ✅ aiolimiter version: X.X.X
INFO - 📤 Queue system started: 3 workers, max_size=10000, global_rate=20/sec, per_chat_rate=0.5/sec
INFO - 📤 Queue worker 1 started
INFO - 📤 Queue worker 2 started
INFO - 📤 Queue worker 3 started
```

**ИЛИ fallback (если aiolimiter не установлен):**
```
ERROR - ❌ CRITICAL: aiolimiter not installed! Queue system disabled.
ERROR - Install with: pip install aiolimiter
ERROR - Falling back to direct send (no rate limiting).
```

### 2. При поступлении трейдов (первые 1-2 минуты):

**Проверка, что сообщения добавляются в очередь:**
- В логах НЕ должно быть прямых вызовов `send_trade_alert` (кроме воркеров)
- Должны появляться логи воркеров: `📤 Queue worker X started`

**Проверка обработки:**
- Сообщения должны доставляться пользователям
- В логах могут появляться обычные логи отправки (MUTED_SKIP, SEND_OK, etc.)

### 3. Статистика очереди (через 1 минуту после старта):

**Должна появиться строка:**
```
INFO - 📊 Queue stats: queue_size=X, oldest_age_sec=Y, avg_age_sec=Z, sent_per_min=W, dropped_per_min=V, retryafter_per_min=U, worker_count=3
```

**ИЛИ с предупреждениями:**
```
INFO - 📊 Queue stats: queue_size=X, oldest_age_sec=Y, ..., warnings=[WARN_QUEUE_LAG]
INFO - 📊 Queue stats: queue_size=X, ..., dropped_per_min=5, ..., warnings=[WARN_QUEUE_DROPS]
```

**Проверьте:**
- `queue_size` - должно быть небольшим (0-100) при нормальной нагрузке
- `oldest_age_sec` - обычный режим: < 20 секунд; пик: допускается до 120 секунд, главное чтобы затем снижалось
- `sent_per_min` - должно быть > 0, если были трейды
- `worker_count=3` - все воркеры работают
- `warnings` - если есть, проверьте причину (WARN_QUEUE_LAG или WARN_QUEUE_DROPS)

### 4. Статистика мута (через 1 минуту):

**Должна появиться строка:**
```
INFO - 📊 Mute stats: muted_count=X, retryafter_per_min=Y, top_muted=[...]
```

### 5. Проверка rate limiting (первые 2-3 минуты):

**Глобальный лимит:**
- `sent_per_min` в статистике должно быть ≤ 1200 (20 msg/sec * 60)
- Если больше - лимит не работает

**Per-chat лимит:**
- Для одного chat_id не должно быть более 1 сообщения в 2 секунды
- Проверьте логи: между отправками одному chat_id должна быть задержка ≥ 2 секунды

### 6. Проверка переполнения (если очередь заполнилась):

**Должна появиться строка:**
```
WARNING - QUEUE_FULL dropped=1 queue_size=10000
```

**Если это происходит часто:**
- Увеличьте `WORKER_COUNT` или `GLOBAL_RATE`
- Проверьте, что воркеры работают (`worker_count=3`)

---

## 📱 Команды в Telegram для проверки

### 1. `/queue_status`

**Ожидаемый вывод:**
```
**Queue Status:**

**Queue Size:** X
**Dropped Total:** Y
**Sent Total:** Z
**Error Total:** W
**Workers:** 3/3
**Oldest Task Age:** Xs (avg: Ys)
```

**Проверьте:**
- `Queue Size` - должно быть небольшим (< 100)
- `Oldest Task Age` - должно быть небольшим (< 10 секунд)
- `Workers: 3/3` - все воркеры работают
- `Sent Total` - должно увеличиваться при поступлении трейдов

### 2. `/mute_status`

**Ожидаемый вывод:**
```
**Mute Statistics:**

**Currently Muted:** X
**RetryAfter (last min):** Y

**Top Muted Users:**
• `chat_id`: Xh Ym left, until YYYY-MM-DD HH:MM:SS, reason=..., streak=..., level=...
```

**Проверьте:**
- Статистика отображается корректно
- Если есть замученные пользователи - они показываются

### 3. `/admin`

**Проверьте:**
- В секции "📤 **Queue:**" есть команды:
  - `/queue_status` — статистика очереди
  - `/queue_clear` — очистить очередь

---

## ✅ Критерии успешного теста

1. ✅ **Очередь запустилась:**
   - В логах есть `📤 Queue system started`
   - Все 3 воркера запущены

2. ✅ **Сообщения доставляются:**
   - Пользователи получают алерты
   - `sent_total` в `/queue_status` увеличивается

3. ✅ **Rate limiting работает:**
   - `sent_per_min` ≤ 1200
   - Между отправками одному chat_id ≥ 2 секунды

4. ✅ **Статистика логируется:**
   - Каждую минуту появляется `📊 Queue stats` с `oldest_age_sec`
   - Каждую минуту появляется `📊 Mute stats`

5. ✅ **Админ-команды работают:**
   - `/queue_status` показывает корректные данные
   - `/mute_status` работает
   - `/admin` содержит команды очереди

6. ✅ **Задержка приемлемая:**
   - Обычный режим: `oldest_age_sec` < 20 секунд
   - Пик: допускается до 120 секунд, главное чтобы затем снижалось
   - `queue_size` < 100 при нормальной нагрузке
   - Нет предупреждений `WARN_QUEUE_LAG` (3 минуты подряд с lag > 120s)
   - Нет предупреждений `WARN_QUEUE_DROPS` (dropped_per_min > 0)

---

## ⚠️ Проблемы и решения

### Проблема: `oldest_age_sec` всегда None
**Причина:** Очередь пустая или oldest tracking не работает
**Решение:** Проверьте, что трейды поступают и очередь не пустая

### Проблема: `WARN_QUEUE_LAG` появляется
**Причина:** `oldest_age_sec > 120s` в течение 3 минут подряд
**Решение:** Увеличьте `WORKER_COUNT` или `GLOBAL_RATE`, проверьте что воркеры работают

### Проблема: `WARN_QUEUE_DROPS` появляется
**Причина:** `dropped_per_min > 0` - очередь переполняется
**Решение:** Увеличьте `QUEUE_MAX_SIZE`, `WORKER_COUNT` или `GLOBAL_RATE`

### Проблема: `queue_size` постоянно растёт
**Причина:** Воркеры не успевают обрабатывать или rate limit слишком строгий
**Решение:** Увеличьте `WORKER_COUNT` или `GLOBAL_RATE`

### Проблема: Сообщения не доставляются
**Причина:** Воркеры не работают или очередь отключена
**Решение:** Проверьте логи на ошибки воркеров, проверьте что `_queue_enabled = True`

### Проблема: `aiolimiter not installed`
**Причина:** Зависимость не установлена
**Решение:** `pip install aiolimiter` или `pip install -r requirements.txt`

---

## 📝 Пример успешного лога (первые 5 минут)

```
INFO - ✅ aiolimiter version: 1.1.0
INFO - 📤 Queue system started: 3 workers, max_size=10000, global_rate=20/sec, per_chat_rate=0.5/sec
INFO - 📤 Queue worker 1 started
INFO - 📤 Queue worker 2 started
INFO - 📤 Queue worker 3 started
...
INFO - 📊 Queue stats: queue_size=5, oldest_age_sec=2, avg_age_sec=1, sent_per_min=45, dropped_per_min=0, retryafter_per_min=0, worker_count=3
INFO - 📊 Mute stats: muted_count=1, retryafter_per_min=0, top_muted=[(1580869819, 81822)]
...
INFO - 📊 Queue stats: queue_size=3, oldest_age_sec=1, avg_age_sec=0, sent_per_min=52, dropped_per_min=0, retryafter_per_min=0, worker_count=3

**Пример с предупреждением:**
INFO - 📊 Queue stats: queue_size=150, oldest_age_sec=125, avg_age_sec=62, sent_per_min=1200, dropped_per_min=0, retryafter_per_min=0, worker_count=3, warnings=[WARN_QUEUE_LAG]
```
