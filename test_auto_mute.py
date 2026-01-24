#!/usr/bin/env python3
"""
Тестовый скрипт для проверки auto-mute логики.
Симулирует различные сценарии ошибок и проверяет поведение системы.
"""

import asyncio
import logging
import sys
import time
from unittest.mock import AsyncMock, patch
from aiogram.exceptions import TelegramRetryAfter

# Настройка логирования для тестов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Импортируем функции после настройки логирования
sys.path.insert(0, '.')

# Импортируем модуль telegram_service
from services.telegram_service import (
    send_trade_alert,
    muted_until,
    fail_streak,
    mute_level,
    last_fail_reason,
    _is_muted,
    _apply_mute
)

# Тестовый chat_id
TEST_CHAT_ID = 999999999

def reset_test_state():
    """Сброс состояния для тестового chat_id."""
    muted_until.pop(TEST_CHAT_ID, None)
    fail_streak.pop(TEST_CHAT_ID, None)
    mute_level.pop(TEST_CHAT_ID, None)
    last_fail_reason.pop(TEST_CHAT_ID, None)
    print(f"\n{'='*80}")
    print(f"🧹 Сброс состояния для chat_id={TEST_CHAT_ID}")
    print(f"{'='*80}\n")

async def test_scenario_1_short_retry():
    """Тест 1: TelegramRetryAfter(retry_after=5) - короткий ретрай."""
    print("\n" + "="*80)
    print("ТЕСТ 1: TelegramRetryAfter(retry_after=5) - короткий ретрай")
    print("="*80)
    reset_test_state()
    
    call_count = 0
    
    async def mock_send_message(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Первый вызов - ошибка с retry_after=5
            raise TelegramRetryAfter(method='sendMessage', message='Flood control', retry_after=5)
        # Второй вызов - успех
        return AsyncMock()
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message):
        start_time = time.time()
        await send_trade_alert(TEST_CHAT_ID, "Test message 1")
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Время выполнения: {elapsed:.2f} секунд")
        print(f"📊 Состояние после теста:")
        print(f"   - muted_until: {muted_until.get(TEST_CHAT_ID, 'None')}")
        print(f"   - fail_streak: {fail_streak.get(TEST_CHAT_ID, 0)}")
        print(f"   - mute_level: {mute_level.get(TEST_CHAT_ID, 0)}")
        
        # Ожидаемое поведение:
        # 1. RETRY_AFTER short с retry_after=5
        # 2. sleep(5) - около 5 секунд
        # 3. Успешная отправка
        # 4. Нет мута
        assert elapsed >= 4.5 and elapsed <= 6.0, f"Ожидалось ~5 секунд, получено {elapsed:.2f}"
        assert TEST_CHAT_ID not in muted_until, "Не должно быть мута для короткого retry_after"
        print("✅ ТЕСТ 1 ПРОЙДЕН")

async def test_scenario_2_long_retry():
    """Тест 2: TelegramRetryAfter(retry_after=7000) - длинный ретрай, должен замутить."""
    print("\n" + "="*80)
    print("ТЕСТ 2: TelegramRetryAfter(retry_after=7000) - длинный ретрай → мут")
    print("="*80)
    reset_test_state()
    
    async def mock_send_message(*args, **kwargs):
        # Сразу ошибка с retry_after=7000
        raise TelegramRetryAfter(method='sendMessage', message='Flood control', retry_after=7000)
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message):
        start_time = time.time()
        await send_trade_alert(TEST_CHAT_ID, "Test message 2")
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Время выполнения: {elapsed:.2f} секунд")
        print(f"📊 Состояние после теста:")
        print(f"   - muted_until: {muted_until.get(TEST_CHAT_ID, 'None')}")
        if TEST_CHAT_ID in muted_until:
            seconds_left = muted_until[TEST_CHAT_ID] - time.time()
            print(f"   - seconds_left: {int(seconds_left)}")
        print(f"   - fail_streak: {fail_streak.get(TEST_CHAT_ID, 0)}")
        print(f"   - mute_level: {mute_level.get(TEST_CHAT_ID, 0)}")
        
        # Ожидаемое поведение:
        # 1. MUTED с retry_after=7000
        # 2. НЕТ sleep(7000) - сразу возврат
        # 3. Мут применен (1 час для первого уровня)
        assert elapsed < 1.0, f"Не должно быть долгого ожидания, получено {elapsed:.2f} секунд"
        assert TEST_CHAT_ID in muted_until, "Должен быть применен мут"
        assert muted_until[TEST_CHAT_ID] > time.time(), "Мут должен быть в будущем"
        print("✅ ТЕСТ 2 ПРОЙДЕН")

