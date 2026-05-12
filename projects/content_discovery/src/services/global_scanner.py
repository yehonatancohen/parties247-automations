"""
Global Viral Scanner for Content Discovery Bot.

Discovers globally trending party content on TikTok by scanning
hashtag pages - not limited to followed accounts.
"""

import asyncio
import math
import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import yt_dlp

from config import Config
from models import VideoCandidate


class GlobalScanner:
    """
    Scans TikTok hashtag pages to discover globally viral party content.

    Scoring is composite (no per-user baseline available):
        - Engagement rate (likes+comments+shares / views) — 30%
        - Absolute reach (log-scaled view count)           — 30%
        - Party relevance (keyword/hashtag depth)          — 25%
        - Upload velocity (views per hour since upload)    — 15%
    """

    # ------------------------------------------------------------------ #
    # Party keyword bank (English + Hebrew)                                #
    # ------------------------------------------------------------------ #
    PARTY_KEYWORDS = [
        # English – generic
        "party", "rave", "festival", "nightlife", "club", "clubbing",
        "afterparty", "after party", "dance", "dancing",
        # English – genres
        "techno", "trance", "psytrance", "psy trance", "house music",
        "housemusic", "edm", "dj set", "djset", "dj", "electronic",
        # English – culture
        "raveculture", "rave culture", "festivalseason", "festival season",
        "plur", "underground",
        # Hebrew
        "מסיבה", "מסיבות", "טראנס", "פסטיבל", "מועדון",
        "ריקוד", "ריקודים", "אלקטרוני", "דיג'יי", "רייב",
        # Israeli scene
        "telaviv", "tel aviv", "israel", "ישראל",
    ]

    # Score threshold (0-1) to flag as globally viral
    VIRALITY_THRESHOLD = 0.35

    def __init__(self):
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "ignoreerrors": True,
            "socket_timeout": 15,
            "retries": 2,
        }

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    async def scan_trending_hashtags(
        self,
        max_hashtags: int = None,
        videos_per_hashtag: int = 20,
    ) -> List[VideoCandidate]:
        """
        Scan configured hashtag pages and return globally viral party videos.

        Args:
            max_hashtags: Override Config.GLOBAL_MAX_HASHTAGS_PER_RUN.
            videos_per_hashtag: Max videos to fetch per hashtag page.

        Returns:
            List of VideoCandidate objects tagged source="global",
            sorted by virality_score descending, capped at Config.GLOBAL_TOP_N.
        """
        if not Config.GLOBAL_SCAN_ENABLED:
            print("🌍 Global scan disabled in config.")
            return []

        hashtags = Config.GLOBAL_SCAN_HASHTAGS
        limit = max_hashtags or Config.GLOBAL_MAX_HASHTAGS_PER_RUN
        hashtags = hashtags[:limit]

        print(f"🌍 Global scan: checking {len(hashtags)} hashtags…")

        semaphore = asyncio.Semaphore(3)  # max 3 concurrent hashtag fetches

        async def _fetch_one(tag: str) -> List[VideoCandidate]:
            async with semaphore:
                await asyncio.sleep(random.uniform(1.5, 4.0))
                return await self._scan_hashtag(tag, videos_per_hashtag)

        tasks = [_fetch_one(tag) for tag in hashtags]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_candidates: List[VideoCandidate] = []
        seen_ids: set = set()

        for result in results:
            if isinstance(result, Exception):
                print(f"⚠️ Global scan task error: {result}")
                continue
            for video in result:
                vid_id = video.video_url
                if vid_id not in seen_ids:
                    seen_ids.add(vid_id)
                    all_candidates.append(video)

        # Filter by minimum views
        all_candidates = [
            v for v in all_candidates if v.views >= Config.GLOBAL_MIN_VIEWS
        ]

        # Sort by virality score
        all_candidates.sort(key=lambda v: v.virality_score, reverse=True)
        top = all_candidates[: Config.GLOBAL_TOP_N]

        print(
            f"🌍 Global scan complete: {len(all_candidates)} candidates "
            f"→ top {len(top)} returned"
        )
        return top

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    async def _scan_hashtag(
        self, hashtag: str, count: int
    ) -> List[VideoCandidate]:
        """Fetch videos from a single TikTok hashtag page."""
        tag_clean = hashtag.lstrip("#")
        url = f"https://www.tiktok.com/tag/{tag_clean}"

        opts = self.ydl_opts.copy()
        opts["playlistend"] = count

        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(
                None, lambda: self._fetch_safe(opts, url)
            )
        except Exception as e:
            print(f"⚠️ Hashtag #{tag_clean} fetch error: {e}")
            return []

        if not info or "entries" not in info:
            print(f"⚠️ No entries for #{tag_clean}")
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=Config.VIDEO_AGE_HOURS)
        videos = []

        for entry in info.get("entries", []):
            if not entry:
                continue
            video = self._entry_to_candidate(entry, hashtag)
            if video is None:
                continue
            # Age filter
            if video.posted_at and video.posted_at < cutoff:
                continue
            videos.append(video)

        print(f"🏷️  #{tag_clean}: {len(videos)} recent videos")
        return videos

    def _entry_to_candidate(
        self, entry: dict, source_hashtag: str
    ) -> Optional[VideoCandidate]:
        """Convert a yt-dlp flat-extract entry into a VideoCandidate."""
        try:
            views = entry.get("view_count") or 0
            likes = entry.get("like_count") or 0
            comments = entry.get("comment_count") or 0
            shares = (entry.get("repost_count") or entry.get("share_count") or 0)

            username = (
                entry.get("uploader_id")
                or entry.get("uploader")
                or entry.get("channel")
                or "unknown"
            )
            # Strip leading @ if present
            username = username.lstrip("@")

            video_id = entry.get("id", "")
            url = (
                entry.get("webpage_url")
                or f"https://www.tiktok.com/@{username}/video/{video_id}"
            )

            # Parse upload time
            posted_at: Optional[datetime] = None
            ts = entry.get("timestamp")
            upload_date = entry.get("upload_date")
            if ts:
                posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif upload_date:
                try:
                    posted_at = datetime.strptime(upload_date, "%Y%m%d").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    pass

            caption = entry.get("description") or entry.get("title") or ""
            hashtags = entry.get("tags") or []

            # Score
            virality_score = self._compute_virality_score(
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                posted_at=posted_at,
                caption=caption,
                hashtags=hashtags,
            )

            video = VideoCandidate(
                platform="tiktok",
                video_url=url,
                thumbnail_url=entry.get("thumbnail"),
                author_username=username,
                author_display_name=entry.get("uploader") or username,
                author_followers=0,
                posted_at=posted_at,
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                caption=caption,
                hashtags=hashtags,
                source="global",
                virality_score=virality_score,
                is_potential_hit=(virality_score >= self.VIRALITY_THRESHOLD),
                category=self._categorize(caption, hashtags),
            )
            return video

        except Exception as e:
            print(f"⚠️ Entry parse error: {e}")
            return None

    def _compute_virality_score(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int,
        posted_at: Optional[datetime],
        caption: str,
        hashtags: List[str],
    ) -> float:
        """
        Composite virality score in [0, 1].

        Components:
            engagement_rate (30%) — interaction ratio vs views
            reach_score     (30%) — log-scaled view count
            relevance_score (25%) — party keyword density
            velocity_score  (15%) — views per hour since upload
        """
        # 1. Engagement rate (cap at 30% which is extremely high)
        total_eng = likes + comments + shares
        eng_rate = (total_eng / views) if views > 0 else 0.0
        engagement_score = min(eng_rate / 0.30, 1.0)

        # 2. Reach (log scale: 0 at 1 view → 1 at 10M views)
        if views > 0:
            reach_score = min(math.log10(views) / 7.0, 1.0)  # log10(10M) = 7
        else:
            reach_score = 0.0

        # 3. Party relevance
        text = (caption + " " + " ".join(hashtags)).lower()
        matched = sum(1 for kw in self.PARTY_KEYWORDS if kw in text)
        relevance_score = min(matched / 5.0, 1.0)  # saturates at 5 matches

        # 4. Velocity (views per hour; cap at 50K/h which is very viral)
        velocity_score = 0.0
        if posted_at:
            now = datetime.now(timezone.utc)
            hours_live = max((now - posted_at).total_seconds() / 3600, 0.5)
            views_per_hour = views / hours_live
            velocity_score = min(views_per_hour / 50_000, 1.0)

        # Weighted composite
        score = (
            0.30 * engagement_score
            + 0.30 * reach_score
            + 0.25 * relevance_score
            + 0.15 * velocity_score
        )
        return round(score, 4)

    def _categorize(self, caption: str, hashtags: List[str]) -> str:
        """Simple category detection for global content."""
        text = (caption + " " + " ".join(hashtags)).lower()

        genre_map = {
            "psytrance": ["psytrance", "psy trance", "טראנס", "trance"],
            "techno": ["techno", "techno music"],
            "house": ["house music", "housemusic", "deep house", "tech house"],
            "festival": ["festival", "פסטיבל", "festivalseason"],
            "release": ["new track", "release", "out now", "שיר חדש", "premiere"],
            "rave": ["rave", "raveculture", "underground", "רייב"],
            "israeli_scene": ["israel", "telaviv", "tel aviv", "ישראל", "מסיבה"],
        }

        for category, keywords in genre_map.items():
            if any(kw in text for kw in keywords):
                return category

        return "party"  # generic fallback for global content

    def _fetch_safe(self, opts: dict, url: str) -> Optional[dict]:
        """Synchronous yt-dlp fetch, returns None on failure."""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"⚠️ yt-dlp error for {url}: {e}")
            return None
