import os
import sys
from dotenv import load_dotenv

# Set encoding for all I/O operations
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Load environment variables
# Try .env.test first
env_test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env.test")
if os.path.exists(env_test_path):
    print(f"Loading config from {env_test_path}")
    load_dotenv(env_test_path)
else:
    load_dotenv()

class Config:
    # Environment
    APP_ENV = os.getenv("APP_ENV", "local")

    # Telegram
    if APP_ENV == "production":
        TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    else:
        TELEGRAM_TOKEN = os.getenv("TELEGRAM_INT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

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
        os.makedirs(Config.INSTAGRAM_SESSION_DIR, exist_ok=True)
