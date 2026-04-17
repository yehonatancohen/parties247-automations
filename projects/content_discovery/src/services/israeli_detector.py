"""
Israeli Content Detector.

Signal-weighted heuristic that returns an Israeli-ness score for a video
based on caption, hashtags, location metadata, and author identity.
No external language-detection dependency — Hebrew unicode range plus
curated keyword lists from Config are sufficient and deterministic.
"""

import re
from typing import Dict, List, Optional, Tuple

from config import Config


HEBREW_CHAR_RE = re.compile(r"[\u0590-\u05FF]")


SIGNAL_WEIGHTS = {
    "author_allowlist": 4.0,
    "location_israel": 3.5,
    "hebrew_hashtag": 2.5,
    "hebrew_caption": 2.0,
    "venue_match": 2.0,
    "city_match": 1.5,
    "latin_nightlife_hashtag": 1.5,
}


class IsraeliContentDetector:
    """Stateless detector producing a weighted Israeli-content score."""

    def __init__(self):
        self._djs = {dj.lower() for dj in Config.ISRAELI_DJS}
        self._creators = {c.lower() for c in Config.ISRAELI_CREATORS}
        self._venues = [v.lower() for v in Config.ISRAELI_VENUES]
        self._cities = [c.lower() for c in Config.ISRAELI_CITIES]
        self._he_tags = {t.lower() for t in Config.ISRAELI_HASHTAGS_HE}
        self._en_tags = {t.lower() for t in Config.ISRAELI_HASHTAGS_EN}
        self._threshold = Config.ISRAELI_SIGNAL_THRESHOLD
        self._hebrew_ratio_threshold = Config.HEBREW_CHAR_RATIO_THRESHOLD

    @staticmethod
    def hebrew_char_ratio(text: str) -> float:
        """Ratio of Hebrew characters to non-space characters in text."""
        if not text:
            return 0.0
        stripped = re.sub(r"\s+", "", text)
        if not stripped:
            return 0.0
        hebrew_count = len(HEBREW_CHAR_RE.findall(stripped))
        return hebrew_count / len(stripped)

    def _match_author(self, username: str) -> Optional[str]:
        u = (username or "").lower()
        if not u:
            return None
        if u in self._creators:
            return f"creator:{u}"
        # Compare in a normalized form so "infected_mushroom" matches "infected mushroom"
        u_norm = re.sub(r"[\s_]", "", u)
        for dj in self._djs:
            dj_norm = re.sub(r"[\s_]", "", dj)
            if dj_norm and dj_norm in u_norm:
                return f"dj:{dj}"
        return None

    def _match_location(self, location: Optional[Dict]) -> Optional[str]:
        if not location:
            return None
        country = (location.get("country") or "").strip().lower()
        if country in {"il", "israel", "ישראל"}:
            return "country:IL"
        city = (location.get("city") or location.get("name") or "").strip().lower()
        if city:
            for c in self._cities:
                if c in city:
                    return f"city:{c}"
        return None

    def _match_hebrew_hashtag(self, tags: List[str]) -> Optional[str]:
        for raw in tags or []:
            t = (raw or "").strip().lstrip("#").lower()
            if not t:
                continue
            if HEBREW_CHAR_RE.search(t):
                return f"hashtag:{t}"
            if t in self._he_tags:
                return f"hashtag:{t}"
        return None

    def _match_latin_hashtag(self, tags: List[str]) -> Optional[str]:
        for raw in tags or []:
            t = (raw or "").strip().lstrip("#").lower()
            if t and t in self._en_tags:
                return f"hashtag:{t}"
        return None

    def _match_venue(self, haystack: str) -> Optional[str]:
        for venue in self._venues:
            if venue in haystack:
                return f"venue:{venue}"
        return None

    def _match_city(self, haystack: str) -> Optional[str]:
        for city in self._cities:
            if city in haystack:
                return f"city_text:{city}"
        return None

    def detect(
        self,
        caption: str = "",
        hashtags: Optional[List[str]] = None,
        location: Optional[Dict] = None,
        author_username: str = "",
    ) -> Dict:
        """Return {is_israeli, score, signals}."""
        hashtags = hashtags or []
        caption_lower = (caption or "").lower()

        score = 0.0
        signals: List[str] = []

        match = self._match_author(author_username)
        if match:
            score += SIGNAL_WEIGHTS["author_allowlist"]
            signals.append(match)

        match = self._match_location(location)
        if match:
            score += SIGNAL_WEIGHTS["location_israel"]
            signals.append(match)

        match = self._match_hebrew_hashtag(hashtags)
        if match:
            score += SIGNAL_WEIGHTS["hebrew_hashtag"]
            signals.append(match)

        if self.hebrew_char_ratio(caption) >= self._hebrew_ratio_threshold:
            score += SIGNAL_WEIGHTS["hebrew_caption"]
            signals.append("hebrew_caption")

        # Venues and cities are matched in the caption text only — otherwise
        # a single Israeli-city hashtag would double-count (both as a
        # city-text match and as a Latin-nightlife-hashtag match).
        match = self._match_venue(caption_lower)
        if match:
            score += SIGNAL_WEIGHTS["venue_match"]
            signals.append(match)

        match = self._match_city(caption_lower)
        if match:
            score += SIGNAL_WEIGHTS["city_match"]
            signals.append(match)

        match = self._match_latin_hashtag(hashtags)
        if match:
            score += SIGNAL_WEIGHTS["latin_nightlife_hashtag"]
            signals.append(match)

        return {
            "is_israeli": score >= self._threshold,
            "score": round(score, 2),
            "signals": signals,
        }
