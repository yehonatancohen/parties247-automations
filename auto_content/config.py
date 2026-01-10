import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID")) # אבטחה: שרק אתה תוכל להפעיל
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Paths
    # Use the assets directory relative to this config file (inside auto_content)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    OUTPUT_DIR = "output"
    TEMP_DIR = "temp"
    WOOD_IMAGE_PATH = os.path.join(ASSETS_DIR, "wood_sign.png")
    
    # Fonts
    # Switched to Heebo temporarily because the provided Rubik-Bold.ttf is a Variable Font
    # which Pillow loads as "Light". Heebo is a static bold font and works correctly.
    FONT_BOLD = os.path.join(ASSETS_DIR, "fonts", "Heebo-Bold.ttf")
    FONT_REGULAR = os.path.join(ASSETS_DIR, "fonts", "Heebo-Bold.ttf")

    # Video Settings
    VIDEO_SIZE = (1080, 1920)
    
    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)