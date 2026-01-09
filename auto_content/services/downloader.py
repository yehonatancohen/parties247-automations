import os
import uuid
import requests
import yt_dlp
from playwright.sync_api import sync_playwright
from config import Config

class VideoDownloader:
            @staticmethod
            def download_video(url: str) -> tuple[str, dict]:
                """
                Downloads a video and returns (path, metadata).
                """
                output_filename = f"{uuid.uuid4()}.mp4"
                output_path = os.path.join(Config.TEMP_DIR, output_filename)
                
                if "tiktok.com" in url:
                    try:
                        return VideoDownloader._download_with_playwright(url, output_path)
                    except Exception as e:
                        print(f"⚠️ Playwright failed: {e}. Falling back to yt-dlp...")
                        return VideoDownloader._download_with_ytdlp(url, output_path)
                else:
                    return VideoDownloader._download_with_ytdlp(url, output_path)
        
            @staticmethod
            def _download_with_ytdlp(url: str, output_path: str) -> tuple[str, dict]:
                print(f"⬇️ Downloading via yt-dlp...")
                ydl_opts = {
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                    'outtmpl': output_path,
                    'quiet': True,
                    'no_warnings': True,
                }
        
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        metadata = {
                            'title': info.get('title', 'N/A'),
                            'description': info.get('description', 'N/A'),
                            'uploader': info.get('uploader', 'N/A'),
                            'tags': info.get('tags', [])
                        }
                    
                    final_path = output_path
                    if not os.path.exists(final_path):
                        if os.path.exists(output_path + ".mp4"): final_path = output_path + ".mp4"
                        elif os.path.exists(output_path.replace(".mp4", ".mkv")): final_path = output_path.replace(".mp4", ".mkv")
                        else: raise FileNotFoundError(f"Download failed: {output_path}")
                        
                    return final_path, metadata
                except Exception as e:
                    print(f"❌ yt-dlp failed: {e}")
                    raise e
        
            @staticmethod
            def _download_with_playwright(url: str, output_path: str) -> tuple[str, dict]:
                print(f"⬇️ Downloading via Playwright...")
                metadata = {'title': 'TikTok Video', 'description': 'N/A', 'uploader': 'N/A', 'tags': []}
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
                        context = browser.new_context(
                            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
                            viewport={'width': 375, 'height': 812}
                        )
                        page = context.new_page()
                        page.goto(url, timeout=60000, wait_until='domcontentloaded')
                        
                        # Extract Metadata
                        try:
                            metadata['title'] = page.title()
                            # Try to find description in meta tags
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
                        
                        if not video_url:
                            content = page.content()
                            import re
                            matches = re.search(r'"playAddr":"(https?://[^"]+)"', content)
                            if matches:
                                video_url = matches.group(1).encode('utf-8').decode('unicode_escape')
                        
                        if not video_url:
                            raise Exception("Video URL not found.")
                        
                        # Download
                        cookies = {c['name']: c['value'] for c in context.cookies()}
                        headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': 'https://www.tiktok.com/'}
                        with requests.get(video_url, headers=headers, cookies=cookies, stream=True) as r:
                            r.raise_for_status()
                            with open(output_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                                    
                        browser.close()
                        
                    return output_path, metadata
                except Exception as e:
                    print(f"❌ Playwright failed: {e}")
                    raise e
        
            @staticmethod
            def get_video_info(url: str) -> dict:
                """Legacy helper, now mostly unused by main flow."""
                return {}
        