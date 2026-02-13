import sys
import os

# Add the project directory to sys.path so we can import trend_hunter
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from trend_hunter import process_all_users, logger

if __name__ == "__main__":
    logger.info("🚀 Starting manual test run of TikTok Trend Hunter...")
    
    try:
        process_all_users()
        logger.info("✅ Test run completed.")
    except Exception as e:
        logger.error(f"❌ Test run failed: {e}")
