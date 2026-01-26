#!/usr/bin/env python3
"""
Smoke test for blocked_reason functionality.
Tests that reasons are recorded and cleared correctly.
"""

import sys
import os
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

# Setup path
sys.path.append(os.getcwd())

from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage


async def test_directionality_fail():
    """Test that directionality failure records blocked_reason."""
    print("=" * 60)
    print("TEST 1: Directionality failure")
    print("=" * 60)
    
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Set up scenario
    service.update_setting('cluster_enabled', 'true')
    service.update_setting('cluster_min_direction_pct', '90')
    service.update_setting('cluster_min_wallets', '2')
    service.update_setting('cluster_min_total_usd', '1000')
    
    # Create synthetic market_id
    market_id = "0xTEST_DIRECTIONALITY"
    
    # Mock storage to return trades with low directionality
    with patch('storage.alerts_storage.get_trades_window') as mock_get_trades:
        mock_get_trades.return_value = [
            {
                'id': 1,
                'wallet': '0xWALLET1',
                'trade_size_usd': 6000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            },
            {
                'id': 2,
                'wallet': '0xWALLET2',
                'trade_size_usd': 4000,
                'timestamp': int(time.time()),
                'outcome': 'NO',  # Different outcome = low directionality
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            }
        ]
        
        # Run check
        result = service._check_cluster(market_id)
        
        # Verify
        assert result is None, "Should return None (directionality too low)"
        assert market_id in service._active_clusters, "Market should be in buffer"
        
        buffer_entry = service._active_clusters[market_id]
        assert 'blocked_reason' in buffer_entry, "Should have blocked_reason"
        assert 'blocked_code' in buffer_entry, "Should have blocked_code"
        assert buffer_entry['blocked_code'] == 'DIRECTIONALITY_TOO_LOW', f"Expected DIRECTIONALITY_TOO_LOW, got {buffer_entry['blocked_code']}"
        assert 'blocked_at' in buffer_entry, "Should have blocked_at"
        
        print(f"✅ PASSED: blocked_code={buffer_entry['blocked_code']}")
        print(f"   blocked_reason={buffer_entry['blocked_reason']}")
        print(f"   blocked_at={buffer_entry['blocked_at']}")


async def test_cooldown_fail():
    """Test that cooldown failure records blocked_reason."""
    print("\n" + "=" * 60)
    print("TEST 2: Cooldown failure")
    print("=" * 60)
    
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Set up scenario
    service.update_setting('cluster_enabled', 'true')
    service.update_setting('cluster_min_direction_pct', '50')
    service.update_setting('cluster_min_wallets', '2')
    service.update_setting('cluster_min_total_usd', '1000')
    service.update_setting('cooldown_hours', '24')
    
    market_id = "0xTEST_COOLDOWN"
    
    # Mark as published
    alerts_storage.mark_published(
        scenario='CLUSTER',
        market_id=market_id,
        outcome='YES',
        market_title='Test Market',
        total_volume=10000,
        participants_count=2,
        wallet_list=['0xWALLET1', '0xWALLET2']
    )
    
    # Mock storage to return trades
    with patch('storage.alerts_storage.get_trades_window') as mock_get_trades:
        mock_get_trades.return_value = [
            {
                'id': 1,
                'wallet': '0xWALLET1',
                'trade_size_usd': 6000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            },
            {
                'id': 2,
                'wallet': '0xWALLET2',
                'trade_size_usd': 5000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            }
        ]
        
        # Run check
        result = service._check_cluster(market_id)
        
        # Verify
        assert result is None, "Should return None (cooldown active)"
        assert market_id in service._active_clusters, "Market should be in buffer"
        
        buffer_entry = service._active_clusters[market_id]
        assert 'blocked_reason' in buffer_entry, "Should have blocked_reason"
        assert buffer_entry['blocked_code'] == 'COOLDOWN_ACTIVE', f"Expected COOLDOWN_ACTIVE, got {buffer_entry['blocked_code']}"
        
        print(f"✅ PASSED: blocked_code={buffer_entry['blocked_code']}")
        print(f"   blocked_reason={buffer_entry['blocked_reason']}")


