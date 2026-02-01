"""
Configuration for Instagram Stories automation project.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Environment
    APP_ENV = os.getenv("APP_ENV", "local")

    # Telegram - Uses separate bot token for Instagram Stories
    # This allows running both bots independently
    if APP_ENV == "production":
        TELEGRAM_TOKEN = os.getenv("IG_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    else:
        TELEGRAM_TOKEN = os.getenv("IG_TELEGRAM_INT_TOKEN") or os.getenv("IG_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_TOKEN")


    # Allowed users (comma-separated list)
    _raw_allowed_user_id = os.getenv("ALLOWED_USER_ID")
    if not _raw_allowed_user_id:
        ALLOWED_USER_ID = None
    else:
        try:
            ALLOWED_USER_ID = int(_raw_allowed_user_id)
        except ValueError as exc:
            raise ValueError("ALLOWED_USER_ID must be an integer.") from exc

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

    @staticmethod
    def get_allowed_user_ids():
        """Get all allowed user IDs (combines single and multiple configs)."""
        user_ids = set()
        if Config.ALLOWED_USER_ID:
            user_ids.add(Config.ALLOWED_USER_ID)
        user_ids.update(Config.ALLOWED_USER_IDS)
        return list(user_ids)

    # Instagram Credentials
    INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
    INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
    INSTAGRAM_SESSION_FILE = os.getenv("INSTAGRAM_SESSION_FILE", "instagram_session.json")

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    TEMP_DIR = os.path.join(BASE_DIR, "temp")
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
    # Database
    DATABASE_PATH = os.path.join(DATA_DIR, "scheduled_stories.db")

    # Fonts
    FONT_BOLD = os.getenv("FONT_PATH", "/usr/share/fonts/truetype/custom/Rubik-ExtraBold.ttf")
    
    # Story Settings
    STORY_SIZE = (1080, 1920)
    
    # Link sticker position (bottom center)
    LINK_STICKER_X = 0.5  # Center horizontally
    LINK_STICKER_Y = 0.85  # Near bottom
    LINK_STICKER_WIDTH = 0.7
    LINK_STICKER_HEIGHT = 0.1

    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.ASSETS_DIR, exist_ok=True)
