# PUBLIC SHELL VERSION
"""
Check why specific trade didn't get into buffer
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage
wallet = '0x918558448E5be06B6AfaA4191c8B9163cf543E45'
trade_value = 926
price_pct = 0.8
market_title_search = 'Fed decreases interest rates by 25 bps after January 2026 meeting'
print(f"🔍 Checking why trade didn't get into buffer")
print(f'   Wallet: {wallet}')
print(f'   Value: ${trade_value}')
print(f'   Price: {price_pct}%')
print(f'   Market: {market_title_search}\n')
alerts_storage.init_db()
service = InsiderAlertsService()
print('⚙️  Insider Alerts Settings:')
print(f'   Enabled: {service.is_enabled()}')
print(f'   Probability min: {service.settings.get('probability_min', '0')}%')
print(f'   Probability max: {service.settings.get('probability_max', '100')}%')
print(f'   BURST enabled: {service.settings.get('burst_enabled', 'false')}')
print(f'   BURST min wallets: {service.settings.get('burst_min_wallets', '8')}')
print(f'   BURST interval: {service.settings.get('burst_interval_hours', '1')}h')
print(f'   BURST max wallet age: {service.settings.get('burst_wallet_age_hours', '72')}h')
print(f'   BURST max positions: {service.settings.get('burst_max_positions', '3')}')
print(f'   BURST min USD: ${service.settings.get('burst_min_usd', '1000')}')
prob_min = float(service.settings.get('probability_min', '0'))
prob_max = float(service.settings.get('probability_max', '100'))
print(f'\n📊 Probability Filter Check:')
print(f'   Trade price: {price_pct}%')
print(f'   Allowed range: {prob_min}% - {prob_max}%')
if not prob_min <= price_pct <= prob_max:
    print(f'   ❌ TRADE REJECTED: Price {price_pct}% is outside allowed range!')
    print(f"   This is why the trade didn't get stored in insider alerts database.")
else:
    print(f'   ✅ Price is within allowed range')
conn = alerts_storage._get_connection()
try:
    rows = conn.execute('\n        SELECT * FROM alerts_raw_trades \n        WHERE wallet LIKE ?\n        ORDER BY timestamp DESC\n        LIMIT 10\n    ', (f'%{wallet[-10:]}%',)).fetchall()
    if rows:
        print(f'\n📋 Found {len(rows)} trades for this wallet (partial match):')
        for i, row in enumerate(rows, 1):
            row_dict = dict(row)
            age_h = (int(time.time()) - row_dict['timestamp']) / 3600
            print(f'   {i}. Market: {row_dict.get('market_title', '')[:60]}')
            print(f'      Size: ${row_dict.get('trade_size_usd', 0):.2f}')
            print(f'      Price: {(row_dict.get('price', 0) * 100 if row_dict.get('price') else 'N/A')}%')
            print(f'      Age: {age_h:.1f}h ago')
            print(f'      Consumed: {row_dict.get('consumed_by_scenario', 'No')}')
    else:
        print(f'\n❌ No trades found in database for wallet ending in ...{wallet[-10:]}')
        print(f'   This confirms the trade was never stored.')
        if not prob_min <= price_pct <= prob_max:
            print(f'\n💡 SOLUTION: Adjust probability filter to include 0.8%')
            print(f'   Current: {prob_min}% - {prob_max}%')
            print(f'   Should be: {prob_min}% - {prob_max}% (or lower min to 0)')
except Exception as e:
    print(f'Error: {e}')
finally:
    conn.close()
print(f'\n📊 Active BURSTS in buffer:')
active_bursts = service._active_bursts
if active_bursts:
    for market_id, burst in list(active_bursts.items())[:5]:
        title = burst.get('title', '')[:60]
        wallets = burst.get('wallets', 0)
        min_wallets = burst.get('min_wallets', 0)
        print(f'   - {title}')
        print(f'     Wallets: {wallets}/{min_wallets}')
        if market_title_search.lower() in title.lower():
            print(f"     ✅ This is the market we're looking for!")
            wallet_list = burst.get('wallet_list', [])
            if wallet in wallet_list:
                print(f'     ✅ Wallet IS in buffer!')
            else:
                print(f'     ❌ Wallet NOT in buffer')
else:
    print('   No active bursts')