"""
Test Instagram video downloading using the VideoDownloader service.
"""
import os
import sys

os.environ['ALLOWED_USER_ID'] = '12345'

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

from config import Config
from services.downloader import VideoDownloader


def test_instagram_download():
    """Test downloading an Instagram reel."""
    Config.ensure_dirs()
    
    url = "https://www.instagram.com/reel/DT-zYb6CCjZ/?igsh=YzN4enQ3cXdhMXli"
    
    print("=" * 60)
    print("Instagram Download Test")
    print("=" * 60)
    print(f"URL: {url}")
    print("-" * 60)
    
    try:
        video_path, metadata = VideoDownloader.download_video(url)
        
        print(f"\n✅ SUCCESS!")
        print(f"   Video path: {video_path}")
        print(f"   File size: {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
        print(f"   Metadata: {metadata}")
        
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
            print(f"   Cleaned up test file")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


if __name__ == "__main__":
    success = test_instagram_download()
    print("\n" + "=" * 60)
    if success:
        print("✅ Test PASSED")
    else:
        print("❌ Test FAILED")
    sys.exit(0 if success else 1)
