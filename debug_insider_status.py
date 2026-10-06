# PUBLIC SHELL VERSION
import asyncio
import sys
import os
import json
from datetime import datetime
sys.path.append(os.getcwd())
from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage

async def check_status():
    pass
if __name__ == '__main__':
    asyncio.run(check_status())