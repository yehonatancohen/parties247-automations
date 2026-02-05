"""
Instagram Stories Automation Bot

Telegram bot for scheduling Instagram story uploads with link stickers.
Supports natural language scheduling in Hebrew and English.
"""

import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    CommandHandler,
)
from telegram.request import HTTPXRequest

from stories_config import Config
from models import Database, ScheduledStory
from schedule_parser import parse_schedule, format_schedule_summary, ParsedSchedule, get_local_now

# Initialize services
db = Database()

# Conversation states
IMAGE, LINK, SCHEDULE, LINK_TEXT, CONFIRM = range(5)


async def story_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the story scheduling conversation with /story command."""
    user_id = update.effective_user.id
    allowed_users = Config.get_allowed_user_ids()
    
    if allowed_users and user_id not in allowed_users:
        await update.message.reply_text("⛔ גישה נדחתה.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📸 *תזמון סטורי לאינסטגרם*\n\n"
        "שלח לי את התמונה שתרצה להעלות:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    return IMAGE


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the story image."""
    # Check if it's a photo
    if update.message.photo:
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Save to temp directory
        Config.ensure_dirs()
        image_path = os.path.join(
            Config.TEMP_DIR, 
            f"story_{update.effective_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        )
        await file.download_to_drive(image_path)
        context.user_data['image_path'] = image_path
        
        await update.message.reply_text(
            "✅ תמונה התקבלה!\n\n"
            "עכשיו שלח את הלינק שיופיע בסטורי (לחיצה על הלינק תעביר לאתר):"
        )
        return LINK
    
    # Check if it's a document (image file)
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        file = await context.bot.get_file(update.message.document.file_id)
        
        Config.ensure_dirs()
        image_path = os.path.join(
            Config.TEMP_DIR,
            f"story_{update.effective_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        )
        await file.download_to_drive(image_path)
        context.user_data['image_path'] = image_path
        
        await update.message.reply_text(
            "✅ תמונה התקבלה!\n\n"
            "עכשיו שלח את הלינק שיופיע בסטורי:"
        )
        return LINK
    
    await update.message.reply_text(
        "❌ אנא שלח תמונה (לא קובץ אחר).\n"
        "נסה שוב:"
    )
    return IMAGE


async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the link URL."""
    link = update.message.text.strip()
    
    # Basic URL validation
    if not (link.startswith('http://') or link.startswith('https://')):
        await update.message.reply_text(
            "❌ הלינק חייב להתחיל ב-http:// או https://\n"
            "נסה שוב:"
        )
        return LINK
    
    context.user_data['link_url'] = link
    
    # Provide preset options for link text
    keyboard = [
        ['🛒 קנה כאן', '🎫 לרכישת כרטיסים'],
        ['👆 לחץ כאן', '📍 לפרטים נוספים'],
        ['✍️ טקסט מותאם אישית']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "✅ לינק נשמר!\n\n"
        "בחר את הטקסט שיופיע על הסטורי (מעל הלינק):",
        reply_markup=reply_markup
    )
    return LINK_TEXT


async def receive_link_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the link text to display."""
    text = update.message.text.strip()
    
    # Check if user wants custom text
    if 'מותאם אישית' in text or 'custom' in text.lower():
        await update.message.reply_text(
            "✍️ שלח את הטקסט שתרצה שיופיע על הסטורי:",
            reply_markup=ReplyKeyboardRemove()
        )
        return LINK_TEXT
    
    # Use selected preset (remove emoji prefix from keyboard buttons)
    context.user_data['link_text'] = text
    
    # Time presets
    now = get_local_now()
    today_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now.hour >= 18:
        today_18 += timedelta(days=1)
        label_18 = "מחר 18:00"
    else:
        label_18 = "היום 18:00"
        
    tomorrow_10 = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    keyboard = [
        [label_18, 'מחר 10:00'],
        ['עוד שעה', 'עוד 3 שעות'],
        ['ביטול']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "✅ טקסט נשמר!\n\n"
        "עכשיו שלח מתי להעלות את הסטורי או בחר אפשרות:",
        reply_markup=reply_markup
    )
    return SCHEDULE


async def receive_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse and validate the schedule."""
    schedule_text = update.message.text.strip()
    
    # Handle relative time buttons
    now = get_local_now()
    if schedule_text == 'עוד שעה':
        target_time = now + timedelta(hours=1)
        schedule = ParsedSchedule(times=[target_time], recurrence=None, recurrence_day=None)
        context.user_data['schedule'] = schedule
        schedule_parsed = True
    elif schedule_text == 'עוד 3 שעות':
        target_time = now + timedelta(hours=3)
        schedule = ParsedSchedule(times=[target_time], recurrence=None, recurrence_day=None)
        context.user_data['schedule'] = schedule
        schedule_parsed = True
    else:
        try:
            schedule = parse_schedule(schedule_text)
            context.user_data['schedule'] = schedule
            schedule_parsed = True
        except ValueError as e:
            await update.message.reply_text(str(e))
            return SCHEDULE
            
    if schedule_parsed:
        # Format confirmation message
        summary = format_schedule_summary(schedule)
        
        keyboard = [['✅ אישור והעלאה', '❌ ביטול']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"📋 *סיכום הסטורי:*\n\n"
            f"🔗 לינק: {context.user_data['link_url']}\n"
            f"💬 טקסט: {context.user_data['link_text']}\n\n"
            f"*תזמון:*\n{summary}\n\n"
            f"האם לאשר?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return CONFIRM


async def confirm_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and save the scheduled story."""
    choice = update.message.text.strip()
    
    if 'ביטול' in choice or 'cancel' in choice.lower():
        # Cleanup temp image
        image_path = context.user_data.get('image_path')
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        
        context.user_data.clear()
        await update.message.reply_text(
            "❌ הפעולה בוטלה.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Save scheduled stories to database
    schedule = context.user_data['schedule']
    saved_count = 0
    
    for scheduled_time in schedule.times:
        story = ScheduledStory(
            id=None,
            user_id=update.effective_user.id,
            image_path=context.user_data['image_path'],
            link_url=context.user_data['link_url'],
            link_text=context.user_data['link_text'],
            scheduled_time=scheduled_time,
            recurrence=schedule.recurrence,
            recurrence_day=schedule.recurrence_day,
            status='pending',
            created_at=get_local_now()
        )
        db.add_story(story)
        saved_count += 1
    
    # Schedule the jobs in the job queue
    for scheduled_time in schedule.times:
        delay = (scheduled_time - get_local_now()).total_seconds()
        if delay > 0:
            context.job_queue.run_once(
                upload_story_job,
                when=delay,
                data={
                    'image_path': context.user_data['image_path'],
                    'link_url': context.user_data['link_url'],
                    'link_text': context.user_data['link_text'],
                    'user_id': update.effective_user.id,
                },
                name=f"story_{update.effective_user.id}_{scheduled_time.isoformat()}"
            )
    
    await update.message.reply_text(
        f"✅ *נשמר בהצלחה!*\n\n"
        f"📸 {saved_count} סטוריז תוזמנו לתזכורת.\n"
        f"תקבל את התמונה והלינק בזמן שנבחר.\n\n"
        f"השתמש ב-/mystories כדי לראות את כל הסטוריז המתוזמנים שלך.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def upload_story_job(context: ContextTypes.DEFAULT_TYPE):
    """Background job to remind user to upload a scheduled story."""
    job_data = context.job.data
    
    try:
        # Prepare caption with the link and text
        caption = (
            f"⏰ *תזכורת להעלאת סטורי!*\n\n"
            f"🔗 לינק: {job_data['link_url']}\n"
            f"💬 טקסט בסטורי: {job_data['link_text']}\n\n"
            f"אנא העלה את הסטורי עכשיו ידנית דרך האפליקציה."
        )
        
        # Send the photo back to the user
        await context.bot.send_photo(
            chat_id=job_data['user_id'],
            photo=job_data['image_path'],
            caption=caption,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        # Notify user of failure
        await context.bot.send_message(
            chat_id=job_data['user_id'],
            text=f"❌ שגיאה בשליחת תזכורת לסטורי\n\n"
            f"פרטים: {str(e)}",
            parse_mode=None
        )


async def my_stories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's scheduled stories with /mystories command."""
    user_id = update.effective_user.id
    stories = db.get_user_stories(user_id, status='pending')
    
    if not stories:
        await update.message.reply_text(
            "📭 אין לך סטוריז מתוזמנים כרגע.\n\n"
            "השתמש ב-/story כדי לתזמן סטורי חדש."
        )
        return
    
    lines = ["📋 *הסטוריז המתוזמנים שלך:*\n"]
    day_names_he = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
    
    for story in stories[:10]:  # Limit to 10
        day_name = day_names_he[story.scheduled_time.weekday()]
        time_str = story.scheduled_time.strftime('%d/%m %H:%M')
        recurrence_str = ""
        if story.recurrence == 'daily':
            recurrence_str = " 🔄"
        elif story.recurrence == 'weekly':
            recurrence_str = " 🔄"
        
        lines.append(f"• יום {day_name} {time_str}{recurrence_str}")
        lines.append(f"  🔗 {story.link_url[:30]}...")
    
    if len(stories) > 10:
        lines.append(f"\n...ועוד {len(stories) - 10} סטוריז נוספים")
    
    lines.append("\n\nלביטול סטורי, השתמש ב-/cancelstory")
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode='Markdown'
    )


async def cancel_story_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel a scheduled story with /cancelstory command."""
    user_id = update.effective_user.id
    stories = db.get_user_stories(user_id, status='pending')
    
    if not stories:
        await update.message.reply_text("📭 אין לך סטוריז מתוזמנים לביטול.")
        return
    
    # Create numbered list
    lines = ["📋 *בחר סטורי לביטול:*\n"]
    day_names_he = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
    
    for i, story in enumerate(stories[:10], 1):
        day_name = day_names_he[story.scheduled_time.weekday()]
        time_str = story.scheduled_time.strftime('%d/%m %H:%M')
        lines.append(f"{i}. יום {day_name} {time_str}")
    
    lines.append("\n\nשלח את המספר של הסטורי לביטול:")
    
    context.user_data['cancel_stories'] = stories[:10]
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode='Markdown'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current conversation with /cancel command."""
    # Cleanup temp image if exists
    image_path = context.user_data.get('image_path')
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except:
            pass
    
    context.user_data.clear()
    await update.message.reply_text(
        "❌ הפעולה בוטלה.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message with /help command."""
    await update.message.reply_text(
        "📸 *בוט סטוריז לאינסטגרם*\n\n"
        "*פקודות זמינות:*\n"
        "/story - תזמון סטורי חדש\n"
        "/mystories - הצגת סטוריז מתוזמנים\n"
        "/cancelstory - ביטול סטורי מתוזמן\n"
        "/help - עזרה\n\n"
        "*תזמונים אפשריים:*\n"
        "• `היום 18:00` - היום בשעה מסוימת\n"
        "• `מחר 10:00` - מחר בשעה מסוימת\n"
        "• `ראשון 20:00` - ביום ספציפי\n"
        "• `כל ראשון 18:00` - כל שבוע\n"
        "• `כל יום 09:00` - כל יום\n"
        "• `3 פעמים השבוע` - פיזור אוטומטי\n"
        "• `15/02 20:00` - בתאריך ספציפי",
        parse_mode='Markdown'
    )


async def restore_scheduled_jobs(application):
    """Restore scheduled jobs from database on startup."""
    pending_stories = db.get_pending_stories()
    now = get_local_now()
    restored_count = 0
    
    for story in pending_stories:
        if story.scheduled_time > now:
            delay = (story.scheduled_time - now).total_seconds()
            application.job_queue.run_once(
                upload_story_job,
                when=delay,
                data={
                    'image_path': story.image_path,
                    'link_url': story.link_url,
                    'link_text': story.link_text,
                    'user_id': story.user_id,
                },
                name=f"story_{story.user_id}_{story.scheduled_time.isoformat()}"
            )
            restored_count += 1
        else:
            # Mark as failed if time has passed
            db.update_status(story.id, 'failed', 'Missed scheduled time')
    
    print(f"📅 Restored {restored_count} scheduled story jobs")


async def send_startup_notification(application):
    """Send startup notification to allowed users."""
    allowed_users = Config.get_allowed_user_ids()
    if not allowed_users:
        return
    
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        "📸 *בוט הסטוריז מוכן ופעיל!*\n\n"
        f"⏰ זמן התחלה: `{startup_time}`\n"
        "✅ כל המערכות עובדות תקין\n\n"
        "שלח /story כדי לתזמן סטורי 🚀"
    )
    
    for user_id in allowed_users:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"⚠️ Failed to send startup notification to {user_id}: {e}")


async def setup_stories_bot(application):
    """Setup the Instagram Stories bot handlers and services."""
    print("=" * 50)
    print("📸 Setting up Instagram Stories Bot")
    print("=" * 50)
    
    Config.ensure_dirs()
    
    # Story scheduling conversation handler
    story_conv = ConversationHandler(
        entry_points=[CommandHandler('story', story_command)],
        states={
            IMAGE: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            LINK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link_text)],
            SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_schedule)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_schedule)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers to the shared application
    application.add_handler(story_conv)
    application.add_handler(CommandHandler('mystories', my_stories))
    application.add_handler(CommandHandler('cancelstory', cancel_story_command))
    application.add_handler(CommandHandler('help_stories', help_command))  # Renamed to avoid conflict
    
    # Restore scheduled jobs from database
    await restore_scheduled_jobs(application)
    
    # We skip startup notification here as the main bot handles it
    print("📸 Instagram Stories handlers registered!")
