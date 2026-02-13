"""
Content Discovery Bot Configuration
Monitors TikTok and Instagram for potential viral content.
"""

import os
import sys
from dotenv import load_dotenv

# Set encoding for all I/O operations
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Load environment variables
# Try .env.test first (often used in this repo)
env_test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env.test")
if os.path.exists(env_test_path):
    print(f"Loading config from {env_test_path}")
    load_dotenv(env_test_path)
else:
    # Fallback to standard search
    load_dotenv()


class Config:
    """Configuration for Content Discovery Bot."""
    
    # Environment
    APP_ENV = os.getenv("APP_ENV", "local")
    
    # Telegram
    # Always try INT token first as it's the intended one for this bot in this context
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_INT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    
    if not TELEGRAM_TOKEN:
        print("⚠️ Warning: TELEGRAM_TOKEN/TELEGRAM_INT_TOKEN is missing from environment!")
    
    # Allowed users (comma-separated)
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
    
    # TikTok credentials
    TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "yehonatancohen976")
    TIKTOK_PASSWORD = os.getenv("TIKTOK_PASSWORD", "")
    
    # Instagram credentials
    INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_CD_USERNAME", "cheetah.5609688")
    INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_CD_PASSWORD", "")
    
    # Scheduling
    DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "8"))  # 8 AM
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Jerusalem")
    
    # Engagement thresholds
    HIT_THRESHOLD = float(os.getenv("HIT_THRESHOLD", "1.5"))  # 1.5x baseline = potential hit
    VIDEO_AGE_HOURS = int(os.getenv("VIDEO_AGE_HOURS", "48"))  # Check videos from last 24h
    BASELINE_POSTS_COUNT = int(os.getenv("BASELINE_POSTS_COUNT", "20"))  # Posts to calculate baseline
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    CACHE_FILE = os.path.join(DATA_DIR, "cache.json")
    BASELINE_CACHE_FILE = os.path.join(DATA_DIR, "baseline_cache.json")
    FOLLOWING_CACHE_FILE = os.path.join(DATA_DIR, "following_cache.json")
    
    # Session storage
    SESSION_DIR = os.path.join(BASE_DIR, "sessions")
    TIKTOK_COOKIES_FILE = os.path.join(SESSION_DIR, "tiktok_cookies.json")
    INSTAGRAM_SESSION_FILE = os.path.join(SESSION_DIR, "instagram_session.json")
    
    # Rate limiting (delays in seconds)
    REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "2.0"))
    REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "5.0"))
    
    # Israeli media sources to monitor
    MEDIA_SOURCES = [
        {
            "name": "Secret Tel Aviv",
            "url": "https://secrettelaviv.com/",
            "type": "scrape",
            "keywords": ["party", "festival", "dj", "rave", "club", "טראנס", "מסיבה"]
        },
        {
            "name": "Ynet Entertainment",
            "url": "https://www.ynet.co.il/entertainment",
            "type": "scrape", 
            "keywords": ["מסיבה", "DJ", "פסטיבל", "טראנס", "אלקטרוני"]
        }
    ]
    
    # Categories and their keywords
    CATEGORY_KEYWORDS = {
        "release": ["release", "new track", "premiere", "out now", "שיר חדש", "יצא"],
        "unreleased": ["unreleased", "ID", "teaser", "preview", "snippet", "לא יצא"],
        "festival": ["festival", "event", "פסטיבל", "אירוע", "הופעה"],
        "viral": ["fail", "funny", "viral", "crazy", "insane", "מטורף"],
        "israeli_dj": []  # Will be populated with Israeli DJ names
    }
    
    # Known Israeli DJs (for categorization)
    ISRAELI_DJS = [
        "infected mushroom", "astrix", "vini vici", "blastoyz", "ace ventura",
        "captain hook", "berg", "xerox", "volcano", "reality test", "symphonix",
        "generic", "omiki", "paz", "skazi", "yahel", "offer nissim", "guy gerber"
    ]
    
    @staticmethod
    def get_allowed_user_ids():
        """Get all allowed user IDs."""
        return Config.ALLOWED_USER_IDS
    
    @staticmethod
    def ensure_dirs():
        """Create necessary directories."""
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.SESSION_DIR, exist_ok=True)
