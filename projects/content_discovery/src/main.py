"""
Content Discovery Bot - Module

Monitors TikTok and Instagram for potential viral content,
scans Israeli media, and sends daily reports via Telegram.

Designed to be integrated into the main parties247 bot via setup_content_discovery().
"""

import asyncio
import os
import sys
from datetime import datetime, time
from typing import List, Dict, Set

import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Add content_discovery src to path so its local imports work
_cd_src_dir = os.path.dirname(os.path.abspath(__file__))
if _cd_src_dir not in sys.path:
    sys.path.insert(0, _cd_src_dir)

from config import Config
from models import VideoCandidate, MediaArticle, FollowSuggestion, DailyReport
from services.engagement_calculator import EngagementCalculator
from services.instagram_scraper import InstagramScraper
from services.tiktok_scraper import TikTokScraper
from services.media_scraper import MediaScraper
from services.follow_suggester import FollowSuggester
from services.israeli_detector import IsraeliContentDetector
from services.discovery_scraper import HashtagDiscoveryScraper

# Ensure directories exist
Config.ensure_dirs()

# Initialize services
israeli_detector = IsraeliContentDetector()
engagement_calc = EngagementCalculator(detector=israeli_detector)
instagram_scraper = InstagramScraper()
tiktok_scraper = TikTokScraper()
media_scraper = MediaScraper()
follow_suggester = FollowSuggester()


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    allowed = Config.get_allowed_user_ids()
    return not allowed or user_id in allowed


# ============================================================
# Command Handlers
# ============================================================

