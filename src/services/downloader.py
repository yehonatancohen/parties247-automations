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
        Download Instagram video using third-party API services.
        """
        print(f"⬇️ Downloading Instagram via API...")
        metadata = {'title': 'Instagram Video', 'description': 'N/A', 'uploader': 'N/A', 'tags': []}
        
        # Extract shortcode from URL
        import re
        shortcode_match = re.search(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            raise Exception("Could not extract Instagram shortcode from URL")
        
        shortcode = shortcode_match.group(1)
        
        # Try multiple API services
        api_services = [
            VideoDownloader._try_saveig_api,
            VideoDownloader._try_igdownloader_api,
        ]
        
        for api_func in api_services:
            try:
                video_url = api_func(url, shortcode)
                if video_url:
                    # Download the video
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    with requests.get(video_url, headers=headers, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(output_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        return output_path, metadata
            except Exception as e:
                print(f"[WARN] API service failed: {e}")
                continue
        
        raise Exception("All Instagram API services failed")
    
    @staticmethod
    def _try_saveig_api(url: str, shortcode: str) -> str:
        """Try saveig.app API"""
        try:
            api_url = "https://v3.saveig.app/api/ajaxSearch"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://saveig.app',
                'Referer': 'https://saveig.app/'
            }
            data = {'q': url, 't': 'media', 'lang': 'en'}
            
            response = requests.post(api_url, headers=headers, data=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok' and result.get('data'):
                    import re
                    # Find video download link in response
                    html = result.get('data', '')
                    video_match = re.search(r'href="([^"]+)"[^>]*>Download Video', html)
                    if video_match:
                        return video_match.group(1)
        except Exception as e:
            print(f"[DEBUG] saveig.app failed: {e}")
        return None
    
    @staticmethod
    def _try_igdownloader_api(url: str, shortcode: str) -> str:
        """Try alternative Instagram downloader"""
        try:
            # Using a simple embed approach to get video URL
            embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(embed_url, headers=headers, timeout=30)
            if response.status_code == 200:
                import re
                # Look for video URL in embed page
                video_match = re.search(r'"video_url":"([^"]+)"', response.text)
                if video_match:
                    video_url = video_match.group(1).encode('utf-8').decode('unicode_escape')
                    return video_url
        except Exception as e:
            print(f"[DEBUG] embed approach failed: {e}")
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
        