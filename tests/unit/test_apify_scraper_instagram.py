"""
Unit tests for Instagram outperformer detection in apify_scraper.py.

Covers:
- get_video_views: videoViewCount vs videoPlayCount (Reels) fallback
- get_engagement: video-first then likesCount fallback
- analyze_instagram_profile: baseline uses video-only avg when videos exist
- analyze_instagram_profile: falls back to mixed avg when no video data
- analyze_instagram_profile: outperformer correctly detected with Reels data
- analyze_instagram_profile: photos-only profile → empty recent_videos → no outperformer
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import modules.apify_scraper as scraper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(days_ago: int = 0) -> str:
    """ISO timestamp N days ago."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _make_video_post(views: int, via_reels: bool = False, days_ago: int = 1) -> dict:
    """Minimal Instagram post dict with video views."""
    key = "videoPlayCount" if via_reels else "videoViewCount"
    return {key: views, "likesCount": 50, "timestamp": _ts(days_ago), "id": f"v{views}"}


def _make_photo_post(likes: int, days_ago: int = 1) -> dict:
    """Minimal Instagram photo post dict (no video views)."""
    return {"likesCount": likes, "timestamp": _ts(days_ago), "id": f"p{likes}"}


# ---------------------------------------------------------------------------
# Inline extraction of the two local helpers (we test them via a wrapper
# because they are defined inside analyze_instagram_profile).
# We replicate the exact same logic here to test it in isolation.
# ---------------------------------------------------------------------------

def _get_video_views(post: dict) -> int:
    return post.get("videoViewCount") or post.get("videoPlayCount") or 0


def _get_engagement(post: dict) -> int:
    return _get_video_views(post) or post.get("likesCount") or 0


# ---------------------------------------------------------------------------
# Tests for get_video_views / get_engagement logic
# ---------------------------------------------------------------------------

class TestGetVideoViews:
    def test_videoViewCount_classic(self):
        assert _get_video_views({"videoViewCount": 5000}) == 5000

    def test_videoPlayCount_reels(self):
        assert _get_video_views({"videoPlayCount": 8000}) == 8000

    def test_videoViewCount_takes_precedence(self):
        assert _get_video_views({"videoViewCount": 5000, "videoPlayCount": 8000}) == 5000

    def test_photo_returns_zero(self):
        assert _get_video_views({"likesCount": 1000}) == 0

    def test_empty_dict(self):
        assert _get_video_views({}) == 0


class TestGetEngagement:
    def test_video_first(self):
        assert _get_engagement({"videoViewCount": 5000, "likesCount": 100}) == 5000

    def test_reels_first(self):
        assert _get_engagement({"videoPlayCount": 3000, "likesCount": 100}) == 3000

    def test_falls_back_to_likes(self):
        assert _get_engagement({"likesCount": 200}) == 200

    def test_empty_dict(self):
        assert _get_engagement({}) == 0


# ---------------------------------------------------------------------------
# Tests for analyze_instagram_profile via mocked run_actor + DB calls
# ---------------------------------------------------------------------------

_BASE_CFG = {
    "min_followers": 1_000,
    "max_followers": 80_000,
    "multiplier_threshold": 3.0,
    "multiplier_threshold_followers_ig": 2.0,
    "min_views_instagram": 100,
    "lookback_days": 30,
    "results_per_profile": 30,
}

_PROFILE_DETAILS = [
    {"followersCount": 10_000, "fullName": "Test User"}
]


def _patch_db():
    """Patch all DB calls used inside analyze_instagram_profile."""
    return patch.multiple(
        "modules.apify_scraper",
        is_apify_video_sent=MagicMock(return_value=False),
        mark_apify_video_sent=MagicMock(),
        save_outperformer_video=MagicMock(),
        update_apify_profile_analyzed=MagicMock(),
    )