async def test_publish_error():
    """Test that publish error records blocked_reason."""
    print("\n" + "=" * 60)
    print("TEST 3: Publish error")
    print("=" * 60)
    
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Set up scenario
    service.update_setting('cluster_enabled', 'true')
    service.update_setting('cluster_min_direction_pct', '50')
    service.update_setting('cluster_min_wallets', '2')
    service.update_setting('cluster_min_total_usd', '1000')
    service.update_setting('channel_id', '-1001234567890')
    
    market_id = "0xTEST_PUBLISH_ERROR"
    
    # Create mock bot that raises exception
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram API error: 429"))
    service.set_bot(mock_bot)
    
    # Mock storage
    with patch('storage.alerts_storage.get_trades_window') as mock_get_trades, \
         patch('storage.alerts_storage.was_published') as mock_was_published, \
         patch('services.insider_alerts.InsiderAlertsService._verify_positions') as mock_verify:
        
        mock_get_trades.return_value = [
            {
                'id': 1,
                'wallet': '0xWALLET1',
                'trade_size_usd': 6000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            },
            {
                'id': 2,
                'wallet': '0xWALLET2',
                'trade_size_usd': 5000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            }
        ]
        mock_was_published.return_value = False
        mock_verify.return_value = {
            'market_id': market_id,
            'outcome': 'YES',
            'trades': mock_get_trades.return_value,
            'wallet_count': 2,
            'total_volume': 11000
        }
        
        # Run check (should return alert_data)
        alert_data = service._check_cluster(market_id)
        assert alert_data is not None, "Should return alert_data (all checks passed)"
        
        # Try to publish (should fail)
        service._publish_alert('CLUSTER', alert_data)
        
        # Wait a bit for async task
        await asyncio.sleep(0.5)
        
        # Verify
        assert market_id in service._active_clusters, "Market should be in buffer"
        buffer_entry = service._active_clusters[market_id]
        assert 'blocked_reason' in buffer_entry, "Should have blocked_reason after publish error"
        assert buffer_entry['blocked_code'] == 'PUBLISH_ERROR', f"Expected PUBLISH_ERROR, got {buffer_entry.get('blocked_code')}"
        
        print(f"✅ PASSED: blocked_code={buffer_entry['blocked_code']}")
        print(f"   blocked_reason={buffer_entry['blocked_reason']}")


async def test_successful_publish():
    """Test that blocked_reason is cleared after successful publish."""
    print("\n" + "=" * 60)
    print("TEST 4: Successful publish (clears blocked_reason)")
    print("=" * 60)
    
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Set up scenario
    service.update_setting('cluster_enabled', 'true')
    service.update_setting('cluster_min_direction_pct', '50')
    service.update_setting('cluster_min_wallets', '2')
    service.update_setting('cluster_min_total_usd', '1000')
    service.update_setting('channel_id', '-1001234567890')
    
    market_id = "0xTEST_SUCCESS"
    
    # Create mock bot that succeeds
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(return_value=Mock(message_id=123))
    service.set_bot(mock_bot)
    
    # Mock storage
    with patch('storage.alerts_storage.get_trades_window') as mock_get_trades, \
         patch('storage.alerts_storage.was_published') as mock_was_published, \
         patch('storage.alerts_storage.mark_published') as mock_mark_published, \
         patch('services.insider_alerts.InsiderAlertsService._verify_positions') as mock_verify:
        
        mock_get_trades.return_value = [
            {
                'id': 1,
                'wallet': '0xWALLET1',
                'trade_size_usd': 6000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            },
            {
                'id': 2,
                'wallet': '0xWALLET2',
                'trade_size_usd': 5000,
                'timestamp': int(time.time()),
                'outcome': 'YES',
                'trade_action': 'buy',
                'open_positions': 1,
                'market_title': 'Test Market',
                'event_slug': 'test-market',
                'category': 'other'
            }
        ]
        mock_was_published.return_value = False
        mock_verify.return_value = {
            'market_id': market_id,
            'outcome': 'YES',
            'trades': mock_get_trades.return_value,
            'wallet_count': 2,
            'total_volume': 11000
        }
        
        # First, set a blocked_reason manually
        service._active_clusters[market_id] = {
            'wallets': 2,
            'wallet_list': ['0xWALLET1', '0xWALLET2'],
            'volume': 11000,
            'last_ts': int(time.time()),
            'title': 'Test Market',
            'min_wallets': 2,
            'min_total': 1000,
            'blocked_reason': 'Test reason',
            'blocked_code': 'TEST_CODE',
            'blocked_at': int(time.time())
        }
        
        # Run check
        alert_data = service._check_cluster(market_id)
        assert alert_data is not None, "Should return alert_data"
        
        # Publish
        service._publish_alert('CLUSTER', alert_data)
        
        # Wait for async task
        await asyncio.sleep(0.5)
        
        # Verify blocked_reason is cleared
        assert market_id in service._active_clusters, "Market should still be in buffer"
        buffer_entry = service._active_clusters[market_id]
        assert 'blocked_reason' not in buffer_entry or buffer_entry.get('blocked_reason') is None, "blocked_reason should be cleared"
        assert 'blocked_code' not in buffer_entry or buffer_entry.get('blocked_code') is None, "blocked_code should be cleared"
        
        print(f"✅ PASSED: blocked_reason cleared after successful publish")
        print(f"   buffer_entry keys: {list(buffer_entry.keys())}")


async def main():
    """Run all tests."""
    try:
        await test_directionality_fail()
        await test_cooldown_fail()
        await test_publish_error()
        await test_successful_publish()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
