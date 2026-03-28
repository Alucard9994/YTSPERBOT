"""
Unit tests — funzioni database.py
Testano le funzioni di persistenza con il DB di test (SQLite reale, non mock).
"""
import pytest
from datetime import datetime, timezone, timedelta
from modules.database import (
    log_alert,
    get_alerts_log,
    log_youtube_outperformer,
    get_youtube_outperformer_log,
    log_competitor_video,
    get_competitor_video_log,
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
)


class TestLogAlert:

    def test_insert_and_retrieve(self):
        log_alert("rss_trend", "AI video", "rss", velocity_pct=120.0)
        rows = get_alerts_log(hours=1)
        assert len(rows) == 1
        row = rows[0]
        assert row["keyword"] == "AI video"
        assert row["alert_type"] == "rss_trend"
        assert row["source"] == "rss"
        assert abs(row["velocity_pct"] - 120.0) < 0.01

    def test_velocity_none_stored_as_null(self):
        log_alert("cross_signal", "paranormal", "cross_signal")
        rows = get_alerts_log(hours=1)
        assert rows[0]["velocity_pct"] is None

    def test_priority_default(self):
        log_alert("google_trends", "horror", "google_trends")
        rows = get_alerts_log(hours=1)
        assert rows[0]["priority"] == 5

    def test_priority_custom(self):
        log_alert("cross_signal", "keyword", "cross_signal", priority=9)
        rows = get_alerts_log(hours=1)
        assert rows[0]["priority"] == 9

    def test_hours_filter(self):
        """Alert dentro la finestra vengono restituiti; fuori no."""
        log_alert("rss_trend", "inside", "rss")
        rows = get_alerts_log(hours=1)
        assert any(r["keyword"] == "inside" for r in rows)

    def test_limit(self):
        for i in range(5):
            log_alert("rss_trend", f"kw{i}", "rss")
        rows = get_alerts_log(hours=1, limit=3)
        assert len(rows) == 3

    def test_multiple_alerts_ordered_desc(self):
        log_alert("rss_trend", "first", "rss")
        log_alert("rss_trend", "second", "rss")
        rows = get_alerts_log(hours=1)
        # più recente prima
        assert rows[0]["keyword"] == "second"


class TestLogYoutubeOutperformer:

    def test_insert_and_retrieve(self):
        log_youtube_outperformer(
            video_id="abc123",
            title="Test video",
            channel_name="Test Channel",
            channel_id="UC123",
            subscribers=100_000,
            views=500_000,
            avg_views=50_000.0,
            multiplier_avg=10.0,
            multiplier_subs=5.0,
            video_type="long",
            duration_seconds=600,
            published_at="2024-01-01T10:00:00",
        )
        rows = get_youtube_outperformer_log(days=365)
        assert len(rows) == 1
        r = rows[0]
        assert r["video_id"] == "abc123"
        assert r["title"] == "Test video"
        assert r["multiplier_avg"] == pytest.approx(10.0)
        assert r["video_type"] == "long"

    def _make(self, video_id, **kwargs):
        defaults = dict(
            title="T", channel_name="C", channel_id="UC0",
            subscribers=0, views=0, avg_views=0.0,
            multiplier_avg=0.0, multiplier_subs=0.0,
            video_type="long", duration_seconds=0, published_at=None,
        )
        defaults.update(kwargs)
        log_youtube_outperformer(video_id=video_id, **defaults)

    def test_duplicate_video_id_ignored(self):
        """UNIQUE constraint su video_id: il secondo insert non solleva eccezione."""
        self._make("dup1")
        self._make("dup1")
        rows = get_youtube_outperformer_log(days=365)
        assert len(rows) == 1

    def test_video_type_short(self):
        self._make("s1", video_type="short")
        rows = get_youtube_outperformer_log(days=365)
        assert rows[0]["video_type"] == "short"


class TestLogCompetitorVideo:

    def test_insert_and_retrieve(self):
        log_competitor_video(
            video_id="comp1",
            title="Competitor video",
            channel_name="CompChan",
            channel_id="UC999",
            matched_keyword="horror",
            published_at="2024-01-01T08:00:00",
        )
        rows = get_competitor_video_log(hours=24 * 365)
        assert len(rows) == 1
        assert rows[0]["matched_keyword"] == "horror"

    def test_duplicate_ignored(self):
        log_competitor_video(video_id="cv1", title="A", channel_name="C", channel_id="UC0")
        log_competitor_video(video_id="cv1", title="B", channel_name="C", channel_id="UC0")
        rows = get_competitor_video_log(hours=24 * 365)
        assert len(rows) == 1


class TestKeywordMentions:

    def test_save_and_retrieve(self):
        save_keyword_count("paranormal", "rss", 10)
        rows = get_keyword_counts("paranormal", "rss", 1)
        assert len(rows) >= 1
        assert rows[0]["count"] == 10

    def test_multiple_sources_independent(self):
        save_keyword_count("horror", "rss", 5)
        save_keyword_count("horror", "reddit", 8)
        rss = get_keyword_counts("horror", "rss", 1)
        reddit = get_keyword_counts("horror", "reddit", 1)
        assert rss[0]["count"] == 5
        assert reddit[0]["count"] == 8


class TestAlertDeduplication:

    def test_not_sent_recently_initially(self):
        assert was_alert_sent_recently("new_keyword", "rss_trend", hours=6) is False

    def test_sent_recently_after_mark(self):
        mark_alert_sent("my_keyword", "rss_trend")
        assert was_alert_sent_recently("my_keyword", "rss_trend", hours=6) is True

    def test_different_type_not_deduplicated(self):
        mark_alert_sent("shared_kw", "rss_trend")
        # tipo diverso → non considerato come già inviato
        assert was_alert_sent_recently("shared_kw", "google_trends", hours=6) is False

    def test_different_keyword_not_deduplicated(self):
        mark_alert_sent("kw_A", "rss_trend")
        assert was_alert_sent_recently("kw_B", "rss_trend", hours=6) is False
