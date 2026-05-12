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
from services.global_scanner import GlobalScanner


# Ensure directories exist
Config.ensure_dirs()

# Initialize services
engagement_calc = EngagementCalculator()
instagram_scraper = InstagramScraper()
tiktok_scraper = TikTokScraper()
media_scraper = MediaScraper()
follow_suggester = FollowSuggester()
global_scanner = GlobalScanner()



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
        f"📊 Hit threshold: {Config.HIT_THRESHOLD}x baseline\n"
        f"⏰ Video age limit: {Config.VIDEO_AGE_HOURS}h\n"
        f"🌍 Global scan: {'enabled' if Config.GLOBAL_SCAN_ENABLED else 'disabled'} "
        f"({Config.GLOBAL_MAX_HASHTAGS_PER_RUN} hashtags, min {Config.GLOBAL_MIN_VIEWS:,} views)",
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
                        analysis = engagement_calc.analyze_video(
                            views=video.views, likes=video.likes,
                            comments=video.comments, shares=video.shares,
                            followers=video.author_followers, baseline=baseline,
                            caption=video.caption, hashtags=video.hashtags
                        )
                        video.engagement_rate = analysis["engagement_rate"]
                        video.baseline_rate = baseline
                        video.hit_score = analysis["hit_score"]
                        video.is_potential_hit = analysis["is_potential_hit"]
                        video.category = analysis["category"]
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
                        analysis = engagement_calc.analyze_video(
                            views=video.views, likes=video.likes,
                            comments=video.comments, shares=video.shares,
                            followers=video.author_followers, baseline=baseline,
                            caption=video.caption, hashtags=video.hashtags
                        )
                        video.engagement_rate = analysis["engagement_rate"]
                        video.baseline_rate = baseline
                        video.hit_score = analysis["hit_score"]
                        video.is_potential_hit = analysis["is_potential_hit"]
                        video.category = analysis["category"]
                        all_videos.append(video)
            except Exception as e:
                report.errors.append(f"Instagram @{user['username']}: {str(e)}")
    except Exception as e:
        report.errors.append(f"Instagram scan error: {str(e)}")
        print(f"❌ Instagram scan error: {e}")

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

    # ===== Global Viral Scan =====
    try:
        print("🌍 Scanning global hashtags for viral party content...")
        global_vids = await global_scanner.scan_trending_hashtags()
        # Exclude any accounts already in the following lists
        all_following_usernames = (
            current_following.get("tiktok", set())
            | current_following.get("instagram", set())
        )
        report.global_discoveries = [
            v for v in global_vids
            if v.author_username not in all_following_usernames
        ]
        print(f"🌍 Global scan: {len(report.global_discoveries)} viral party videos discovered")
    except Exception as e:
        report.errors.append(f"Global scan error: {str(e)}")
        print(f"❌ Global scan error: {e}")

    # ===== Process Results =====
    report.potential_hits = [v for v in all_videos if v.is_potential_hit]
    report.other_videos = [v for v in all_videos if not v.is_potential_hit]
    report.potential_hits.sort(key=lambda v: v.hit_score, reverse=True)

    try:
        report.follow_suggestions = follow_suggester.generate_suggestions(
            all_videos, current_following
        )
    except Exception as e:
        report.errors.append(f"Suggestions error: {str(e)}")

    print(f"✅ Scan complete! Found {len(report.potential_hits)} potential hits, {len(report.global_discoveries)} global discoveries")
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
    lines.append(f"• Videos scanned (following): {stats['total_videos_scanned']}")
    lines.append(f"• Potential hits: {stats['potential_hits_count']}")
    lines.append(f"• 🌍 Global discoveries: {stats['global_discoveries_count']}")
    lines.append(f"• Media articles: {stats['media_articles_count']}")
    lines.append(f"• New followings: {stats['new_followings_count']}")
    lines.append("")

    if report.potential_hits:
        lines.append("🔥 *POTENTIAL HITS (from following):*")
        for i, video in enumerate(report.potential_hits[:10], 1):
            emoji = "🎵" if video.category == "release" else "🎤" if video.category == "israeli_dj" else "🎪" if video.category == "festival" else "🔥"
            lines.append(
                f"\n{i}. {emoji} @{video.author_username} ({video.platform})\n"
                f"   Score: {video.hit_score:.1f}x | {video.views:,} views\n"
                f"   Category: {video.category}\n"
                f"   [View]({video.video_url})"
            )
        lines.append("")
    else:
        lines.append("📭 No potential hits from following today.")
        lines.append("")

    if report.global_discoveries:
        lines.append("🌍 *GLOBAL VIRAL DISCOVERIES:*")
        for i, video in enumerate(report.global_discoveries[:10], 1):
            cat_emoji = {
                "psytrance": "🌀", "techno": "⚡", "house": "🏠",
                "festival": "🎪", "rave": "🔥", "release": "🎵",
                "israeli_scene": "🇮🇱",
            }.get(video.category, "🌍")

            if video.views >= 1_000_000:
                views_str = f"{video.views / 1_000_000:.1f}M"
            elif video.views >= 1_000:
                views_str = f"{video.views / 1_000:.0f}K"
            else:
                views_str = str(video.views)

            eng_rate = 0.0
            if video.views > 0:
                eng_rate = (video.likes + video.comments + video.shares) / video.views * 100

            top_tags = " ".join(f"#{t}" for t in (video.hashtags or [])[:4])

            lines.append(
                f"\n{i}. {cat_emoji} @{video.author_username}\n"
                f"   📈 {views_str} views | {eng_rate:.1f}% engagement\n"
                f"   🏷️ {video.category} | Score: {video.virality_score:.2f}\n"
                + (f"   {top_tags}\n" if top_tags else "")
                + f"   [Watch]({video.video_url})"
            )
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
