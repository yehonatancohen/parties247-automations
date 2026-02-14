import os
import PIL.Image

# Monkey patch ANTIALIAS for older libraries (moviepy, pilmoji)
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

import asyncio
import subprocess
from time import time
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    MessageHandler, 
    filters, 
    ConversationHandler,
    CommandHandler
)
from telegram.request import HTTPXRequest

from config import Config
from keep_alive import keep_alive
from services.downloader import VideoDownloader
from services.graphics import GraphicsEngine
from services.ai_generator import AIGenerator
from services.instagram_auth import get_instagram_auth

# Import Instagram Stories Bot
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
stories_src = os.path.abspath(os.path.join(current_dir, "../../instagram_stories/src"))
if stories_src not in sys.path:
    sys.path.append(stories_src)

try:
    from story_bot import setup_stories_bot
    STORIES_BOT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Could not load Instagram Stories Bot: {e}")
    STORIES_BOT_AVAILABLE = False

# Import Trend Scanner (merged content discovery + trend hunter)
try:
    from trend_scanner import setup_trend_scanner
    TREND_SCANNER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Could not load Trend Scanner: {e}")
    TREND_SCANNER_AVAILABLE = False

# Initialize Services
graphics_engine = GraphicsEngine()
ai_generator = AIGenerator()


