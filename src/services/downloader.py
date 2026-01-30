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
        Download Instagram video using multiple third-party API services.
        No yt-dlp - only external APIs for reliability.
        """
        print(f"⬇️ Downloading Instagram via APIs...")
        metadata = {'title': 'Instagram Video', 'description': 'N/A', 'uploader': 'N/A', 'tags': []}
        
        # Extract shortcode from URL
        import re
        shortcode_match = re.search(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            raise Exception("Could not extract Instagram shortcode from URL")
        shortcode = shortcode_match.group(1)
        
        # Try multiple API services in order
        api_funcs = [
            ("RapidAPI Style 1", lambda: VideoDownloader._try_rapidapi_1(url, shortcode)),
            ("RapidAPI Style 2", lambda: VideoDownloader._try_rapidapi_2(url, shortcode)),
            ("SaveFrom Style", lambda: VideoDownloader._try_savefrom(url, shortcode)),
            ("Direct Scrape", lambda: VideoDownloader._try_direct_scrape(url, shortcode)),
            ("GraphQL API", lambda: VideoDownloader._try_graphql_api(url, shortcode)),
        ]
        
        for api_name, api_func in api_funcs:
            try:
                print(f"[INFO] Trying {api_name}...")
                video_url = api_func()
                if video_url:
                    print(f"[INFO] Found video URL via {api_name}, downloading...")
                    if VideoDownloader._download_video_url(video_url, output_path, url):
                        return output_path, metadata
            except Exception as e:
                print(f"[WARN] {api_name} failed: {e}")
                continue
        
        raise Exception("All Instagram API services failed")
    
    @staticmethod
    def _try_rapidapi_1(url: str, shortcode: str) -> str:
        """Try instagram-scraper-api style endpoint."""
        import json
        
        # Use a public Instagram data endpoint
        api_url = f"https://www.instagram.com/api/v1/media/{shortcode}/info/"
        
        headers = {
            'User-Agent': 'Instagram 275.0.0.27.98 Android (33/13; 420dpi; 1080x2400; Google/google; Pixel 7; panther; panther; en_US; 458229237)',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-IG-App-ID': '936619743392459',
            'X-ASBD-ID': '129477',
            'X-IG-WWW-Claim': '0',
        }
        
        resp = requests.get(api_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if items:
                item = items[0]
                # Check for video_versions (for reels/videos)
                video_versions = item.get('video_versions', [])
                if video_versions:
                    return video_versions[0].get('url')
                # Check for carousel (multiple media)
                carousel = item.get('carousel_media', [])
                for media in carousel:
                    if media.get('video_versions'):
                        return media['video_versions'][0].get('url')
        return None
    
    @staticmethod
    def _try_rapidapi_2(url: str, shortcode: str) -> str:
        """Try instagram embed with different user agent."""
        import re
        
        # Try the embed endpoint with various headers
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        resp = requests.get(embed_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            # Multiple patterns to find video URL
            patterns = [
                r'"video_url"\s*:\s*"([^"]+)"',
                r'"contentUrl"\s*:\s*"([^"]+)"',
                r'property="og:video"\s+content="([^"]+)"',
                r'property="og:video:secure_url"\s+content="([^"]+)"',
                r'"playbackUrl"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, resp.text)
                if match:
                    video_url = match.group(1)
                    # Decode unicode escapes
                    video_url = video_url.encode('utf-8').decode('unicode_escape')
                    video_url = video_url.replace('\\u0026', '&').replace('\\/', '/')
                    if 'cdninstagram' in video_url or '.mp4' in video_url or 'video' in video_url:
                        return video_url
        return None
    
    @staticmethod
    def _try_savefrom(url: str, shortcode: str) -> str:
        """Try savefrom-style API."""
        import re
        
        # Try accessing via different Instagram endpoints
        endpoints = [
            f"https://www.instagram.com/reel/{shortcode}/embed/",
            f"https://www.instagram.com/p/{shortcode}/embed/",
            f"https://www.instagram.com/tv/{shortcode}/embed/",
        ]
        
        for endpoint in endpoints:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                }
                resp = requests.get(endpoint, headers=headers, timeout=30)
                if resp.status_code == 200:
                    # Look for video URL in script tags
                    script_match = re.search(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                    if script_match:
                        script_content = script_match.group(1)
                        video_match = re.search(r'"video_url"\s*:\s*"([^"]+)"', script_content)
                        if video_match:
                            video_url = video_match.group(1).encode('utf-8').decode('unicode_escape')
                            return video_url
            except:
                continue
        return None
    
    @staticmethod
    def _try_direct_scrape(url: str, shortcode: str) -> str:
        """Try direct page scraping with mobile user agent."""
        import re
        
        mobile_url = f"https://www.instagram.com/reel/{shortcode}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        }
        
        resp = requests.get(mobile_url, headers=headers, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            # Look for video URL in page source
            patterns = [
                r'"video_url"\s*:\s*"([^"]+)"',
                r'"playbackUrl"\s*:\s*"([^"]+)"',
                r'<meta property="og:video" content="([^"]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, resp.text)
                if match:
                    video_url = match.group(1)
                    video_url = video_url.encode('utf-8').decode('unicode_escape')
                    video_url = video_url.replace('\\u0026', '&')
                    return video_url
        return None
    
    @staticmethod
    def _try_graphql_api(url: str, shortcode: str) -> str:
        """Try Instagram GraphQL API endpoint."""
        import json
        
        # GraphQL query hash for media info
        query_hash = "b3055c01b4b222b8a47dc12b090e4e64"
        variables = json.dumps({"shortcode": shortcode})
        
        api_url = f"https://www.instagram.com/graphql/query/?query_hash={query_hash}&variables={variables}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        try:
            resp = requests.get(api_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                media = data.get('data', {}).get('shortcode_media', {})
                video_url = media.get('video_url')
                if video_url:
                    return video_url
        except:
            pass
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
        
        # Note: Instagram uses API-only approach, no cookies needed for yt-dlp

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
        