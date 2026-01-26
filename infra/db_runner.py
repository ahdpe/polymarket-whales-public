"""
Database operation runner with optional async offloading and timeout support.

Feature flags (via config):
- DB_ASYNC_OFFLOAD: 0=sync (default), 1=async via asyncio.to_thread
- DB_TIMEOUT_SEC: Timeout for async operations (default: 5)
- DB_LOG_SLOW_SEC: Log threshold for slow operations (default: 1.0)
"""
import asyncio
import logging
import time
from typing import Callable, Any

from config import DB_ASYNC_OFFLOAD, DB_TIMEOUT_SEC, DB_LOG_SLOW_SEC

logger = logging.getLogger(__name__)


async def run_db(
    fn: Callable,
    *args,
    timeout: float = None,
    op_name: str = ""
) -> Any:
    """
    Execute database operation with optional async offloading and timeout.
    
    Args:
        fn: Synchronous function to execute
        *args: Arguments to pass to fn
        timeout: Timeout in seconds (defaults to DB_TIMEOUT_SEC from config)
        op_name: Operation name for logging (e.g., "get_user", "save_trade")
    
    Returns:
        Result of fn(*args)
    
    Raises:
        asyncio.TimeoutError: If operation times out (only when DB_ASYNC_OFFLOAD=1)
        Any exception raised by fn: Re-raised after logging
    """
    if timeout is None:
        timeout = DB_TIMEOUT_SEC
    
    start_time = time.time()
    
    try:
        if DB_ASYNC_OFFLOAD == 1:
            # Execute in thread pool with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(fn, *args),
                timeout=timeout
            )
        else:
            # Execute synchronously (default behavior, no change)
            result = fn(*args)
        
        # Check if operation was slow
        latency = time.time() - start_time
        if latency > DB_LOG_SLOW_SEC:
            log_level = logger.warning if latency > DB_LOG_SLOW_SEC * 2 else logger.debug
            log_level(f"db_slow op={op_name} latency={latency:.3f}s")
        
        return result
    
    except asyncio.TimeoutError:
        latency = time.time() - start_time
        logger.error(f"db_timeout op={op_name} timeout={timeout:.1f}s latency={latency:.3f}s")
        raise
    
    except Exception as e:
        latency = time.time() - start_time
        logger.error(f"db_error op={op_name} err={type(e).__name__}: {e} latency={latency:.3f}s")
        raise