async def cd_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cd_help command."""
    if not is_user_allowed(update.effective_user.id):
        return

    await update.message.reply_text(
        "📚 *Content Discovery Commands*\n\n"
        "__User Management__\n"
        "• `/add <link>` - Add a user by TikTok profile or video link.\n"
        "• `/add <username>` - Add a user by username.\n\n"
        "__Discovery__\n"
        "• `/scan` - Run a manual scan of all monitored users immediately.\n"
        "• `/report` - Show the last generated daily report.\n"
        "• `/suggest` - Get suggestions for new accounts to follow.\n\n"
        "__System__\n"
        "• `/cd_status` - Check content discovery status.\n"
        "• `/update_cookies` - Update TikTok session cookies if scraping fails.\n"
        "• `/cd_help` - Show this help message.",
        parse_mode="Markdown"
    )


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command to monitor new users."""
    if not is_user_allowed(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /add <username_or_link>")
        return

    input_str = context.args[0]
    await update.message.reply_text(f"🔍 Processing {input_str}...")

    try:
        success, msg = await tiktok_scraper.add_monitored_account(input_str)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cd_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cd_status command."""
    if not is_user_allowed(update.effective_user.id):
        return

    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)

    await update.message.reply_text(
        f"✅ *Content Discovery Status*\n\n"
        f"🕐 Current time: {now.strftime('%H:%M %Z')}\n"
        f"📅 Next report: {Config.DAILY_REPORT_HOUR}:00\n"
        f"📊 Potential-hit threshold: {Config.POTENTIAL_HIT_THRESHOLD}\n"
        f"⏰ Video age limit: {Config.VIDEO_AGE_HOURS}h",
        parse_mode="Markdown"
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command - run immediate scan."""
    user_id = update.effective_user.id
    print(f"Received /scan command from user {user_id}")

    if not is_user_allowed(user_id):
        await update.message.reply_text("⛔ Access Denied: Your User ID is not in the allowed list.")
        print(f"❌ User {user_id} denied access.")
        return

    status_msg = await update.message.reply_text("🔍 Starting content discovery scan... This may take a few minutes.")

    try:
        report = await run_discovery_scan()
        message = format_report_message(report)

        # Split if too long
        if len(message) > 4000:
            await update.message.reply_text(message[:4000], parse_mode="Markdown", disable_web_page_preview=True)
            await update.message.reply_text(message[4000:], parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")
        print(f"❌ Scan Exception: {e}")


async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /suggest command - show follow suggestions."""
    if not is_user_allowed(update.effective_user.id):
        return

    await update.message.reply_text("🔍 Generating follow suggestions...")

    try:
        all_videos = []
        tiktok_following = await tiktok_scraper.get_following_list()
        for user in tiktok_following[:5]:
            videos = await tiktok_scraper.get_recent_videos(user["username"])
            all_videos.extend(videos)

        await tiktok_scraper.close()

        current_following = {
            "tiktok": {u["username"] for u in tiktok_following},
            "instagram": set()
        }

        suggestions = follow_suggester.generate_suggestions(all_videos, current_following)

        if suggestions:
            lines = ["💡 *Follow Suggestions:*\n"]
            for s in suggestions[:10]:
                lines.append(f"• @{s.username} ({s.platform})")
                lines.append(f"  _{s.reason}_\n")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("No new suggestions right now.")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def update_cookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /update_cookies command."""
    if not is_user_allowed(update.effective_user.id):
        return

    await update.message.reply_text(
        "🍪 *Update TikTok Cookies*\n\n"
        "To update cookies:\n"
        "1. Install 'EditThisCookie' extension on Chrome/Edge\n"
        "2. Log into TikTok\n"
        "3. Copy all cookies to clipboard (Export)\n"
        "4. Reply to this message with the JSON data\n\n"
        "Or reply with 'cancel' to abort.",
        parse_mode="Markdown"
    )
    return 1  # ConversationHandler.WAITING_FOR_COOKIES


async def handle_cookie_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the user's cookie data."""
    if not is_user_allowed(update.effective_user.id):
        return ConversationHandler.END

    data = update.message.text
    if data.lower() == 'cancel':
        await update.message.reply_text("❌ Update cancelled.")
        return ConversationHandler.END

    try:
        success = tiktok_scraper.update_cookies(data)
        if success:
            await update.message.reply_text("✅ Cookies updated successfully! Run /scan to test.")
        else:
            await update.message.reply_text("❌ Failed to parse cookies. Please check format and try again.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

    return ConversationHandler.END


# ============================================================
# Scan & Report Logic
# ============================================================

def _apply_analysis(video: VideoCandidate, baseline: float) -> None:
    """Run detector + scoring on one VideoCandidate in-place."""
    analysis = engagement_calc.analyze_video(
        views=video.views,
        likes=video.likes,
        comments=video.comments,
        shares=video.shares,
        followers=video.author_followers,
        baseline=baseline,
        caption=video.caption,
        hashtags=video.hashtags,
        saves=video.saves,
        posted_at=video.posted_at,
        location=video.location,
        author_username=video.author_username,
    )
    video.engagement_rate = analysis["engagement_rate"]
    video.baseline_rate = baseline
    video.potential_score = analysis["potential_score"]
    video.velocity_score = analysis["velocity_score"]
    video.reach_score = analysis["reach_score"]
    video.is_potential_hit = analysis["is_potential_hit"]
    video.category = analysis["category"]
    video.is_israeli = analysis["is_israeli"]
    video.israeli_signal_score = analysis["israeli_signal_score"]
    video.israeli_signals = analysis["israeli_signals"]


async def run_discovery_scan() -> DailyReport:
    """Run a full content discovery scan."""
    print("🔍 Starting content discovery scan...")

    tz = pytz.timezone(Config.TIMEZONE)
    report = DailyReport(generated_at=datetime.now(tz))

    all_videos = []
    current_following = {"tiktok": set(), "instagram": set()}

    # ===== TikTok Scan =====
    try:
        print("📱 Scanning TikTok...")
        tiktok_following = await tiktok_scraper.get_following_list()
        current_following["tiktok"] = {u["username"] for u in tiktok_following}

        new_tiktok = await tiktok_scraper.get_new_followings()
        for u in new_tiktok:
            report.new_followings_detected.append(f"TikTok: @{u['username']}")

        for user in tiktok_following[:20]:
            try:
                videos = await tiktok_scraper.get_recent_videos(user["username"])
                if videos:
                    baseline = await tiktok_scraper.get_user_baseline(user["username"])
                    for video in videos:
                        _apply_analysis(video, baseline)
                        all_videos.append(video)
            except Exception as e:
                report.errors.append(f"TikTok @{user['username']}: {str(e)}")
    except Exception as e:
        report.errors.append(f"TikTok scan error: {str(e)}")
        print(f"❌ TikTok scan error: {e}")
    finally:
        await tiktok_scraper.close()

    # ===== Instagram Scan =====
    try:
        print("📸 Scanning Instagram...")
        insta_following = instagram_scraper.get_following_list()
        current_following["instagram"] = {u["username"] for u in insta_following}

        new_insta = instagram_scraper.get_new_followings()
        for u in new_insta:
            report.new_followings_detected.append(f"Instagram: @{u['username']}")

        for user in insta_following[:20]:
            if user.get("is_private"):
                continue
            try:
                videos = instagram_scraper.get_recent_reels(user["username"])
                if videos:
                    baseline = instagram_scraper.get_user_baseline(user["username"])
                    for video in videos:
                        _apply_analysis(video, baseline)
                        all_videos.append(video)
            except Exception as e:
                report.errors.append(f"Instagram @{user['username']}: {str(e)}")
    except Exception as e:
        report.errors.append(f"Instagram scan error: {str(e)}")
        print(f"❌ Instagram scan error: {e}")

    # ===== Hashtag Discovery (new Israeli creators) =====
    discovered_suggestions: List[FollowSuggestion] = []
    if Config.ENABLE_HASHTAG_DISCOVERY:
        try:
            print("🔎 Running hashtag discovery crawl...")
            monitored = HashtagDiscoveryScraper.load_monitored_usernames()
            monitored.update(current_following.get("tiktok", set()))
            monitored.update(current_following.get("instagram", set()))
            discovery = HashtagDiscoveryScraper(
                detector=israeli_detector,
                instagram_scraper=instagram_scraper,
                monitored_usernames=monitored,
            )
            seen_urls = {v.video_url for v in all_videos if v.video_url}
            discovered_videos = await discovery.crawl(seen_urls=seen_urls)
            for video in discovered_videos:
                _apply_analysis(video, baseline=0.0)
                all_videos.append(video)
            discovered_suggestions = discovery.suggest_authors(discovered_videos)
            report.new_followings_detected.extend(
                f"Discovered: @{s.username} ({s.platform})"
                for s in discovered_suggestions[:5]
            )
        except Exception as e:
            report.errors.append(f"Hashtag discovery error: {str(e)}")
            print(f"❌ Hashtag discovery error: {e}")

    # ===== Media Scan =====
    try:
        print("📰 Scanning Israeli media...")
        articles = await media_scraper.scrape_all_sources()
        report.media_articles = articles
    except Exception as e:
        report.errors.append(f"Media scan error: {str(e)}")
        print(f"❌ Media scan error: {e}")
    finally:
        await media_scraper.close()

    # ===== Process Results =====
    report.potential_hits = [v for v in all_videos if v.is_potential_hit]
    report.other_videos = [v for v in all_videos if not v.is_potential_hit]
    report.potential_hits.sort(key=lambda v: v.potential_score, reverse=True)

    try:
        base_suggestions = follow_suggester.generate_suggestions(
            all_videos, current_following
        )
        merged = list(discovered_suggestions) + list(base_suggestions)
        seen_sug = set()
        deduped = []
        for s in merged:
            key = f"{s.platform}:{s.username.lower()}"
            if key in seen_sug:
                continue
            seen_sug.add(key)
            deduped.append(s)
        report.follow_suggestions = deduped[:15]
    except Exception as e:
        report.errors.append(f"Suggestions error: {str(e)}")

    print(f"✅ Scan complete! Found {len(report.potential_hits)} potential hits")
    return report


def format_report_message(report: DailyReport) -> str:
    """Format the report as a Telegram message."""
    lines = [
        f"🎉 *Daily Content Discovery Report*",
        f"📅 {report.generated_at.strftime('%d/%m/%Y %H:%M')}",
        ""
    ]

    stats = report.get_summary_stats()
    lines.append(f"📊 *Summary:*")
    lines.append(f"• Videos scanned: {stats['total_videos_scanned']}")
    lines.append(f"• Potential hits: {stats['potential_hits_count']}")
    lines.append(f"• Media articles: {stats['media_articles_count']}")
    lines.append(f"• New followings: {stats['new_followings_count']}")
    lines.append("")

    if report.potential_hits:
        lines.append("🔥 *POTENTIAL HITS:*")
        now = datetime.now()
        for i, video in enumerate(report.potential_hits[:10], 1):
            emoji = "🎵" if video.category == "release" else "🎪" if video.category == "festival" else "🔥"
            il_flag = "🇮🇱 " if video.is_israeli else ""
            discovered_tag = (
                f" [via #{video.discovered_via_hashtag}]"
                if video.discovered_via_hashtag
                else ""
            )
            likes_per_hour = 0.0
            if video.posted_at:
                pa = video.posted_at.replace(tzinfo=None) if video.posted_at.tzinfo else video.posted_at
                hours = max((now - pa).total_seconds() / 3600, 0.5)
                likes_per_hour = (video.likes or 0) / hours
            lines.append(
                f"\n{i}. {il_flag}{emoji} @{video.author_username} ({video.platform}){discovered_tag}\n"
                f"   Score: {video.potential_score:.2f} | {video.views:,} views | {likes_per_hour:.0f} likes/hr\n"
                f"   Category: {video.category}"
            )
            if video.israeli_signals:
                lines.append(f"   Signals: {', '.join(video.israeli_signals[:4])}")
            lines.append(f"   [View]({video.video_url})")
        lines.append("")
    else:
        lines.append("📭 No potential hits found today.")
        lines.append("")

    if report.media_articles:
        lines.append("📰 *Party News:*")
        for article in report.media_articles[:5]:
            lines.append(f"• [{article.title[:50]}...]({article.url})")
        lines.append("")

    if report.new_followings_detected:
        lines.append("🆕 *New Followings Detected:*")
        for f in report.new_followings_detected[:5]:
            lines.append(f"• {f}")
        lines.append("")

    if report.follow_suggestions:
        lines.append("💡 *Follow Suggestions:*")
        for s in report.follow_suggestions[:5]:
            lines.append(f"• @{s.username} ({s.platform})")
            lines.append(f"  _{s.reason}_")
        lines.append("")

    if report.errors:
        lines.append(f"⚠️ {len(report.errors)} errors occurred during scan.")

    return "\n".join(lines)


# ============================================================
# Scheduled Jobs
# ============================================================

async def daily_report_job(context: CallbackContext):
    """Scheduled job for daily reports."""
    print("📬 Running scheduled daily report...")

    try:
        report = await run_discovery_scan()
        message = format_report_message(report)

        for user_id in Config.get_allowed_user_ids():
            try:
                if len(message) > 4000:
                    await context.bot.send_message(user_id, message[:4000], parse_mode="Markdown", disable_web_page_preview=True)
                    await context.bot.send_message(user_id, message[4000:], parse_mode="Markdown", disable_web_page_preview=True)
                else:
                    await context.bot.send_message(user_id, message, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                print(f"❌ Failed to send report: {e}")

    except Exception as e:
        print(f"❌ Daily report failed: {e}")


# ============================================================
# Setup Function (called by main bot)
# ============================================================

async def setup_content_discovery(application: Application):
    """
    Setup the Content Discovery module on the shared bot application.
    
    This registers all CD command handlers and schedules the daily report job.
    Called by the main parties247 bot during initialization.
    """
    print("=" * 50)
    print("🔍 Setting up Content Discovery Module")
    print("=" * 50)

    # Cookie update conversation handler
    cookie_handler = ConversationHandler(
        entry_points=[CommandHandler('update_cookies', update_cookies_command)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookie_response)]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )

    # Register handlers
    application.add_handler(cookie_handler)
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("add", add_user_command))
    application.add_handler(CommandHandler("suggest", suggest_command))
    application.add_handler(CommandHandler("cd_status", cd_status_command))
    application.add_handler(CommandHandler("cd_help", cd_help_command))

    # Schedule daily report
    tz = pytz.timezone(Config.TIMEZONE)
    report_time = time(hour=Config.DAILY_REPORT_HOUR, minute=0, tzinfo=tz)

    application.job_queue.run_daily(
        daily_report_job,
        time=report_time,
        name="cd_daily_report"
    )

    print(f"📅 Content Discovery: Daily report scheduled for {Config.DAILY_REPORT_HOUR}:00 {Config.TIMEZONE}")
    print("🔍 Content Discovery handlers registered!")
