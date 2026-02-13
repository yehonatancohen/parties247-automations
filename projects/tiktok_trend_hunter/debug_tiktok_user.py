
import asyncio
import sys
import os
from TikTokApi import TikTokApi

# Ensure ProactorEventLoop is used on Windows for Playwright compatibility
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def inspect_user_object(username):
    print(f"[*] Inspecting User object for: {username}")
    async with TikTokApi() as api:
        await api.create_sessions(num_sessions=1, sleep_after=3)
        user = api.user(username)
        print("Attributes of User object:")
        try:
            # We need to await info() to ensure the object is populated if it's lazy, 
            # though usually the object wrapper exists immediately.
            # But let's just print dir(user)
            print(dir(user))
        except Exception as e:
            print(f"Error inspecting: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_tiktok_user.py <username>")
    else:
        asyncio.run(inspect_user_object(sys.argv[1]))
