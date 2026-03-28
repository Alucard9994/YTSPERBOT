"""
Integration tests — /api/youtube/*
"""
from modules.database import (
    log_youtube_outperformer,
    log_competitor_video,
    save_keyword_count,
    get_connection,
)


def _log_video(video_id, **kwargs):
    """Helper: inserisce un outperformer con valori di default."""
    defaults = dict(
        title="T", channel_name="C", channel_id="UC0",
        subscribers=0, views=0, avg_views=0.0,
        multiplier_avg=0.0, multiplier_subs=0.0,
        video_type="long", duration_seconds=0, published_at=None,
    )
    defaults.update(kwargs)
    log_youtube_outperformer(video_id=video_id, **defaults)


class TestOutperformer:

    def test_empty(self, client):
        r = client.get("/api/youtube/outperformer")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_video(self, client):
        _log_video("vid1", title="Test Title", channel_name="Chan",
                   channel_id="UC1", subscribers=50_000, views=200_000,
                   avg_views=10_000.0, multiplier_avg=20.0, multiplier_subs=4.0,
                   video_type="long", duration_seconds=720)
        r = client.get("/api/youtube/outperformer?days=365")
        data = r.json()
        assert len(data) == 1
        assert data[0]["video_id"] == "vid1"
        assert data[0]["multiplier_avg"] == 20.0

    def test_limit_param(self, client):
        for i in range(5):
            _log_video(f"v{i}")
        r = client.get("/api/youtube/outperformer?days=365&limit=3")
        assert len(r.json()) == 3

    def test_response_has_required_fields(self, client):
        _log_video("vf1")
        r = client.get("/api/youtube/outperformer?days=365")
        row = r.json()[0]
        for field in ["video_id", "title", "channel_name", "detected_at"]:
            assert field in row


class TestCompetitorVideos:

    def test_empty(self, client):
        r = client.get("/api/youtube/competitor-videos")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_video(self, client):
        log_competitor_video(
            video_id="cv1", title="Competitor Title",
            channel_name="CompChan", channel_id="UC99", matched_keyword="horror",
        )
        r = client.get("/api/youtube/competitor-videos?hours=8760")
        data = r.json()
        assert len(data) == 1
        assert data[0]["matched_keyword"] == "horror"


class TestCompetitors:

    def test_empty(self, client):
        r = client.get("/api/youtube/competitors")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_returns_competitor_with_growth(self, client):
        conn = get_connection()
        conn.execute("""
            INSERT INTO channel_subscribers_history
              (channel_id, channel_name, subscribers, recorded_at)
            VALUES
              ('UC_A', 'Channel A', 90000, datetime('now', '-5 days')),
              ('UC_A', 'Channel A', 100000, datetime('now'))
        """)
        conn.commit()
        conn.close()

        r = client.get("/api/youtube/competitors")
        data = r.json()
        chan = next((d for d in data if d["channel_id"] == "UC_A"), None)
        assert chan is not None
        assert chan["growth_pct"] == pytest.approx(11.1, abs=0.5)

    def test_growth_pct_field_present(self, client):
        conn = get_connection()
        conn.execute("""
            INSERT INTO channel_subscribers_history
              (channel_id, channel_name, subscribers, recorded_at)
            VALUES ('UC_B', 'Channel B', 50000, datetime('now'))
        """)
        conn.commit()
        conn.close()
        r = client.get("/api/youtube/competitors")
        row = next(d for d in r.json() if d["channel_id"] == "UC_B")
        assert "growth_pct" in row


class TestCommentKeywords:

    def test_empty(self, client):
        r = client.get("/api/youtube/comments/keywords")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_returns_comment_keyword(self, client):
        save_keyword_count("AI tools", "yt_comments", 12)
        r = client.get("/api/youtube/comments/keywords?hours=1")
        keywords = [d["keyword"] for d in r.json()]
        assert "AI tools" in keywords


import pytest
