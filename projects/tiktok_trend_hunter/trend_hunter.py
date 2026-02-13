import os
import sys
import time
import random
import schedule
import requests
import yt_dlp
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURATION
# ==========================================

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
env_test_path = os.path.join(project_root, '.env.test')
env_path = os.path.join(project_root, '.env')

if os.path.exists(env_test_path):
    load_dotenv(env_test_path)
    logger.info(f"Loaded configuration from {env_test_path}")
elif os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f"Loaded configuration from {env_path}")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_INT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("ALLOWED_USER_ID")
USERS_FILE = os.path.join(current_dir, "users.txt")
VIDEO_FETCH_LIMIT = 30

# ==========================================
# CORE LOGIC
# ==========================================

def get_target_users():
    """Reads users from users.txt."""
    if not os.path.exists(USERS_FILE):
        logger.warning(f"Users file not found: {USERS_FILE}")
        return []
    
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def fetch_videos_yt_dlp(username):
    """
    Fetch recent videos for a user using yt-dlp.
    Returns a list of video dicts.
    """
    # Random sleep to avoid rapid-fire requests
    time.sleep(random.uniform(2, 5))
    
    url = f"https://www.tiktok.com/@{username}"
    # Reduced timeout to fail faster on hangs
    ydl_opts = {
        'extract_flat': 'in_playlist',  # Fast extraction (metadata only)
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'playlistend': VIDEO_FETCH_LIMIT, # Limit to most recent videos
        'socket_timeout': 10,             # Fail fast if connection hangs
        'retries': 3,                     # Retry automatically by yt-dlp
    }

    # Manual retry loop for robustness
    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)
            
            if not result:
                return []
                
            entries = result.get('entries', [])
            # entries can be a lazy iterator, force list
            return list(entries)
            
        except Exception as e:
            logger.error(f"Error fetching {username} (attempt {attempt+1}): {e}")
            time.sleep(5)
            
    return []

def score_video(video, baseline_avg_engagement):
    """
    Scores a video based on engagement ratio and content.
    Returns a score tuple: (final_score, engagement_ratio, content_bonus)
    """
    # Stats from yt-dlp entry (might vary by extractor version, but usually in 'view_count', etc.)
    views = video.get('view_count', 0)
    likes = video.get('like_count', 0)
    comments = video.get('comment_count', 0)
    shares = video.get('repost_count', 0) or video.get('share_count', 0)
    
    total_engagement = (likes or 0) + (comments or 0) + (shares or 0)
    engagement_rate = total_engagement / views if views > 0 else 0
    
    # Engagement Score (Ratio vs User average)
    engagement_ratio = engagement_rate / baseline_avg_engagement if baseline_avg_engagement > 0 else 1.0
    
    # Content Score (DJ Name detection)
    description = video.get('description', '').lower()
    title = video.get('title', '').lower()
    content_bonus = 0
    
    # Look for capitalized names or "special" keywords if possible
    # For now: if there's any text in description, it's slightly better
    if description:
        # Check for multiple words starting with capitals in original title/desc if available
        # Simple heuristic: if description length > 10, count as good
        content_bonus = 0.5
        
        # Check for 'dj' or typical music names
        if 'dj' in description or 'live' in description:
            content_bonus += 0.5
            
    final_score = (engagement_ratio * 0.7) + (content_bonus * 0.3)
    return final_score, engagement_ratio, content_bonus

import concurrent.futures

