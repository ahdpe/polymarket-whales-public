#!/usr/bin/env python3
"""Republish an insider alert that was blocked due to missing channel_id."""
import asyncio
import sys
from storage import alerts_storage
from services.insider_alerts import InsiderAlertsService, get_insider_alerts_service
from services.polymarket import PolymarketService
from services.telegram_service import bot as telegram_bot

async def republish_alert(market_id: str, scenario: str = 'BURST'):
    """Republish a specific alert."""
    # Initialize services
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Use bot instance from telegram_service
    if not telegram_bot:
        print("❌ Бот не инициализирован. Убедитесь, что бот запущен.")
        return False
    
    service.set_bot(telegram_bot)
    
    # Get PolymarketService for position verification
    poly_service = PolymarketService()
    service.set_poly_service(poly_service)
    
    # Try to get published alert data first (for reference)
    recent = alerts_storage.get_recent_published(limit=100)
    alert_data = None
    for alert in recent:
        if alert.get('market_id') == market_id and alert.get('scenario') == scenario:
            alert_data = alert
            break
    
    # Get trades for this market
    trades = alerts_storage.get_trades_window(
        market_id=market_id,
        window_hours=72,  # Large window to catch all trades
        max_wallet_age_hours=None
    )
    
    if not trades:
        print("❌ Не найдены трейды для этого рынка")
        return False
    
    # Determine outcome from trades (most common)
    from collections import defaultdict
    outcome_counts = defaultdict(int)
    for t in trades:
        out = t.get('outcome', '').upper()
        if out:
            outcome_counts[out] += 1
    
    if not outcome_counts:
        print("❌ Не удалось определить outcome из трейдов")
        return False
    
    outcome = max(outcome_counts.items(), key=lambda x: x[1])[0]
    
    # Filter trades by outcome
    trades = [t for t in trades if t.get('outcome', '').upper() == outcome.upper()]
    
    if not trades:
        print(f"❌ Не найдены трейды для outcome {outcome}")
        return False
    
    if alert_data:
        print(f"📋 Найден алерт: {alert_data.get('market_title', 'N/A')}")
        print(f"   Scenario: {scenario}, Outcome: {outcome}")
        print(f"   Volume: ${alert_data.get('total_volume', 0):,.0f}")
        print(f"   Participants: {alert_data.get('participants_count', 0)}")
    else:
        print(f"📋 Создаю алерт из трейдов")
        print(f"   Scenario: {scenario}, Outcome: {outcome}")
    
    print(f"✅ Найдено {len(trades)} трейдов")
    
    # Reconstruct alert_data structure
    total_volume = sum(t.get('trade_size_usd', 0) for t in trades)
    unique_wallets = set(t.get('wallet') for t in trades if t.get('wallet'))
    
    reconstructed_alert = {
        'market_id': market_id,
        'outcome': outcome,
        'total_volume': total_volume,
        'wallet_count': len(unique_wallets),
        'trades': trades,
        'window_hours': 1.0 if scenario == 'BURST' else 2.0,
        'include_profiles': 'true'
    }
    
    # Calculate directionality
    from collections import defaultdict
    outcome_volumes = defaultdict(float)
    for trade in trades:
        out = trade.get('outcome', 'UNKNOWN').upper()
        vol = trade.get('trade_size_usd', 0)
        outcome_volumes[out] += vol
    
    if outcome_volumes:
        dominant = max(outcome_volumes.items(), key=lambda x: x[1])
        directionality = (dominant[1] / total_volume) * 100 if total_volume > 0 else 0
        reconstructed_alert['directionality'] = directionality
    
    # Remove from published to allow republishing (if exists)
    import sqlite3
    conn = alerts_storage._get_connection()
    try:
        cursor = conn.execute("""
            DELETE FROM alerts_published 
            WHERE scenario = ? AND market_id = ? AND outcome = ?
        """, (scenario, market_id, outcome))
        if cursor.rowcount > 0:
            print("🔄 Удалена запись из published для переопубликации...")
        conn.commit()
    finally:
        conn.close()
    
    # Publish alert directly (bypassing _publish_alert to avoid async task issues)
    print(f"📤 Публикую алерт в канал...")
    try:
        channel_id = service.get_channel_id()
        if not channel_id:
            print("❌ Channel ID не настроен!")
            return False
        
        # Verify positions first
        print("🔍 Проверяю позиции кошельков...")
        verified_data = await service._verify_positions(reconstructed_alert, scenario)
        
        if verified_data is None:
            print("❌ Недостаточно кошельков с активными позициями")
            return False
        
        print(f"✅ {verified_data.get('wallet_count', 0)} кошельков прошли проверку")
        
        # Get wallet list
        wallet_list = list(set(
            t.get('wallet') for t in verified_data.get('trades', []) 
            if t.get('wallet')
        ))
        
        # Check shared funding
        shared_wallets = set()
        shared_sources = []
        try:
            from services.shared_funding import analyze_shared_funding
            if wallet_list:
                funding_result = await analyze_shared_funding(scenario, wallet_list)
                shared_wallets = funding_result.get('shared_wallets', set())
                shared_sources = funding_result.get('shared_sources', [])
        except Exception as e:
            print(f"⚠️  Пропущена проверка shared funding: {e}")
        
        # Add shared_sources to alert_data (method expects it there)
        verified_data['shared_sources'] = shared_sources

        event_slug = (verified_data.get('trades') or [{}])[0].get('event_slug', '') or ''
        raw_px = await service._fetch_gamma_outcome_price(market_id, event_slug, outcome)
        verified_data['signal_market_price_pct'] = raw_px * 100.0 if raw_px is not None else None
        
        # Format message
        message = service._format_alert_message(scenario, verified_data, shared_wallets=shared_wallets)
        
        # Send message
        print(f"📨 Отправляю сообщение в канал {channel_id}...")
        await telegram_bot.send_message(
            chat_id=channel_id,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        
        # Mark as published
        cooldown = int(service.settings.get('cooldown_hours', '24'))
        market_title = verified_data.get('trades', [{}])[0].get('market_title', '')
        alerts_storage.mark_published(
            scenario=scenario,
            market_id=market_id,
            outcome=outcome,
            market_title=market_title,
            total_volume=verified_data.get('total_volume', 0),
            participants_count=len(verified_data.get('trades', [])),
            wallet_list=wallet_list
        )
        
        print("✅ Алерт успешно опубликован в канал!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при публикации: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python republish_alert.py <market_id> [scenario]")
        print("Example: python republish_alert.py 0x46d40e851b24d9b0af4bc1942ccd86439cae82a9011767da14950df0ad997adf BURST")
        sys.exit(1)
    
    market_id = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else 'BURST'
    
    asyncio.run(republish_alert(market_id, scenario))
