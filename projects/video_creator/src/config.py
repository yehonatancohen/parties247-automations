import os
import sys
from dotenv import load_dotenv

# Set encoding for all I/O operations
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Load environment variables
# Try .env.test first, then .env
current_dir = os.path.dirname(os.path.abspath(__file__))
# 1: src, 2: video_creator, 3: projects, 4: root
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
env_test_path = os.path.join(root_dir, ".env.test")
env_path = os.path.join(root_dir, ".env")

if os.path.exists(env_test_path):
    print(f"[CONFIG] Loading config from {env_test_path}")
    load_dotenv(env_test_path)
elif os.path.exists(env_path):
    print(f"[CONFIG] Loading config from {env_path}")
    load_dotenv(env_path)
else:
    print(f"[CONFIG] No .env or .env.test found at {root_dir}. Relying on system environment variables.")
    load_dotenv()

# DEBUG: Print environment status (secrets masked)
print(f"[CONFIG] TELEGRAM_TOKEN found: {'YES' if os.getenv('TELEGRAM_TOKEN') else 'NO'}")
print(f"[CONFIG] TELEGRAM_INT_TOKEN found: {'YES' if os.getenv('TELEGRAM_INT_TOKEN') else 'NO'}")
print(f"[CONFIG] GEMINI_API_KEY found: {'YES' if os.getenv('GEMINI_API_KEY') else 'NO'}")

class Config:
    # Environment
    APP_ENV = os.getenv("APP_ENV", "local")

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_INT_TOKEN")
    if not TELEGRAM_TOKEN:
        print("[CONFIG] CRITICAL: TELEGRAM_TOKEN is missing!")

    # Single allowed user (for backward compatibility)
    _raw_allowed_user_id = os.getenv("ALLOWED_USER_ID")
    if not _raw_allowed_user_id:
        ALLOWED_USER_ID = None
    else:
        try:
            ALLOWED_USER_ID = int(_raw_allowed_user_id)
        except ValueError as exc:
            raise ValueError("ALLOWED_USER_ID must be an integer.") from exc
    
    # Multiple allowed users (comma-separated list)
    _raw_allowed_user_ids = os.getenv("ALLOWED_USER_IDS", "")
    ALLOWED_USER_IDS = []
    if _raw_allowed_user_ids:
        for uid in _raw_allowed_user_ids.split(","):
            uid = uid.strip()
            if uid:
                try:
                    ALLOWED_USER_IDS.append(int(uid))
                except ValueError:
                    print(f"Warning: Invalid user ID in ALLOWED_USER_IDS: {uid}")
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    @staticmethod
    def get_allowed_user_ids():
        """Get all allowed user IDs (combines single and multiple configs)."""
        user_ids = set()
        if Config.ALLOWED_USER_ID:
            user_ids.add(Config.ALLOWED_USER_ID)
        user_ids.update(Config.ALLOWED_USER_IDS)
        return list(user_ids)

    # Paths
    # Use the assets directory relative to this config file (inside auto_content)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    TEMP_DIR = os.path.join(BASE_DIR, "temp")
    # Headless pipeline (CLI / MCP): one directory per job
    JOBS_DIR = os.path.join(OUTPUT_DIR, "jobs")
    # Where media sent through Telegram lands; the only local path remote callers may use as a source
    INBOX_DIR = os.path.join(OUTPUT_DIR, "inbox")
    # 'manual' = hand the finished video to the user on Telegram. 'instagram' = Graph API (not wired yet).
    # Server-side setting on purpose: the calling model cannot change it.
    PUBLISH_MODE = os.getenv("PUBLISH_MODE", "manual")
    # Instagram API with Instagram Login (no Facebook Page needed). The token is a long-lived (60 day)
    # Instagram user token; once stored in the token file it refreshes itself, the env var is only the seed.
    IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
    # Optional second account for dry runs. IG_TARGET picks which one is used ('main' or 'test');
    # it is a server-side env var, so the calling model cannot redirect posts.
    IG_TEST_ACCESS_TOKEN = os.getenv("IG_TEST_ACCESS_TOKEN", "")
    IG_TARGET = os.getenv("IG_TARGET", "main")
    IG_GRAPH_VERSION = os.getenv("IG_GRAPH_VERSION", "v23.0")
    # Real publishing needs a one-time code sent to the owner on Telegram and typed back in the chat.
    APPROVAL_CODE_REQUIRED = os.getenv("APPROVAL_CODE_REQUIRED", "1") != "0"
    # Public base URL of the MCP server, used to build preview links, e.g. https://videos.example.com
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    WOOD_IMAGE_PATH = os.path.join(ASSETS_DIR, "wood_sign.png")
    # Ready-to-use overlay template (User provided)
    READY_OVERLAY_PATH = os.path.join(ASSETS_DIR, "overlay_template.png")
    
    # Instagram session storage
    INSTAGRAM_SESSION_DIR = os.path.join(BASE_DIR, "instagram_session")
    INSTAGRAM_COOKIES_FILE = os.path.join(INSTAGRAM_SESSION_DIR, "cookies.json")
    
    # Fonts
    # Switched to Heebo-Bold to provide a true Bold look (800 equivalent).
    FONT_BOLD = os.path.join(ASSETS_DIR, "fonts", "Rubik-ExtraBold.ttf")
    FONT_REGULAR = os.path.join(ASSETS_DIR, "fonts", "Rubik-ExtraBold.ttf")

    # Video Settings
    VIDEO_SIZE = (1080, 1920)
    
    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        os.makedirs(Config.JOBS_DIR, exist_ok=True)
        os.makedirs(Config.INBOX_DIR, exist_ok=True)
        os.makedirs(Config.INSTAGRAM_SESSION_DIR, exist_ok=True)
