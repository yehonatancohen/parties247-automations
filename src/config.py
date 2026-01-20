import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Environment
    APP_ENV = os.getenv("APP_ENV", "local")

    # Telegram
    if APP_ENV == "production":
        TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    else:
        TELEGRAM_TOKEN = os.getenv("TELEGRAM_INT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

    _raw_allowed_user_id = os.getenv("ALLOWED_USER_ID")
    if not _raw_allowed_user_id:
        ALLOWED_USER_ID = None
    else:
        try:
            ALLOWED_USER_ID = int(_raw_allowed_user_id)
        except ValueError as exc:
            raise ValueError("ALLOWED_USER_ID must be an integer.") from exc
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Paths
    # Use the assets directory relative to this config file (inside auto_content)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    TEMP_DIR = os.path.join(BASE_DIR, "temp")
    WOOD_IMAGE_PATH = os.path.join(ASSETS_DIR, "wood_sign.png")
    # Ready-to-use overlay template (User provided)
    READY_OVERLAY_PATH = os.path.join(ASSETS_DIR, "overlay_template.png")
    
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
