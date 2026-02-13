"""
TikTok Scraper Service using yt-dlp.

Robust metadata extraction without browser automation.
"""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import yt_dlp
from config import Config
from models import VideoCandidate

class TikTokScraper:
    """Scrapes TikTok metadata using yt-dlp."""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download video, just metadata
            'dump_single_json': True,
            'ignoreerrors': True,
            # Use cookies if available
            'cookiefile': os.path.join(Config.SESSION_DIR, "tiktok_cookies.json") if os.path.exists(os.path.join(Config.SESSION_DIR, "tiktok_cookies.json")) else None
        }
    
    async def get_user_videos(
        self,
        username: str,
        count: int = 10,
        hours: int = None
    ) -> List[VideoCandidate]:
        """
        Get recent videos from a user using yt-dlp.
        
        Args:
            username: TikTok username (without @)
            count: Max videos to fetch (approximate)
            hours: Only include videos from last N hours
        """
        hours = hours or Config.VIDEO_AGE_HOURS
        videos = []
        
        # Prepare URL and options
        url = f"https://www.tiktok.com/@{username}"
        opts = self.ydl_opts.copy()
        opts.update({
             'playlistend': count,
             'socket_timeout': 10,
             'retries': 3,
        })

        # Retry logic for robustness
        info = None
        for attempt in range(2):
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: self._fetch_metadata_safe(opts, url))
                if info and 'entries' in info:
                    break
            except Exception as e:
                print(f"⚠️ Retry {attempt+1} for @{username}: {e}")
                await asyncio.sleep(2)
        
        if not info or 'entries' not in info:
            return []

        entries = info['entries']
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for entry in entries:
            if not entry:
                continue
                
            # yt-dlp returns inconsistent date formats, handle gracefully
            upload_date = entry.get('upload_date')
            timestamp = entry.get('timestamp')
            posted_at = datetime.now()
            
            if timestamp:
                posted_at = datetime.fromtimestamp(timestamp)
            elif upload_date:
                try:
                    posted_at = datetime.strptime(upload_date, '%Y%m%d')
                except:
                    pass
            
            # Filter by age
            if posted_at < cutoff_time:
                continue
            
            video = VideoCandidate(
                platform="tiktok",
                video_url=entry.get('webpage_url') or entry.get('webpage_url_basename'), # fallback
                thumbnail_url=entry.get('thumbnail'),
                author_username=entry.get('uploader') or username,
                author_display_name=entry.get('uploader') or username,
                author_followers=0,  # yt-dlp might not provide this
                posted_at=posted_at,
                views=entry.get('view_count', 0),
                likes=entry.get('like_count', 0),
                comments=entry.get('comment_count', 0),
                shares=entry.get('repost_count', 0),
                caption=entry.get('description', '') or entry.get('title', ''),
                hashtags=entry.get('tags', [])
            )
            
            # yt-dlp return validation
            video.video_url = video.video_url or f"https://www.tiktok.com/@{username}/video/{entry.get('id')}"
            video.views = video.views or 0
            video.likes = video.likes or 0
            video.comments = video.comments or 0
            video.shares = video.shares or 0
            
            videos.append(video)
            
            if len(videos) >= count:
                break
        
        if videos:
             print(f"📹 TikTok: Found {len(videos)} new from @{username}")
        return videos

    def _fetch_metadata_safe(self, opts, url):
        """Helper to run yt-dlp extraction safely."""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception:
            return None

    def _fetch_metadata(self, url: str, max_items: int) -> Dict:
        """Deprecated helper, kept for compatibility."""
        opts = self.ydl_opts.copy()
        opts['playlistend'] = max_items
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    async def scan_following_for_videos(
        self,
        max_accounts: int = 1500
    ) -> List[VideoCandidate]:
        """
        Scan monitored accounts list in parallel.
        """
        # Load monitored accounts from a file
        accounts_file = os.path.join(Config.DATA_DIR, "monitored_accounts.json")
        accounts = []
        
        if os.path.exists(accounts_file):
            try:
                with open(accounts_file, 'r', encoding='utf-8') as f:
                    accounts = json.load(f)
            except:
                accounts = []
        
        # Fallback if empty
        if not accounts:
             # Try users.txt from trend_hunter if it exists
             users_txt = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(Config.BASE_DIR))), "tiktok_trend_hunter", "users.txt")
             if os.path.exists(users_txt):
                 with open(users_txt, 'r', encoding='utf-8') as f:
                     accounts = [line.strip() for line in f if line.strip() and not line.startswith('#')]
             else:
                 accounts = ["infected_mushroom", "astikiofficial"]
            
        print(f"📋 Scanning {len(accounts)} monitored accounts in parallel (5 workers)...")
        
        all_videos = []
        
        # Helper for thread execution
        def fetch_worker(username):
            # We need a new event loop for async in thread, or just run synchronous yt-dlp here?
            # Actually, get_user_videos is async. ThreadPoolExecutor runs sync functions.
            # We can't easily run async function in ThreadPool.
            # However, since yt-dlp is blocking anyway, we can just call the synchronous logic directly!
            
            # But get_user_videos uses loop.run_in_executor. 
            # It's better to use asyncio.gather for async functions!
            pass 

        # Using asyncio.gather with a semaphore to limit concurrency is better than ThreadPool for async functions
        semaphore = asyncio.Semaphore(5)
        
        async def protected_fetch(username):
            async with semaphore:
                await asyncio.sleep(random.uniform(1.0, 3.0)) # Random jitter
                try:
                    return await self.get_user_videos(username, count=8)
                except Exception as e:
                    print(f"Error scanning {username}: {e}")
                    return []

        # Create tasks
        tasks = [protected_fetch(user) for user in accounts[:max_accounts]]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res:
                all_videos.extend(res)
            
        return all_videos

    def update_cookies(self, cookie_data: str) -> bool:
        """Update Netscape cookies for yt-dlp."""
        try:
            # yt-dlp prefers Netscape format
            cookie_file = os.path.join(Config.SESSION_DIR, "tiktok_cookies.txt")
            
            # If JSON (EditThisCookie), convert to Netscape
            if cookie_data.strip().startswith('['):
                json_cookies = json.loads(cookie_data)
                with open(cookie_file, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for c in json_cookies:
                        domain = c.get('domain', '')
                        flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                        path = c.get('path', '/')
                        secure = 'TRUE' if c.get('secure') else 'FALSE'
                        expiration = str(int(c.get('expirationDate', 0)))
                        name = c.get('name', '')
                        value = c.get('value', '')
                        f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}\n")
            else:
                # Assume it's already Netscape or raw text
                with open(cookie_file, 'w') as f:
                    f.write(cookie_data)
                    
            print("✅ Cookies updated for yt-dlp")
            
            # Update opts
            self.ydl_opts['cookiefile'] = cookie_file
            return True
            
        except Exception as e:
            print(f"❌ Failed to update cookies: {e}")
            return False
