# PUBLIC SHELL VERSION
import json
import sqlite3
import os
try:
    with open('user_settings.json', 'r') as f:
        data = json.load(f)
        probs = data.get('filters', {}).get('probabilities', {})
        print('User Settings keys:', data.keys())
        print('User Probabilities:', data.get('user_probabilities', {}))
except Exception as e:
    print(f'Error reading user_settings: {e}')
try:
    path = os.path.join(os.getcwd(), 'data', 'insider_alerts.db')
    print(f'Checking DB at {path}')
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM alerts_settings WHERE key LIKE 'probability_%'")
    rows = cursor.fetchall()
    print('\nInsider Settings (DB):')
    for row in rows:
        print(f'{row[0]}: {row[1]}')
    conn.close()
except Exception as e:
    print(f'Error reading DB: {e}')