async def test_scenario_3_consecutive_failures():
    """Тест 3: 3 подряд обычные ошибки отправки → мут."""
    print("\n" + "="*80)
    print("ТЕСТ 3: 3 подряд обычные ошибки отправки → мут")
    print("="*80)
    reset_test_state()
    
    call_count = 0
    
    async def mock_send_message(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Всегда ошибка
        raise Exception(f"Test error {call_count}")
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message):
        # Первая попытка - streak=1
        await send_trade_alert(TEST_CHAT_ID, "Test message 3-1")
        print(f"   После 1-й ошибки: streak={fail_streak.get(TEST_CHAT_ID, 0)}, muted={TEST_CHAT_ID in muted_until}")
        
        # Вторая попытка - streak=2
        await send_trade_alert(TEST_CHAT_ID, "Test message 3-2")
        print(f"   После 2-й ошибки: streak={fail_streak.get(TEST_CHAT_ID, 0)}, muted={TEST_CHAT_ID in muted_until}")
        
        # Третья попытка - streak=3 → мут
        start_time = time.time()
        await send_trade_alert(TEST_CHAT_ID, "Test message 3-3")
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Время выполнения 3-й попытки: {elapsed:.2f} секунд")
        print(f"📊 Состояние после теста:")
        print(f"   - muted_until: {muted_until.get(TEST_CHAT_ID, 'None')}")
        if TEST_CHAT_ID in muted_until:
            seconds_left = muted_until[TEST_CHAT_ID] - time.time()
            print(f"   - seconds_left: {int(seconds_left)}")
        print(f"   - fail_streak: {fail_streak.get(TEST_CHAT_ID, 0)}")
        print(f"   - mute_level: {mute_level.get(TEST_CHAT_ID, 0)}")
        print(f"   - last_fail_reason: {last_fail_reason.get(TEST_CHAT_ID, 'None')}")
        
        # Ожидаемое поведение:
        # 1. После 3-й ошибки должен быть применен мут
        # 2. Нет долгого ожидания
        assert elapsed < 5.0, f"Не должно быть долгого ожидания, получено {elapsed:.2f} секунд"
        assert TEST_CHAT_ID in muted_until, "Должен быть применен мут после 3 ошибок"
        assert fail_streak.get(TEST_CHAT_ID, 0) == 3, "Streak должен быть 3"
        print("✅ ТЕСТ 3 ПРОЙДЕН")

async def test_scenario_4_mute_skip():
    """Тест 4: retry_after=7000 → мут → повторная отправка → MUTED_SKIP."""
    print("\n" + "="*80)
    print("ТЕСТ 4: retry_after=7000 → мут → повторная отправка → MUTED_SKIP")
    print("="*80)
    reset_test_state()
    
    # Шаг 1: Создаем мут через retry_after=7000
    async def mock_send_message_1(*args, **kwargs):
        raise TelegramRetryAfter(method='sendMessage', message='Flood control', retry_after=7000)
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message_1):
        await send_trade_alert(TEST_CHAT_ID, "Test message 4-1")
        print(f"   После retry_after=7000: muted={TEST_CHAT_ID in muted_until}")
        assert TEST_CHAT_ID in muted_until, "Должен быть мут"
    
    # Шаг 2: Попытка отправить в период мута
    call_count = 0
    async def mock_send_message_2(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return AsyncMock()
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message_2):
        start_time = time.time()
        await send_trade_alert(TEST_CHAT_ID, "Test message 4-2")
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Время выполнения попытки в период мута: {elapsed:.2f} секунд")
        print(f"📊 Состояние:")
        print(f"   - muted_until: {muted_until.get(TEST_CHAT_ID, 'None')}")
        if TEST_CHAT_ID in muted_until:
            seconds_left = muted_until[TEST_CHAT_ID] - time.time()
            print(f"   - seconds_left: {int(seconds_left)}")
        print(f"   - call_count (bot.send_message): {call_count}")
        
        # Ожидаемое поведение:
        # 1. MUTED_SKIP в логах
        # 2. bot.send_message НЕ вызывается (call_count=0)
        # 3. Нет долгого ожидания
        assert elapsed < 0.1, f"Должен быть мгновенный возврат, получено {elapsed:.2f} секунд"
        assert call_count == 0, "bot.send_message не должен вызываться при муте"
        print("✅ ТЕСТ 4 ПРОЙДЕН")

