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
    VIDEO_AGE_HOURS = int(os.getenv("VIDEO_AGE_HOURS", "48"))  # Check videos from last N hours
    BASELINE_POSTS_COUNT = int(os.getenv("BASELINE_POSTS_COUNT", "20"))  # Posts to calculate baseline

    # Potential-hit scoring (new composite score)
    POTENTIAL_HIT_THRESHOLD = float(os.getenv("POTENTIAL_HIT_THRESHOLD", "0.55"))
    SMALL_CREATOR_FOLLOWER_CAP = int(os.getenv("SMALL_CREATOR_FOLLOWER_CAP", "20000"))
    MID_CREATOR_FOLLOWER_CAP = int(os.getenv("MID_CREATOR_FOLLOWER_CAP", "100000"))
    VELOCITY_LOG_DIVISOR = float(os.getenv("VELOCITY_LOG_DIVISOR", "2.5"))
    REACH_LOG_DIVISOR = float(os.getenv("REACH_LOG_DIVISOR", "6.0"))

    # Israeli detection
    HEBREW_CHAR_RATIO_THRESHOLD = float(os.getenv("HEBREW_CHAR_RATIO_THRESHOLD", "0.15"))
    ISRAELI_SIGNAL_THRESHOLD = float(os.getenv("ISRAELI_SIGNAL_THRESHOLD", "2.0"))

    # Hashtag discovery
    ENABLE_HASHTAG_DISCOVERY = os.getenv("ENABLE_HASHTAG_DISCOVERY", "1") == "1"
    DISCOVERY_VIDEOS_PER_HASHTAG = int(os.getenv("DISCOVERY_VIDEOS_PER_HASHTAG", "15"))
    DISCOVERY_MAX_HASHTAGS_PER_RUN = int(os.getenv("DISCOVERY_MAX_HASHTAGS_PER_RUN", "8"))
    DISCOVERY_CONCURRENCY = int(os.getenv("DISCOVERY_CONCURRENCY", "2"))
    
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
    
    # Known Israeli DJs (for categorization & Israeli-signal scoring)
    ISRAELI_DJS = [
        "infected mushroom", "astrix", "vini vici", "blastoyz", "ace ventura",
        "captain hook", "berg", "xerox", "volcano", "reality test", "symphonix",
        "generic", "omiki", "paz", "skazi", "yahel", "offer nissim", "guy gerber",
        "keren peles", "static & ben el", "noy alooshe", "ran harel",
        "guy scheiman", "itay kalderon",
    ]

    # Non-DJ Israeli creators allowlist (TikTok/IG usernames, lowercased)
    ISRAELI_CREATORS: list = []

    # Israeli venues (nightclubs, festival spots) — matched as substrings in caption/hashtags
    ISRAELI_VENUES = [
        "haoman 17", "haoman17", "forum tlv", "forum tel aviv",
        "the block", "block tlv", "gagarin", "shablul", "pacha tlv",
        "teder", "kuli alma", "alphabet", "breakfast club",
        "radio epgb", "clara", "phi beach tlv",
    ]

    # Israeli cities (English + Hebrew forms)
    ISRAELI_CITIES = [
        "tel aviv", "tel-aviv", "telaviv", "jerusalem", "eilat", "haifa",
        "herzliya", "ashdod", "netanya", "beer sheva",
        "תל אביב", "תל־אביב", "ירושלים", "אילת", "חיפה", "הרצליה", "ראשון לציון",
    ]

    # Hebrew hashtags commonly used in Israeli nightlife/party content
    ISRAELI_HASHTAGS_HE = [
        "מסיבה", "מסיבות", "טראנס", "פסיטרנס", "פסיכדלי", "פסטיבל",
        "מועדון", "תלאביב", "תל_אביב", "ירושלים", "אילת", "חיפה",
        "דיגיי", "דיג׳יי", "רייב", "טכנו", "האומן17", "לילה",
        "חיינייט", "ישראל", "נייטלייף", "קליפ", "מיקס", "סט",
    ]

    # Latin-alphabet hashtags for Israeli nightlife content
    ISRAELI_HASHTAGS_EN = [
        "telaviv", "telavivnightlife", "israelparty", "israelnightlife",
        "haoman17", "forumtlv", "tlvnights", "blocktlv", "pachatlv",
        "gagarintlv", "shablultlv",
    ]

    # Hashtags used to crawl for new Israeli creators (curated subset)
    DISCOVERY_HASHTAGS = [
        "מסיבה", "טראנס", "פסטיבל", "רייב", "תלאביב",
        "telaviv", "telavivnightlife", "israelnightlife", "haoman17",
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
