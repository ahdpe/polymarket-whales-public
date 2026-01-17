
import sys
import os
sys.path.append(os.getcwd())

from services.twitter_service import TwitterService, get_twitter_settings

def test_logic():
    ts = TwitterService()
    # Mock data for $787 trade
    trade_data = {
        'price': 0.5,
        'size': 1574, # 0.5 * 1574 = 787
        'value_usd': 787,
        'side': 'BUY',
        'wallet_age_str': '<1h',  # specific insider trigger
        'open_positions_count': 1,
        'category': 'other'
    }
    
    # Reload settings to be sure
    t_settings = get_twitter_settings()
    print("Settings:", t_settings)
    
    wants, reason = ts.wants_trade(trade_data)
    print(f"Trade $787: Wants={wants}, Reason={reason}")
    
    # Mock data for $96k trade
    trade_data_96 = {
        'price': 0.9,
        'size': 100000, 
        'value_usd': 96000,
        'side': 'BUY',
        'wallet_age_str': '<1h',
        'open_positions_count': 1,
        'category': 'other'
    }
    wants_96, reason_96 = ts.wants_trade(trade_data_96)
    print(f"Trade $96k: Wants={wants_96}, Reason={reason_96}")

if __name__ == "__main__":
    test_logic()
