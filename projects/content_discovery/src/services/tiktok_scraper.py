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
        
        try:
            url = f"https://www.tiktok.com/@{username}"
            
            # Run yt-dlp in a thread to avoid blocking asyncio loop
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._fetch_metadata, url, count)
            
            if not info or 'entries' not in info:
                # Fallback: try feed URL
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
                    video_url=entry.get('webpage_url') or entry.get('url'),
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
                
                # yt-dlp returns None for 0 sometimes
                video.views = video.views or 0
                video.likes = video.likes or 0
                video.comments = video.comments or 0
                video.shares = video.shares or 0
                
                videos.append(video)
                
                if len(videos) >= count:
                    break
            
            print(f"📹 TikTok (yt-dlp): Found {len(videos)} recent videos from @{username}")
            return videos
            
        except Exception as e:
            print(f"❌ Error fetching videos from @{username}: {e}")
            return []

    def _fetch_metadata(self, url: str, max_items: int) -> Dict:
        """Helper to run yt-dlp extraction."""
        opts = self.ydl_opts.copy()
        opts['playlistend'] = max_items
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    async def scan_following_for_videos(
        self,
        max_accounts: int = 10
    ) -> List[VideoCandidate]:
        """
        Scan explicit accounts list since following feed is blocked.
        """
        # Load monitored accounts from a file
        accounts_file = os.path.join(Config.DATA_DIR, "monitored_accounts.json")
        accounts = []
        
        if os.path.exists(accounts_file):
            try:
                with open(accounts_file, 'r') as f:
                    accounts = json.load(f)
            except:
                accounts = []
        
        # Default accounts if none configured
        if not accounts:
            accounts = ["infected_mushroom", "astikiofficial", "djborisofficial"]
            
        print(f"📋 Scanning {len(accounts)} monitored accounts...")
        
        all_videos = []
        for username in accounts[:max_accounts]:
            videos = await self.get_user_videos(username, count=5)
            all_videos.extend(videos)
            await asyncio.sleep(2)
            
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
