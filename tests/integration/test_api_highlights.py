"""
Integration tests — GET /api/dashboard/highlights
"""

from modules.database import (
    log_alert,
    log_youtube_outperformer,
    get_connection,
)
from datetime import datetime, timezone


def _insert_social_video(platform, video_id, username, multiplier, views=10000):
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO apify_outperformer_videos
           (platform, video_id, username, title, views, url, multiplier, detected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (platform, video_id, username, f"Test {video_id}",
         views, f"https://example.com/{video_id}", multiplier,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def _insert_comment(video_id, text, likes, video_title="Test Video"):
    conn = get_connection()
    conn.execute(
        """INSERT INTO youtube_comment_intel
           (video_id, video_title, channel_name, comment_text, likes, detected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (video_id, video_title, "TestChannel", text, likes,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


class TestHighlightsEndpoint:
    def test_returns_200_empty_db(self, client):
        r = client.get("/api/dashboard/highlights")
        assert r.status_code == 200

    def test_response_shape(self, client):
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert "youtube_top" in data
        assert "social_top" in data
        assert "comments_top" in data
        assert "reddit_top" in data
        assert "twitter_top" in data
        assert "pinterest_top" in data
        assert "news_top" in data

    def test_empty_lists_when_no_data(self, client):
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert data["youtube_top"] == []
        assert data["social_top"] == []
        assert data["comments_top"] == []
        assert data["reddit_top"] is None
        assert data["twitter_top"] is None
        assert data["pinterest_top"] is None
        assert data["news_top"] is None

    def test_youtube_top_ordered_by_multiplier(self, client):
        log_youtube_outperformer(
            video_id="yt1", title="Low mult", channel_name="C", channel_id="UC1",
            subscribers=0, views=1000, avg_views=500.0, multiplier_avg=2.0,
            multiplier_subs=0.0, video_type="long", duration_seconds=300, published_at=None,
        )
        log_youtube_outperformer(
            video_id="yt2", title="High mult", channel_name="C", channel_id="UC2",
            subscribers=0, views=5000, avg_views=500.0, multiplier_avg=10.0,
            multiplier_subs=0.0, video_type="long", duration_seconds=300, published_at=None,
        )
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert len(data["youtube_top"]) == 2
        # Ordinato per multiplier DESC → primo deve avere multiplier più alto
        assert data["youtube_top"][0]["multiplier_avg"] >= data["youtube_top"][1]["multiplier_avg"]

    def test_youtube_top_max_3(self, client):
        for i in range(5):
            log_youtube_outperformer(
                video_id=f"ytmax{i}", title=f"Video {i}", channel_name="C",
                channel_id=f"UC{i}", subscribers=0, views=1000,
                avg_views=100.0, multiplier_avg=float(i),
                multiplier_subs=0.0, video_type="long",
                duration_seconds=300, published_at=None,
            )
        r = client.get("/api/dashboard/highlights")
        assert len(r.json()["youtube_top"]) <= 3

    def test_social_top_ordered_by_multiplier(self, client):
        _insert_social_video("tiktok", "tt1", "user1", multiplier=3.0)
        _insert_social_video("instagram", "ig1", "user2", multiplier=7.5)
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert len(data["social_top"]) == 2
        assert data["social_top"][0]["multiplier"] >= data["social_top"][1]["multiplier"]

    def test_social_top_max_3(self, client):
        for i in range(6):
            _insert_social_video("tiktok", f"tt{i}", f"u{i}", multiplier=float(i))
        r = client.get("/api/dashboard/highlights")
        assert len(r.json()["social_top"]) <= 3

    def test_comments_top_ordered_by_likes(self, client):
        _insert_comment("v1", "Commento con pochi like", likes=5)
        _insert_comment("v2", "Commento con molti like", likes=500)
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert len(data["comments_top"]) == 2
        assert data["comments_top"][0]["likes"] >= data["comments_top"][1]["likes"]

    def test_comments_top_max_3(self, client):
        for i in range(5):
            _insert_comment(f"vc{i}", f"Commento {i}", likes=i * 10)
        r = client.get("/api/dashboard/highlights")
        assert len(r.json()["comments_top"]) <= 3

    def test_reddit_top_picks_highest_velocity(self, client):
        log_alert("reddit_trend", "kw_low",  "reddit", velocity_pct=100.0)
        log_alert("reddit_trend", "kw_high", "reddit", velocity_pct=800.0)
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert data["reddit_top"] is not None
        assert data["reddit_top"]["keyword"] == "kw_high"
        assert data["reddit_top"]["velocity_pct"] == 800.0

    def test_twitter_top_picks_highest_velocity(self, client):
        log_alert("twitter_trend", "tw_low",  "twitter", velocity_pct=200.0)
        log_alert("twitter_trend", "tw_best", "twitter_apify", velocity_pct=950.0)
        r = client.get("/api/dashboard/highlights")
        data = r.json()
        assert data["twitter_top"] is not None
        assert data["twitter_top"]["keyword"] == "tw_best"

    def test_pinterest_top(self, client):
        log_alert("pinterest_velocity", "pins_kw", "pinterest_IT", velocity_pct=350.0)
        r = client.get("/api/dashboard/highlights")
        assert r.json()["pinterest_top"]["keyword"] == "pins_kw"

    def test_news_top(self, client):
        log_alert("news_trend", "news_kw", "news", velocity_pct=220.0)
        r = client.get("/api/dashboard/highlights")
        assert r.json()["news_top"]["keyword"] == "news_kw"

    def test_signals_null_when_only_old_data(self, client):
        """Alert più vecchi di 7 giorni non devono apparire negli highlights."""
        conn = get_connection()
        conn.execute(
            """INSERT INTO alerts_log (alert_type, keyword, source, velocity_pct, sent_at)
               VALUES ('reddit_trend', 'old_kw', 'reddit', 999.0,
               datetime('now', '-8 days'))"""
        )
        conn.commit()
        conn.close()
        r = client.get("/api/dashboard/highlights")
        assert r.json()["reddit_top"] is None

    def test_comment_fields_present(self, client):
        _insert_comment("v_shape", "Test commento per shape", likes=42,
                        video_title="My Video Title")
        r = client.get("/api/dashboard/highlights")
        c = r.json()["comments_top"][0]
        assert "comment_text" in c
        assert "likes" in c
        assert "video_title" in c

    def test_youtube_fields_present(self, client):
        log_youtube_outperformer(
            video_id="yt_shape", title="Shape Test", channel_name="Chan",
            channel_id="UC_s", subscribers=10000, views=50000, avg_views=5000.0,
            multiplier_avg=10.0, multiplier_subs=5.0, video_type="short",
            duration_seconds=60, published_at="2024-01-01T10:00:00",
        )
        r = client.get("/api/dashboard/highlights")
        v = r.json()["youtube_top"][0]
        assert "video_id" in v
        assert "title" in v
        assert "channel_name" in v
        assert "multiplier_avg" in v
        assert "views" in v
