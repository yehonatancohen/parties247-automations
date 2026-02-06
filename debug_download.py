import sys
import os
import traceback

# Add project source to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, 'projects', 'video_creator', 'src')
sys.path.append(src_path)

try:
    from services.downloader import VideoDownloader
    from config import Config
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)



def run_debug_download():
    # Ensure dirs exist
    try:
        Config.ensure_dirs()
    except Exception as e:
        print(f"Warning: Could not ensure directories: {e}")

    # URL to test (Reel is fine, it should return 1 story)
    url = "https://www.instagram.com/reel/DT-zYb6CCjZ/?igsh=YzN4enQ3cXdhMXli"
    
    print("=" * 60)
    print("Instagram Story/Playlist Fetch Test")
    print("=" * 60)
    print(f"Target URL: {url}")
    print("-" * 60)
    print("Calling VideoDownloader.fetch_available_stories(url)...")

    try:
        stories = VideoDownloader.fetch_available_stories(url)
        print("\n" + "=" * 60)
        print("✅ SUCCESS!")
        print(f"Found {len(stories)} stories/videos:")
        
        for i, story in enumerate(stories):
            print(f"[{i+1}] {story.get('title')} (ID: {story.get('id')})")
            print(f"    URL: {story.get('url')}")
            print(f"    Duration: {story.get('duration')}s")

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ FETCH FAILED")
        print(f"Error: {e}")
        print("-" * 60)
        print("Traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    run_debug_download()