def process_user_metrics(username, cutoff_time):
    """
    Worker function to fetch and process a single user.
    Returns a list of 'new_videos' that are candidates (with scores).
    """
    entries = fetch_videos_yt_dlp(username)
    if not entries:
        logger.info(f"No entries found for {username}")
        return []
    
    # Debug: Check latest video time
    latest_ts = 0
    for e in entries:
        ts = e.get('timestamp')
        if ts and ts > latest_ts:
            latest_ts = ts
    
    if latest_ts > 0:
        latest_date = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
        logger.info(f"  {username}: Last upload {latest_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    else:
        logger.info(f"  {username}: No timestamped videos found.")
        
    # Separate "New" (last 24h) from "Old" (baseline)
    new_videos = []
    old_engagements = []
    
    for entry in entries:
        ts = entry.get('timestamp')
        if not ts: continue
        
        upload_time = datetime.fromtimestamp(ts, tz=timezone.utc)
        
        # Calculate engagement rate for baseline
        views = entry.get('view_count', 0)
        if views > 0:
            likes = entry.get('like_count', 0) or 0
            comments = entry.get('comment_count', 0) or 0
            shares = entry.get('repost_count', 0) or entry.get('share_count', 0) or 0
            er = (likes + comments + shares) / views
        else:
            er = 0

        if upload_time > cutoff_time:
            new_videos.append(entry)
        else:
            old_engagements.append(er)
    
    if not new_videos:
        return []
        
    # Score new videos
    avg_baseline = sum(old_engagements) / len(old_engagements) if old_engagements else 0.01
    scored_candidates = []
    
    for v in new_videos:
        score, ratio, bonus = score_video(v, avg_baseline)
        v['final_score'] = score
        v['engagement_ratio'] = ratio
        v['content_bonus'] = bonus
        v['username'] = username
        scored_candidates.append(v)
        
    return scored_candidates

def process_all_users():
    """Main scanning logic with ThreadPool."""
    users = get_target_users()
    if not users:
        logger.info("No users to scan.")
        return

    all_recent_candidates = []
    current_time = datetime.now(timezone.utc)
    cutoff_time = current_time - timedelta(hours=24)
    
    logger.info(f"Starting parallel scan for {len(users)} users (Workers: 5)...")

    # Parallelize fetching
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Dictionary to map future to username
        future_to_user = {executor.submit(process_user_metrics, user, cutoff_time): user for user in users}
        
        for future in concurrent.futures.as_completed(future_to_user):
            user = future_to_user[future]
            try:
                candidates = future.result()
                if candidates:
                    all_recent_candidates.extend(candidates)
                    logger.info(f"Found {len(candidates)} new videos for {user}")
            except Exception as exc:
                logger.error(f"{user} generated an exception: {exc}")

    # Pick Top 5
    top_5 = sorted(all_recent_candidates, key=lambda x: x['final_score'], reverse=True)[:5]
    
    if top_5:
        send_to_telegram(top_5)
    else:
        logger.info("Found no videos to recommend today.")

def send_to_telegram(videos):
    """Formates and sends results to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram config missing. Printing results instead.")
        for i, v in enumerate(videos, 1):
             print(f"{i}. @{v['username']} - Score: {v['final_score']:.2f} - https://www.tiktok.com/video/{v['id']}")
        return

    message = "🔥 **Top 5 TikTok Picks for Today** 🔥\n\n"
    
    for i, v in enumerate(videos, 1):
        url = f"https://www.tiktok.com/@{v['username']}/video/{v['id']}"
        message += (
            f"{i}. **@{v['username']}**\n"
            f"📈 Perf: `{v['engagement_ratio']:.1f}x` better\n"
            f"🔗 [Watch Video]({url})\n\n"
        )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    
    try:
        requests.post(url, json=payload).raise_for_status()
        logger.info("Sent Top 5 to Telegram.")
    except Exception as e:
        logger.error(f"Failed to send Telegram: {e}")

# ==========================================
# SCHEDULER
# ==========================================

def run_scheduler():
    logger.info("TikTok Trend Hunter Scheduler Started. Scans daily at 07:30.")
    
    # Schedule daily scan
    schedule.every().day.at("07:30").do(process_all_users)
    
    # Optional: Initial run for testing if manually triggered or debug flag
    if "--now" in sys.argv:
        logger.info("Running manual scan now...")
        process_all_users()

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    try:
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("Stopping...")
