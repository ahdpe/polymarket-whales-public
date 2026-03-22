# PUBLIC SHELL VERSION
"""Republish an insider alert that was blocked due to missing channel_id."""
import asyncio
import sys
from storage import alerts_storage
from services.insider_alerts import InsiderAlertsService, get_insider_alerts_service
from services.polymarket import PolymarketService
from services.telegram_service import bot as telegram_bot

async def republish_alert(market_id: str, scenario: str='BURST'):
    """Republish a specific alert."""
    pass
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python republish_alert.py <market_id> [scenario]')
        print('Example: python republish_alert.py 0x46d40e851b24d9b0af4bc1942ccd86439cae82a9011767da14950df0ad997adf BURST')
        sys.exit(1)
    market_id = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else 'BURST'
    asyncio.run(republish_alert(market_id, scenario))