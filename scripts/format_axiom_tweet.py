# PUBLIC SHELL VERSION
import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.twitter_service import TwitterService

async def main():
    pass
if __name__ == '__main__':
    asyncio.run(main())