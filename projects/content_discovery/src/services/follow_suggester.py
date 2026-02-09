"""
Follow Suggestion Service for Content Discovery Bot.

Suggests new accounts to follow based on content analysis.
"""

import json
import os
import random
from datetime import datetime
from typing import List, Set, Dict, Any

from config import Config
from models import FollowSuggestion, VideoCandidate


class FollowSuggester:
    """Suggests new accounts to follow for better content discovery."""
    
    def __init__(self):
        self.suggestions_cache_file = os.path.join(Config.DATA_DIR, "suggestions_cache.json")
        self.rejected_accounts: Set[str] = set()
        self._load_rejected()
    
    def _load_rejected(self):
        """Load list of rejected suggestions (accounts user doesn't want)."""
        try:
            if os.path.exists(self.suggestions_cache_file):
                with open(self.suggestions_cache_file, 'r') as f:
                    data = json.load(f)
                    self.rejected_accounts = set(data.get("rejected", []))
        except Exception as e:
            print(f"Error loading rejected accounts: {e}")
    
    def _save_rejected(self):
        """Save list of rejected accounts."""
        try:
            data = {"rejected": list(self.rejected_accounts), "updated": datetime.now().isoformat()}
            os.makedirs(os.path.dirname(self.suggestions_cache_file), exist_ok=True)
            with open(self.suggestions_cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving rejected accounts: {e}")
    
    def reject_suggestion(self, platform: str, username: str):
        """Mark an account as rejected (user doesn't want to follow)."""
        key = f"{platform}:{username}"
        self.rejected_accounts.add(key)
        self._save_rejected()
    
    def is_rejected(self, platform: str, username: str) -> bool:
        """Check if an account has been rejected."""
        key = f"{platform}:{username}"
        return key in self.rejected_accounts
    
    def extract_suggestions_from_videos(
        self,
        videos: List[VideoCandidate],
        current_following: Set[str]
    ) -> List[FollowSuggestion]:
        """
        Extract follow suggestions from analyzed videos.
        
        Strategy:
        1. Find accounts mentioned/tagged in high-performing videos
        2. Find accounts that post content matching our categories
        3. Prioritize accounts with good engagement that we don't follow
        
        Args:
            videos: List of analyzed VideoCandidate objects
            current_following: Set of usernames we already follow
        
        Returns:
            List of FollowSuggestion objects
        """
        suggestions = []
        seen_accounts = set()
        
        # Group videos by author
        author_videos: Dict[str, List[VideoCandidate]] = {}
        for video in videos:
            key = f"{video.platform}:{video.author_username}"
            if key not in author_videos:
                author_videos[key] = []
            author_videos[key].append(video)
        
        # Find high-performing accounts we don't follow
        for key, user_videos in author_videos.items():
            platform, username = key.split(":", 1)
            
            # Skip if already following or rejected
            if username in current_following:
                continue
            if self.is_rejected(platform, username):
                continue
            if key in seen_accounts:
                continue
            
            # Check if they have potential hits
            hits = [v for v in user_videos if v.is_potential_hit]
            if hits:
                best_video = max(hits, key=lambda v: v.hit_score)
                
                suggestions.append(FollowSuggestion(
                    platform=platform,
                    username=username,
                    display_name=best_video.author_display_name,
                    followers=best_video.author_followers,
                    reason=f"Posted potential hit video ({best_video.hit_score:.1f}x engagement)",
                    sample_content=best_video.caption[:100] if best_video.caption else ""
                ))
                seen_accounts.add(key)
        
        # Sort by follower count (prefer smaller accounts with good content)
        suggestions.sort(key=lambda s: s.followers)
        
        print(f"💡 Found {len(suggestions)} follow suggestions")
        return suggestions[:10]  # Return top 10
    
    def extract_mentioned_accounts(
        self,
        videos: List[VideoCandidate]
    ) -> List[FollowSuggestion]:
        """
        Extract accounts mentioned in video captions.
        
        Args:
            videos: List of VideoCandidate objects
        
        Returns:
            List of FollowSuggestion objects for mentioned accounts
        """
        import re
        
        suggestions = []
        seen_accounts = set()
        
        for video in videos:
            if not video.caption:
                continue
            
            # Find @mentions
            mentions = re.findall(r'@(\w+)', video.caption)
            
            for username in mentions:
                key = f"{video.platform}:{username}"
                
                if key in seen_accounts:
                    continue
                if self.is_rejected(video.platform, username):
                    continue
                
                suggestions.append(FollowSuggestion(
                    platform=video.platform,
                    username=username,
                    display_name="",
                    followers=0,
                    reason=f"Mentioned in video by @{video.author_username}",
                    sample_content=""
                ))
                seen_accounts.add(key)
        
        return suggestions
    
    def generate_suggestions(
        self,
        videos: List[VideoCandidate],
        current_following: Dict[str, Set[str]]
    ) -> List[FollowSuggestion]:
        """
        Generate all follow suggestions.
        
        Args:
            videos: List of all analyzed videos
            current_following: Dict with "tiktok" and "instagram" sets of usernames
        
        Returns:
            Combined list of suggestions
        """
        all_suggestions = []
        
        # Combine all following
        all_following = set()
        for platform_following in current_following.values():
            all_following.update(platform_following)
        
        # Get suggestions from video analysis
        from_videos = self.extract_suggestions_from_videos(videos, all_following)
        all_suggestions.extend(from_videos)
        
        # Get mentioned accounts
        mentioned = self.extract_mentioned_accounts(videos)
        all_suggestions.extend(mentioned)
        
        # Deduplicate
        seen = set()
        unique_suggestions = []
        for s in all_suggestions:
            key = f"{s.platform}:{s.username}"
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)
        
        print(f"💡 Total {len(unique_suggestions)} unique follow suggestions")
        return unique_suggestions[:15]  # Limit to 15


# Test
if __name__ == "__main__":
    from models import VideoCandidate
    from datetime import datetime
    
    # Create test data
    test_videos = [
        VideoCandidate(
            platform="instagram",
            video_url="https://instagram.com/reel/123",
            author_username="newdj",
            author_display_name="New DJ",
            author_followers=5000,
            views=10000,
            likes=2000,
            comments=100,
            engagement_rate=21.0,
            baseline_rate=5.0,
            hit_score=4.2,
            is_potential_hit=True,
            caption="Amazing set at @theclub with @dj_friend! 🔥",
            category="viral"
        ),
        VideoCandidate(
            platform="tiktok",
            video_url="https://tiktok.com/@user/video/456",
            author_username="partygirl",
            author_display_name="Party Girl",
            author_followers=15000,
            views=50000,
            likes=8000,
            comments=500,
            engagement_rate=17.0,
            baseline_rate=8.0,
            hit_score=2.1,
            is_potential_hit=True,
            caption="Check out this new track by @israelidj",
            category="release"
        )
    ]
    
    suggester = FollowSuggester()
    
    current_following = {
        "instagram": {"existinguser1", "existinguser2"},
        "tiktok": {"existinguser3"}
    }
    
    suggestions = suggester.generate_suggestions(test_videos, current_following)
    
    for s in suggestions:
        print(f"\n💡 {s.platform}: @{s.username}")
        print(f"   Reason: {s.reason}")
