
import json
import sqlite3
import os

# Check user settings
try:
    with open('user_settings.json', 'r') as f:
        data = json.load(f)
        probs = data.get('filters', {}).get('probabilities', {}) # format might differ, let's check structure
        # user_settings.json structure depends on how it's saved.
        # Based on telegram_service.py: save_settings() dumps all dicts.
        # Wait, save_settings() in telegram_service usually dumps:
        # { 'user_filters': ..., 'user_probabilities': ..., ... }
        print("User Settings keys:", data.keys())
        print("User Probabilities:", data.get('user_probabilities', {}))
except Exception as e:
    print(f"Error reading user_settings: {e}")

# Check alerts storage
try:
    path = os.path.join(os.getcwd(), 'data', 'insider_alerts.db')
    print(f"Checking DB at {path}")
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM alerts_settings WHERE key LIKE 'probability_%'")
    rows = cursor.fetchall()
    print("\nInsider Settings (DB):")
    for row in rows:
        print(f"{row[0]}: {row[1]}")
    conn.close()
except Exception as e:
    print(f"Error reading DB: {e}")
