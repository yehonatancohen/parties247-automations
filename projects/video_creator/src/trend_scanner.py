"""
Trend Scanner - Merged Content Discovery + TikTok Trend Hunter

A self-contained module that scans TikTok users for trending videos.
Integrates directly into the main parties247 bot.

Commands:
  /scan     - Run a manual scan now
  /add      - Add a TikTok username to monitor
  /remove   - Remove a TikTok username
  /watchlist - Show all monitored users
  /trendshelp - Show help for trend scanner
"""

import os
import sys
import random
import logging
import concurrent.futures
from datetime import datetime, timedelta, time, timezone

import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackContext,
)

logger = logging.getLogger("trend_scanner")

# ============================================================
# CONFIGURATION
# ============================================================

# Users file lives in tiktok_trend_hunter project (shared source of truth)
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
USERS_FILE = os.path.join(_project_root, "projects", "tiktok_trend_hunter", "users.txt")

# Fallback: if that doesn't exist, create one locally
if not os.path.exists(USERS_FILE):
    USERS_FILE = os.path.join(_this_dir, "trend_users.txt")
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            f.write("# TikTok usernames to monitor (one per line)\n")

VIDEO_FETCH_LIMIT = 30
SCAN_HOUR = 7
SCAN_MINUTE = 30
TIMEZONE = "Asia/Jerusalem"


# ============================================================
# USER LIST MANAGEMENT
# ============================================================

def get_target_users() -> list:
    """Reads usernames from users.txt."""
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def add_user_to_file(username: str) -> tuple:
    """Add a username to users.txt. Returns (success, message)."""
    username = username.strip().lstrip("@").lower()
    
    # Clean TikTok URLs
    if "tiktok.com/" in username:
        # Extract username from URL like tiktok.com/@username or tiktok.com/@username/video/123
        parts = username.split("tiktok.com/")
        if len(parts) > 1:
            path = parts[1].split("/")[0].split("?")[0]
            username = path.lstrip("@")
    
    if not username:
        return False, "❌ Invalid username."
    
    current = get_target_users()
    if username in current:
        return False, f"ℹ️ @{username} is already in the watchlist."
    
    with open(USERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{username}\n")
    
    return True, f"✅ Added @{username} to watchlist ({len(current) + 1} total users)."


def remove_user_from_file(username: str) -> tuple:
    """Remove a username from users.txt. Returns (success, message)."""
    username = username.strip().lstrip("@").lower()
    
    if not os.path.exists(USERS_FILE):
        return False, "❌ Users file not found."
    
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    new_lines = []
    found = False
    for line in lines:
        if line.strip().lower() == username:
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        return False, f"❌ @{username} not found in watchlist."
    
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    return True, f"✅ Removed @{username} from watchlist."


# ============================================================
# TIKTOK SCANNING (yt-dlp based, from trend_hunter)
# ============================================================

def fetch_videos_yt_dlp(username: str) -> list:
    """Fetch recent videos for a user using yt-dlp."""
    import time as _time
    _time.sleep(random.uniform(2, 5))
    
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp not installed")
        return []
    
    url = f"https://www.tiktok.com/@{username}"
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'playlistend': VIDEO_FETCH_LIMIT,
        'socket_timeout': 10,
        'retries': 3,
    }

    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)
            if not result:
                return []
            entries = result.get('entries', [])
            return list(entries)
        except Exception as e:
            logger.error(f"Error fetching {username} (attempt {attempt+1}): {e}")
            import time as _time
            _time.sleep(5)
    return []


def score_video(video: dict, baseline_avg: float) -> tuple:
    """Score a video based on engagement vs baseline."""
    views = video.get('view_count', 0) or 0
    likes = video.get('like_count', 0) or 0
    comments = video.get('comment_count', 0) or 0
    shares = video.get('repost_count', 0) or video.get('share_count', 0) or 0
    
    total_engagement = likes + comments + shares
    engagement_rate = total_engagement / views if views > 0 else 0
    engagement_ratio = engagement_rate / baseline_avg if baseline_avg > 0 else 1.0
    
    description = (video.get('description', '') or '').lower()
    content_bonus = 0
    if description:
        content_bonus = 0.5
        if 'dj' in description or 'live' in description:
            content_bonus += 0.5
    
    final_score = (engagement_ratio * 0.7) + (content_bonus * 0.3)
    return final_score, engagement_ratio, content_bonus