# Conversation states for video creation
LINK, TITLE, BODY, LAYOUT_CHOICE, CHOOSE_STORY = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != Config.ALLOWED_USER_ID:
        await update.message.reply_text("⛔ גישה נדחתה.")
        return ConversationHandler.END

    await update.message.reply_text(
        r"👋 היי! בוא ניצור סרטון חדש." + "\n\n"
        r"שלח לי את הלינק לסרטון (TikTok/Instagram/YouTube)" + "\n"
        r"*או שלח לי סרטון ישירות מהגלריה!* 📤" + "\n\n"
        r"_(או שלח /story לתזמון סטורי לאינסטגרם)_",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    return LINK



async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct video upload from user"""
    video = update.message.video or update.message.document
    
    # Basic validation
    if not video:
        await update.message.reply_text("❌ לא זוהה סרטון תקין.")
        return LINK
        
    status_msg = await update.message.reply_text("📥 מוריד את הסרטון...")
    
    file_id = video.file_id
    unique_id = video.file_unique_id
    filename = f"upload_{unique_id}.mp4"
    file_path = os.path.join(Config.TEMP_DIR, filename)
    
    try:
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive(custom_path=file_path)
        
        # Create metadata
        metadata = {
            'title': 'User Upload',
            'description': update.message.caption or 'Uploaded video',
            'uploader': 'User',
            'duration': getattr(video, 'duration', 0),
            'url': 'Uploaded File'
        }
        
        # Store in context similar to download flow
        context.user_data['link'] = 'Uploaded File'
        
        # Create a completed future to mock the background task
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result((file_path, metadata))
        
        context.user_data['download_task'] = future
        
        await status_msg.edit_text("✅ הסרטון התקבל בהצלחה!")
        
        await update.message.reply_text(
            "עכשיו שלח את הכותרת (שתופיע בגדול):"
        )
        return TITLE
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        await status_msg.edit_text(f"❌ שגיאה בהורדת הסרטון: {e}")
        return LINK


async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    context.user_data['link'] = link
    
    await update.message.reply_text("⏳ בודק את הלינק...")
    
    # Check for playlist/stories info
    stories = await asyncio.to_thread(VideoDownloader.fetch_available_stories, link)
    
    # If multiple entries found
    if len(stories) > 1:
        context.user_data['playlist_entries'] = stories
        context.user_data['original_link'] = link
        
        msg = f"🔎 נמצאו {len(stories)} סטוריז/סרטונים:\n\n"
        for i, entry in enumerate(stories[:15], 1):
            title = entry.get('title', 'N/A')
            duration = int(entry.get('duration', 0) or 0)
            date = entry.get('upload_date', '')
            date_str = ""
            if date and len(str(date)) == 8:
                 # Format YYYYMMDD -> DD/MM
                 date_str = f" [{date[6:8]}/{date[4:6]}]"
            
            msg += f"{i}. {title} ({duration}s){date_str}\n"
        
        msg += "\nשלח את מספר הסרטון שברצונך להוריד:"
        
        await update.message.reply_text(msg)
        return CHOOSE_STORY
    
    # Single video flow
    if stories:
        # Update link to the specific resolved URL if available, otherwise keep original
        # Ideally we use the resolved one to be safe, but sometimes original is better context.
        # For single video, let's stick to original or the one we found.
        # But if stories has 1 entry, use that one's URL if it differs?
        single_story = stories[0]
        if single_story.get('url'):
            link = single_story.get('url')
            context.user_data['link'] = link

    
    # Fallback/Single flow continues below...
    
    # Fallback to single video flow
    
    # --- EARLY DOWNLOAD START ---
    async def download_task_wrapper(url):
        print(f"🚀 Starting background download for: {url}")
        return await asyncio.to_thread(VideoDownloader.download_video, url)

    # Start the task and store it
    task = asyncio.create_task(download_task_wrapper(link))
    context.user_data['download_task'] = task
    
    await update.message.reply_text(
        "✅ לינק התקבל (ההורדה מתחילה ברקע... ⏳)\n"
        "עכשיו שלח את הכותרת (שתופיע בגדול):"
    )
    return TITLE

async def receive_story_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    entries = context.user_data.get('playlist_entries')
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(entries):
            target_entry = entries[idx]
            target_url = target_entry.get('url') or target_entry.get('webpage_url')
            
            # If internal info doesn't have full URL, we might need a way to construct it
            # But usually 'webpage_url' or 'url' is present. 
            # If using 'url' (direct video), download might fail if it requires auth headers from extraction.
            # Ideally we pass the 'webpage_url' if available, or the ID.
            
            if not target_url:
                 # Fallback: construct if possible or warn
                 target_url = context.user_data['original_link'] # Might re-trigger playlist
            
            context.user_data['link'] = target_url # Update link to specific story
            
            # Start download
            async def download_task_wrapper(url):
                print(f"🚀 Starting background download for: {url}")
                return await asyncio.to_thread(VideoDownloader.download_video, url)

            task = asyncio.create_task(download_task_wrapper(target_url))
            context.user_data['download_task'] = task
            
            await update.message.reply_text(
                f"✅ בחרת את סרטון #{idx+1}.\n"
                "ההורדה מתחילה ברקע... ⏳\n\n"
                "עכשיו שלח את הכותרת (שתופיע בגדול):"
            )
            return TITLE
        else:
            await update.message.reply_text("❌ מספר לא תקין. נסה שוב:")
            return CHOOSE_STORY
    except ValueError:
        await update.message.reply_text("❌ אנא שלח מספר בלבד.")
        return CHOOSE_STORY

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    context.user_data['title'] = title
    
    await update.message.reply_text(
        "✅ כותרת נשמרה.\n"
        "עכשיו שלח את הטקסט (גוף ההודעה):"
    )
    return BODY

async def receive_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    body = update.message.text.strip()
    context.user_data['body'] = body
    
    # Ask for Layout Preference
    keyboard = [['👇 מרכוז נמוך (לחיתוך כתוביות)', '⏺️ מרכוז רגיל']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "✅ טקסט נשמר.\n"
        "איך למקם את הסרטון?",
        reply_markup=reply_markup
    )
    return LAYOUT_CHOICE

async def receive_layout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    # Default to lower if unknown
    layout_mode = 'lower'
    if 'רגיל' in choice:
        layout_mode = 'standard'
    
    context.user_data['layout'] = layout_mode
    
    # Retrieve all data
    url = context.user_data['link']
    headline = context.user_data['title']
    body_text = context.user_data['body']
    
    await update.message.reply_text(
        f"✅ נבחר: {choice}\n"
        "⏳ מסים לעבד... (ממתין להורדה אם טרם הסתיימה)",
        reply_markup=ReplyKeyboardRemove()
    )

    try:
        # 1. Retrieve the Pre-started Download Task (returns path, metadata)
        download_task = context.user_data.get('download_task')
        if not download_task:
            print("⚠️ Download task missing, starting now...")
            video_path, video_info = await asyncio.to_thread(VideoDownloader.download_video, url)
        else:
            print("⏳ Awaiting background download task...")
            video_path, video_info = await download_task
            
        print(f"✅ Video ready at: {os.path.basename(video_path)}")

        # Add URL to info so it can be passed to AI
        video_info['url'] = url

        # 2. Sequential Execution (AI then Render) to save memory
        description = "סרטון חדש! 🎥" # Default
        try:
            print("🧠 Generating AI description...")
            context_prompt = f"Video Title (User): {headline}\nVideo Body (User): {body_text}"
            # Run AI in thread
            description = await asyncio.to_thread(ai_generator.generate_description, context_prompt, video_info)
            print("✅ AI Description generated.")
        except Exception as ai_e:
            print(f"⚠️ AI Generation failed (skipping): {ai_e}")
            description = f"{headline}\n\n{body_text}"

        print("🎨 Starting video render...")
        final_video_path = await asyncio.to_thread(
            graphics_engine.render_video, 
            video_path, 
            headline, 
            body_text,
            layout_mode 
        )
        print(f"✅ Rendering complete: {os.path.basename(final_video_path)}")
        
        # 4. Send back
        await update.message.reply_text("🚀 מוכן! מעלה אליך...")
        
        with open(final_video_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=description,
                width=1080,
                height=1920,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300 
            )
        
        # 5. Cleanup
        files_to_remove = [video_path, final_video_path, os.path.join(Config.TEMP_DIR, "overlay.png")]
        for f in files_to_remove:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"⚠️ Cleanup warning: Could not remove {f}: {e}")
        
        print("✨ Task completed successfully and cleaned up.")
        
        # Reset state
        context.user_data.clear()

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        await update.message.reply_text(f"❌ שגיאה: {str(e)}")
        # Partial Cleanup
        if 'video_path' in locals() and os.path.exists(video_path):
            os.remove(video_path)
        overlay_tmp = os.path.join(Config.TEMP_DIR, "overlay.png")
        if os.path.exists(overlay_tmp):
            os.remove(overlay_tmp)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ הפעולה בוטלה.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

async def send_startup_notification(application):
    """Send a startup notification to all allowed users."""
    from datetime import datetime
    
    allowed_users = Config.get_allowed_user_ids()
    if not allowed_users:
        print("⚠️ No allowed users configured for startup notification.")
        return
    
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    

    # Check Instagram login status
    ig_auth = get_instagram_auth()
    # Login check removed as per request
        
    ig_status = "❌ לא מחובר (מבוטל)" 
    
    message = (
        r"🤖 *הבוט מוכן ופעיל!*" + "\n\n"
        f"⏰ זמן התחלה: `{startup_time}`\n"
        r"✅ כל המערכות עובדות תקין" + "\n\n"
        f"📸 סטטוס אינסטגרם: {ig_status}\n\n"
        r"*פקודות זמינות:*" + "\n"
        r"• /start - ליצור סרטון חדש" + "\n"
        r"• /story - תזמון סטורי לאינסטגרם" + "\n"
        r"• /scan - סריקת טרנדים" + "\n"
        r"• /add - הוספת משתמש TikTok למעקב" + "\n"
        r"• /remove - הסרת משתמש מהמעקב" + "\n"
        r"• /watchlist - רשימת המעקב" + "\n"
        r"• /trendshelp - עזרה" + "\n"
        r"• /cancel - ביטול פעולה נוכחית"
    )
    
    for user_id in allowed_users:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            print(f"✅ Startup notification sent to user {user_id}")
        except Exception as e:
            print(f"⚠️ Failed to send startup notification to {user_id}: {e}")
            # Try sending without markdown as fallback
            try:
                await application.bot.send_message(chat_id=user_id, text=message)
                print(f"✅ Startup notification sent (raw fallback) to {user_id}")
            except:
                pass



# ============================================================
# Instagram Login Handlers (REMOVED)
# ============================================================


async def main():
    """Main async function to run the bot."""
    Config.ensure_dirs()
    
    keep_alive()
    
    await asyncio.sleep(3)
    
    print("🤖 Bot is starting...")
    
    trequest = HTTPXRequest(connection_pool_size=8, read_timeout=300, write_timeout=300, connect_timeout=60)
    
    application = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).request(trequest).build()
    

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link),
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video)
            ],
            CHOOSE_STORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_story_choice)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_body)],
            LAYOUT_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_layout_choice)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Initialize the application and send startup notification
    await application.initialize()
    
    # Setup Instagram Stories Bot (if available)
    if STORIES_BOT_AVAILABLE:
        try:
            await setup_stories_bot(application)
        except Exception as e:
            print(f"❌ Failed to setup Instagram Stories Bot: {e}")

    # Setup Trend Scanner (merged content discovery + trend hunter)
    if TREND_SCANNER_AVAILABLE:
        try:
            await setup_trend_scanner(application)
        except Exception as e:
            print(f"❌ Failed to setup Trend Scanner: {e}")

    await send_startup_notification(application)
    
    # Start polling
    await application.start()
    await application.updater.start_polling()
    
    print("🤖 Bot is now running and ready!")
    
    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Shutting down...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == '__main__':
    asyncio.run(main())