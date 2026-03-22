import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.twitter_service import get_twitter_service

async def check():
    svc = get_twitter_service()
    if not svc:
        print("Twitter service not configured (missing keys).")
        return
        
    print("Checking Twitter API...")
    try:
        # Run in executor to avoid blocking, get the authenticated user's info
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: svc.client.get_me()
        )
        if response.data:
            print(f"✅ API is working. Authenticated as: @{response.data.username} (ID: {response.data.id})")
        else:
            print("❌ API responded, but could not get user data.")
    except Exception as e:
        print(f"❌ API Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
