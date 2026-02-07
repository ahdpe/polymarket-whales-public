import asyncio
import logging
import sys
import os
import time

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config
import config
config.QUEUE_MAX_SIZE = 1000
config.WORKER_COUNT = 1  # Use 1 worker to easily demonstrate blocking
config.GLOBAL_RATE = 100
# config.PER_CHAT_RATE = 0.5  # This won't work if already imported

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock objects
from services import telegram_service
from unittest.mock import MagicMock, AsyncMock

# Patch constants
telegram_service.PER_CHAT_RATE = 0.5
telegram_service.QUEUE_MAX_SIZE = 1000
telegram_service.WORKER_COUNT = 1

# Mock bot
telegram_service.bot = AsyncMock()
telegram_service.bot.send_message = AsyncMock()
telegram_service.is_bot_enabled = lambda: True
telegram_service.is_user_active = lambda cid: True
telegram_service._is_muted = lambda cid: (False, 0)
telegram_service.get_user_min_threshold = lambda cid: 0

async def test_queue_blocking():
    logger.info("🚀 Starting Queue Blocking Verification")
    
    # Initialize queue
    telegram_service._aiolimiter_available = True
    telegram_service.start_queue_workers()
    
    # User A (Slow) - fills queue
    slow_user_id = 111
    # User B (Fast) - should be processed quickly
    fast_user_id = 222
    
    logger.info(f"enqueueing 5 tasks for Slow User {slow_user_id}...")
    for i in range(5):
        await telegram_service.enqueue_trade_alert(
            chat_id=slow_user_id,
            message_text=f"Slow Message {i}",
            bypass_filters=True
        )
    
    logger.info(f"enqueueing 1 task for Fast User {fast_user_id}...")
    start_time = time.time()
    await telegram_service.enqueue_trade_alert(
        chat_id=fast_user_id,
        message_text="FAST MESSAGE",
        bypass_filters=True
    )
    
    # Wait for processing
    logger.info("Waiting for tasks to be processed...")
    
    # We poll the mock to see when Fast User message is sent
    fast_sent_time = None
    max_wait = 10
    
    while time.time() - start_time < max_wait:
        # Check mock calls
        calls = telegram_service.bot.send_message.call_args_list
        for call in calls:
            if call.kwargs.get('chat_id') == fast_user_id:
                fast_sent_time = time.time()
                break
        
        if fast_sent_time:
            break
        
        await asyncio.sleep(0.1)
    
    # Stop workers
    await telegram_service.stop_queue_workers()
    
    if fast_sent_time:
        duration = fast_sent_time - start_time
        logger.info(f"✅ Fast user message sent in {duration:.2f} seconds")
        
        # With 1 worker and 5 slow tasks (each taking 2s), without fix it would take > 2s (likely > 10s for all).
        # With fix, it should be fast (re-queuing slow tasks).
        # First slow task takes 0s (sends immediately).
        # Second slow task waits 2s.
        # Worker checks delay, re-queues.
        # Worker picks up next. 
        # Ideally Fast task is picked up.
        
        if duration < 2.0:
            logger.info("✅ SUCCESS: Queue unblocked! Fast message sent quickly.")
        else:
            logger.warning("⚠️ WARNING: Fast message took longer than expected.")
    else:
        logger.error("❌ FAILURE: Fast user message NOT sent within timeout.")

if __name__ == "__main__":
    asyncio.run(test_queue_blocking())
