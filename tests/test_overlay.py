import os
import sys
from dotenv import load_dotenv

os.environ['ALLOWED_USER_ID'] = '12345' # Dummy value for testing
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from services.graphics import GraphicsEngine
from config import Config

def test_overlay_creation_with_emojis(mocker):
    """
    Tests the creation of an overlay image with Hebrew and emojis,
    and verifies the output overlay file is generated successfully.
    """
    # --- Configuration ---
    Config.ensure_dirs()
    headline = "בדיקה 🎉"
    body = "חוגגים לגיל 5! 🎂 המון מזל טוב, אושר, ועושר. שתהיה לך שנה נפלאה ומתוקה. 💖 אוהבים, כל המשפחה. 👨‍👩‍👧‍👦"

    # --- Engine Initialization ---
    graphics_engine = GraphicsEngine()

    # --- Create a dummy video file ---
    dummy_video_path = os.path.join(Config.TEMP_DIR, "dummy_video.mp4")
    # Create an empty dummy video file
    with open(dummy_video_path, 'a'):
        os.utime(dummy_video_path, None)

    # Mock subprocess.run to prevent actual ffmpeg calls
    mock_subprocess_run = mocker.patch('subprocess.run')
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stdout = b'10.0' # for ffprobe
    mock_subprocess_run.return_value.stderr = b''

    # --- Overlay Creation ---
    overlay_path = None
    try:
        # Directly call _create_overlay to generate the overlay image
        overlay_path = graphics_engine._create_overlay(headline, body)
        print(f"✅ Overlay image created successfully at: {overlay_path}")
    except Exception as e:
        print(f"❌ Error creating overlay image: {e}")
        raise e

    # --- Assertion ---
    assert overlay_path is not None
    assert os.path.exists(overlay_path)

