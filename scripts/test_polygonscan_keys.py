#!/usr/bin/env python3
"""Test all PolygonScan API keys for validity."""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# Check both variable names
keys_str = os.getenv("POLYGONSCAN_API_KEY", "") or os.getenv("POLYGONSCAN_API_KEYS", "")

print(f"Raw keys from env: {keys_str[:50]}..." if len(keys_str) > 50 else f"Raw keys from env: {keys_str}")

if not keys_str:
    print("❌ No PolygonScan API keys found!")
    print("   Expected: POLYGONSCAN_API_KEY in .env")
    sys.exit(1)

# Parse keys
if "," in keys_str:
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
else:
    keys = [keys_str.strip()] if keys_str.strip() else []

print(f"\n📊 Found {len(keys)} API key(s)\n")

# Test wallet - vitalik.eth, known to have Polygon activity
test_wallet = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

for i, key in enumerate(keys, 1):
    # Use the Etherscan v2 API (same as in polymarket.py)
    url = (
        "https://api.etherscan.io/v2/api"
        f"?chainid=137&module=account&action=txlist"
        f"&address={test_wallet}&startblock=0&endblock=99999999"
        f"&page=1&offset=1&sort=asc&apikey={key}"
    )
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        status = data.get("status")
        message = data.get("message", "")
        result = data.get("result", [])
        
        # Mask key for display
        masked_key = f"{key[:6]}...{key[-4:]}"
        
        if status == "1" and result:
            print(f"✅ Key {i}: {masked_key} - WORKING")
            if result and isinstance(result, list) and len(result) > 0:
                ts = result[0].get("timeStamp", "N/A")
                print(f"   └─ First tx timestamp: {ts}")
        elif status == "0" and "rate limit" in str(message).lower():
            print(f"⚠️  Key {i}: {masked_key} - RATE LIMITED")
        elif status == "0" and "invalid" in str(message).lower():
            print(f"❌ Key {i}: {masked_key} - INVALID")
            print(f"   └─ Error: {message}")
        else:
            print(f"⚠️  Key {i}: {masked_key} - Status: {status}, Message: {message}")
            
    except requests.exceptions.Timeout:
        print(f"⏱️  Key {i}: {masked_key} - TIMEOUT")
    except Exception as e:
        print(f"❌ Key {i}: {masked_key} - ERROR: {e}")

print("\n" + "="*50)
print("CONFIGURATION CHECK:")
print("="*50)

# Check which variable is being read
key_singular = os.getenv("POLYGONSCAN_API_KEY", "")
key_plural = os.getenv("POLYGONSCAN_API_KEYS", "")

if key_singular:
    print("✅ POLYGONSCAN_API_KEY (singular) is set")
else:
    print("❌ POLYGONSCAN_API_KEY (singular) is NOT set")

if key_plural:
    print("✅ POLYGONSCAN_API_KEYS (plural) is set")
else:
    print("❌ POLYGONSCAN_API_KEYS (plural) is NOT set")

if key_plural and not key_singular:
    print("\n⚠️  WARNING: Keys are in POLYGONSCAN_API_KEYS but config.py reads POLYGONSCAN_API_KEY!")
    print("   FIX: Rename POLYGONSCAN_API_KEYS to POLYGONSCAN_API_KEY in .env")
