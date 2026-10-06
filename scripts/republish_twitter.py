# PUBLIC SHELL VERSION
import asyncio
import json
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.utils import polymarket_event_url
from services.twitter_service import get_twitter_service
logging.basicConfig(level=logging.INFO)

async def main():
    pass
if __name__ == '__main__':
    asyncio.run(main())