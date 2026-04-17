"""Tests for HashtagDiscoveryScraper dedupe, filtering, and author ranking."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from models import FollowSuggestion, VideoCandidate
from services.discovery_scraper import HashtagDiscoveryScraper
from services.israeli_detector import IsraeliContentDetector


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mk_tiktok_entry(url, uploader, desc="", tags=None):
    return {
        "webpage_url": url,
        "uploader": uploader,
        "description": desc,
        "tags": tags or [],
        "view_count": 1000,
        "like_count": 50,
        "comment_count": 5,
        "repost_count": 2,
    }


def test_tiktok_crawl_dedupes_and_filters_non_israeli():
    detector = IsraeliContentDetector()
    scraper = HashtagDiscoveryScraper(
        detector=detector,
        instagram_scraper=None,
        monitored_usernames={"monitored_dude"},
    )

    entries = [
        _mk_tiktok_entry(
            "https://tiktok.com/@a/video/1",
            "monitored_dude",  # will be deduped because URL is seen
            desc="מסיבה מטורפת #מסיבה",
        ),
        _mk_tiktok_entry(
            "https://tiktok.com/@b/video/2",
            "dj_random",
            desc="random english content",  # not Israeli
        ),
        _mk_tiktok_entry(
            "https://tiktok.com/@c/video/3",
            "new_israeli",
            desc="מסיבה ברביעי",
            tags=["מסיבה"],
        ),
    ]
    fake_info = {"entries": entries}

    with patch.object(
        scraper, "_fetch_tiktok_tag_sync", return_value=fake_info
    ):
        videos = _run(
            scraper.crawl(
                tags=["מסיבה"],
                seen_urls={"https://tiktok.com/@a/video/1"},
            )
        )

    assert len(videos) == 1
    assert videos[0].video_url == "https://tiktok.com/@c/video/3"
    assert videos[0].is_israeli is True


def test_instagram_login_required_is_graceful():
    class FakeIGScraper:
        client = SimpleNamespace(
            hashtag_medias_recent=lambda *a, **kw: (_ for _ in ()).throw(
                Exception("LoginRequired")
            ),
            hashtag_medias_top=lambda *a, **kw: (_ for _ in ()).throw(
                Exception("LoginRequired")
            ),
        )

        def login(self):
            return True

    scraper = HashtagDiscoveryScraper(
        detector=IsraeliContentDetector(),
        instagram_scraper=FakeIGScraper(),
        monitored_usernames=set(),
    )
    # Skip TikTok by mocking it to return nothing
    with patch.object(scraper, "_fetch_tiktok_tag_sync", return_value=None):
        videos = _run(scraper.crawl(tags=["מסיבה"]))
    assert videos == []


def test_author_suggestion_ranking():
    detector = IsraeliContentDetector()
    scraper = HashtagDiscoveryScraper(
        detector=detector,
        instagram_scraper=None,
        monitored_usernames=set(),
    )

    def vid(username, score):
        return VideoCandidate(
            platform="tiktok",
            video_url=f"https://tiktok.com/@{username}/video/{score}",
            author_username=username,
            caption="מסיבה",
            potential_score=score,
            is_israeli=True,
            discovered_via_hashtag="מסיבה",
        )

    videos = [
        vid("author_a", 0.7),
        vid("author_a", 0.7),
        vid("author_a", 0.7),
        vid("author_b", 0.3),
        vid("author_b", 0.3),
        vid("author_b", 0.3),
        vid("author_b", 0.3),
        vid("author_b", 0.3),
    ]
    suggestions = scraper.suggest_authors(videos, top_n=2)
    assert len(suggestions) == 2
    assert suggestions[0].username == "author_a"  # 3 * 0.7 = 2.1
    assert suggestions[1].username == "author_b"  # 5 * 0.3 = 1.5
