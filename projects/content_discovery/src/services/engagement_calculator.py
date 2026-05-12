"""
Engagement Rate Calculator for Content Discovery Bot.

Calculates engagement rates and identifies potential viral content.
"""

import math
import re
from typing import List, Optional
from config import Config



class EngagementCalculator:
    """Calculate engagement rates and identify potential hits."""
    
    def __init__(self, hit_threshold: float = None):
        """
        Initialize the calculator.
        
        Args:
            hit_threshold: Multiplier above baseline to consider a hit (default: 1.5)
        """
        self.hit_threshold = hit_threshold or Config.HIT_THRESHOLD
        self.category_keywords = Config.CATEGORY_KEYWORDS
        self.israeli_djs = [dj.lower() for dj in Config.ISRAELI_DJS]
    
    def calculate_engagement_rate(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int = 0,
        followers: int = 0
    ) -> float:
        """
        Calculate engagement rate for a video.
        
        For videos with significant views (>100):
            Engagement = (likes + comments + shares) / views * 100
        
        For new videos with few views:
            Engagement = (likes + comments) / followers * 100
        
        Args:
            views: Number of views
            likes: Number of likes
            comments: Number of comments
            shares: Number of shares (optional)
            followers: Author's follower count (used for low-view videos)
        
        Returns:
            Engagement rate as a percentage
        """
        total_engagement = likes + comments + shares
        
        if views >= 100:
            # Standard engagement rate based on views
            return (total_engagement / views) * 100 if views > 0 else 0.0
        elif followers > 0:
            # Fall back to follower-based engagement for new content
            return ((likes + comments) / followers) * 100
        else:
            # Can't calculate meaningful engagement
            return 0.0
    
    def calculate_baseline(self, videos_data: List[dict]) -> float:
        """
        Calculate baseline engagement rate from historical videos.
        
        Args:
            videos_data: List of dicts with views, likes, comments, shares
        
        Returns:
            Average engagement rate
        """
        if not videos_data:
            return 0.0
        
        rates = []
        for video in videos_data:
            rate = self.calculate_engagement_rate(
                views=video.get("views", 0),
                likes=video.get("likes", 0),
                comments=video.get("comments", 0),
                shares=video.get("shares", 0),
                followers=video.get("followers", 0)
            )
            if rate > 0:
                rates.append(rate)
        
        return sum(rates) / len(rates) if rates else 0.0
    
    def calculate_hit_score(self, engagement_rate: float, baseline: float) -> float:
        """
        Calculate hit score (how much above baseline).
        
        Args:
            engagement_rate: Current video's engagement rate
            baseline: Author's baseline engagement rate
        
        Returns:
            Hit score (e.g., 2.0 means 2x the baseline)
        """
        if baseline <= 0:
            return 0.0
        return engagement_rate / baseline
    
    def is_potential_hit(self, hit_score: float) -> bool:
        """
        Determine if a video is a potential hit.
        
        Args:
            hit_score: The calculated hit score
        
        Returns:
            True if hit score >= threshold (default 1.5x)
        """
        return hit_score >= self.hit_threshold
    
    def categorize_video(self, caption: str, hashtags: List[str] = None) -> str:
        """
        Categorize video based on content analysis.

        Args:
            caption: Video caption/description
            hashtags: List of hashtags

        Returns:
            Category string
        """
        text = caption.lower()
        if hashtags:
            text += " " + " ".join(h.lower() for h in hashtags)

        # Check for Israeli DJs
        for dj in self.israeli_djs:
            if dj in text:
                return "israeli_dj"

        # Check category keywords
        for category, keywords in self.category_keywords.items():
            if category == "israeli_dj":
                continue  # Already checked above
            for keyword in keywords:
                if keyword.lower() in text:
                    return category

        # Extended party sub-genre detection
        genre_signals = {
            "psytrance": ["psytrance", "psy trance", "טראנס", "psychedelic trance", "full on", "darkpsy"],
            "techno":    ["techno", "industrial", "gabber", "hard techno"],
            "house":     ["house music", "deep house", "tech house", "afro house"],
            "rave":      ["rave", "underground", "רייב", "free party", "squat party"],
            "festival":  ["פסטיבל", "festival", "outdoor", "camping"],
            "viral":     ["viral", "fail", "funny", "מטורף", "crazy", "insane"],
        }
        for category, keywords in genre_signals.items():
            if any(kw in text for kw in keywords):
                return category

        return "general"

    def calculate_virality_score(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int = 0,
        posted_at=None,
        caption: str = "",
        hashtags: List[str] = None,
    ) -> float:
        """
        Composite virality score in [0, 1] for global (no-baseline) content.

        Components:
            engagement_rate (30%) — interaction ratio vs views
            reach_score     (30%) — log-scaled view count
            relevance_score (25%) — party keyword density
            velocity_score  (15%) — views per hour since upload

        Args:
            views:     Number of views
            likes:     Number of likes
            comments:  Number of comments
            shares:    Number of shares
            posted_at: datetime of upload (timezone-aware preferred)
            caption:   Video caption/description text
            hashtags:  List of hashtag strings

        Returns:
            Float in [0, 1]; higher is more viral and more party-relevant.
        """
        from datetime import datetime, timezone

        party_keywords = [
            "party", "rave", "festival", "nightlife", "club", "clubbing",
            "afterparty", "techno", "trance", "psytrance", "housemusic",
            "edm", "dj", "electronic", "raveculture", "festivalseason",
            "מסיבה", "טראנס", "פסטיבל", "מועדון", "דיג'יי", "רייב",
            "israel", "telaviv", "ישראל",
        ]

        # 1. Engagement rate (cap at 30% = extremely high)
        total_eng = likes + comments + shares
        eng_rate = (total_eng / views) if views > 0 else 0.0
        engagement_score = min(eng_rate / 0.30, 1.0)

        # 2. Reach (log scale: 0 at 1 view → 1 at 10M views)
        reach_score = min(math.log10(views) / 7.0, 1.0) if views > 0 else 0.0

        # 3. Party relevance keyword density
        text = (caption + " " + " ".join(hashtags or [])).lower()
        matched = sum(1 for kw in party_keywords if kw in text)
        relevance_score = min(matched / 5.0, 1.0)

        # 4. Velocity (views/hour; saturates at 50K/h)
        velocity_score = 0.0
        if posted_at:
            now = datetime.now(timezone.utc)
            # Handle naive datetimes gracefully
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
            hours_live = max((now - posted_at).total_seconds() / 3600, 0.5)
            views_per_hour = views / hours_live
            velocity_score = min(views_per_hour / 50_000, 1.0)

        score = (
            0.30 * engagement_score
            + 0.30 * reach_score
            + 0.25 * relevance_score
            + 0.15 * velocity_score
        )
        return round(score, 4)

    
    def analyze_video(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int,
        followers: int,
        baseline: float,
        caption: str = "",
        hashtags: List[str] = None
    ) -> dict:
        """
        Full analysis of a video.
        
        Returns:
            Dict with engagement_rate, hit_score, is_potential_hit, category
        """
        engagement_rate = self.calculate_engagement_rate(
            views, likes, comments, shares, followers
        )
        hit_score = self.calculate_hit_score(engagement_rate, baseline)
        potential_hit = self.is_potential_hit(hit_score)
        category = self.categorize_video(caption, hashtags)
        
        return {
            "engagement_rate": round(engagement_rate, 2),
            "hit_score": round(hit_score, 2),
            "is_potential_hit": potential_hit,
            "category": category
        }


# Simple test
if __name__ == "__main__":
    calc = EngagementCalculator()
    
    # Test engagement calculation
    rate = calc.calculate_engagement_rate(
        views=10000,
        likes=500,
        comments=50,
        shares=100
    )
    print(f"Engagement rate: {rate}%")
    
    # Test baseline calculation
    historical = [
        {"views": 5000, "likes": 200, "comments": 20, "shares": 30},
        {"views": 8000, "likes": 300, "comments": 40, "shares": 50},
        {"views": 3000, "likes": 100, "comments": 15, "shares": 10},
    ]
    baseline = calc.calculate_baseline(historical)
    print(f"Baseline: {baseline}%")
    
    # Test hit detection
    hit_score = calc.calculate_hit_score(rate, baseline)
    print(f"Hit score: {hit_score}x")
    print(f"Is potential hit: {calc.is_potential_hit(hit_score)}")
    
    # Test categorization
    category = calc.categorize_video(
        "New track by Infected Mushroom dropping soon! 🔥 #newmusic #psytrance"
    )
    print(f"Category: {category}")
