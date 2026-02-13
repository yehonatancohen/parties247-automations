import asyncio
import os
import sys
from TikTokApi import TikTokApi
from dotenv import load_dotenv

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

# Load environment
env_path = os.path.join(PROJECT_ROOT, '.env.test')
if os.path.exists(env_path):
    load_dotenv(env_path)

async def debug_user_obj(username):
    async with TikTokApi() as api:
        await api.create_sessions(ms_tokens=[os.getenv("MS_TOKEN")], num_sessions=1, sleep_after=3)
        user = api.user(username)
        with open("user_debug.txt", "w") as f:
            f.write(f"Attributes for User '{username}':\n")
            for attr in dir(user):
                f.write(f"  - {attr}\n")
            
            # Try to get info to see if that works
            try:
                info = await user.info()
                f.write("\nUser Info Keys:\n")
                f.write(", ".join(info.keys()))
            except Exception as e:
                f.write(f"\nError getting info: {e}\n")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(debug_user_obj("yehonatancohen976"))
