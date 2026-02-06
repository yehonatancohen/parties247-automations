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

    # URL from the existing test file
    url = "https://www.instagram.com/reel/DT-zYb6CCjZ/?igsh=YzN4enQ3cXdhMXli"
    
    print("=" * 60)
    print("Instagram Download Validaton Script")
    print("=" * 60)
    print(f"Target URL: {url}")
    print("-" * 60)
    print("Calling VideoDownloader.download_video(url)...")

    try:
        path, metadata = VideoDownloader.download_video(url)
        print("\n" + "=" * 60)
        print("✅ SUCCESS!")
        print(f"Video saved to: {path}")
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"File Size: {size_mb:.2f} MB")
        else:
            print("WARNING: File path returned but file does not exist!")
            
        print("Metadata extracted:")
        for k, v in metadata.items():
            print(f"  {k}: {v}")
            
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ DOWNLOAD FAILED")
        print(f"Error: {e}")
        print("-" * 60)
        print("Traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    run_debug_download()
