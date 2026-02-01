import os
import sys
import base64
from dotenv import load_dotenv

# Force load .env.test
print("📂 Loading .env.test...")
load_dotenv('.env.test', override=True)

# Add project path to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_src = os.path.join(current_dir, 'projects', 'video_creator', 'src')
sys.path.append(project_src)

from services.instagram_auth import InstagramAuth

def debug_auth():
    print("\n🔍 --- Debugging Instagram Auth ---")
    
    # Check Env Var
    cookies_env = os.environ.get('INSTAGRAM_COOKIES')
    if not cookies_env:
        print("❌ INSTAGRAM_COOKIES environment variable is EMPTY or NOT SET.")
        return
    
    print(f"✅ INSTAGRAM_COOKIES found. Length: {len(cookies_env)} chars")
    print(f"   First 50 chars: {cookies_env[:50]}...")
    
    # Try Decoding (mimic logic)
    content = cookies_env
    try:
        decoded = base64.b64decode(cookies_env).decode('utf-8')
        content = decoded
        print("✅ Detected Base64 encoding. Decoded successfully.")
    except:
        print("ℹ️  Not Base64 or failed decode, treating as raw text.")
    
    # Try Parsing
    print("\nParsing Cookies...")
    auth = InstagramAuth()
    cookies = auth._parse_netscape_cookies(content)
    
    print(f"🍪 Parsed {len(cookies)} cookies.")
    
    if 'sessionid' in cookies:
        print("✅ Found 'sessionid' cookie.")
    else:
        print("❌ MISSING 'sessionid' cookie!")
        
    if 'ds_user_id' in cookies:
        print("✅ Found 'ds_user_id' cookie.")
    else:
        print("❌ MISSING 'ds_user_id' cookie!")

    # Attempt Login
    print("\n🔐 Attempting Login Simulation...")
    if auth._load_cookies_from_env():
        print("🚀 SUCCESS: Cookies loaded and session created!")
    else:
        print("❌ FAILURE: _load_cookies_from_env returned False.")

if __name__ == "__main__":
    debug_auth()
