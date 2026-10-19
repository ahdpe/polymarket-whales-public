# PUBLIC SHELL VERSION
"""Send insider messages without treating an unconfirmed request as published."""
import asyncio
import logging
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNotFound, TelegramRetryAfter, TelegramUnauthorizedError
from storage import insider_delivery as delivery
logger = logging.getLogger(__name__)

async def send(bot, channel_id, text, publication, *, cooldown_hours=24):
    pass