def process_user(username: str, cutoff_time) -> list:
    """Fetch and score videos for a single user."""
    entries = fetch_videos_yt_dlp(username)
    if not entries:
        return []
    
    new_videos = []
    old_engagements = []
    
    for entry in entries:
        ts = entry.get('timestamp')
        if not ts:
            continue
        
        upload_time = datetime.fromtimestamp(ts, tz=timezone.utc)
        views = entry.get('view_count', 0) or 0
        
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
    
    avg_baseline = sum(old_engagements) / len(old_engagements) if old_engagements else 0.01
    scored = []
    
    for v in new_videos:
        final, ratio, bonus = score_video(v, avg_baseline)
        v['final_score'] = final
        v['engagement_ratio'] = ratio
        v['content_bonus'] = bonus
        v['username'] = username
        scored.append(v)
    
    return scored


def run_full_scan() -> list:
    """
    Scan all monitored users and return top scoring videos.
    Returns list of scored video dicts, sorted by score.
    """
    users = get_target_users()
    if not users:
        return []
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    all_candidates = []
    
    logger.info(f"Scanning {len(users)} users...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_user, user, cutoff): user for user in users}
        for future in concurrent.futures.as_completed(futures):
            user = futures[future]
            try:
                candidates = future.result()
                if candidates:
                    all_candidates.extend(candidates)
                    logger.info(f"Found {len(candidates)} new videos for {user}")
            except Exception as exc:
                logger.error(f"{user}: {exc}")
    
    all_candidates.sort(key=lambda x: x.get('final_score', 0), reverse=True)
    return all_candidates


def format_scan_results(videos: list, limit: int = 10) -> str:
    """Format scan results as a Telegram message."""
    if not videos:
        return "📭 No trending videos found in the last 24 hours."
    
    top = videos[:limit]
    lines = [f"🔥 *Top {len(top)} Trending Videos* 🔥\n"]
    
    for i, v in enumerate(top, 1):
        username = v.get('username', '?')
        video_id = v.get('id', '')
        views = v.get('view_count', 0) or 0
        ratio = v.get('engagement_ratio', 0)
        url = f"https://www.tiktok.com/@{username}/video/{video_id}"
        desc = (v.get('description', '') or '')[:60]
        
        lines.append(
            f"{i}. *@{username}*\n"
            f"   📈 {ratio:.1f}x avg engagement | 👁 {views:,} views\n"
            f"   {desc}\n"
            f"   [Watch]({url})\n"
        )
    
    total_users = len(get_target_users())
    lines.append(f"\n📊 Scanned {total_users} users | Found {len(videos)} new videos")
    
    return "\n".join(lines)


# ============================================================
# TELEGRAM COMMAND HANDLERS
# ============================================================

def _is_allowed(user_id: int) -> bool:
    """Check if user is allowed."""
    allowed_id = os.getenv("ALLOWED_USER_ID")
    allowed_ids = os.getenv("ALLOWED_USER_IDS", "")
    
    allowed = set()
    if allowed_id:
        try:
            allowed.add(int(allowed_id))
        except ValueError:
            pass
    for uid in allowed_ids.split(","):
        uid = uid.strip()
        if uid:
            try:
                allowed.add(int(uid))
            except ValueError:
                pass
    
    return not allowed or user_id in allowed


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan - run a trend scan now."""
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.")
        return
    
    users = get_target_users()
    status = await update.message.reply_text(
        f"🔍 Starting trend scan of {len(users)} users...\n"
        "This may take a few minutes."
    )
    
    try:
        import asyncio
        results = await asyncio.to_thread(run_full_scan)
        message = format_scan_results(results)
        
        if len(message) > 4000:
            await update.message.reply_text(message[:4000], parse_mode="Markdown", disable_web_page_preview=True)
            if len(message) > 4000:
                await update.message.reply_text(message[4000:], parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
        
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status.message_id)
        except Exception:
            pass
            
    except Exception as e:
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")
        logger.error(f"Scan error: {e}")


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add <username_or_link> - add user to watchlist."""
    if not _is_allowed(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /add <username or TikTok link>\n\n"
            "Examples:\n"
            "  /add johnsummit\n"
            "  /add https://www.tiktok.com/@johnsummit"
        )
        return
    
    input_str = context.args[0]
    success, msg = add_user_to_file(input_str)
    await update.message.reply_text(msg)


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove <username> - remove user from watchlist."""
    if not _is_allowed(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /remove <username>")
        return
    
    success, msg = remove_user_from_file(context.args[0])
    await update.message.reply_text(msg)


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watchlist - show all monitored users."""
    if not _is_allowed(update.effective_user.id):
        return
    
    users = get_target_users()
    if not users:
        await update.message.reply_text("📭 Watchlist is empty. Use /add to add users.")
        return
    
    # Show in columns
    lines = [f"👁 *Watchlist* ({len(users)} users)\n"]
    for i, user in enumerate(users, 1):
        lines.append(f"{i}. @{user}")
    
    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n..."
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def trends_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trendshelp - show trend scanner help."""
    if not _is_allowed(update.effective_user.id):
        return
    
    await update.message.reply_text(
        "🔍 *Trend Scanner Commands*\n\n"
        "/scan - Run a manual scan of all monitored TikTok users\n"
        "/add <user> - Add a TikTok username or link to monitor\n"
        "/remove <user> - Remove a user from monitoring\n"
        "/watchlist - Show all monitored users\n"
        "/trendshelp - Show this help\n\n"
        f"📅 Automatic daily scan runs at {SCAN_HOUR:02d}:{SCAN_MINUTE:02d} Israel time\n"
        f"👁 Currently monitoring {len(get_target_users())} users",
        parse_mode="Markdown"
    )


# ============================================================
# SCHEDULED JOB
# ============================================================

async def daily_scan_job(context: CallbackContext):
    """Scheduled daily scan job."""
    import asyncio
    logger.info("Running scheduled daily trend scan...")
    
    try:
        results = await asyncio.to_thread(run_full_scan)
        message = format_scan_results(results, limit=5)
        
        # Prepend daily header
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        header = f"📅 *Daily Trend Report* - {now.strftime('%d/%m/%Y')}\n\n"
        message = header + message
        
        # Send to all allowed users
        allowed_id = os.getenv("ALLOWED_USER_ID")
        allowed_ids = os.getenv("ALLOWED_USER_IDS", "")
        
        recipients = set()
        if allowed_id:
            try:
                recipients.add(int(allowed_id))
            except ValueError:
                pass
        for uid in allowed_ids.split(","):
            uid = uid.strip()
            if uid:
                try:
                    recipients.add(int(uid))
                except ValueError:
                    pass
        
        for user_id in recipients:
            try:
                if len(message) > 4000:
                    await context.bot.send_message(user_id, message[:4000], parse_mode="Markdown", disable_web_page_preview=True)
                else:
                    await context.bot.send_message(user_id, message, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Failed to send report to {user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Daily scan failed: {e}")


# ============================================================
# SETUP (called by main bot)
# ============================================================

async def setup_trend_scanner(application: Application):
    """
    Register trend scanner handlers and schedule daily job.
    Called by the main parties247 bot during initialization.
    """
    print("=" * 50)
    print("🔍 Setting up Trend Scanner")
    print("=" * 50)
    
    # Register command handlers
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("watchlist", watchlist_command))
    application.add_handler(CommandHandler("trendshelp", trends_help_command))
    
    # Schedule daily scan
    tz = pytz.timezone(TIMEZONE)
    scan_time = time(hour=SCAN_HOUR, minute=SCAN_MINUTE, tzinfo=tz)
    
    application.job_queue.run_daily(
        daily_scan_job,
        time=scan_time,
        name="daily_trend_scan"
    )
    
    users_count = len(get_target_users())
    print(f"📅 Daily scan scheduled for {SCAN_HOUR:02d}:{SCAN_MINUTE:02d} {TIMEZONE}")
    print(f"👁 Monitoring {users_count} TikTok users")
    print(f"📄 Users file: {USERS_FILE}")
    print("🔍 Trend Scanner handlers registered!")
