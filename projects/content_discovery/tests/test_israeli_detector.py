"""Tests for IsraeliContentDetector signal scoring."""

from services.israeli_detector import IsraeliContentDetector


def test_pure_hebrew_caption_is_israeli():
    detector = IsraeliContentDetector()
    result = detector.detect(
        caption="מסיבה מטורפת הלילה, בואו כולם!",
        hashtags=[],
        location=None,
        author_username="some_user",
    )
    assert result["is_israeli"] is True
    assert result["score"] >= 2.0
    assert "hebrew_caption" in result["signals"]


def test_english_caption_with_venue_is_israeli():
    detector = IsraeliContentDetector()
    result = detector.detect(
        caption="Live set at Haoman 17 tonight, don't miss it!",
        hashtags=[],
        location=None,
        author_username="random_dj",
    )
    assert result["is_israeli"] is True
    assert any(s.startswith("venue:") for s in result["signals"])


def test_known_israeli_dj_author_is_israeli():
    detector = IsraeliContentDetector()
    result = detector.detect(
        caption="New set out now",
        hashtags=["psytrance"],
        location=None,
        author_username="infected_mushroom",
    )
    assert result["is_israeli"] is True
    assert any(s.startswith("dj:") for s in result["signals"])


def test_only_telaviv_hashtag_does_not_cross_threshold():
    detector = IsraeliContentDetector()
    result = detector.detect(
        caption="Great vibes last night",
        hashtags=["telaviv"],
        location=None,
        author_username="random_dj",
    )
    # Only the Latin-nightlife hashtag hit (+1.5) — below the 2.5 threshold
    assert result["is_israeli"] is False
    assert result["score"] < 2.5


def test_spanish_caption_not_israeli():
    detector = IsraeliContentDetector()
    result = detector.detect(
        caption="Noche increíble con la reggaeton en la playa",
        hashtags=["reggaeton", "fiesta"],
        location=None,
        author_username="djlatino",
    )
    assert result["is_israeli"] is False
    assert result["score"] == 0.0
