"""Tests for the composite potential-hit scoring."""

from datetime import datetime, timedelta

from services.engagement_calculator import EngagementCalculator


def _hour_ago(n):
    return datetime.now() - timedelta(hours=n)


def test_small_creator_crosses_threshold():
    calc = EngagementCalculator()
    result = calc.calculate_potential_score(
        views=10000,
        likes=500,
        comments=30,
        shares=20,
        saves=10,
        followers=5000,
        baseline_rate=3.0,
        posted_at=_hour_ago(1),
        israeli_signal_score=0.0,
    )
    assert result["is_potential_hit"] is True
    assert result["potential_score"] >= 0.55


def test_large_creator_scores_lower_than_small_for_same_numbers():
    calc = EngagementCalculator()
    small = calc.calculate_potential_score(
        views=10000, likes=500, comments=30, shares=20, saves=10,
        followers=5000, baseline_rate=3.0, posted_at=_hour_ago(1),
        israeli_signal_score=0.0,
    )
    large = calc.calculate_potential_score(
        views=10000, likes=500, comments=30, shares=20, saves=10,
        followers=500000, baseline_rate=3.0, posted_at=_hour_ago(1),
        israeli_signal_score=0.0,
    )
    assert small["potential_score"] > large["potential_score"]


def test_israeli_signal_boosts_score():
    calc = EngagementCalculator()
    plain = calc.calculate_potential_score(
        views=10000, likes=500, comments=30, shares=20, saves=10,
        followers=50000, baseline_rate=3.0, posted_at=_hour_ago(1),
        israeli_signal_score=0.0,
    )
    israeli = calc.calculate_potential_score(
        views=10000, likes=500, comments=30, shares=20, saves=10,
        followers=50000, baseline_rate=3.0, posted_at=_hour_ago(1),
        israeli_signal_score=6.0,
    )
    # Multiplier at score=6 is 1.0 + 0.5 (clamped) = 1.5
    assert israeli["potential_score"] > plain["potential_score"]
    ratio = israeli["potential_score"] / max(plain["potential_score"], 1e-6)
    assert 1.4 < ratio < 1.6


def test_zero_views_zero_likes_no_error():
    calc = EngagementCalculator()
    result = calc.calculate_potential_score(
        views=0, likes=0, comments=0, shares=0, saves=0,
        followers=0, baseline_rate=0.0, posted_at=_hour_ago(1),
        israeli_signal_score=0.0,
    )
    assert result["potential_score"] == 0.0
    assert result["is_potential_hit"] is False


def test_old_video_velocity_decays():
    calc = EngagementCalculator()
    fresh = calc.calculate_potential_score(
        views=5000, likes=300, comments=15, shares=10, saves=5,
        followers=30000, baseline_rate=3.0, posted_at=_hour_ago(1),
        israeli_signal_score=0.0,
    )
    old = calc.calculate_potential_score(
        views=5000, likes=300, comments=15, shares=10, saves=5,
        followers=30000, baseline_rate=3.0, posted_at=_hour_ago(48),
        israeli_signal_score=0.0,
    )
    assert fresh["velocity_score"] > old["velocity_score"]
    assert fresh["potential_score"] > old["potential_score"]
