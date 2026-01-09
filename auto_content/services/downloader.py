import os
import uuid
import requests
import yt_dlp
from playwright.sync_api import sync_playwright
from config import Config

class VideoDownloader:
    @staticmethod
    def download_video(url: str) -> str:
        """
        Downloads a video. Uses Playwright for TikTok (anti-bot bypass) and yt-dlp for everything else.
        """
        output_filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(Config.TEMP_DIR, output_filename)
        
        # --- STRATEGY SELECTION ---
        if "tiktok.com" in url:
            return VideoDownloader._download_with_playwright(url, output_path)
        else:
            return VideoDownloader._download_with_ytdlp(url, output_path)

    @staticmethod
    def _download_with_ytdlp(url: str, output_path: str) -> str:
        print(f"⬇️ Downloading via yt-dlp: {url}...")
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Verify file exists and handle potential extension changes
            if not os.path.exists(output_path):
                if os.path.exists(output_path + ".mp4"):
                    return output_path + ".mp4"
                elif os.path.exists(output_path.replace(".mp4", ".mkv")):
                    return output_path.replace(".mp4", ".mkv")
                
                raise FileNotFoundError(f"Download finished but file not found at {output_path}")
                
            print(f"✅ Download complete: {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ yt-dlp failed: {e}")
            raise e

    @staticmethod
    def _download_with_playwright(url: str, output_path: str) -> str:
        print(f"⬇️ Downloading via Playwright: {url}...")
        try:
            with sync_playwright() as p:
                # Launch browser (headless=True for background)
                browser = p.chromium.launch(headless=True)
                
                # Create context with mobile user agent
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
                    viewport={'width': 375, 'height': 812}
                )
                
                page = context.new_page()
                
                print("   - Navigating to page...")
                page.goto(url, timeout=60000)
                
                print("   - Waiting for video element...")
                try:
                    video_element = page.wait_for_selector('video', timeout=30000)
                except Exception:
                    print("   ! Video element not found immediately, waiting longer...")
                    video_element = page.wait_for_selector('video', timeout=60000)
                
                if not video_element:
                    raise Exception("Could not find <video> tag on page.")
                
                # Get the src attribute
                video_url = video_element.get_attribute('src')
                print(f"   - Found video URL: {video_url[:50]}...")
                
                # Get cookies
                cookies = context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                
                # Download
                print("   - Downloading content...")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
                    'Referer': url 
                }
                
                with requests.get(video_url, headers=headers, cookies=cookie_dict, stream=True) as r:
                    r.raise_for_status()
                    with open(output_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                browser.close()
                
            if not os.path.exists(output_path):
                 raise FileNotFoundError("Download finished but file not found.")

            print(f"✅ Download complete: {output_path}")
            return output_path

        except Exception as e:
            print(f"❌ Playwright failed: {e}")
            raise e