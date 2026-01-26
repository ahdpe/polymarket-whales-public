
import sqlite3
import os

DB_PATH = '/root/PolymarketWhales/data/insider_alerts.db'

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"File not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    print("--- Settings ---")
    try:
        rows = conn.execute("SELECT * FROM alerts_settings").fetchall()
        for r in rows:
            if 'accumulation' in r['key']:
                print(f"{r['key']}: {r['value']}")
    except Exception as e:
        print(f"Error reading settings: {e}")
        
    print("\n--- Trade Count ---")
    try:
        cnt = conn.execute("SELECT COUNT(*) as c FROM alerts_raw_trades").fetchone()['c']
        print(f"Total trades: {cnt}")
        
        # Check recent trades
        rows = conn.execute("SELECT * FROM alerts_raw_trades ORDER BY timestamp DESC LIMIT 5").fetchall()
        print("\n--- Recent Trades ---")
        for r in rows:
            print(f"{r['market_title'][:50]}... | {r['wallet'][:6]} | size: {r['trade_size_usd']}")
            
    except Exception as e:
        print(f"Error reading trades: {e}")

    conn.close()

if __name__ == "__main__":
    check_db()
