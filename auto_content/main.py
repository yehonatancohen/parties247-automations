import os
import asyncio
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

# Initialize Services
graphics_engine = GraphicsEngine()
ai_generator = AIGenerator()

# States
LINK, TITLE, BODY, LAYOUT_CHOICE = range(4)

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

        # 2. Parallel Render & AI
        def ai_task(info):
            context_prompt = f"Video Title (User): {headline}\nVideo Body (User): {body_text}"
            return ai_generator.generate_description(context_prompt, info)
        
        print("🎨 Starting render & AI generation...")
        render_future = asyncio.to_thread(
            graphics_engine.render_video, 
            video_path, 
            headline, 
            body_text,
            layout_mode 
        )
        
        ai_future = asyncio.to_thread(ai_task, video_info)
        
        final_video_path, description = await asyncio.gather(render_future, ai_future)
        
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

if __name__ == '__main__':
    Config.ensure_dirs()

    keep_alive()

    asyncio.sleep(3)
    
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
    
    application.add_handler(conv_handler)
    
    application.run_polling()