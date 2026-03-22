import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.twitter_service import get_twitter_service

logging.basicConfig(level=logging.INFO)

async def main():
    twitter_data = {
      "title": "Will the Iranian regime fall by June 30?",
      "market_url": "https://polymarket.com/event/will-the-iranian-regime-fall-by-june-30",
      "side": "BUY",
      "outcome": "No",
      "price": 0.6,
      "size": 333000.0,
      "category": "other",
      "trader_address": "0xfd22b8843ae03a33a8a4c5e39ef1e5ff33ebad91",
      "trader_name": "AML",
      "level_name": "\u041c\u0435\u0433\u0430 \u041a\u0438\u0442",
      "position_stats": {
        "pnl_usd": 2552.1563000000315,
        "pnl_percent": 0.6985667466864093,
        "open_count": 2,
        "total_value": 367893.9525
      },
      "wallet_age_str": "6mo 17d",
      "open_positions_count": 2
    }
    
    print(f"Will attempt to post: {twitter_data.get('title')}")
    
    svc = get_twitter_service()
    if not svc:
        print("Twitter service not configured")
        return
        
    text = svc.format_tweet(twitter_data)
    
    print("------------- TWEET -------------")
    print(text)
    print("---------------------------------")
    
    for attempt in range(5):
        print(f"Attempting to post (Attempt {attempt + 1})...")
        try:
            result = await svc.post_tweet(text)
            if result:
                print(f"✅ Successfully posted tweet: https://twitter.com/i/web/status/{result}")
                return
            else:
                print("❌ Failed to post tweet")
        except Exception as e:
            print(f"❌ Exception: {e}")
        await asyncio.sleep(5)
    print("Failed after 5 attempts.")

if __name__ == "__main__":
    asyncio.run(main())
