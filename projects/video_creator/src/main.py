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

# Initialize Services
graphics_engine = GraphicsEngine()
ai_generator = AIGenerator()

# Conversation states for video creation
LINK, TITLE, BODY, LAYOUT_CHOICE = range(4)

# Conversation states for Instagram login
IG_USERNAME, IG_PASSWORD, IG_2FA_CODE = range(10, 13)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != Config.ALLOWED_USER_ID:
        await update.message.reply_text("⛔ גישה נדחתה.")
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 היי! בוא ניצור סרטון חדש.\n"
        "שלח לי את הלינק לסרטון (TikTok/Instagram/YouTube):",
        reply_markup=ReplyKeyboardRemove()
    )
    return LINK

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    context.user_data['link'] = link
    
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
    ig_status = "✅ מחובר" if ig_auth.has_saved_session() else "❌ לא מחובר"
    
    message = (
        "🤖 *הבוט מוכן ופעיל!*\n\n"
        f"⏰ זמן התחלה: `{startup_time}`\n"
        "✅ כל המערכות עובדות תקין\n\n"
        f"📸 סטטוס אינסטגרם: {ig_status}\n\n"
        "*פקודות זמינות:*\n"
        "• /start - ליצור סרטון חדש\n"
        "• /login\\_instagram - התחבר לאינסטגרם\n"
        "• /logout\\_instagram - התנתק מאינסטגרם\n"
        "• /instagram\\_status - בדוק סטטוס\n"
        "• /cancel - ביטול פעולה נוכחית"
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


# ============================================================
# Instagram Login Handlers
# ============================================================

async def login_instagram_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Instagram login process."""
    user_id = update.effective_user.id
    if user_id not in Config.get_allowed_user_ids():
        await update.message.reply_text("⛔ גישה נדחתה.")
        return ConversationHandler.END
    
    ig_auth = get_instagram_auth()
    
    # Check if already logged in
    if ig_auth.has_saved_session():
        await update.message.reply_text(
            "✅ אתה כבר מחובר לאינסטגרם!\n"
            "אם ברצונך להתנתק, שלח /logout_instagram"
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔐 *התחברות לאינסטגרם*\n\n"
        "זה יאפשר לי להוריד סרטונים מאינסטגרם בצורה אמינה יותר.\n\n"
        "📧 שלח את שם המשתמש שלך באינסטגרם:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    return IG_USERNAME


async def receive_ig_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive Instagram username."""
    username = update.message.text.strip()
    context.user_data['ig_username'] = username
    
    await update.message.reply_text(
        "🔑 עכשיו שלח את הסיסמה שלך:\n\n"
        "_(ההודעה תימחק מיד לאבטחה)_",
        parse_mode='Markdown'
    )
    return IG_PASSWORD


async def receive_ig_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive Instagram password and attempt login."""
    password = update.message.text.strip()
    username = context.user_data.get('ig_username', '')
    
    # Try to delete the password message for security
    try:
        await update.message.delete()
    except:
        pass
    
    # Store password for potential 2FA retry
    context.user_data['ig_password'] = password
    
    await update.message.reply_text(
        "⏳ מנסה להתחבר לאינסטגרם...\n"
        "זה עשוי לקחת מספר שניות..."
    )
    
    ig_auth = get_instagram_auth()
    
    # Create a 2FA callback that will signal we need 2FA
    context.user_data['needs_2fa'] = False
    
    async def on_2fa_required():
        """Called when Instagram requests 2FA."""
        context.user_data['needs_2fa'] = True
        # Wait for user to provide 2FA code
        await update.message.reply_text(
            "🔐 *נדרש קוד אימות דו-שלבי*\n\n"
            "אינסטגרם שולח לך קוד SMS או קוד מאפליקציית האימות.\n"
            "שלח את הקוד כאן:",
            parse_mode='Markdown'
        )
        
        # Wait for code to be set in context
        for _ in range(120):  # Wait up to 2 minutes
            await asyncio.sleep(1)
            if context.user_data.get('2fa_code'):
                code = context.user_data.pop('2fa_code')
                return code
        return None
    
    try:
        result = await ig_auth.login(username, password, on_2fa_required)
        
        # Clear sensitive data
        context.user_data.pop('ig_password', None)
        
        if result.get('needs_2fa'):
            await update.message.reply_text(
                "🔐 *נדרש קוד אימות דו-שלבי*\n\n"
                "אינסטגרם שולח לך קוד SMS או קוד מאפליקציית האימות.\n"
                "שלח את הקוד כאן:",
                parse_mode='Markdown'
            )
            return IG_2FA_CODE
        
        if result.get('success'):
            await update.message.reply_text(
                "✅ *התחברת בהצלחה לאינסטגרם!*\n\n"
                "עכשיו אני יכול להוריד סרטונים מחשבונות פרטיים ובאמינות גבוהה יותר.\n\n"
                "שלח /start כדי ליצור סרטון חדש 🚀",
                parse_mode='Markdown'
            )
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"❌ ההתחברות נכשלה:\n{result.get('message', 'שגיאה לא ידועה')}\n\n"
                "נסה שוב עם /login_instagram"
            )
            context.user_data.clear()
            return ConversationHandler.END
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ שגיאה בהתחברות: {str(e)}\n\n"
            "נסה שוב מאוחר יותר."
        )
        context.user_data.clear()
        return ConversationHandler.END


async def receive_ig_2fa_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process 2FA code."""
    code = update.message.text.strip()
    
    # Store code for the waiting login process
    context.user_data['2fa_code'] = code
    
    await update.message.reply_text(
        "⏳ מאמת את הקוד...",
    )
    
    # Wait a moment for the login process to pick up the code
    await asyncio.sleep(5)
    
    # Check if login succeeded
    ig_auth = get_instagram_auth()
    if ig_auth.has_saved_session():
        await update.message.reply_text(
            "✅ *התחברת בהצלחה לאינסטגרם!*\n\n"
            "עכשיו אני יכול להוריד סרטונים מחשבונות פרטיים ובאמינות גבוהה יותר.\n\n"
            "שלח /start כדי ליצור סרטון חדש 🚀",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ הקוד לא התקבל או שפג תוקפו.\n"
            "נסה שוב עם /login_instagram"
        )
    
    context.user_data.clear()
    return ConversationHandler.END


async def logout_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logout from Instagram (clear saved session)."""
    user_id = update.effective_user.id
    if user_id not in Config.get_allowed_user_ids():
        await update.message.reply_text("⛔ גישה נדחתה.")
        return
    
    ig_auth = get_instagram_auth()
    ig_auth.clear_session()
    
    await update.message.reply_text(
        "✅ התנתקת מאינסטגרם בהצלחה.\n\n"
        "אם תרצה להתחבר שוב, שלח /login_instagram"
    )


async def instagram_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check Instagram login status."""
    user_id = update.effective_user.id
    if user_id not in Config.get_allowed_user_ids():
        await update.message.reply_text("⛔ גישה נדחתה.")
        return
    
    ig_auth = get_instagram_auth()
    
    if ig_auth.has_saved_session():
        await update.message.reply_text(
            "✅ *סטטוס אינסטגרם: מחובר*\n\n"
            "הורדת סרטונים מאינסטגרם תעבוד באמינות גבוהה.\n\n"
            "• להתנתק: /logout\_instagram",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ *סטטוס אינסטגרם: לא מחובר*\n\n"
            "הורדת סרטונים מאינסטגרם עשויה להיכשל עקב הגבלות.\n\n"
            "• להתחבר: /login\_instagram",
            parse_mode='Markdown'
        )


async def cancel_instagram_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel Instagram login process."""
    await update.message.reply_text(
        "❌ ההתחברות לאינסטגרם בוטלה.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


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
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_body)],
            LAYOUT_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_layout_choice)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Instagram login conversation handler
    ig_login_handler = ConversationHandler(
        entry_points=[CommandHandler('login_instagram', login_instagram_start)],
        states={
            IG_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ig_username)],
            IG_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ig_password)],
            IG_2FA_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ig_2fa_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel_instagram_login)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(ig_login_handler)
    
    # Standalone Instagram commands
    application.add_handler(CommandHandler('logout_instagram', logout_instagram))
    application.add_handler(CommandHandler('instagram_status', instagram_status))
    
    # Initialize the application and send startup notification
    await application.initialize()
    
    # Setup Instagram Stories Bot (if available)
    if STORIES_BOT_AVAILABLE:
        try:
            await setup_stories_bot(application)
        except Exception as e:
            print(f"❌ Failed to setup Instagram Stories Bot: {e}")

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