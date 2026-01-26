
import sqlite3
import time
from datetime import datetime


# Based on files, it seems insider data is either in insider_alerts.db or trades.db
# Usually 'trades' table is in trades.db? 
# or insider_alerts.py uses storage/alerts_storage.py which likely uses 'insider_alerts.db' or something similar.
# Let's check storage/alerts_storage.py to see where it stores trades.
# But for now, try insider_alerts.db as it was in the LS output.
# Actually, the previous script tried whales.db.
# Let's try insider_alerts.db
DB_PATH = '/root/PolymarketWhales/data/insider_alerts.db'

def analyze_market():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Find Market
    print("Searching for Stellan market...")

    c.execute("SELECT market_id, market_title FROM alerts_raw_trades WHERE market_title LIKE '%Stellan%' LIMIT 1")
    market = c.fetchone()
    
    if not market:
        print("Market not found in DB.")
        return
        
    market_id = market['market_id']
    print(f"Found: {market['market_title']} ({market_id})")
    

    # 2. Get Trades
    # Get all trades for this market to analyze timing
    c.execute("SELECT timestamp, trade_size_usd, wallet_age_hours, wallet FROM alerts_raw_trades WHERE market_id = ?", (market_id,))
    trades = c.fetchall()
    
    print(f"Total trades: {len(trades)}")
    
    if not trades:
        return

    # 3. Analyze Time Spread
    timestamps = [t['timestamp'] for t in trades]
    min_ts = min(timestamps)
    max_ts = max(timestamps)
    
    duration_hours = (max_ts - min_ts) / 3600
    print(f"Time span: {duration_hours:.1f} hours ({duration_hours/24:.1f} days)")
    
    # 4. Check 'Distinct Days' for Accumulation
    dates = set()
    for t in timestamps:
        dates.add(datetime.fromtimestamp(t).date())
    
    print(f"Distinct calendar days: {len(dates)}")
    print(f"Dates: {[d.isoformat() for d in sorted(list(dates))]}")
    
    # 5. Check Cluster eligibility (max 2h sliding window)
    # We need to see if there was EVER a 2h window with enough volume/wallets?
    # Or just currently? The user asks "now".
    # But usually Cluster checks rolling window.
    # Let's check the DENSITY.
    
    # Sort by time
    trades.sort(key=lambda x: x['timestamp'])
    
    # Simulate Cluster Check (Window 2h, Min Wallets 4, Min Vol 10k normally)
    # Current user settings potentially: Wallets 4, Vol 10k? 
    # From screenshot: Wallets: 23/4. 
    
    # Find max wallets in any 2h window
    max_wallets_2h = 0
    best_window_start = 0
    
    window_sec = 2 * 3600
    
    for i in range(len(timestamps)):
        start_t = timestamps[i]
        end_t = start_t + window_sec
        
        # Count unique wallets in this window
        window_wallets = set()
        for t in trades:
            if start_t <= t['timestamp'] <= end_t:
                window_wallets.add(t['wallet'])
        
        if len(window_wallets) > max_wallets_2h:
            max_wallets_2h = len(window_wallets)
            best_window_start = start_t
            
    print(f"Max unique wallets in any 2h window: {max_wallets_2h}")
    
    conn.close()

if __name__ == "__main__":
    analyze_market()
