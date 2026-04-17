"""
Engagement & Potential-Hit Calculator for Content Discovery Bot.

`potential_score` combines velocity (likes/hour), engagement ratio vs baseline,
absolute reach, share/save boost, a small-creator multiplier, and an
Israeli-signal multiplier supplied by IsraeliContentDetector.
"""

from datetime import datetime
from math import log10
from typing import List, Optional

from config import Config
from services.israeli_detector import IsraeliContentDetector


class EngagementCalculator:
    """Calculate engagement rates, Israeli signals, and potential-hit score."""

    def __init__(
        self,
        detector: Optional[IsraeliContentDetector] = None,
        potential_hit_threshold: Optional[float] = None,
    ):
        self.detector = detector or IsraeliContentDetector()
        self.threshold = (
            potential_hit_threshold
            if potential_hit_threshold is not None
            else Config.POTENTIAL_HIT_THRESHOLD
        )
        self.category_keywords = Config.CATEGORY_KEYWORDS
        self.israeli_djs = [dj.lower() for dj in Config.ISRAELI_DJS]

    # ------------------------------------------------------------------ #
    # Engagement rate + baseline                                         #
    # ------------------------------------------------------------------ #

    def calculate_engagement_rate(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int = 0,
        followers: int = 0,
    ) -> float:
        """Engagement as a percentage. Uses views when meaningful, else followers."""
        total = likes + comments + shares
        if views and views >= 100:
            return (total / views) * 100
        if followers > 0:
            return ((likes + comments) / followers) * 100
        return 0.0

    def calculate_baseline(self, videos_data: List[dict]) -> float:
        """Average engagement rate across historical videos (non-zero only)."""
        if not videos_data:
            return 0.0
        rates = []
        for v in videos_data:
            r = self.calculate_engagement_rate(
                views=v.get("views", 0),
                likes=v.get("likes", 0),
                comments=v.get("comments", 0),
                shares=v.get("shares", 0),
                followers=v.get("followers", 0),
            )
            if r > 0:
                rates.append(r)
        return sum(rates) / len(rates) if rates else 0.0

    # ------------------------------------------------------------------ #
    # Potential-hit score                                                #
    # ------------------------------------------------------------------ #

    def calculate_potential_score(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int,
        saves: int,
        followers: int,
        baseline_rate: float,
        posted_at: Optional[datetime],
        israeli_signal_score: float = 0.0,
    ) -> dict:
        """Composite potential-hit score. See plan §2 for the formula."""
        now = datetime.now()
        if posted_at is None:
            hours = 1.0
        else:
            # posted_at may be tz-aware; strip for a simple delta
            pa = posted_at.replace(tzinfo=None) if posted_at.tzinfo else posted_at
            hours = max((now - pa).total_seconds() / 3600, 0.5)

        # Velocity: likes per hour, log-scaled to ~0..2
        likes_per_hour = (likes or 0) / hours
        velocity = log10(1 + likes_per_hour) / max(Config.VELOCITY_LOG_DIVISOR, 0.01)

        # Engagement ratio vs baseline, capped and normalized to 0..1
        engagement_rate = self.calculate_engagement_rate(
            views, likes, comments, shares, followers
        )
        ratio = engagement_rate / max(baseline_rate, 0.01)
        engagement = min(ratio, 5.0) / 5.0

        # Reach: log-scaled views, roughly 0..1.3
        reach = log10(1 + max(views or 0, 0)) / max(Config.REACH_LOG_DIVISOR, 0.01)

        # Share / save boost relative to likes (weighted: shares count more than saves)
        share_weight = ((shares or 0) * 3 + (saves or 0) * 2) / max(likes or 1, 1)
        share_boost = min(share_weight, 0.5)

        # Small-creator multiplier
        if followers and followers < Config.SMALL_CREATOR_FOLLOWER_CAP:
            small_creator = 1.3
        elif followers and followers < Config.MID_CREATOR_FOLLOWER_CAP:
            small_creator = 1.1
        else:
            small_creator = 1.0

        # Israeli-signal multiplier, up to +50%
        israeli_mult = 1.0 + min(max(israeli_signal_score, 0.0) / 10.0, 0.5)

        base = (
            0.45 * velocity
            + 0.30 * engagement
            + 0.15 * reach
            + 0.10 * share_boost
        )
        potential = base * small_creator * israeli_mult

        return {
            "potential_score": round(potential, 4),
            "velocity_score": round(velocity, 4),
            "reach_score": round(reach, 4),
            "engagement_rate": round(engagement_rate, 2),
            "is_potential_hit": potential >= self.threshold,
        }

    # ------------------------------------------------------------------ #
    # Categorization (kept for report emoji — orthogonal to scoring)     #
    # ------------------------------------------------------------------ #

    def categorize_video(self, caption: str, hashtags: Optional[List[str]] = None) -> str:
        text = (caption or "").lower()
        if hashtags:
            text += " " + " ".join((h or "").lower() for h in hashtags)

        for dj in self.israeli_djs:
            if dj in text:
                return "israeli_dj"

        for category, keywords in self.category_keywords.items():
            if category == "israeli_dj":
                continue
            for keyword in keywords:
                if keyword.lower() in text:
                    return category

        return "general"

    # ------------------------------------------------------------------ #
    # Full video analysis                                                #
    # ------------------------------------------------------------------ #

    def analyze_video(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int,
        followers: int,
        baseline: float,
        caption: str = "",
        hashtags: Optional[List[str]] = None,
        saves: int = 0,
        posted_at: Optional[datetime] = None,
        location: Optional[dict] = None,
        author_username: str = "",
    ) -> dict:
        """Full analysis — detector + potential score + category."""
        israeli = self.detector.detect(
            caption=caption,
            hashtags=hashtags,
            location=location,
            author_username=author_username,
        )

        score_info = self.calculate_potential_score(
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            followers=followers,
            baseline_rate=baseline,
            posted_at=posted_at,
            israeli_signal_score=israeli["score"],
        )

        return {
            "engagement_rate": score_info["engagement_rate"],
            "potential_score": score_info["potential_score"],
            "velocity_score": score_info["velocity_score"],
            "reach_score": score_info["reach_score"],
            "is_potential_hit": score_info["is_potential_hit"],
            "category": self.categorize_video(caption, hashtags),
            "is_israeli": israeli["is_israeli"],
            "israeli_signal_score": israeli["score"],
            "israeli_signals": israeli["signals"],
        }


if __name__ == "__main__":
    calc = EngagementCalculator()
    result = calc.analyze_video(
        views=10000,
        likes=500,
        comments=50,
        shares=100,
        followers=5000,
        baseline=5.0,
        caption="מסיבה מטורפת ב-Haoman 17 הלילה! #מסיבה #תלאביב",
        hashtags=["מסיבה", "תלאביב"],
        saves=20,
        posted_at=datetime.now(),
    )
    print(result)
