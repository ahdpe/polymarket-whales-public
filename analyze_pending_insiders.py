#!/usr/bin/env python3
"""
Анализ скопившихся позиций инсайдеров и проверка, почему они не публикуются.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Setup path
sys.path.append(os.getcwd())

from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage
from core.categories import detect_category

def format_number(num):
    """Форматирование чисел для вывода."""
    if num is None:
        return "N/A"
    if isinstance(num, float):
        return f"{num:,.0f}" if num >= 1000 else f"{num:.1f}"
    return str(num)

def check_filter_reason(service: InsiderAlertsService, scenario: str, market_id: str, category: str) -> Dict[str, Any]:
    """
    Детальная проверка, почему позиция не проходит фильтры.
    Возвращает словарь с результатами проверки каждого фильтра.
    """
    result = {
        'market_id': market_id,
        'scenario': scenario,
        'category': category,
        'passed': False,
        'reasons': [],
        'details': {}
    }
    
    settings = service.settings
    
    # 1. Проверка: включен ли глобально сервис
    if not service.is_enabled():
        result['reasons'].append("❌ Глобально отключен (enabled=false)")
        return result
    
    # 2. Проверка: включен ли сценарий
    scenario_enabled_key = f"{scenario.lower()}_enabled"
    if settings.get(scenario_enabled_key, 'false').lower() != 'true':
        result['reasons'].append(f"❌ Сценарий {scenario} отключен")
        return result
    
    # 3. Проверка категории
    cat_key = f"cat_{category}_enabled"
    if settings.get(cat_key, 'true').lower() != 'true':
        result['reasons'].append(f"❌ Категория '{category}' отключена")
        return result
    
    # 4. Получение параметров сценария
    if scenario == 'CLUSTER':
        interval = float(settings.get('cluster_interval_hours', '2'))
        max_age = float(settings.get('cluster_wallet_age_hours', '24'))
        min_usd = float(settings.get('cluster_min_usd', '5000'))
        min_total = float(settings.get('cluster_min_total_usd', '10000'))
        min_wallets = int(settings.get('cluster_min_wallets', '4'))
        min_dir = float(settings.get('cluster_min_direction_pct', '75'))
        max_pos = int(settings.get('cluster_max_positions', '3'))
        side_filter = settings.get('cluster_side', 'both').lower()
        cooldown = int(settings.get('cooldown_hours', '24'))
        
    elif scenario == 'BURST':
        interval = float(settings.get('burst_interval_hours', '1'))
        max_age = float(settings.get('burst_wallet_age_hours', '72'))
        min_usd = float(settings.get('burst_min_usd', '1000'))
        min_total = float(settings.get('burst_min_total_usd', '5000'))
        min_wallets = int(settings.get('burst_min_wallets', '8'))
        min_dir = float(settings.get('burst_min_direction_pct', '70'))
        max_pos = int(settings.get('burst_max_positions', '3'))
        side_filter = 'both'  # BURST не имеет side фильтра
        cooldown = int(settings.get('cooldown_hours', '24'))
        
    elif scenario == 'ACCUMULATION':
        interval_days = float(settings.get('accumulation_interval_days', '14'))
        interval = interval_days * 24  # Конвертируем дни в часы
        max_age = float(settings.get('accumulation_wallet_age_hours', '48'))
        min_usd = float(settings.get('accumulation_min_usd', '10000'))
        min_total = float(settings.get('accumulation_min_total_usd', '50000'))
        min_wallets = int(settings.get('accumulation_min_wallets', '3'))
        min_dir = float(settings.get('accumulation_min_direction_pct', '70'))
        max_pos = int(settings.get('accumulation_max_positions', '3'))
        side_filter = 'both'
        cooldown = int(settings.get('cooldown_hours', '24'))
    else:
        result['reasons'].append(f"❌ Неизвестный сценарий: {scenario}")
        return result
    
    # 5. Получение трейдов
    trades = alerts_storage.get_trades_window(
        market_id=market_id,
        window_hours=interval,
        max_wallet_age_hours=max_age
    )
    
    if not trades:
        result['reasons'].append(f"❌ Нет трейдов в окне {interval:.1f} часов")
        result['details']['trades_count'] = 0
        return result
    
    result['details']['trades_count'] = len(trades)
    result['details']['window_hours'] = interval
    
    # 6. Проверка категории (повторная проверка)
    if trades:
        sample = trades[0]
        detected_cat = detect_category(
            sample.get('market_title', ''), 
            sample.get('event_slug', ''), 
            ""
        )
        if detected_cat != category:
            result['reasons'].append(f"⚠️ Категория изменилась: {category} -> {detected_cat}")
        cat_key_check = f"cat_{detected_cat}_enabled"
        if settings.get(cat_key_check, 'true').lower() != 'true':
            result['reasons'].append(f"❌ Обнаруженная категория '{detected_cat}' отключена")
            return result
    
    # 7. Фильтр по стороне (side)
    if side_filter != 'both':
        filtered = []
        for t in trades:
            act = (t.get('trade_action') or '').lower()
            if side_filter == 'buy' and act in ['buy', 'split']:
                filtered.append(t)
            elif side_filter == 'sell' and act in ['sell', 'merge', 'redeem']:
                filtered.append(t)
        trades = filtered
        result['details']['after_side_filter'] = len(trades)
        if not trades:
            result['reasons'].append(f"❌ Нет трейдов после фильтра по стороне '{side_filter}'")
            return result
    
    # 8. Фильтр по минимальному размеру трейда
    trades = [t for t in trades if t.get('trade_size_usd', 0) >= min_usd]
    result['details']['after_min_usd_filter'] = len(trades)
    if not trades:
        result['reasons'].append(f"❌ Нет трейдов >= ${min_usd:,.0f}")
        return result
    
    # 9. Фильтр по максимальному количеству позиций
    trades = [t for t in trades if (t.get('open_positions') or 0) <= max_pos]
    result['details']['after_max_pos_filter'] = len(trades)
    if not trades:
        result['reasons'].append(f"❌ Нет трейдов от кошельков с <= {max_pos} позиций")
        return result
    
    # 10. Подсчет уникальных кошельков и объема
    unique_wallets = set(t['wallet'] for t in trades)
    total_volume = sum(t.get('trade_size_usd', 0) for t in trades)
    wallet_count = len(unique_wallets)
    
    result['details']['unique_wallets'] = wallet_count
    result['details']['total_volume'] = total_volume
    result['details']['min_wallets_required'] = min_wallets
    result['details']['min_total_required'] = min_total
    
    # 11. Проверка минимального количества кошельков
    if wallet_count < min_wallets:
        result['reasons'].append(f"❌ Недостаточно кошельков: {wallet_count} < {min_wallets}")
    else:
        result['details']['wallets_check'] = f"✅ {wallet_count} >= {min_wallets}"
    
    # 12. Проверка минимального общего объема
    if total_volume < min_total:
        result['reasons'].append(f"❌ Недостаточный объем: ${total_volume:,.0f} < ${min_total:,.0f}")
    else:
        result['details']['volume_check'] = f"✅ ${total_volume:,.0f} >= ${min_total:,.0f}"
    
    # 13. Проверка направленности (directionality)
    dominant_outcome, directionality = service._calculate_directionality(trades)
    result['details']['dominant_outcome'] = dominant_outcome
    result['details']['directionality'] = directionality
    result['details']['min_directionality_required'] = min_dir
    
    if directionality < min_dir:
        result['reasons'].append(f"❌ Недостаточная направленность: {directionality:.1f}% < {min_dir}%")
    else:
        result['details']['directionality_check'] = f"✅ {directionality:.1f}% >= {min_dir}%"
    
    # 14. Проверка cooldown (была ли уже опубликована)
    if alerts_storage.was_published(scenario, market_id, dominant_outcome, cooldown):
        result['reasons'].append(f"❌ Уже опубликована недавно (cooldown {cooldown}h)")
    else:
        result['details']['cooldown_check'] = f"✅ Не опубликована в последние {cooldown}h"
    
    # Если все проверки пройдены
    if not result['reasons']:
        result['passed'] = True
        result['reasons'].append("✅ Все фильтры пройдены!")
    
    return result

async def analyze_all_pending():
    """Анализ всех скопившихся позиций."""
    print("=" * 80)
    print("АНАЛИЗ СКОПИВШИХСЯ ПОЗИЦИЙ ИНСАЙДЕРОВ")
    print("=" * 80)
    print()
    
    # Инициализация
    print("Инициализация сервиса...")
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Получение статуса
    status = service.get_status()
    
    print("\n--- НАСТРОЙКИ ---")
    print(f"Глобально включен: {status['enabled']}")
    print(f"CLUSTER включен: {status['scenarios']['CLUSTER']['enabled']}")
    print(f"BURST включен: {status['scenarios']['BURST']['enabled']}")
    print(f"ACCUMULATION включен: {status['scenarios']['ACCUMULATION']['enabled']}")
    print()
    
    # Получение активных паттернов
    pending_patterns = status.get('pending_patterns', {})
    clusters = pending_patterns.get('clusters', [])
    bursts = pending_patterns.get('bursts', [])
    accumulations = pending_patterns.get('accumulations', [])
    
    print(f"--- АКТИВНЫЕ ПАТТЕРНЫ ---")
    print(f"CLUSTER: {len(clusters)}")
    print(f"BURST: {len(bursts)}")
    print(f"ACCUMULATION: {len(accumulations)}")
    print()
    
    # Получение всех активных рынков
    markets = alerts_storage.get_all_active_markets(hours_back=72)
    print(f"Всего активных рынков: {len(markets)}")
    print()
    
    # Если нет паттернов в pending, проверим все активные рынки
    if not clusters and not bursts and not accumulations:
        print("⚠️ Нет активных паттернов в pending_patterns.")
        print("Проверяю все активные рынки напрямую...")
        print()
        
        # Проверяем все активные рынки, которые имеют активность
        markets_with_activity = []
        
        for market in markets:
            market_id = market['market_id']
            category = market.get('category', 'other')
            
            # Проверяем каждый сценарий
            has_activity = False
            market_results = {}
            
            for scenario in ['CLUSTER', 'BURST', 'ACCUMULATION']:
                result = check_filter_reason(service, scenario, market_id, category)
                trades_count = result['details'].get('trades_count', 0)
                
                if trades_count > 0:
                    has_activity = True
                    market_results[scenario] = result
            
            if has_activity:
                markets_with_activity.append({
                    'market_id': market_id,
                    'category': category,
                    'results': market_results
                })
        
        print(f"Найдено рынков с активностью: {len(markets_with_activity)}")
        print()
        
        # Выводим детальный анализ
        for i, market_data in enumerate(markets_with_activity[:50], 1):  # Ограничим до 50
            market_id = market_data['market_id']
            category = market_data['category']
            results = market_data['results']
            
            # Получим название рынка
            trades = alerts_storage.get_trades_window(market_id, 24, None)
            market_title = trades[0].get('market_title', 'Unknown') if trades else 'Unknown'
            
            print("=" * 80)
            print(f"{i}. РЫНОК: {market_title[:70]}")
            print(f"   Market ID: {market_id[:50]}...")
            print(f"   Категория: {category}")
            print()
            
            for scenario, result in results.items():
                print(f"   --- {scenario} ---")
                details = result['details']
                
                print(f"   Трейдов: {details.get('trades_count', 0)}")
                print(f"   Уникальных кошельков: {details.get('unique_wallets', 0)}")
                print(f"   Общий объем: ${details.get('total_volume', 0):,.0f}")
                
                if details.get('directionality') is not None:
                    print(f"   Направленность: {details.get('directionality', 0):.1f}% "
                          f"({details.get('dominant_outcome', 'N/A')})")
                    print(f"   Требуется: >= {details.get('min_directionality_required', 0)}%")
                
                if result['passed']:
                    print(f"   ✅ СТАТУС: ПРОХОДИТ ВСЕ ФИЛЬТРЫ!")
                else:
                    print(f"   ❌ СТАТУС: НЕ ПРОХОДИТ")
                    print(f"   Причины блокировки:")
                    for reason in result['reasons']:
                        print(f"     {reason}")
                
                print()
        
        return
    
    # Функция для поиска market_id по title
    def find_market_id_by_title(title: str, scenario: str) -> Optional[str]:
        """Найти market_id по title из базы данных."""
        import sqlite3
        conn = sqlite3.connect("data/insider_alerts.db")
        conn.row_factory = sqlite3.Row
        try:
            # Ищем по точному совпадению title
            rows = conn.execute("""
                SELECT DISTINCT market_id, market_title 
                FROM alerts_raw_trades 
                WHERE market_title = ? 
                AND consumed_by_scenario IS NULL
                ORDER BY timestamp DESC
                LIMIT 10
            """, (title,)).fetchall()
            
            if rows:
                return rows[0]['market_id']
            
            # Если не нашли, попробуем частичное совпадение
            rows = conn.execute("""
                SELECT DISTINCT market_id, market_title 
                FROM alerts_raw_trades 
                WHERE market_title LIKE ? 
                AND consumed_by_scenario IS NULL
                ORDER BY timestamp DESC
                LIMIT 10
            """, (f"%{title[:50]}%",)).fetchall()
            
            if rows:
                return rows[0]['market_id']
            
            return None
        finally:
            conn.close()
    
    # Анализ каждого паттерна
    all_results = []
    
    # CLUSTER
    if clusters:
        print("=" * 80)
        print("АНАЛИЗ CLUSTER ПАТТЕРНОВ")
        print("=" * 80)
        for i, cluster in enumerate(clusters, 1):
            title = cluster.get('title', 'Unknown')
            market_id = find_market_id_by_title(title, 'CLUSTER')
            
            if not market_id:
                # Попробуем найти через активные рынки
                for m in markets:
                    trades = alerts_storage.get_trades_window(m['market_id'], 2, 24)
                    if trades:
                        trade_title = trades[0].get('market_title', '')
                        if title in trade_title or trade_title in title:
                            market_id = m['market_id']
                            break
            
            if not market_id:
                print(f"\n{i}. CLUSTER: Не удалось определить market_id")
                print(f"   Title: {cluster.get('title', 'Unknown')}")
                continue
            
            # Получим категорию
            trades = alerts_storage.get_trades_window(market_id, 2, 24)
            category = 'other'
            if trades:
                sample = trades[0]
                category = detect_category(
                    sample.get('market_title', ''), 
                    sample.get('event_slug', ''), 
                    ""
                ) or 'other'
            
            result = check_filter_reason(service, 'CLUSTER', market_id, category)
            all_results.append(result)
            
            print(f"\n{i}. CLUSTER: {cluster.get('title', 'Unknown')[:60]}")
            print(f"   Market ID: {market_id[:40]}...")
            print(f"   Категория: {category}")
            print(f"   Кошельков: {cluster.get('wallets', 0)}/{cluster.get('min_wallets', 4)}")
            print(f"   Объем: ${cluster.get('volume', 0):,.0f}")
            print(f"   Статус: {'✅ ПРОХОДИТ' if result['passed'] else '❌ НЕ ПРОХОДИТ'}")
            
            if result['reasons']:
                print(f"   Причины:")
                for reason in result['reasons']:
                    print(f"     {reason}")
            
            if result['details']:
                print(f"   Детали:")
                for key, value in result['details'].items():
                    print(f"     {key}: {value}")
    
    # BURST
    if bursts:
        print("\n" + "=" * 80)
        print("АНАЛИЗ BURST ПАТТЕРНОВ")
        print("=" * 80)
        for i, burst in enumerate(bursts, 1):
            title = burst.get('title', 'Unknown')
            market_id = find_market_id_by_title(title, 'BURST')
            
            if not market_id:
                for m in markets:
                    trades = alerts_storage.get_trades_window(m['market_id'], 1, 72)
                    if trades:
                        trade_title = trades[0].get('market_title', '')
                        if title in trade_title or trade_title in title:
                            market_id = m['market_id']
                            break
            
            if not market_id:
                print(f"\n{i}. BURST: Не удалось определить market_id")
                print(f"   Title: {burst.get('title', 'Unknown')}")
                continue
            
            trades = alerts_storage.get_trades_window(market_id, 1, 72)
            category = 'other'
            if trades:
                sample = trades[0]
                category = detect_category(
                    sample.get('market_title', ''), 
                    sample.get('event_slug', ''), 
                    ""
                ) or 'other'
            
            result = check_filter_reason(service, 'BURST', market_id, category)
            all_results.append(result)
            
            print(f"\n{i}. BURST: {burst.get('title', 'Unknown')[:60]}")
            print(f"   Market ID: {market_id[:40]}...")
            print(f"   Категория: {category}")
            print(f"   Кошельков: {burst.get('wallets', 0)}/{burst.get('min_wallets', 8)}")
            print(f"   Объем: ${burst.get('volume', 0):,.0f}")
            print(f"   Статус: {'✅ ПРОХОДИТ' if result['passed'] else '❌ НЕ ПРОХОДИТ'}")
            
            if result['reasons']:
                print(f"   Причины:")
                for reason in result['reasons']:
                    print(f"     {reason}")
            
            if result['details']:
                print(f"   Детали:")
                for key, value in result['details'].items():
                    print(f"     {key}: {value}")
    
    # ACCUMULATION
    if accumulations:
        print("\n" + "=" * 80)
        print("АНАЛИЗ ACCUMULATION ПАТТЕРНОВ")
        print("=" * 80)
        for i, acc in enumerate(accumulations, 1):
            title = acc.get('title', 'Unknown')
            market_id = find_market_id_by_title(title, 'ACCUMULATION')
            
            if not market_id:
                for m in markets:
                    trades = alerts_storage.get_trades_window(m['market_id'], 14*24, 48)
                    if trades:
                        trade_title = trades[0].get('market_title', '')
                        if title in trade_title or trade_title in title:
                            market_id = m['market_id']
                            break
            
            if not market_id:
                print(f"\n{i}. ACCUMULATION: Не удалось определить market_id")
                print(f"   Title: {acc.get('title', 'Unknown')}")
                continue
            
            trades = alerts_storage.get_trades_window(market_id, 14*24, 48)
            category = 'other'
            if trades:
                sample = trades[0]
                category = detect_category(
                    sample.get('market_title', ''), 
                    sample.get('event_slug', ''), 
                    ""
                ) or 'other'
            
            result = check_filter_reason(service, 'ACCUMULATION', market_id, category)
            all_results.append(result)
            
            print(f"\n{i}. ACCUMULATION: {acc.get('title', 'Unknown')[:60]}")
            print(f"   Market ID: {market_id[:40]}...")
            print(f"   Категория: {category}")
            print(f"   Кошельков: {acc.get('wallets', 0)}/{acc.get('min_wallets', 3)}")
            print(f"   Объем: ${acc.get('volume', 0):,.0f}")
            print(f"   Статус: {'✅ ПРОХОДИТ' if result['passed'] else '❌ НЕ ПРОХОДИТ'}")
            
            if result['reasons']:
                print(f"   Причины:")
                for reason in result['reasons']:
                    print(f"     {reason}")
            
            if result['details']:
                print(f"   Детали:")
                for key, value in result['details'].items():
                    print(f"     {key}: {value}")
    
    # Итоговая статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    
    passed = sum(1 for r in all_results if r['passed'])
    failed = len(all_results) - passed
    
    print(f"Всего проанализировано: {len(all_results)}")
    print(f"✅ Проходят все фильтры: {passed}")
    print(f"❌ Не проходят фильтры: {failed}")
    
    if failed > 0:
        print("\nОсновные причины блокировки:")
        reasons_count = {}
        for result in all_results:
            if not result['passed']:
                for reason in result['reasons']:
                    if reason.startswith('❌'):
                        reason_key = reason.split(':')[0] if ':' in reason else reason
                        reasons_count[reason_key] = reasons_count.get(reason_key, 0) + 1
        
        for reason, count in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count}")
    
    # Показываем реальные настройки
    print("\n" + "=" * 80)
    print("ТЕКУЩИЕ НАСТРОЙКИ ФИЛЬТРОВ")
    print("=" * 80)
    print(f"CLUSTER:")
    print(f"  min_usd: ${float(service.settings.get('cluster_min_usd', '5000')):,.0f}")
    print(f"  min_total: ${float(service.settings.get('cluster_min_total_usd', '10000')):,.0f}")
    print(f"  min_wallets: {service.settings.get('cluster_min_wallets', '4')}")
    print(f"  min_direction_pct: {service.settings.get('cluster_min_direction_pct', '75')}%")
    print(f"  max_positions: {service.settings.get('cluster_max_positions', '3')}")
    print(f"\nBURST:")
    print(f"  min_usd: ${float(service.settings.get('burst_min_usd', '1000')):,.0f}")
    print(f"  min_total: ${float(service.settings.get('burst_min_total_usd', '5000')):,.0f}")
    print(f"  min_wallets: {service.settings.get('burst_min_wallets', '8')}")
    print(f"  min_direction_pct: {service.settings.get('burst_min_direction_pct', '70')}%")
    print(f"  max_positions: {service.settings.get('burst_max_positions', '3')}")
    print(f"\nACCUMULATION:")
    print(f"  interval_days: {service.settings.get('accumulation_interval_days', '14')}")
    print(f"  min_usd: ${float(service.settings.get('accumulation_min_usd', '10000')):,.0f}")
    print(f"  min_total: ${float(service.settings.get('accumulation_min_total_usd', '50000')):,.0f}")
    print(f"  min_wallets: {service.settings.get('accumulation_min_wallets', '3')}")
    print(f"  min_direction_pct: {service.settings.get('accumulation_min_direction_pct', '70')}%")
    print(f"  max_positions: {service.settings.get('accumulation_max_positions', '3')}")

if __name__ == "__main__":
    asyncio.run(analyze_all_pending())
