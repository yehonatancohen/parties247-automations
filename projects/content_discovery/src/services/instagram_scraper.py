"""
Instagram Scraper Service for Content Discovery Bot.

Uses instagrapi library to fetch following list and recent reels.
"""

import asyncio
import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

try:
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired, ChallengeRequired
    INSTAGRAPI_AVAILABLE = True
except ImportError:
    INSTAGRAPI_AVAILABLE = False
    print("Warning: instagrapi not installed. Instagram scraping will not work.")

from config import Config
from models import VideoCandidate


class InstagramScraper:
    """Scrapes Instagram for reels and following info using instagrapi."""
    
    def __init__(self):
        self.client = None
        self.logged_in = False
        self.following_cache_file = Config.FOLLOWING_CACHE_FILE
        self.session_file = Config.INSTAGRAM_SESSION_FILE
        
    def _random_delay(self):
        """Add random delay to avoid rate limiting."""
        delay = random.uniform(Config.REQUEST_DELAY_MIN, Config.REQUEST_DELAY_MAX)
        time.sleep(delay)
    
    def login(self) -> bool:
        """
        Login to Instagram.
        
        Returns:
            True if login successful
        """
        if not INSTAGRAPI_AVAILABLE:
            print("instagrapi not available")
            return False
        
        if self.logged_in and self.client:
            return True
        
        self.client = Client()
        
        # Try to load existing session
        if os.path.exists(self.session_file):
            try:
                self.client.load_settings(self.session_file)
                self.client.login(Config.INSTAGRAM_USERNAME, Config.INSTAGRAM_PASSWORD)
                self.logged_in = True
                print(f"✅ Instagram: Logged in as {Config.INSTAGRAM_USERNAME} (from session)")
                return True
            except Exception as e:
                print(f"Session expired, performing fresh login: {e}")
        
        # Fresh login
        try:
            self.client.login(Config.INSTAGRAM_USERNAME, Config.INSTAGRAM_PASSWORD)
            self.client.dump_settings(self.session_file)
            self.logged_in = True
            print(f"✅ Instagram: Logged in as {Config.INSTAGRAM_USERNAME}")
            return True
        except ChallengeRequired as e:
            print(f"❌ Instagram login requires challenge: {e}")
            return False
        except LoginRequired as e:
            print(f"❌ Instagram login failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Instagram login error: {e}")
            return False
    
    def get_following_list(self) -> List[Dict[str, Any]]:
        """
        Get list of accounts the user follows.
        
        Returns:
            List of dicts with username, user_id, full_name
        """
        if not self.login():
            return []
        
        try:
            user_id = self.client.user_id_from_username(Config.INSTAGRAM_USERNAME)
            following = self.client.user_following(user_id)
            
            result = []
            for user_id, user_info in following.items():
                result.append({
                    "user_id": str(user_id),
                    "username": user_info.username,
                    "full_name": user_info.full_name,
                    "is_private": user_info.is_private
                })
                self._random_delay()
            
            print(f"📋 Instagram: Found {len(result)} accounts in following list")
            return result
            
        except Exception as e:
            print(f"❌ Error fetching following list: {e}")
            return []
    
    def get_new_followings(self) -> List[Dict[str, Any]]:
        """
        Compare current following with cached list to find new follows.
        
        Returns:
            List of newly followed accounts
        """
        current = self.get_following_list()
        if not current:
            return []
        
        current_usernames = {u["username"] for u in current}
        
        # Load cached followings
        cached_usernames = set()
        if os.path.exists(self.following_cache_file):
            try:
                with open(self.following_cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    cached_usernames = set(cached.get("instagram", []))
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        # Find new followings
        new_usernames = current_usernames - cached_usernames
        new_followings = [u for u in current if u["username"] in new_usernames]
        
        # Update cache
        try:
            cache_data = {}
            if os.path.exists(self.following_cache_file):
                with open(self.following_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            
            cache_data["instagram"] = list(current_usernames)
            cache_data["instagram_updated"] = datetime.now().isoformat()
            
            os.makedirs(os.path.dirname(self.following_cache_file), exist_ok=True)
            with open(self.following_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"Error saving cache: {e}")
        
        if new_followings:
            print(f"🆕 Instagram: Found {len(new_followings)} new followings")
        
        return new_followings
    
    def get_recent_reels(
        self,
        username: str,
        hours: int = None
    ) -> List[VideoCandidate]:
        """
        Get reels from the last N hours for a user.
        
        Args:
            username: Instagram username
            hours: Number of hours to look back (default: Config.VIDEO_AGE_HOURS)
        
        Returns:
            List of VideoCandidate objects
        """
        hours = hours or Config.VIDEO_AGE_HOURS
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if not self.login():
            return []
        
        try:
            user_id = self.client.user_id_from_username(username)
            self._random_delay()
            
            # Get user's reels
            reels = self.client.user_clips(user_id, amount=20)
            self._random_delay()
            
            # Get user info for followers count
            user_info = self.client.user_info(user_id)
            followers = user_info.follower_count
            
            videos = []
            for reel in reels:
                # Check if within time window
                posted_at = reel.taken_at
                if posted_at and posted_at.replace(tzinfo=None) < cutoff_time:
                    continue
                
                video = VideoCandidate(
                    platform="instagram",
                    video_url=f"https://www.instagram.com/reel/{reel.code}/",
                    thumbnail_url=str(reel.thumbnail_url) if reel.thumbnail_url else None,
                    author_username=username,
                    author_display_name=user_info.full_name,
                    author_followers=followers,
                    posted_at=posted_at,
                    views=reel.play_count or 0,
                    likes=reel.like_count or 0,
                    comments=reel.comment_count or 0,
                    shares=0,  # Instagram doesn't expose share count
                    caption=reel.caption_text or "",
                    hashtags=self._extract_hashtags(reel.caption_text or "")
                )
                videos.append(video)
            
            print(f"📹 Instagram: Found {len(videos)} recent reels from @{username}")
            return videos
            
        except Exception as e:
            print(f"❌ Error fetching reels from @{username}: {e}")
            return []
    
    def get_user_baseline(self, username: str) -> float:
        """
        Calculate baseline engagement rate for a user.
        
        Args:
            username: Instagram username
        
        Returns:
            Average engagement rate
        """
        if not self.login():
            return 0.0
        
        try:
            user_id = self.client.user_id_from_username(username)
            self._random_delay()
            
            # Get user's recent reels
            reels = self.client.user_clips(user_id, amount=Config.BASELINE_POSTS_COUNT)
            self._random_delay()
            
            # Get follower count
            user_info = self.client.user_info(user_id)
            followers = user_info.follower_count
            
            videos_data = []
            for reel in reels:
                videos_data.append({
                    "views": reel.play_count or 0,
                    "likes": reel.like_count or 0,
                    "comments": reel.comment_count or 0,
                    "shares": 0,
                    "followers": followers
                })
            
            from services.engagement_calculator import EngagementCalculator
            calc = EngagementCalculator()
            baseline = calc.calculate_baseline(videos_data)
            
            print(f"📊 Instagram: Baseline for @{username}: {baseline:.2f}%")
            return baseline
            
        except Exception as e:
            print(f"❌ Error calculating baseline for @{username}: {e}")
            return 0.0
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text."""
        import re
        return re.findall(r'#(\w+)', text)
    
    async def scan_following_for_videos(self) -> List[VideoCandidate]:
        """
        Scan all followed accounts for recent videos.
        
        Returns:
            List of all VideoCandidate objects found
        """
        following = self.get_following_list()
        all_videos = []
        
        for user in following:
            if user.get("is_private"):
                continue  # Skip private accounts
            
            try:
                videos = self.get_recent_reels(user["username"])
                all_videos.extend(videos)
                self._random_delay()
            except Exception as e:
                print(f"Error scanning @{user['username']}: {e}")
        
        print(f"📹 Instagram: Total {len(all_videos)} videos found from {len(following)} accounts")
        return all_videos


# Test
if __name__ == "__main__":
    Config.ensure_dirs()
    scraper = InstagramScraper()
    
    print("Testing Instagram login...")
    if scraper.login():
        print("\nFetching following list...")
        following = scraper.get_following_list()
        print(f"Following {len(following)} accounts")
        
        if following:
            # Test getting reels from first public account
            for user in following[:5]:
                if not user.get("is_private"):
                    print(f"\nFetching reels from @{user['username']}...")
                    videos = scraper.get_recent_reels(user["username"])
                    for v in videos[:2]:
                        print(f"  - {v.video_url} ({v.views} views, {v.likes} likes)")
                    break
