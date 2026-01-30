#!/usr/bin/env python3
"""
Check why Fed interest rates signal didn't appear in buffer
"""
import asyncio
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage
from core.categories import detect_category

async def check_fed_signal():
    """Check Fed interest rates signal status"""
    
    # Initialize service
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Search for market by title
    market_title = "Fed decreases interest rates by 25 bps after January 2026 meeting?"
    
    print(f"🔍 Searching for market: {market_title}\n")
    
    # Get all active markets
    markets = alerts_storage.get_all_active_markets(hours_back=72)
    
    matching_markets = []
    for m in markets:
        title = m.get('market_title', '')
        if 'Fed' in title and 'interest rates' in title and '25 bps' in title:
            matching_markets.append(m)
    
    if not matching_markets:
        print("❌ Market not found in active markets")
        print("\nTrying to find in database...")
        
        # Try to find in trades table
        conn = alerts_storage._get_connection()
        try:
            rows = conn.execute("""
                SELECT DISTINCT market_id, market_title 
                FROM alerts_raw_trades 
                WHERE market_title LIKE '%Fed%interest rates%25 bps%'
                ORDER BY timestamp DESC
                LIMIT 10
            """).fetchall()
            
            if rows:
                print(f"\nFound {len(rows)} matching markets in database:")
                for row in rows:
                    print(f"  - {row['market_id']}: {row['market_title']}")
                    matching_markets.append({
                        'market_id': row['market_id'],
                        'market_title': row['market_title']
                    })
            else:
                print("❌ No matching markets found in database")
                return
        finally:
            conn.close()
    
    # Check each matching market
    for market in matching_markets:
        market_id = market['market_id']
        title = market.get('market_title', 'Unknown')
        
        print(f"\n{'='*80}")
        print(f"📊 Market: {title}")
        print(f"🆔 Market ID: {market_id}")
        print(f"{'='*80}\n")
        
        # Check ALL trades in database for this market (no time filter)
        conn = alerts_storage._get_connection()
        try:
            all_trades_rows = conn.execute("""
                SELECT * FROM alerts_raw_trades 
                WHERE market_id = ?
                ORDER BY timestamp DESC
                LIMIT 20
            """, (market_id,)).fetchall()
            
            if all_trades_rows:
                print(f"📊 Total trades in database (all time): {len(all_trades_rows)}")
                latest_trade = dict(all_trades_rows[0])
                latest_ts = latest_trade['timestamp']
                now_ts = int(time.time())
                age_hours = (now_ts - latest_ts) / 3600
                print(f"   Latest trade: {age_hours:.1f} hours ago")
                print(f"   Latest trade size: ${latest_trade.get('trade_size_usd', 0):.2f}")
                print(f"   Latest wallet: {latest_trade.get('wallet', '')[:20]}...")
                print(f"   Latest wallet age: {latest_trade.get('wallet_age_hours', 0):.1f}h")
                print(f"   Latest positions: {latest_trade.get('open_positions', 0)}")
            else:
                print("❌ No trades found in database at all for this market")
                continue
        finally:
            conn.close()
        
        # Get recent trades with filters
        interval = float(service.settings.get('burst_interval_hours', '1'))
        max_age = float(service.settings.get('burst_wallet_age_hours', '72'))
        
        trades = alerts_storage.get_trades_window(
            market_id=market_id,
            window_hours=interval,
            max_wallet_age_hours=max_age
        )
        
        print(f"\n📈 Trades in window (interval={interval}h, max_age={max_age}h): {len(trades)}")
        
        if not trades:
            print("❌ No trades found in the time window")
            print("\n   Possible reasons:")
            print(f"   1. Trades are older than {interval}h (burst interval)")
            print(f"   2. Wallets are older than {max_age}h (max wallet age)")
            print(f"   3. Trades were consumed by another scenario")
            
            # Check if trades were consumed
            if all_trades_rows:
                consumed_count = sum(1 for t in all_trades_rows if dict(t).get('consumed_by_scenario'))
                if consumed_count > 0:
                    print(f"\n   ⚠️  Found {consumed_count} consumed trades (excluded from buffer)")
                    print(f"\n   📋 All trades details:")
                    for i, t in enumerate(all_trades_rows, 1):
                        t_dict = dict(t)
                        consumed = t_dict.get('consumed_by_scenario', '')
                        age_h = (now_ts - t_dict['timestamp']) / 3600
                        wallet_short = t_dict.get('wallet', '')[:10] + '...' + t_dict.get('wallet', '')[-6:] if len(t_dict.get('wallet', '')) > 16 else t_dict.get('wallet', '')
                        print(f"      {i}. Wallet: {wallet_short}")
                        print(f"         Size: ${t_dict.get('trade_size_usd', 0):.2f}")
                        print(f"         Positions: {t_dict.get('open_positions', 0)}")
                        print(f"         Wallet age: {t_dict.get('wallet_age_hours', 0):.1f}h")
                        print(f"         Trade age: {age_h:.1f}h ago")
                        if consumed:
                            print(f"         ❌ Consumed by: {consumed}")
                        else:
                            print(f"         ✅ Not consumed")
            continue
        
        # Check category
        sample = trades[0]
        detected_cat = detect_category(
            sample.get('market_title', ''),
            sample.get('event_slug', ''),
            ""
        )
        cat_key = f"cat_{detected_cat}_enabled"
        cat_enabled = service.settings.get(cat_key, 'true').lower() == 'true'
        
        print(f"📂 Category: {detected_cat} (enabled: {cat_enabled})")
        
        if not cat_enabled:
            print(f"❌ Category {detected_cat} is DISABLED - signal won't appear in buffer!")
            continue
        
        # Get BURST settings
        min_usd = float(service.settings.get('burst_min_usd', '1000'))
        min_total = float(service.settings.get('burst_min_total_usd', '5000'))
        min_wallets = int(service.settings.get('burst_min_wallets', '8'))
        max_pos = int(service.settings.get('burst_max_positions', '3'))
        max_age = float(service.settings.get('burst_wallet_age_hours', '72'))
        interval = float(service.settings.get('burst_interval_hours', '1'))
        min_dir = float(service.settings.get('burst_min_direction_pct', '70'))
        
        print(f"\n⚙️  BURST Settings:")
        print(f"   Min trade size: ${min_usd}")
        print(f"   Min total volume: ${min_total}")
        print(f"   Min wallets: {min_wallets}")
        print(f"   Max positions: {max_pos}")
        print(f"   Max wallet age: {max_age}h")
        print(f"   Interval: {interval}h")
        print(f"   Min directionality: {min_dir}%")
        
        # Filter trades
        qualifying_trades = [t for t in trades if t.get('trade_size_usd', 0) >= min_usd]
        print(f"\n💰 Trades >= ${min_usd}: {len(qualifying_trades)}")
        
        if not qualifying_trades:
            print(f"❌ No trades meet minimum size (${min_usd})")
            print(f"\n   Trade sizes found:")
            for t in trades[:5]:
                print(f"     - ${t.get('trade_size_usd', 0):.2f} (wallet: {t.get('wallet', '')[:10]}...)")
            continue
        
        # Filter by positions
        qualifying_trades = [t for t in qualifying_trades if (t.get('open_positions') or 0) <= max_pos]
        print(f"👤 Trades with <= {max_pos} positions: {len(qualifying_trades)}")
        
        if not qualifying_trades:
            print(f"❌ No trades meet max positions filter (<= {max_pos})")
            continue
        
        # Get unique wallets
        unique_wallets = set(t['wallet'] for t in qualifying_trades)
        wallet_count = len(unique_wallets)
        total_volume = sum(t['trade_size_usd'] for t in qualifying_trades)
        
        print(f"\n👥 Unique wallets: {wallet_count} (min required: {min_wallets})")
        print(f"💵 Total volume: ${total_volume:,.2f} (min required: ${min_total:,.2f})")
        
        # Check if in active bursts buffer
        active_burst = service._active_bursts.get(market_id)
        if active_burst:
            print(f"\n✅ Signal IS in active_bursts buffer!")
            print(f"   Wallets: {active_burst.get('wallets', 0)}/{active_burst.get('min_wallets', 0)}")
            print(f"   Volume: ${active_burst.get('volume', 0):,.2f}")
            print(f"   Blocked reason: {active_burst.get('blocked_reason', 'None')}")
            print(f"   Wallet list: {len(active_burst.get('wallet_list', []))} wallets")
            if active_burst.get('wallet_list'):
                print(f"   First few wallets:")
                for w in active_burst.get('wallet_list', [])[:5]:
                    print(f"     - {w}")
        else:
            print(f"\n❌ Signal NOT in active_bursts buffer")
            print(f"   This means _check_burst() hasn't been called recently or returned None")
        
        # Try to check burst manually
        print(f"\n🔬 Running _check_burst() manually...")
        burst_result = service._check_burst(market_id)
        
        if burst_result:
            print(f"✅ BURST check PASSED - signal should be published!")
            print(f"   Wallets: {burst_result.get('wallet_count', 0)}")
            print(f"   Directionality: {burst_result.get('directionality', 0):.1f}%")
        else:
            print(f"❌ BURST check FAILED")
            
            # Check active_bursts again after check
            active_burst_after = service._active_bursts.get(market_id)
            if active_burst_after:
                print(f"\n   But signal IS now in buffer after check:")
                print(f"   Wallets: {active_burst_after.get('wallets', 0)}/{active_burst_after.get('min_wallets', 0)}")
                print(f"   Blocked reason: {active_burst_after.get('blocked_reason', 'None')}")
            else:
                print(f"   Signal still not in buffer")
        
        # Show wallet details
        print(f"\n📋 Wallet Details:")
        for i, wallet in enumerate(sorted(unique_wallets)[:10], 1):
            wallet_trades = [t for t in qualifying_trades if t['wallet'] == wallet]
            total_wallet_volume = sum(t['trade_size_usd'] for t in wallet_trades)
            positions = wallet_trades[0].get('open_positions', 0) if wallet_trades else 0
            wallet_age_h = wallet_trades[0].get('wallet_age_hours', 0) if wallet_trades else 0
            
            print(f"   {i}. {wallet}")
            print(f"      Volume: ${total_wallet_volume:,.2f}")
            print(f"      Positions: {positions}")
            print(f"      Age: {wallet_age_h:.1f}h")
        
        if wallet_count > 10:
            print(f"   ... and {wallet_count - 10} more wallets")

if __name__ == "__main__":
    asyncio.run(check_fed_signal())
