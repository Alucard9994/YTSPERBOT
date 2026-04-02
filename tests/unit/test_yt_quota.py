"""Unit tests for YouTube API quota exhaustion detection and early-exit behavior."""
import pytest
from unittest.mock import patch, MagicMock

from modules.yt_api import yt_get, YouTubeQuotaExceeded


# ---------------------------------------------------------------------------
# yt_api.yt_get — quota detection
# ---------------------------------------------------------------------------

def _mock_403(reason: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 403
    resp.json.return_value = {
        "error": {"errors": [{"reason": reason, "domain": "youtube.quota"}]}
    }
    resp.raise_for_status.side_effect = Exception("403")
    return resp


class TestYtGet:
    def test_raises_quota_exceeded_on_quotaExceeded(self):
        with patch("requests.get", return_value=_mock_403("quotaExceeded")):
            with pytest.raises(YouTubeQuotaExceeded):
                yt_get("channels", {"part": "id", "id": "UCxxx"})

    def test_raises_quota_exceeded_on_dailyLimitExceeded(self):
        with patch("requests.get", return_value=_mock_403("dailyLimitExceeded")):
            with pytest.raises(YouTubeQuotaExceeded):
                yt_get("channels", {"part": "id", "id": "UCxxx"})

    def test_raises_http_error_on_generic_403(self):
        resp = MagicMock()
        resp.status_code = 403
        resp.json.return_value = {"error": {"errors": [{"reason": "forbidden"}]}}
        resp.raise_for_status.side_effect = Exception("403 Forbidden")
        with patch("requests.get", return_value=resp):
            with pytest.raises(Exception, match="403"):
                yt_get("channels", {"part": "id", "id": "UCxxx"})

    def test_returns_json_on_200(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"items": [{"id": "UCxxx"}]}
        resp.raise_for_status.return_value = None
        with patch("requests.get", return_value=resp):
            result = yt_get("channels", {"part": "id", "id": "UCxxx"})
        assert result == {"items": [{"id": "UCxxx"}]}

    def test_handles_malformed_403_body_gracefully(self):
        """If the 403 body can't be parsed, fall through to raise_for_status."""
        resp = MagicMock()
        resp.status_code = 403
        resp.json.side_effect = ValueError("not json")
        resp.raise_for_status.side_effect = Exception("403 Forbidden")
        with patch("requests.get", return_value=resp):
            with pytest.raises(Exception, match="403"):
                yt_get("channels", {"part": "id", "id": "UCxxx"})


# ---------------------------------------------------------------------------
# youtube_comments — early exit on quota exhaustion
# ---------------------------------------------------------------------------

class TestYouTubeCommentsQuotaExit:
    def _base_config(self):
        return {
            "trend_detector": {"min_mentions_to_track": 3},
            "youtube_comments": {
                "max_comments_per_video": 100,
                "velocity_threshold": 200,
                "max_videos_per_channel": 3,
            },
            "keywords": ["ghost", "paranormal"],
            "youtube_search_queries": {"en": ["ghost sightings", "paranormal activity"]},
            "competitor_channels": {
                "it": [
                    {"handle": "channelA"},
                    {"handle": "channelB"},
                    {"handle": "channelC"},
                ]
            },
            "priority_score": {"min_score": 1},
        }

    def test_list1_stops_on_quota(self, capsys):
        call_count = 0

        def fake_yt_get(endpoint, params):
            nonlocal call_count
            call_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.youtube_comments import run_comments_trend_detector
        with patch("modules.youtube_comments.yt_get", side_effect=fake_yt_get):
            run_comments_trend_detector(self._base_config())

        assert call_count == 1
        assert "Lista 1 interrotta" in capsys.readouterr().out

    def test_list2_stops_on_quota_at_handle_resolution(self, capsys):
        call_count = 0

        def fake_resolve(handle):
            nonlocal call_count
            call_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.youtube_comments import run_competitor_comments
        with patch("modules.youtube_comments.resolve_channel_handle", side_effect=fake_resolve):
            run_competitor_comments(self._base_config())

        # Only 1 handle attempted before stopping
        assert call_count == 1
        assert "Lista 2 interrotta" in capsys.readouterr().out

    def test_list2_stops_on_quota_at_video_fetch(self, capsys):
        """Quota hit while fetching videos — should stop after first channel."""
        channel_call_count = 0
        video_call_count = 0

        def fake_resolve(handle):
            nonlocal channel_call_count
            channel_call_count += 1
            return f"UC{handle}"

        def fake_get_videos(channel_id, max_videos):
            nonlocal video_call_count
            video_call_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.youtube_comments import run_competitor_comments
        with patch("modules.youtube_comments.resolve_channel_handle", side_effect=fake_resolve):
            with patch("modules.youtube_comments.get_channel_recent_videos", side_effect=fake_get_videos):
                run_competitor_comments(self._base_config())

        assert channel_call_count == 1
        assert video_call_count == 1
        assert "Lista 2 interrotta" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# competitor_monitor — early exit on quota exhaustion
# ---------------------------------------------------------------------------

class TestCompetitorMonitorQuotaExit:
    def _base_config(self):
        return {
            "competitor_channels": {
                "it": [
                    {"handle": "chanA"},
                    {"handle": "chanB"},
                    {"handle": "chanC"},
                ]
            },
            "competitor_monitor": {
                "new_video_max_age_hours": 48,
                "subscriber_growth_threshold": 0.10,
            },
            "keywords": ["ghost"],
        }

    def test_new_video_monitor_stops_on_quota(self, capsys):
        call_count = 0

        def fake_resolve(handle):
            nonlocal call_count
            call_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.competitor_monitor import run_new_video_monitor
        with patch("modules.competitor_monitor.resolve_and_cache", side_effect=fake_resolve):
            run_new_video_monitor(self._base_config())

        assert call_count == 1
        assert "interrotto" in capsys.readouterr().out

    def test_subscriber_monitor_stops_on_quota_at_resolve(self, capsys):
        call_count = 0

        def fake_resolve(handle):
            nonlocal call_count
            call_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.competitor_monitor import run_subscriber_growth_monitor
        with patch("modules.competitor_monitor.resolve_and_cache", side_effect=fake_resolve):
            run_subscriber_growth_monitor(self._base_config())

        assert call_count == 1
        assert "interrotto" in capsys.readouterr().out

    def test_subscriber_monitor_stops_on_quota_at_yt_get(self, capsys):
        """Quota hit during yt_get for statistics — stops after first channel."""
        resolve_count = 0
        yt_count = 0

        def fake_resolve(handle):
            nonlocal resolve_count
            resolve_count += 1
            return f"UC{handle}"

        def fake_yt_get(endpoint, params):
            nonlocal yt_count
            yt_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.competitor_monitor import run_subscriber_growth_monitor
        with patch("modules.competitor_monitor.resolve_and_cache", side_effect=fake_resolve):
            with patch("modules.competitor_monitor.yt_get", side_effect=fake_yt_get):
                run_subscriber_growth_monitor(self._base_config())

        assert resolve_count == 1
        assert yt_count == 1
        assert "interrotto" in capsys.readouterr().out

    def test_seed_stops_on_quota(self, capsys):
        call_count = 0

        def fake_resolve(handle):
            nonlocal call_count
            call_count += 1
            raise YouTubeQuotaExceeded("quota")

        from modules.competitor_monitor import seed_startup_seen_videos
        with patch("modules.competitor_monitor.resolve_and_cache", side_effect=fake_resolve):
            seed_startup_seen_videos(self._base_config())

        assert call_count == 1
        assert "interrotto" in capsys.readouterr().out
