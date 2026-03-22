import os
import sys
import asyncio

# Add root dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.twitter_service import TwitterService

async def main():
    service = TwitterService()
    
    trade_data = {
        'title': 'Will Axiom be accused of insider trading?',
        'side': 'BUY',
        'outcome': 'No',
        'price': 0.848,
        'value_usd': 290000,
        'trader_address': '0x054eC2F0cCfdaE941886a3eD306635068c716639',
        'name': '',
        'wallet_age_str': '<1h',
        'open_positions_count': 1,
        'category': 'crypto'
    }

    tweet = service.format_tweet(trade_data)
    print("----- PUBLISHING TWEET -----")
    print(tweet)
    print("-------------------------")
    
    tweet_id = await service.post_tweet(tweet)
    if tweet_id:
        print(f"✅ Successfully posted! Tweet ID: {tweet_id}")
    else:
        print("❌ Failed to post tweet. Check logs or rate limits.")

if __name__ == '__main__':
    asyncio.run(main())
