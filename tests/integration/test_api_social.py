"""
Integration tests — /api/social/* endpoints
"""
from datetime import datetime, timezone

from modules.database import (
    upsert_pinned_profile,
    get_connection,
)


def _insert_profile(platform, username, avg_views=1000, followers=5000, is_pinned=0):
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO apify_profiles
            (platform, username, display_name, followers, avg_views, is_pinned, first_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (platform, username, username.title(), followers, avg_views, is_pinned,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def _insert_outperformer_video(platform, video_id, username, multiplier=3.5, views=50000):
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO apify_outperformer_videos
            (platform, video_id, username, title, views, url, multiplier, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (platform, video_id, username, f"Video {video_id}", views,
         f"https://example.com/{video_id}", multiplier,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# GET /social/profiles
# ---------------------------------------------------------------------------

class TestSocialProfiles:
    def test_returns_200_empty(self, client):
        r = client.get("/api/social/profiles")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_profiles_after_insert(self, client):
        _insert_profile("tiktok", "ghosthunter99")
        r = client.get("/api/social/profiles")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_filters_by_platform(self, client):
        _insert_profile("tiktok", "tiktokuser")
        _insert_profile("instagram", "iguser")
        r = client.get("/api/social/profiles?platform=tiktok")
        assert r.status_code == 200
        data = r.json()
        assert all(p["platform"] == "tiktok" for p in data)

    def test_field_normalization(self, client):
        """username→handle, display_name→name, last_analyzed→scraped_at."""
        _insert_profile("tiktok", "haunted_tales")
        r = client.get("/api/social/profiles")
        p = r.json()[0]
        assert "handle" in p
        assert "username" not in p
        assert "name" in p
        assert "display_name" not in p

    def test_ordered_by_avg_views_desc(self, client):
        _insert_profile("tiktok", "low_views", avg_views=100)
        _insert_profile("tiktok", "high_views", avg_views=50000)
        r = client.get("/api/social/profiles?platform=tiktok")
        data = r.json()
        assert data[0]["handle"] == "high_views"


# ---------------------------------------------------------------------------
# GET /social/watchlist
# ---------------------------------------------------------------------------

class TestSocialWatchlist:
    def test_returns_200_empty(self, client):
        r = client.get("/api/social/watchlist")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_pinned_profiles(self, client):
        upsert_pinned_profile("tiktok", "cryptid_hunter")
        r = client.get("/api/social/watchlist")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_filters_watchlist_by_platform(self, client):
        upsert_pinned_profile("tiktok", "tiktokstar")
        upsert_pinned_profile("instagram", "igstar")
        r = client.get("/api/social/watchlist?platform=instagram")
        data = r.json()
        assert len(data) == 1
        assert data[0]["platform"] == "instagram"

    def test_field_normalization(self, client):
        upsert_pinned_profile("tiktok", "darkfolklore")
        r = client.get("/api/social/watchlist")
        p = r.json()[0]
        assert "handle" in p
        assert "username" not in p


# ---------------------------------------------------------------------------
# POST /social/watchlist
# ---------------------------------------------------------------------------

class TestAddToWatchlist:
    def test_returns_ok_for_tiktok(self, client):
        r = client.post("/api/social/watchlist", json={"platform": "tiktok", "handle": "newuser"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_returns_ok_for_instagram(self, client):
        r = client.post("/api/social/watchlist", json={"platform": "instagram", "handle": "iguser"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_returns_400_for_invalid_platform(self, client):
        r = client.post("/api/social/watchlist", json={"platform": "youtube", "handle": "user"})
        assert r.status_code == 400

    def test_profile_appears_in_watchlist_after_add(self, client):
        client.post("/api/social/watchlist", json={"platform": "tiktok", "handle": "addeduser"})
        r = client.get("/api/social/watchlist?platform=tiktok")
        handles = [p["handle"] for p in r.json()]
        assert "addeduser" in handles

    def test_accepts_username_field_for_compat(self, client):
        """Frontend may send 'username' instead of 'handle'."""
        r = client.post("/api/social/watchlist", json={"platform": "tiktok", "username": "legacyuser"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /social/watchlist
# ---------------------------------------------------------------------------

class TestRemoveFromWatchlist:
    def test_returns_ok(self, client):
        r = client.request("DELETE", "/api/social/watchlist", json={"platform": "tiktok", "handle": "nobody"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_profile_gone_after_remove(self, client):
        upsert_pinned_profile("tiktok", "toremove")
        client.request("DELETE", "/api/social/watchlist", json={"platform": "tiktok", "handle": "toremove"})
        r = client.get("/api/social/watchlist?platform=tiktok")
        handles = [p["handle"] for p in r.json()]
        assert "toremove" not in handles


# ---------------------------------------------------------------------------
# GET /social/outperformer-videos
# ---------------------------------------------------------------------------

class TestOutperformerVideos:
    def test_returns_200_empty(self, client):
        r = client.get("/api/social/outperformer-videos")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_video_after_insert(self, client):
        _insert_outperformer_video("tiktok", "vid001", "ghostuser")
        r = client.get("/api/social/outperformer-videos")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_response_has_required_fields(self, client):
        _insert_outperformer_video("instagram", "vid002", "occultfeed", multiplier=4.0)
        r = client.get("/api/social/outperformer-videos")
        v = r.json()[0]
        assert "platform" in v
        assert "video_id" in v
        assert "username" in v
        assert "multiplier" in v

    def test_ordered_by_multiplier_desc(self, client):
        _insert_outperformer_video("tiktok", "low", "user1", multiplier=2.0)
        _insert_outperformer_video("tiktok", "high", "user2", multiplier=8.0)
        r = client.get("/api/social/outperformer-videos")
        data = r.json()
        assert data[0]["video_id"] == "high"

    def test_days_param_filters_old_videos(self, client):
        conn = get_connection()
        conn.execute(
            """INSERT OR IGNORE INTO apify_outperformer_videos
               (platform, video_id, username, title, views, url, multiplier, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '-60 days'))""",
            ("tiktok", "old_vid", "olduser", "Old Video", 1000, "https://ex.com", 3.0),
        )
        conn.commit()
        conn.close()
        r = client.get("/api/social/outperformer-videos?days=30")
        assert all(v["video_id"] != "old_vid" for v in r.json())
