import os
import uuid
import requests
import yt_dlp
from playwright.sync_api import sync_playwright
from config import Config
from services.instagram_auth import get_instagram_auth

import imageio_ffmpeg

class VideoDownloader:
    @staticmethod
    def extract_info(url: str) -> dict:
        """
        Extract video info without downloading.
        Useful for checking if a link is a playlist/story container.
        """
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just list
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return info
            except Exception as e:
                print(f"[WARN] extract_info failed: {e}")
                return {}

    @staticmethod
    def fetch_available_stories(url: str) -> list[dict]:
        """
        Fetches metadata for all stories/videos available at the given URL.
        Returns a list of dictionaries, each representing a story/video.
        """
        info = VideoDownloader.extract_info(url)
        if not info:
            return []
            
        stories = []
        # Check for playlist or entries (covers playlists, stories, multi_video)
        if 'entries' in info:
            entries = info['entries']
            # Filter None entries
            entries = [e for e in entries if e]
            
            for entry in entries:
                story_url = entry.get('url') or entry.get('webpage_url')
                
                # If url is relative or just an ID, try to fallback or keep as is.
                # yt-dlp flat extraction usually gives enough info.
                
                stories.append({
                    'id': entry.get('id'),
                    'url': story_url,
                    'title': entry.get('title') or entry.get('id', 'Unknown'),
                    'duration': entry.get('duration', 0),
                    'thumbnail': entry.get('thumbnail'),
                    'original_url': url # Keep track of parent URL if needed
                })
        else:
            # Single video
            story_url = info.get('webpage_url') or info.get('url')
            stories.append({
                'id': info.get('id'),
                'url': story_url,
                'title': info.get('title') or info.get('id', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'original_url': url
            })
            
        return stories

    @staticmethod
    def download_video(url: str) -> tuple[str, dict]:
        """
        Downloads a video using Cobalt (primary), yt-dlp, or Playwright.
        """
        output_filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(Config.TEMP_DIR, output_filename)
        
        # Strategies: yt-dlp -> Playwright
        strategies = [
            VideoDownloader._download_with_ytdlp,
            VideoDownloader._download_with_playwright
        ]
            
        errors = []
        for strategy in strategies:
            try:
                print(f"[INFO] Trying download strategy: {strategy.__name__}")
                return strategy(url, output_path)
            except Exception as e:
                print(f"[WARN] Strategy {strategy.__name__} failed: {e}")
                errors.append(f"{strategy.__name__}: {e}")
                
        raise Exception(f"All download strategies failed. Details: {'; '.join(errors)}")



    @staticmethod
    def _download_with_ytdlp(url: str, output_path: str) -> tuple[str, dict]:
        print(f"⬇️ Downloading via yt-dlp...")
        
        # Setup ffmpeg
        import shutil
        src_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        dest_ffmpeg = os.path.join(Config.TEMP_DIR, "ffmpeg.exe")
        
        if not os.path.exists(dest_ffmpeg):
            try:
                shutil.copy2(src_ffmpeg, dest_ffmpeg)
            except Exception:
                dest_ffmpeg = src_ffmpeg

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': dest_ffmpeg,
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # Handle cookies from env var
        cookie_file = None
        try:
            cookies_content = os.environ.get('INSTAGRAM_COOKIES')
            if cookies_content:
                import base64
                # Decode base64 if needed
                try:
                    cookies_content = base64.b64decode(cookies_content).decode('utf-8')
                except:
                    pass
                
                # Write to temp file
                cookie_file = os.path.join(Config.TEMP_DIR, f"cookies_{uuid.uuid4()}.txt")
                with open(cookie_file, 'w') as f:
                    f.write(cookies_content)
                
                ydl_opts['cookiefile'] = cookie_file
                print("🍪 Using cookies from INSTAGRAM_COOKIES for yt-dlp")
        except Exception as e:
            print(f"⚠️ Failed to setup cookies for yt-dlp: {e}")
        
        # Internal Retry Loop
        max_retries = 3
        last_error = None
        
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        metadata = {
                            'title': info.get('title', 'N/A'),
                            'description': info.get('description', 'N/A'),
                            'uploader': info.get('uploader', 'N/A'),
                            'tags': info.get('tags', [])
                        }
                    
                    # Verify file exists
                    final_path = output_path
                    if not os.path.exists(final_path):
                        for ext in ['.mp4', '.mkv', '.webm']:
                            if os.path.exists(output_path + ext):
                                final_path = output_path + ext
                                break
                        else: 
                             # Sometimes yt-dlp merges to mkv if mp4 unavailable
                            raise FileNotFoundError(f"Download finished but file not found: {output_path}")
                    
                    return final_path, metadata
                except Exception as e:
                    print(f"⚠️ yt-dlp attempt {attempt}/{max_retries} failed: {e}")
                    last_error = e
                    import time
                    time.sleep(2)
            
            raise last_error

        finally:
            # Cleanup cookie file
            if cookie_file and os.path.exists(cookie_file):
                try:
                    os.remove(cookie_file)
                except:
                    pass

    @staticmethod
    def _download_with_playwright(url: str, output_path: str) -> tuple[str, dict]:
        print(f"⬇️ Downloading via Playwright...")
        metadata = {'title': 'Video', 'description': 'N/A', 'uploader': 'N/A', 'tags': []}
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True, 
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox"
                    ]
                )
                
                # Use mobile user agent for better video compatibility
                device_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
                
                context = browser.new_context(
                    user_agent=device_agent,
                    viewport={'width': 375, 'height': 812}
                )
                # Add cookies if available
                cookies_content = os.environ.get('INSTAGRAM_COOKIES')
                if cookies_content:
                    try:
                        import base64
                        try:
                            # Try decode base64 first
                            decoded = base64.b64decode(cookies_content).decode('utf-8')
                            cookies_content = decoded
                        except:
                            pass
                        
                        # Parse netscape format
                        domain_cookies = []
                        for line in cookies_content.strip().split('\n'):
                            if not line or line.startswith('#'): continue
                            parts = line.split('\t')
                            if len(parts) >= 7:
                                domain_cookies.append({
                                    'name': parts[5],
                                    'value': parts[6],
                                    'domain': parts[0],
                                    'path': parts[2],
                                    'expires': int(parts[4]) if parts[4] else -1,
                                    'httpOnly': False,
                                    'secure': parts[3] == 'TRUE',
                                    'sameSite': 'None'
                                })
                        
                        if domain_cookies:
                            context.add_cookies(domain_cookies)
                            print("🍪 Added cookies to Playwright context")
                    except Exception as e:
                        print(f"⚠️ Failed to add cookies to Playwright: {e}")

                page = context.new_page()
                try:
                    page.goto(url, timeout=60000, wait_until='domcontentloaded')
                except Exception as e:
                    # Capture screenshot on navigation failure
                    screenshot_path = os.path.join(Config.TEMP_DIR, f"error_nav_{uuid.uuid4()}.png")
                    try:
                        page.screenshot(path=screenshot_path)
                        print(f"📸 Navigation failed. Screenshot saved to: {screenshot_path}")
                    except:
                        pass
                    raise e
                
                # Extract Metadata
                try:
                    metadata['title'] = page.title()
                except:
                    pass

                # Find video
                video_url = None
                
                # Wait for video element
                try:
                    page.wait_for_selector('video', timeout=10000)
                except:
                    print("No video tag found initially")
                    # Debug screenshot
                    screenshot_path = os.path.join(Config.TEMP_DIR, f"error_novideo_{uuid.uuid4()}.png")
                    try:
                        page.screenshot(path=screenshot_path)
                        print(f"📸 Video not found. Screenshot saved to: {screenshot_path}")
                    except:
                        pass

                # Strategy 1: Direct video tag
                videos = page.query_selector_all('video')
                for v in videos:
                    src = v.get_attribute('src')
                    if src and src.startswith('http'):
                        video_url = src
                        break
                
                # Strategy 2: Page source regex (TikTok/IG specific)
                if not video_url:
                    content = page.content()
                    import re
                    
                    # IG/TikTok patterns
                    patterns = [
                        r'"playAddr":"(https?://[^"]+)"', # TikTok
                        r'"video_url":"([^"]+)"', # IG
                        r'"contentUrl":"([^"]+\.mp4[^"]*)"', # IG
                        r'video_versions.*?"url":"([^"]+)"', # IG
                    ]
                    
                    for pattern in patterns:
                         matches = re.search(pattern, content)
                         if matches:
                             video_url = matches.group(1).encode('utf-8').decode('unicode_escape')
                             break
                
                if not video_url:
                    raise Exception("Video URL not found in page.")
                
                # Download
                cookies = {c['name']: c['value'] for c in context.cookies()}
                headers = {'User-Agent': device_agent, 'Referer': url}
                
                with requests.get(video_url, headers=headers, cookies=cookies, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(output_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                            
                browser.close()
                
            return output_path, metadata
        except Exception as e:
            print(f"❌ Playwright failed: {e}")
            raise e
        