import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID")) # אבטחה: שרק אתה תוכל להפעיל

    # Paths
    ASSETS_DIR = "assets"
    OUTPUT_DIR = "output"
    TEMP_DIR = "temp"
    WOOD_IMAGE_PATH = os.path.join(ASSETS_DIR, "wood_sign.png")
    
    # Fonts
    FONT_BOLD = os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf")
    # FONT_REGULAR = os.path.join(ASSETS_DIR, "fonts", "Heebo-Regular.ttf") # We'll use bold for both as requested, or keep regular if needed. User asked for "rubik bold" so I'll set bold to rubik.
    FONT_REGULAR = os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf") # Using Rubik Bold for body too per request "use rubik bold as font" (singular)

    # Video Settings
    VIDEO_SIZE = (1080, 1920)
    
    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)