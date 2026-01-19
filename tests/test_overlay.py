import os
import sys
from dotenv import load_dotenv

os.environ['ALLOWED_USER_ID'] = '12345' # Dummy value for testing
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from services.graphics import GraphicsEngine
from config import Config

def test_overlay_creation():
    """
    Tests the creation of an overlay image without running the full video processing pipeline.
    """
    # --- Configuration ---
    Config.ensure_dirs()
    headline = "🎉 מסיבת יום הולדת שמח! 🥳"
    body = "חוגגים לגיל 5! 🎂 המון מזל טוב, אושר, ועושר. שתהיה לך שנה נפלאה ומתוקה. 💖 אוהבים, כל המשפחה. 👨‍👩‍👧‍👦"

    # --- Engine Initialization ---
    graphics_engine = GraphicsEngine()

    # --- Create a dummy video file ---
    dummy_video_path = os.path.join(Config.TEMP_DIR, "dummy_video.mp4")
    if not os.path.exists(dummy_video_path):
        ret_code = os.system(f"ffmpeg -f lavfi -i testsrc=size=1920x1080:rate=30:duration=10 -pix_fmt yuv420p {dummy_video_path}")
        if ret_code != 0:
            print("⚠️ ffmpeg not found. Dummy video not created.")


    # --- Overlay Creation ---
    try:
        # Test with layout_mode='lower'
        output_path = graphics_engine.render_video(dummy_video_path, headline, body, layout_mode='lower')
        print(f"✅ Video rendered successfully at: {output_path}")
    except Exception as e:
        print(f"❌ Error rendering video: {e}")

if __name__ == "__main__":
    test_overlay_creation()
