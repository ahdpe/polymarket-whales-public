# PUBLIC SHELL VERSION
import asyncio
import logging
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
config.QUEUE_MAX_SIZE = 1000
config.WORKER_COUNT = 1
config.GLOBAL_RATE = 100
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from services import telegram_service
from unittest.mock import MagicMock, AsyncMock
telegram_service.PER_CHAT_RATE = 0.5
telegram_service.QUEUE_MAX_SIZE = 1000
telegram_service.WORKER_COUNT = 1
telegram_service.bot = AsyncMock()
telegram_service.bot.send_message = AsyncMock()
telegram_service.is_bot_enabled = lambda: True
telegram_service.is_user_active = lambda cid: True
telegram_service._is_muted = lambda cid: (False, 0)
telegram_service.get_user_min_threshold = lambda cid: 0

async def test_queue_blocking():
    pass
if __name__ == '__main__':
    asyncio.run(test_queue_blocking())