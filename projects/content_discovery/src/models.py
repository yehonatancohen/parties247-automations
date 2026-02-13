"""
Data models for Content Discovery Bot.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import json


@dataclass
class VideoCandidate:
    """Represents a potential video to upload."""
    platform: str  # "tiktok" | "instagram"
    video_url: str
    thumbnail_url: Optional[str] = None
    author_username: str = ""
    author_display_name: str = ""
    author_followers: int = 0
    posted_at: Optional[datetime] = None
    
    # Engagement metrics
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    
    # Calculated scores
    engagement_rate: float = 0.0
    baseline_rate: float = 0.0
    hit_score: float = 0.0
    is_potential_hit: bool = False
    
    # Content info
    caption: str = ""
    category: str = "unknown"
    hashtags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "platform": self.platform,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "author_username": self.author_username,
            "author_display_name": self.author_display_name,
            "author_followers": self.author_followers,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "engagement_rate": self.engagement_rate,
            "baseline_rate": self.baseline_rate,
            "hit_score": self.hit_score,
            "is_potential_hit": self.is_potential_hit,
            "caption": self.caption,
            "category": self.category,
            "hashtags": self.hashtags
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VideoCandidate":
        """Create from dictionary."""
        posted_at = None
        if data.get("posted_at"):
            posted_at = datetime.fromisoformat(data["posted_at"])
        
        return cls(
            platform=data["platform"],
            video_url=data["video_url"],
            thumbnail_url=data.get("thumbnail_url"),
            author_username=data.get("author_username", ""),
            author_display_name=data.get("author_display_name", ""),
            author_followers=data.get("author_followers", 0),
            posted_at=posted_at,
            views=data.get("views", 0),
            likes=data.get("likes", 0),
            comments=data.get("comments", 0),
            shares=data.get("shares", 0),
            engagement_rate=data.get("engagement_rate", 0.0),
            baseline_rate=data.get("baseline_rate", 0.0),
            hit_score=data.get("hit_score", 0.0),
            is_potential_hit=data.get("is_potential_hit", False),
            caption=data.get("caption", ""),
            category=data.get("category", "unknown"),
            hashtags=data.get("hashtags", [])
        )


@dataclass
class MediaArticle:
    """Represents a news article about party/event content."""
    source: str
    title: str
    url: str
    published_at: Optional[datetime] = None
    summary: str = ""
    keywords_matched: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "keywords_matched": self.keywords_matched
        }


@dataclass
class FollowSuggestion:
    """Represents a suggested account to follow."""
    platform: str
    username: str
    display_name: str = ""
    followers: int = 0
    reason: str = ""  # Why we're suggesting this account
    sample_content: str = ""  # Sample of their content
    
    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "username": self.username,
            "display_name": self.display_name,
            "followers": self.followers,
            "reason": self.reason,
            "sample_content": self.sample_content
        }


@dataclass  
class DailyReport:
    """Container for the daily discovery report."""
    generated_at: datetime
    potential_hits: List[VideoCandidate] = field(default_factory=list)
    other_videos: List[VideoCandidate] = field(default_factory=list)
    media_articles: List[MediaArticle] = field(default_factory=list)
    follow_suggestions: List[FollowSuggestion] = field(default_factory=list)
    new_followings_detected: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "potential_hits": [v.to_dict() for v in self.potential_hits],
            "other_videos": [v.to_dict() for v in self.other_videos],
            "media_articles": [a.to_dict() for a in self.media_articles],
            "follow_suggestions": [s.to_dict() for s in self.follow_suggestions],
            "new_followings_detected": self.new_followings_detected,
            "errors": self.errors
        }
    
    def get_summary_stats(self) -> dict:
        """Get summary statistics for the report."""
        return {
            "total_videos_scanned": len(self.potential_hits) + len(self.other_videos),
            "potential_hits_count": len(self.potential_hits),
            "media_articles_count": len(self.media_articles),
            "follow_suggestions_count": len(self.follow_suggestions),
            "new_followings_count": len(self.new_followings_detected),
            "errors_count": len(self.errors)
        }
