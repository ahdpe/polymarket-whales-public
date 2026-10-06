# PUBLIC SHELL VERSION
import sys
import os
import logging
logging.basicConfig(level=logging.INFO)
sys.path.append(os.getcwd())
from services.insider_alerts import InsiderAlertsService
from storage import alerts_storage
print(f'DB Path in module: {alerts_storage.DB_PATH}')
service = InsiderAlertsService()
print('Service initialized.')
status = service.get_status()
print(f'Service Settings: min={status.get('probability_min')}, max={status.get('probability_max')}')
val = alerts_storage.get_setting('probability_min')
print(f"Direct DB get('probability_min'): {val}")