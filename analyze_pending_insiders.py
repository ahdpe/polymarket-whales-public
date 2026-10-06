# PUBLIC SHELL VERSION
"""
Анализ скопившихся позиций инсайдеров и проверка, почему они не публикуются.
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
sys.path.append(os.getcwd())
from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage
from core.categories import detect_category

def format_number(num):
    """Форматирование чисел для вывода."""
    pass

def check_filter_reason(service: InsiderAlertsService, scenario: str, market_id: str, category: str) -> Dict[str, Any]:
    """
    Детальная проверка, почему позиция не проходит фильтры.
    Возвращает словарь с результатами проверки каждого фильтра.
    """
    pass

async def analyze_all_pending():
    """Анализ всех скопившихся позиций."""
    pass
if __name__ == '__main__':
    asyncio.run(analyze_all_pending())