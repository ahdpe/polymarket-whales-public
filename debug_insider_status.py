
import asyncio
import sys
import os
import json
from datetime import datetime

# Setup path
sys.path.append(os.getcwd())

from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage

async def check_status():
    print("Initializing service...")
    alerts_storage.init_db()
    service = InsiderAlertsService()
    
    # Rebuild state
    print("Re-checking markets to rebuild state...")
    await service.check_all_markets()

    # Check Settings
    status = service.get_status()
    print("\n--- SETTINGS ---")
    print(f"Global Enabled: {status['enabled']}")
    print(f"Cluster Enabled: {status['scenarios']['CLUSTER']['enabled']}")
    print(f"Burst Enabled: {status['scenarios']['BURST']['enabled']}")
    print(f"Accumulation Enabled: {status['scenarios']['ACCUMULATION']['enabled']}")

    # Check Stellan Market specifically
    markets = alerts_storage.get_all_active_markets(hours_back=72)
    s_market = next((m for m in markets if "Stellan" in m.get('question', '') or "Stellan" in m.get('market_title', '')), None)
    
    if s_market:
        mid = s_market['market_id']
        print(f"\nAnalyzing Market: {s_market['market_title']} ({mid})")
        
        # Check Scenarios
        print("Checking CLUSTER...")
        cluster = service._check_cluster(mid)
        if cluster:
            print(f"✅ CLUSTER VALID: {cluster['wallet_count']} wallets, dir {cluster['directionality']:.1f}%")
        else:
            print("❌ CLUSTER INVALID")
            
        print("Checking BURST...")
        burst = service._check_burst(mid)
        if burst:
            print(f"✅ BURST VALID: {burst['wallet_count']} wallets, dir {burst['directionality']:.1f}%")
        else:
            print("❌ BURST INVALID")

        print("Checking ACCUMULATION...")
        acc = service._check_accumulation(mid)
        if acc:
            print(f"✅ ACC VALID: {acc['wallet_count']} wallets, {acc['days_count']} days, dir {acc['directionality']:.1f}%")
        else:
             print("❌ ACC INVALID")

        # Check existing publications
        print("\nPublication History:")
        exists = alerts_storage.get_recent_published(limit=100)
        found_pub = False
        for e in exists:
            if e['market_id'] == mid:
                found_pub = True
                print(f" - Published: {e['scenario']} at {datetime.fromtimestamp(e['timestamp'])}")
        
        if not found_pub:
            print(" - No recent publications found.")

    else:
        print("Market not found in active list. Trying to list close matches...")
        for m in markets[:10]:
            print(f" - {m.get('market_title')}")

if __name__ == "__main__":
    asyncio.run(check_status())