async def test_scenario_5_mute_expiry():
    """Тест 5: Истечение мута → попытка отправки снова."""
    print("\n" + "="*80)
    print("ТЕСТ 5: Истечение мута → попытка отправки снова")
    print("="*80)
    
    # Создаем мут с коротким временем (1 секунда для теста)
    _apply_mute(TEST_CHAT_ID, "test_mute", mute_seconds=1)
    print(f"   Применен мут на 1 секунду")
    
    # Проверяем, что мут активен
    is_muted, seconds_left = _is_muted(TEST_CHAT_ID)
    assert is_muted, "Мут должен быть активен"
    print(f"   Мут активен, seconds_left={int(seconds_left)}")
    
    # Ждем истечения мута
    await asyncio.sleep(1.5)
    
    # Проверяем, что мут истек
    is_muted, seconds_left = _is_muted(TEST_CHAT_ID)
    assert not is_muted, "Мут должен истечь"
    print(f"   Мут истек, seconds_left={seconds_left}")
    
    # Попытка отправки после истечения мута
    call_count = 0
    async def mock_send_message(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return AsyncMock()
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message):
        await send_trade_alert(TEST_CHAT_ID, "Test message 5")
        print(f"   После истечения мута: call_count={call_count}")
        
        # Ожидаемое поведение:
        # 1. bot.send_message должен быть вызван
        # 2. Нет MUTED_SKIP
        assert call_count == 1, "bot.send_message должен быть вызван после истечения мута"
        print("✅ ТЕСТ 5 ПРОЙДЕН")

async def test_scenario_6_hotfix_1580869819():
    """Тест 6: Горячая заплатка для chat_id 1580869819."""
    print("\n" + "="*80)
    print("ТЕСТ 6: Горячая заплатка для chat_id 1580869819")
    print("="*80)
    reset_test_state()
    
    HOTFIX_CHAT_ID = 1580869819
    
    async def mock_send_message(*args, **kwargs):
        raise TelegramRetryAfter(method='sendMessage', message='Flood control', retry_after=7000)
    
    with patch('services.telegram_service.bot.send_message', side_effect=mock_send_message):
        start_time = time.time()
        await send_trade_alert(HOTFIX_CHAT_ID, "Test message 6")
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Время выполнения: {elapsed:.2f} секунд")
        print(f"📊 Состояние после теста:")
        print(f"   - muted_until: {muted_until.get(HOTFIX_CHAT_ID, 'None')}")
        if HOTFIX_CHAT_ID in muted_until:
            seconds_left = muted_until[HOTFIX_CHAT_ID] - time.time()
            print(f"   - seconds_left: {int(seconds_left)} (ожидается ~86400)")
        
        # Ожидаемое поведение:
        # 1. Мут на 24 часа (86400 секунд) сразу
        # 2. Нет долгого ожидания
        assert elapsed < 1.0, f"Не должно быть долгого ожидания, получено {elapsed:.2f} секунд"
        assert HOTFIX_CHAT_ID in muted_until, "Должен быть применен мут"
        seconds_left = muted_until[HOTFIX_CHAT_ID] - time.time()
        assert seconds_left > 86000 and seconds_left < 86500, f"Ожидался мут на 24 часа, получено {seconds_left} секунд"
        print("✅ ТЕСТ 6 ПРОЙДЕН")

async def main():
    """Запуск всех тестов."""
    print("\n" + "="*80)
    print("🧪 ЗАПУСК ТЕСТОВ AUTO-MUTE ЛОГИКИ")
    print("="*80)
    
    try:
        await test_scenario_1_short_retry()
        await asyncio.sleep(0.5)
        
        await test_scenario_2_long_retry()
        await asyncio.sleep(0.5)
        
        await test_scenario_3_consecutive_failures()
        await asyncio.sleep(0.5)
        
        await test_scenario_4_mute_skip()
        await asyncio.sleep(0.5)
        
        await test_scenario_5_mute_expiry()
        await asyncio.sleep(0.5)
        
        await test_scenario_6_hotfix_1580869819()
        
        print("\n" + "="*80)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*80)
        
    except AssertionError as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
