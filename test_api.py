# PUBLIC SHELL VERSION
import asyncio
import json
from storage.alerts_storage import get_recent_published
alerts = get_recent_published(5)
print(json.dumps(alerts, indent=2))