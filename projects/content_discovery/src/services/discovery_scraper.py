"""
Hashtag-based discovery scraper.

Crawls TikTok and Instagram hashtag feeds to surface Israeli creators the bot
does not already monitor. Every candidate video is filtered through
IsraeliContentDetector before being yielded. Authors not in the monitored
set are aggregated and returned as FollowSuggestion objects.
"""

import asyncio
import json
import os
import random
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote

import yt_dlp

from config import Config
from models import FollowSuggestion, VideoCandidate
from services.israeli_detector import IsraeliContentDetector


HASHTAG_REGEX = re.compile(r'#([\w\u0590-\u05FF]+)')


class HashtagDiscoveryScraper:
    """Discover new Israeli creators via hashtag feeds on TikTok + Instagram."""

    def __init__(
        self,
        detector: IsraeliContentDetector,
        instagram_scraper=None,
        monitored_usernames: Optional[Set[str]] = None,
    ):
        self.detector = detector
        self.instagram_scraper = instagram_scraper
        self.monitored_usernames = {u.lower() for u in (monitored_usernames or set())}
        self._semaphore = asyncio.Semaphore(Config.DISCOVERY_CONCURRENCY)
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "dump_single_json": True,
            "ignoreerrors": True,
            "playlistend": Config.DISCOVERY_VIDEOS_PER_HASHTAG,
            "socket_timeout": 15,
            "retries": 2,
        }

    # ------------------------------------------------------------------ #
    # TikTok hashtag crawl                                               #
    # ------------------------------------------------------------------ #

    def _tiktok_hashtag_url(self, tag: str) -> str:
        return f"https://www.tiktok.com/tag/{tag}"

    def _fetch_tiktok_tag_sync(self, url: str) -> Optional[Dict]:
        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"⚠️ yt-dlp hashtag fetch failed for {url}: {e}")
            return None

    async def _tiktok_entries_for_tag(self, tag: str) -> List[Dict]:
        """Fetch yt-dlp entries for a TikTok hashtag; retry with URL-encoded form."""
        loop = asyncio.get_event_loop()
        urls = [self._tiktok_hashtag_url(tag)]
        encoded = quote(tag, safe="")
        if encoded != tag:
            urls.append(self._tiktok_hashtag_url(encoded))

        for url in urls:
            info = await loop.run_in_executor(None, self._fetch_tiktok_tag_sync, url)
            if info and info.get("entries"):
                return [e for e in info["entries"] if e]
            await asyncio.sleep(1.0)
        return []

    def _tiktok_entry_to_video(self, entry: Dict, tag: str) -> Optional[VideoCandidate]:
        url = entry.get("webpage_url") or entry.get("url")
        if not url:
            return None
        uploader = entry.get("uploader") or entry.get("channel") or ""
        caption = entry.get("description") or entry.get("title") or ""
        raw_tags = entry.get("tags") or []
        merged_tags = set(t.lower().lstrip("#") for t in raw_tags if t)
        merged_tags.update(m.lower() for m in HASHTAG_REGEX.findall(caption))

        timestamp = entry.get("timestamp")
        posted_at = datetime.fromtimestamp(timestamp) if timestamp else None

        return VideoCandidate(
            platform="tiktok",
            video_url=url,
            thumbnail_url=entry.get("thumbnail"),
            author_username=uploader,
            author_display_name=uploader,
            author_followers=0,
            posted_at=posted_at,
            views=entry.get("view_count", 0) or 0,
            likes=entry.get("like_count", 0) or 0,
            comments=entry.get("comment_count", 0) or 0,
            shares=entry.get("repost_count", 0) or 0,
            saves=0,
            caption=caption,
            hashtags=sorted(merged_tags),
            discovered_via_hashtag=tag,
        )

    async def crawl_tiktok_tag(self, tag: str) -> List[VideoCandidate]:
        entries = await self._tiktok_entries_for_tag(tag)
        out = []
        for e in entries:
            video = self._tiktok_entry_to_video(e, tag)
            if video:
                out.append(video)
        await asyncio.sleep(random.uniform(1.5, 2.5))
        return out

    # ------------------------------------------------------------------ #
    # Instagram hashtag crawl                                            #
    # ------------------------------------------------------------------ #

    def _ig_media_to_video(self, media, tag: str) -> Optional[VideoCandidate]:
        try:
            code = getattr(media, "code", None)
            if not code:
                return None
            caption = getattr(media, "caption_text", "") or ""
            user = getattr(media, "user", None)
            username = getattr(user, "username", "") if user else ""
            display_name = getattr(user, "full_name", "") if user else ""
            taken_at = getattr(media, "taken_at", None)
            location = None
            try:
                raw_loc = getattr(media, "location", None)
                if raw_loc:
                    location = {
                        "name": getattr(raw_loc, "name", None),
                        "city": getattr(raw_loc, "city", None),
                        "country": None,
                    }
            except Exception:
                location = None

            raw_tags = [m.lower() for m in HASHTAG_REGEX.findall(caption)]

            return VideoCandidate(
                platform="instagram",
                video_url=f"https://www.instagram.com/reel/{code}/",
                thumbnail_url=str(getattr(media, "thumbnail_url", "") or "") or None,
                author_username=username,
                author_display_name=display_name,
                author_followers=0,
                posted_at=taken_at,
                views=getattr(media, "play_count", 0) or 0,
                likes=getattr(media, "like_count", 0) or 0,
                comments=getattr(media, "comment_count", 0) or 0,
                shares=0,
                saves=getattr(media, "save_count", 0) or 0,
                caption=caption,
                hashtags=sorted(set(raw_tags)),
                location=location,
                discovered_via_hashtag=tag,
            )
        except Exception as e:
            print(f"⚠️ Instagram media parse error: {e}")
            return None

    async def crawl_instagram_tag(self, tag: str) -> List[VideoCandidate]:
        if not self.instagram_scraper:
            return []

        loop = asyncio.get_event_loop()
        client = getattr(self.instagram_scraper, "client", None)
        if client is None and hasattr(self.instagram_scraper, "login"):
            try:
                self.instagram_scraper.login()
                client = getattr(self.instagram_scraper, "client", None)
            except Exception as e:
                print(f"⚠️ Instagram login failed for discovery: {e}")
                return []
        if client is None:
            return []

        videos: List[VideoCandidate] = []
        # hashtag_medias_recent — primary
        try:
            recent = await loop.run_in_executor(
                None,
                lambda: client.hashtag_medias_recent(tag, amount=Config.DISCOVERY_VIDEOS_PER_HASHTAG),
            )
            for m in recent or []:
                v = self._ig_media_to_video(m, tag)
                if v:
                    videos.append(v)
        except Exception as e:
            print(f"⚠️ IG hashtag_medias_recent failed for #{tag}: {e}")

        await asyncio.sleep(random.uniform(2.5, 3.5))

        # hashtag_medias_top — secondary
        try:
            top = await loop.run_in_executor(
                None,
                lambda: client.hashtag_medias_top(tag, amount=5),
            )
            for m in top or []:
                v = self._ig_media_to_video(m, tag)
                if v:
                    videos.append(v)
        except Exception as e:
            print(f"⚠️ IG hashtag_medias_top failed for #{tag}: {e}")

        await asyncio.sleep(random.uniform(2.5, 3.5))
        return videos

    # ------------------------------------------------------------------ #
    # Orchestration                                                      #
    # ------------------------------------------------------------------ #

    async def _crawl_tag_both(self, tag: str) -> List[VideoCandidate]:
        async with self._semaphore:
            tiktok_videos = await self.crawl_tiktok_tag(tag)
            instagram_videos = await self.crawl_instagram_tag(tag)
            return tiktok_videos + instagram_videos

    async def crawl(
        self,
        tags: Optional[Iterable[str]] = None,
        seen_urls: Optional[Set[str]] = None,
    ) -> List[VideoCandidate]:
        """Crawl the configured discovery hashtags, dedupe, filter by detector."""
        tag_list = list(tags) if tags is not None else list(Config.DISCOVERY_HASHTAGS)
        tag_list = tag_list[: Config.DISCOVERY_MAX_HASHTAGS_PER_RUN]
        if not tag_list:
            return []

        seen_urls = set(seen_urls or set())
        print(f"🔎 Discovery: crawling {len(tag_list)} hashtags...")

        results = await asyncio.gather(*[self._crawl_tag_both(t) for t in tag_list])

        israeli_videos: List[VideoCandidate] = []
        for bucket in results:
            for video in bucket:
                if not video.video_url or video.video_url in seen_urls:
                    continue
                seen_urls.add(video.video_url)

                verdict = self.detector.detect(
                    caption=video.caption,
                    hashtags=video.hashtags,
                    location=video.location,
                    author_username=video.author_username,
                )
                if not verdict["is_israeli"]:
                    continue
                video.is_israeli = True
                video.israeli_signal_score = verdict["score"]
                video.israeli_signals = verdict["signals"]
                israeli_videos.append(video)

        print(f"🔎 Discovery: {len(israeli_videos)} Israeli candidates after filter")
        return israeli_videos

    # ------------------------------------------------------------------ #
    # Author-suggestion derivation                                       #
    # ------------------------------------------------------------------ #

    def suggest_authors(
        self,
        videos: List[VideoCandidate],
        top_n: int = 10,
    ) -> List[FollowSuggestion]:
        """Rank new Israeli authors by count * avg potential_score."""
        buckets: Dict[Tuple[str, str], Dict] = {}
        for v in videos:
            if not v.author_username:
                continue
            username = v.author_username.lower()
            if username in self.monitored_usernames:
                continue
            key = (v.platform, username)
            b = buckets.setdefault(
                key,
                {
                    "count": 0,
                    "score_sum": 0.0,
                    "display_name": v.author_display_name or v.author_username,
                    "sample": v.caption[:100] if v.caption else "",
                    "tag": v.discovered_via_hashtag or "",
                    "followers": v.author_followers,
                },
            )
            b["count"] += 1
            b["score_sum"] += max(v.potential_score, 0.0)

        ranked = []
        for (platform, username), b in buckets.items():
            avg_score = b["score_sum"] / max(b["count"], 1)
            rank_score = b["count"] * avg_score
            ranked.append(
                (
                    rank_score,
                    FollowSuggestion(
                        platform=platform,
                        username=username,
                        display_name=b["display_name"],
                        followers=b["followers"],
                        reason=(
                            f"Discovered via #{b['tag']} — {b['count']} Israeli "
                            f"videos, avg potential {avg_score:.2f}"
                            if b["tag"]
                            else f"{b['count']} Israeli videos, avg potential {avg_score:.2f}"
                        ),
                        sample_content=b["sample"],
                    ),
                )
            )

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in ranked[:top_n]]

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def load_monitored_usernames() -> Set[str]:
        """Load monitored_accounts.json (+ fallback users.txt) as a lowercased set."""
        usernames: Set[str] = set()
        accounts_file = os.path.join(Config.DATA_DIR, "monitored_accounts.json")
        if os.path.exists(accounts_file):
            try:
                with open(accounts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        if isinstance(item, str):
                            usernames.add(item.lower().lstrip("@"))
                        elif isinstance(item, dict) and item.get("username"):
                            usernames.add(item["username"].lower().lstrip("@"))
            except Exception as e:
                print(f"⚠️ Could not read monitored_accounts.json: {e}")

        users_txt = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(Config.BASE_DIR))),
            "tiktok_trend_hunter",
            "users.txt",
        )
        if os.path.exists(users_txt):
            try:
                with open(users_txt, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            usernames.add(line.lower().lstrip("@"))
            except Exception as e:
                print(f"⚠️ Could not read users.txt: {e}")

        return usernames