class TestAnalyzeInstagramProfile:

    def _run(self, posts: list, cfg: dict = None):
        """Run analyze_instagram_profile with mocked actor calls."""
        effective_cfg = cfg or _BASE_CFG
        side_effects = [_PROFILE_DETAILS, posts]
        with patch("modules.apify_scraper.run_actor", side_effect=side_effects):
            return scraper.analyze_instagram_profile("testuser", effective_cfg, is_pinned=False)

    # --- Bug 1: Reels via videoPlayCount ---

    def test_reels_videoPlayCount_detected_as_outperformer(self):
        """Reels post (videoPlayCount) should be detected as outperformer."""
        posts = [
            _make_video_post(500, via_reels=False),   # baseline video
            _make_video_post(500, via_reels=False),
            _make_video_post(500, via_reels=False),
            _make_video_post(5000, via_reels=True),   # Reel — 10x avg → outperformer
        ]
        profile_data, outperformers = self._run(posts)
        assert profile_data is not None
        assert len(outperformers) == 1
        assert outperformers[0]["views"] == 5000

    def test_classic_video_still_detected(self):
        """Classic videoViewCount posts still work after refactor."""
        posts = [
            _make_video_post(500),
            _make_video_post(500),
            _make_video_post(500),
            _make_video_post(6000),  # 12x avg
        ]
        profile_data, outperformers = self._run(posts)
        assert len(outperformers) == 1

    # --- Bug 2: Baseline from video-only when videos exist ---

    def test_baseline_uses_video_only_not_photo_likes(self):
        """With both photos and videos, avg should be based on video views only.

        Setup: 10 photos with 50k likes + 4 videos at 5k views + 1 video at 19k views.
        - video-only avg = (5000*4 + 19000) / 5 = 7800
        - 19000 / 7800 = 2.44x  → below 3.0 threshold (is_avg_out False)
        - profile has 50k followers → 19000 / 50000 = 0.38x → below 2.0 (is_fol_out False)
        - If mixed avg were used: (50000*10 + 5000*4 + 19000)/15 ≈ 34,933 → ~0.54x
          Either way no detection; the point is video-only avg is correctly computed.
        """
        # Use a separate details response with high followers to avoid fol_out triggering
        details_high_followers = [{"followersCount": 50_000, "fullName": "Test User"}]
        posts = (
            [_make_photo_post(50_000)] * 10
            + [_make_video_post(5_000)] * 4
            + [_make_video_post(19_000)]
        )
        with patch("modules.apify_scraper.run_actor", side_effect=[details_high_followers, posts]):
            profile_data, outperformers = scraper.analyze_instagram_profile(
                "testuser", _BASE_CFG, is_pinned=False
            )
        assert profile_data is not None
        # avg_views comes from video-only: 7800. 19000/7800=2.44x < 3.0 → no outperformer
        assert profile_data["avg_views"] == pytest.approx(7800.0)
        assert len(outperformers) == 0

    def test_clear_video_outperformer_over_video_baseline(self):
        """A video clearly above the video-only average is detected."""
        posts = (
            [_make_photo_post(50_000)] * 10
            + [_make_video_post(2_000)] * 4
            + [_make_video_post(30_000)]
        )
        # video-only avg = (2000*4 + 30000) / 5 = 7600
        # 30000 / 7600 ≈ 3.95x → above 3.0 threshold → outperformer
        profile_data, outperformers = self._run(posts)
        assert len(outperformers) == 1
        assert outperformers[0]["views"] == 30_000

    def test_fallback_to_mixed_avg_when_no_videos_at_all(self):
        """When account has only photos, mixed avg is used as fallback."""
        posts = [_make_photo_post(1_000)] * 5
        profile_data, outperformers = self._run(posts)
        # No videos → recent_videos empty → no outperformer (even with fallback avg)
        assert len(outperformers) == 0

    # --- Edge cases ---

    def test_no_posts_returns_none(self):
        with patch("modules.apify_scraper.run_actor", side_effect=[_PROFILE_DETAILS, []]):
            profile_data, outperformers = scraper.analyze_instagram_profile(
                "testuser", _BASE_CFG, is_pinned=False
            )
        assert profile_data is None
        assert outperformers == []

    def test_min_views_filter_applied(self):
        """Posts below min_views_instagram threshold are skipped."""
        cfg = {**_BASE_CFG, "min_views_instagram": 5_000}
        posts = [
            _make_video_post(1_000),
            _make_video_post(1_000),
            _make_video_post(1_000),
            _make_video_post(4_999),  # 4.99x avg but below min_views
        ]
        profile_data, outperformers = self._run(posts, cfg)
        assert len(outperformers) == 0

    def test_old_posts_excluded_from_candidates(self):
        """Posts older than lookback_days are not included as outperformer candidates."""
        posts = [
            _make_video_post(1_000, days_ago=1),
            _make_video_post(1_000, days_ago=1),
            _make_video_post(50_000, days_ago=60),  # too old → not a candidate
        ]
        profile_data, outperformers = self._run(posts)
        # Old post is in video_views_all (baseline) but not in recent_videos
        assert len(outperformers) == 0

    def test_follower_out_of_range_returns_none(self):
        """Profile with followers outside range is filtered out."""
        details = [{"followersCount": 500_000}]  # way above max_followers
        with patch("modules.apify_scraper.run_actor", side_effect=[details, []]):
            profile_data, outperformers = scraper.analyze_instagram_profile(
                "bigstar", _BASE_CFG, is_pinned=False
            )
        assert profile_data is None
