import os
import uuid
import requests
import yt_dlp
from playwright.sync_api import sync_playwright
from config import Config

import imageio_ffmpeg

class VideoDownloader:
    @staticmethod
    def download_video(url: str) -> tuple[str, dict]:
        """
        Downloads a video with multiple fallback strategies.
        """
        output_filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(Config.TEMP_DIR, output_filename)
        
        # Define strategies order based on URL
        strategies = []
        if "tiktok.com" in url:
            # TikTok: Playwright is often better, then yt-dlp
            strategies = [
                VideoDownloader._download_with_playwright,
                VideoDownloader._download_with_ytdlp
            ]
        elif "instagram.com" in url:
            # Instagram: Try third-party API first, then yt-dlp with cookies, then Playwright
            strategies = [
                VideoDownloader._download_instagram_api,
                VideoDownloader._download_with_ytdlp,
                VideoDownloader._download_with_playwright
            ]
        else:
            # Default: yt-dlp is best, Playwright as last resort
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
    def _download_instagram_api(url: str, output_path: str) -> tuple[str, dict]:
        """
        Download Instagram video using multiple fallback strategies:
        1. yt-dlp with cookies file
        2. Third-party API services
        """
        print(f"⬇️ Downloading Instagram...")
        metadata = {'title': 'Instagram Video', 'description': 'N/A', 'uploader': 'N/A', 'tags': []}
        
        # Check for cookies file with actual content
        cookies_file = None
        if os.path.exists(Config.INSTAGRAM_COOKIES_FILE):
            if VideoDownloader._has_valid_cookies(Config.INSTAGRAM_COOKIES_FILE):
                cookies_file = Config.INSTAGRAM_COOKIES_FILE
                print(f"[INFO] Using Instagram cookies from file")
        
        # Strategy 1: Try yt-dlp with cookies
        try:
            result = VideoDownloader._try_ytdlp_extract(url, output_path, cookies_file)
            if result:
                return result
        except Exception as e:
            print(f"[WARN] yt-dlp extraction failed: {e}")
        
        # Strategy 2: Try third-party APIs
        api_funcs = [
            VideoDownloader._try_instagram_api_1,
            VideoDownloader._try_instagram_api_2,
            VideoDownloader._try_instagram_api_3,
        ]
        
        for api_func in api_funcs:
            try:
                video_url = api_func(url)
                if video_url:
                    print(f"[INFO] Found video URL via API, downloading...")
                    if VideoDownloader._download_video_url(video_url, output_path, url):
                        return output_path, metadata
            except Exception as e:
                print(f"[WARN] API failed: {e}")
                continue
        
        raise Exception("All Instagram download methods failed")
    
    @staticmethod
    def _has_valid_cookies(cookies_file: str) -> bool:
        """Check if cookies file has actual cookie data (not just comments)."""
        try:
            with open(cookies_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        # Valid cookie line should have tab-separated fields
                        if '\t' in line:
                            return True
            return False
        except:
            return False
    
    @staticmethod
    def _try_ytdlp_extract(url: str, output_path: str, cookies_file: str = None) -> tuple[str, dict]:
        """Try to extract and download using yt-dlp."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
        }
        
        if cookies_file and os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
            
            metadata = {
                'title': info.get('title', 'Instagram Video'),
                'description': info.get('description', 'N/A'),
                'uploader': info.get('uploader', 'N/A'),
                'tags': info.get('tags', [])
            }
            
            # Find the best video URL
            video_url = info.get('url')
            
            if not video_url and info.get('formats'):
                video_formats = [f for f in info['formats'] if f.get('vcodec') != 'none' and f.get('url')]
                if video_formats:
                    video_formats.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
                    video_url = video_formats[0]['url']
            
            if not video_url:
                return None
            
            print(f"[INFO] Found video URL via yt-dlp, downloading...")
            if VideoDownloader._download_video_url(video_url, output_path, url):
                return output_path, metadata
        
        return None
    
    @staticmethod
    def _download_video_url(video_url: str, output_path: str, referer: str = None) -> bool:
        """Download a video from a direct URL."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        if referer:
            headers['Referer'] = referer
        
        for attempt in range(3):
            try:
                with requests.get(video_url, headers=headers, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(output_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print(f"✅ Video downloaded successfully")
                    return True
            except Exception as e:
                if attempt == 2:
                    raise e
                print(f"[WARN] Download attempt {attempt+1}/3 failed: {e}")
                import time
                time.sleep(2)
        
        return False
    
    @staticmethod
    def _try_instagram_api_1(url: str) -> str:
        """Try Instagram download via embed page scraping."""
        import re
        shortcode_match = re.search(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            return None
        
        shortcode = shortcode_match.group(1)
        
        # Try embed page
        embed_urls = [
            f"https://www.instagram.com/reel/{shortcode}/embed/",
            f"https://www.instagram.com/p/{shortcode}/embed/",
            f"https://www.instagram.com/reel/{shortcode}/embed/captioned/",
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for embed_url in embed_urls:
            try:
                resp = requests.get(embed_url, headers=headers, timeout=30)
                if resp.status_code == 200:
                    # Look for video URL patterns
                    patterns = [
                        r'"video_url":"([^"]+)"',
                        r'"contentUrl":"([^"]+)"',
                        r'video_url=([^&"]+)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, resp.text)
                        if match:
                            video_url = match.group(1)
                            video_url = video_url.encode('utf-8').decode('unicode_escape')
                            video_url = video_url.replace('\\u0026', '&')
                            if 'cdninstagram' in video_url or '.mp4' in video_url:
                                return video_url
            except:
                continue
        
        return None
    
    @staticmethod
    def _try_instagram_api_2(url: str) -> str:
        """Try via modified mobile user agent."""
        import re
        
        headers = {
            'User-Agent': 'Instagram 219.0.0.12.117 Android',
            'Accept': '*/*',
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                patterns = [
                    r'"video_url":"([^"]+)"',
                    r'"playback_url":"([^"]+)"',
                ]
                for pattern in patterns:
                    match = re.search(pattern, resp.text)
                    if match:
                        video_url = match.group(1).encode('utf-8').decode('unicode_escape')
                        return video_url
        except:
            pass
        
        return None
    
    @staticmethod
    def _try_instagram_api_3(url: str) -> str:
        """Try via i.instagram.com API endpoint."""
        import re
        
        shortcode_match = re.search(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            return None
        
        shortcode = shortcode_match.group(1)
        
        # Try the i.instagram.com API
        api_url = f"https://i.instagram.com/api/v1/media/{shortcode}/info/"
        
        headers = {
            'User-Agent': 'Instagram 219.0.0.12.117 Android (26/8.0.0; 480dpi; 1080x1920; samsung; SM-G950F; dreamlte; samsungexynos8895)',
            'X-IG-App-ID': '936619743392459',
        }
        
        try:
            resp = requests.get(api_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                if items:
                    video_versions = items[0].get('video_versions', [])
                    if video_versions:
                        return video_versions[0].get('url')
        except:
            pass
        
        return None
    
    @staticmethod
    def _download_with_ytdlp(url: str, output_path: str) -> tuple[str, dict]:
        print(f"⬇️ Downloading via yt-dlp...")
        
        # Setup ffmpeg (ensure logic is robust)
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
            # Add timeout and retries
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # Add cookies if available and valid (for Instagram)
        if "instagram.com" in url and os.path.exists(Config.INSTAGRAM_COOKIES_FILE):
            if VideoDownloader._has_valid_cookies(Config.INSTAGRAM_COOKIES_FILE):
                ydl_opts['cookiefile'] = Config.INSTAGRAM_COOKIES_FILE
                print(f"[INFO] Using Instagram cookies for yt-dlp")

        # Internal Retry Loop for yt-dlp specifically
        max_retries = 3
        last_error = None
        
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
                    if os.path.exists(output_path + ".mp4"): final_path = output_path + ".mp4"
                    elif os.path.exists(output_path.replace(".mp4", ".mkv")): final_path = output_path.replace(".mp4", ".mkv")
                    else: raise FileNotFoundError(f"Download finished but file not found: {output_path}")
                
                return final_path, metadata
            except Exception as e:
                print(f"⚠️ yt-dlp attempt {attempt}/{max_retries} failed: {e}")
                last_error = e
                import time
                time.sleep(2)
        
        raise last_error

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
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
                    viewport={'width': 375, 'height': 812}
                )
                page = context.new_page()
                page.goto(url, timeout=60000, wait_until='domcontentloaded')
                
                # Extract Metadata
                try:
                    metadata['title'] = page.title()
                    desc = page.query_selector('meta[name="description"]')
                    if desc:
                        metadata['description'] = desc.get_attribute('content')
                except:
                    pass

                # Find video
                video_url = None
                for _ in range(3):
                    videos = page.query_selector_all('video')
                    for v in videos:
                        src = v.get_attribute('src')
                        if src and src.startswith('http'):
                            video_url = src
                            break
                    if video_url: break
                    page.wait_for_timeout(2000)
                
                # TikTok specific regex fallback
                if not video_url:
                    content = page.content()
                    import re
                    matches = re.search(r'"playAddr":"(https?://[^"]+)"', content)
                    if matches:
                        video_url = matches.group(1).encode('utf-8').decode('unicode_escape')
                
                # Instagram specific regex fallback
                if not video_url and "instagram.com" in url:
                    content = page.content()
                    import re
                    # Try to find video_url in Instagram's embedded data
                    patterns = [
                        r'"video_url":"([^"]+)"',
                        r'"contentUrl":"([^"]+\.mp4[^"]*)"',
                        r'video_versions.*?"url":"([^"]+)"',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, content)
                        if match:
                            video_url = match.group(1).encode('utf-8').decode('unicode_escape')
                            break
                
                if not video_url:
                    # Generic fallback: look for any MP4 link in page source? Too risky.
                    raise Exception("Video URL not found in page.")
                
                # Download
                cookies = {c['name']: c['value'] for c in context.cookies()}
                headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': url}
                
                # Requests also needs retries
                for dl_attempt in range(3):
                    try:
                        with requests.get(video_url, headers=headers, cookies=cookies, stream=True, timeout=30) as r:
                            r.raise_for_status()
                            with open(output_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                        break # Success
                    except Exception as e:
                        if dl_attempt == 2: raise e
                        import time
                        time.sleep(1)
                            
                browser.close()
                
            return output_path, metadata
        except Exception as e:
            print(f"❌ Playwright failed: {e}")
            raise e
        
            @staticmethod
            def get_video_info(url: str) -> dict:
                """Legacy helper, now mostly unused by main flow."""
                return {}
        