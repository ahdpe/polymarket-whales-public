
import sqlite3
import os

DB_PATH = '/root/PolymarketWhales/data/insider_alerts.db'

def update_db():
    if not os.path.exists(DB_PATH):
        print(f"File not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    
    print("--- Updating Setting ---")
    try:
        conn.execute("INSERT OR REPLACE INTO alerts_settings (key, value) VALUES (?, ?)", ('accumulation_min_days', '1'))
        conn.commit()
        print("✅ Updated accumulation_min_days to '1'")
        
        # Verify
        val = conn.execute("SELECT value FROM alerts_settings WHERE key = 'accumulation_min_days'").fetchone()[0]
        print(f"Verified value: {val}")
        
    except Exception as e:
        print(f"Error updating settings: {e}")

    conn.close()

if __name__ == "__main__":
    update_db()
