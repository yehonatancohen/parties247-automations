import os
import asyncio
from telegram import Update, ReplyKeyboardRemove
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
from services.downloader import VideoDownloader
from services.graphics import GraphicsEngine

# Initialize Engine globally to load fonts once
graphics_engine = GraphicsEngine()

# States for ConversationHandler
LINK, TITLE, BODY = range(3)

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
    
    await update.message.reply_text(
        "✅ לינק התקבל.\n"
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
    
    # Retrieve data
    url = context.user_data['link']
    headline = context.user_data['title']
    
    await update.message.reply_text("⏳ תודה! מתחיל בעבודה... הורדת סרטון...")

    try:
        # 1. Download (Running in thread to not block async loop)
        video_path = await asyncio.to_thread(VideoDownloader.download_video, url)
        
        # Line 85: Just print to console as requested
        print("🎨 הסרטון ירד, מתחיל עיצוב ורינדור...")
        
        # 2. Render (CPU Bound task - running in thread)
        final_video_path = await asyncio.to_thread(
            graphics_engine.render_video, 
            video_path, 
            headline, 
            body
        )
        
        # 3. Send back
        await update.message.reply_text("🚀 מוכן! מעלה אליך...")
        
        with open(final_video_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                width=1080,
                height=1920,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300 
            )
        
        # 4. Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(final_video_path):
            os.remove(final_video_path)
        
        # Reset state for next time
        context.user_data.clear()

    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה: {str(e)}")
        # Cleanup if failed
        if 'video_path' in locals() and os.path.exists(video_path):
            os.remove(video_path)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ הפעולה בוטלה.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

if __name__ == '__main__':
    Config.ensure_dirs()
    
    print("🤖 Bot is starting...")
    
    # Configure long timeouts for video uploads
    trequest = HTTPXRequest(connection_pool_size=8, read_timeout=300, write_timeout=300, connect_timeout=60)
    
    application = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).request(trequest).build()
    
    # Add ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_body)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    application.run_polling()