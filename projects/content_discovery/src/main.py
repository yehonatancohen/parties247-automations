"""
Content Discovery Bot - Main Entry Point

Monitors TikTok and Instagram for potential viral content,
scans Israeli media, and sends daily reports via Telegram.
"""

import asyncio
import sys
from datetime import datetime, time
from typing import List, Dict, Set

import pytz
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackContext
)

from config import Config
from models import VideoCandidate, MediaArticle, FollowSuggestion, DailyReport
from services.engagement_calculator import EngagementCalculator
from services.instagram_scraper import InstagramScraper
from services.tiktok_scraper import TikTokScraper
from services.media_scraper import MediaScraper
from services.follow_suggester import FollowSuggester

# Ensure directories exist
Config.ensure_dirs()

# Initialize services
engagement_calc = EngagementCalculator()
instagram_scraper = InstagramScraper()
tiktok_scraper = TikTokScraper()
media_scraper = MediaScraper()
follow_suggester = FollowSuggester()


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    allowed = Config.get_allowed_user_ids()
    return not allowed or user_id in allowed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    # Check for arguments (e.g. /start <link>)
    if context.args:
        link = context.args[0]
        if 'tiktok.com' in link:
            await update.message.reply_text("🔗 Processing TikTok link from start command...")
            success, msg = await tiktok_scraper.add_monitored_account(link)
            await update.message.reply_text(msg)
            return

    await update.message.reply_text(
        "🎉 *Parties 24/7 Content Discovery Bot*\n\n"
        "I monitor TikTok and Instagram for potential viral party content.\n\n"
        "*Commands:*\n"
        "/scan - Run a content discovery scan now\n"
        "/add <link/user> - Add a TikTok user to monitor\n"
        "/report - Get the latest discovery report\n"
        "/suggest - Get follow suggestions\n"
        "/status - Check bot status\n\n"
        f"📅 Daily reports are sent at {Config.DAILY_REPORT_HOUR}:00 Israel time.",
        parse_mode="Markdown"
    )

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command to add a monitored user."""
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

# ... (status_command and other existing commands remain same) ...

async def main():
    """Main entry point."""
    print("=" * 60)
    print("🎉 Parties 24/7 Content Discovery Bot")
    print("=" * 60)
    
    if not Config.TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN not set. Exiting.")
        return
    
    # Build application
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(cookie_handler)  # Cookie handler first
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("add", add_user_command))  # New command
    application.add_handler(CommandHandler("suggest", suggest_command))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    if not is_user_allowed(update.effective_user.id):
        return
    
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    
    await update.message.reply_text(
        f"✅ *Bot Status*\n\n"
        f"🕐 Current time: {now.strftime('%H:%M %Z')}\n"
        f"📅 Next report: {Config.DAILY_REPORT_HOUR}:00\n"
        f"📊 Hit threshold: {Config.HIT_THRESHOLD}x baseline\n"
        f"⏰ Video age limit: {Config.VIDEO_AGE_HOURS}h",
        parse_mode="Markdown"
    )


async def run_discovery_scan() -> DailyReport:
    """
    Run a full content discovery scan.
    
    Returns:
        DailyReport with all findings
    """
    print("🔍 Starting content discovery scan...")
    
    tz = pytz.timezone(Config.TIMEZONE)
    report = DailyReport(generated_at=datetime.now(tz))
    
    all_videos = []
    current_following = {"tiktok": set(), "instagram": set()}
    
    # ===== TikTok Scan =====
    try:
        print("📱 Scanning TikTok...")
        
        # Get following list
        tiktok_following = await tiktok_scraper.get_following_list()
        current_following["tiktok"] = {u["username"] for u in tiktok_following}
        
        # Check for new followings
        new_tiktok = await tiktok_scraper.get_new_followings()
        for u in new_tiktok:
            report.new_followings_detected.append(f"TikTok: @{u['username']}")
        
        # Scan videos from followed accounts
        for user in tiktok_following[:20]:  # Limit to avoid rate limits
            try:
                videos = await tiktok_scraper.get_recent_videos(user["username"])
                
                # Calculate baseline and analyze each video
                if videos:
                    baseline = await tiktok_scraper.get_user_baseline(user["username"])
                    
                    for video in videos:
                        analysis = engagement_calc.analyze_video(
                            views=video.views,
                            likes=video.likes,
                            comments=video.comments,
                            shares=video.shares,
                            followers=video.author_followers,
                            baseline=baseline,
                            caption=video.caption,
                            hashtags=video.hashtags
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
        
        # Get following list
        insta_following = instagram_scraper.get_following_list()
        current_following["instagram"] = {u["username"] for u in insta_following}
        
        # Check for new followings
        new_insta = instagram_scraper.get_new_followings()
        for u in new_insta:
            report.new_followings_detected.append(f"Instagram: @{u['username']}")
        
        # Scan reels from followed accounts
        for user in insta_following[:20]:  # Limit
            if user.get("is_private"):
                continue
            
            try:
                videos = instagram_scraper.get_recent_reels(user["username"])
                
                if videos:
                    baseline = instagram_scraper.get_user_baseline(user["username"])
                    
                    for video in videos:
                        analysis = engagement_calc.analyze_video(
                            views=video.views,
                            likes=video.likes,
                            comments=video.comments,
                            shares=video.shares,
                            followers=video.author_followers,
                            baseline=baseline,
                            caption=video.caption,
                            hashtags=video.hashtags
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
    
    # ===== Process Results =====
    # Separate potential hits from regular videos
    report.potential_hits = [v for v in all_videos if v.is_potential_hit]
    report.other_videos = [v for v in all_videos if not v.is_potential_hit]
    
    # Sort by hit score
    report.potential_hits.sort(key=lambda v: v.hit_score, reverse=True)
    
    # Generate follow suggestions
    try:
        report.follow_suggestions = follow_suggester.generate_suggestions(
            all_videos, current_following
        )
    except Exception as e:
        report.errors.append(f"Suggestions error: {str(e)}")
    
    print(f"✅ Scan complete! Found {len(report.potential_hits)} potential hits")
    return report


def format_report_message(report: DailyReport) -> str:
    """Format the report as a Telegram message."""
    tz = pytz.timezone(Config.TIMEZONE)
    
    lines = [
        f"🎉 *Daily Content Discovery Report*",
        f"📅 {report.generated_at.strftime('%d/%m/%Y %H:%M')}",
        ""
    ]
    
    # Stats
    stats = report.get_summary_stats()
    lines.append(f"📊 *Summary:*")
    lines.append(f"• Videos scanned: {stats['total_videos_scanned']}")
    lines.append(f"• Potential hits: {stats['potential_hits_count']}")
    lines.append(f"• Media articles: {stats['media_articles_count']}")
    lines.append(f"• New followings: {stats['new_followings_count']}")
    lines.append("")
    
    # Potential Hits
    if report.potential_hits:
        lines.append("🔥 *POTENTIAL HITS:*")
        for i, video in enumerate(report.potential_hits[:10], 1):
            emoji = "🎵" if video.category == "release" else "🎪" if video.category == "festival" else "🔥"
            lines.append(
                f"\n{i}. {emoji} @{video.author_username} ({video.platform})\n"
                f"   Score: {video.hit_score:.1f}x | {video.views:,} views\n"
                f"   Category: {video.category}\n"
                f"   [View]({video.video_url})"
            )
        lines.append("")
    else:
        lines.append("📭 No potential hits found today.")
        lines.append("")
    
    # Media Articles
    if report.media_articles:
        lines.append("📰 *Party News:*")
        for article in report.media_articles[:5]:
            lines.append(f"• [{article.title[:50]}...]({article.url})")
        lines.append("")
    
    # New Followings
    if report.new_followings_detected:
        lines.append("🆕 *New Followings Detected:*")
        for f in report.new_followings_detected[:5]:
            lines.append(f"• {f}")
        lines.append("")
    
    # Follow Suggestions
    if report.follow_suggestions:
        lines.append("💡 *Follow Suggestions:*")
        for s in report.follow_suggestions[:5]:
            lines.append(f"• @{s.username} ({s.platform})")
            lines.append(f"  _{s.reason}_")
        lines.append("")
    
    # Errors
    if report.errors:
        lines.append(f"⚠️ {len(report.errors)} errors occurred during scan.")
    
    return "\n".join(lines)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command - run immediate scan."""
    if not is_user_allowed(update.effective_user.id):
        return
    
    await update.message.reply_text("🔍 Starting content discovery scan... This may take a few minutes.")
    
    try:
        report = await run_discovery_scan()
        message = format_report_message(report)
        
        # Split if too long
        if len(message) > 4000:
            await update.message.reply_text(message[:4000], parse_mode="Markdown", disable_web_page_preview=True)
            await update.message.reply_text(message[4000:], parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")


async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /suggest command - show follow suggestions."""
    if not is_user_allowed(update.effective_user.id):
        return
    
    await update.message.reply_text("🔍 Generating follow suggestions...")
    
    # Quick scan for suggestions
    try:
        all_videos = []
        
        # Just get recent videos without full analysis
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

# Define ConversationHandler for cookies
from telegram.ext import ConversationHandler, MessageHandler, filters

cookie_handler = ConversationHandler(
    entry_points=[CommandHandler('update_cookies', update_cookies_command)],
    states={
        1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookie_response)]
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
)


async def daily_report_job(context: CallbackContext):
    """Scheduled job for daily reports."""
    print("📬 Running scheduled daily report...")
    
    try:
        report = await run_discovery_scan()
        message = format_report_message(report)
        
        # Send to all allowed users
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

async def send_startup_notification(application):
    """Send startup notification to allowed users."""
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    
    message = (
        f"🚀 *Content Discovery Bot Started*\n\n"
        f"🕐 Time: {now.strftime('%H:%M %Z')}\n"
        f"📅 Daily report: {Config.DAILY_REPORT_HOUR}:00\n"
        f"📊 Hit threshold: {Config.HIT_THRESHOLD}x baseline\n\n"
        f"Use /scan to run a discovery scan now.\n"
        f"Use /update_cookies to update TikTok credentials."
    )
    
    for user_id in Config.get_allowed_user_ids():
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Failed to send startup notification to {user_id}: {e}")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🎉 Parties 24/7 Content Discovery Bot")
    print("=" * 60)
    
    if not Config.TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN not set. Exiting.")
        return
    
    # Build application
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(cookie_handler)  # Cookie handler first
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("suggest", suggest_command))
    
    # Schedule daily report
    tz = pytz.timezone(Config.TIMEZONE)
    report_time = time(hour=Config.DAILY_REPORT_HOUR, minute=0, tzinfo=tz)
    
    application.job_queue.run_daily(
        daily_report_job,
        time=report_time,
        name="daily_report"
    )
    
    print(f"📅 Daily report scheduled for {Config.DAILY_REPORT_HOUR}:00 {Config.TIMEZONE}")
    print(f"👥 Allowed users: {Config.get_allowed_user_ids()}")
    
    # Send startup notification
    await application.initialize()
    await send_startup_notification(application)
    
    # Start polling
    print("✅ Bot is running...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")
