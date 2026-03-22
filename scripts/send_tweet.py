import sys
import os
sys.path.append('/root/PolymarketWhales')

from services.twitter_service import TwitterService

def main():
    service = TwitterService()
    if not service.is_configured:
        print("Twitter not configured!")
        return

    trade_data = {
        'title': 'US strikes Iran by February 28, 2026?',
        'side': 'BUY',
        'outcome': 'No',
        'price': 0.81,
        'size': 150000,
        'trader_address': '0x43372356634781eea88d61bbdd7824cdce958882', # Needs proper value if known, but this is a placeholder
        'name': 'SwissMiss',
        'wallet_age_str': '1y 7mo',
        'open_positions_count': 63
    }

    tweet_text = """US strikes Iran by February 28, 2026?

🔴 BUY No @ 81.0%
Traded: $121,500 💵

SwissMiss 🔥
Wallet age: 1y 7mo"""
    
    # Actually, TwitterService.post_custom_tweet could work. Let's see its methods.
