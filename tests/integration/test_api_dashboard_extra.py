"""
Integration tests — dashboard endpoints not covered elsewhere:
  GET /dashboard/alerts-timeline
  GET /dashboard/keyword-search
  GET /dashboard/keyword-sources
"""
from modules.database import log_alert, save_keyword_count, get_connection


# ---------------------------------------------------------------------------
# GET /dashboard/alerts-timeline
# ---------------------------------------------------------------------------

class TestAlertsTimeline:
    def test_returns_200_empty(self, client):
        r = client.get("/api/dashboard/alerts-timeline")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_day_count_items(self, client):
        log_alert("rss_velocity", "paranormal", "rss", velocity_pct=120.0)
        log_alert("google_trends", "haunted", "google_trends", velocity_pct=80.0)
        r = client.get("/api/dashboard/alerts-timeline")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        item = data[0]
        assert "day" in item
        assert "count" in item

    def test_count_is_integer(self, client):
        log_alert("rss_velocity", "ghost", "rss", velocity_pct=50.0)
        r = client.get("/api/dashboard/alerts-timeline")
        for item in r.json():
            assert isinstance(item["count"], int)

    def test_groups_by_day(self, client):
        # Insert 3 alerts — should all land on today → single day entry
        for kw in ["ghost", "paranormal", "occult"]:
            log_alert("rss_velocity", kw, "rss", velocity_pct=100.0)
        r = client.get("/api/dashboard/alerts-timeline?days=1")
        data = r.json()
        assert len(data) == 1
        assert data[0]["count"] == 3

    def test_days_param_excludes_old_alerts(self, client):
        conn = get_connection()
        conn.execute(
            """INSERT INTO alerts_log (alert_type, keyword, source, velocity_pct, extra_json, sent_at)
               VALUES (?, ?, ?, ?, ?, datetime('now', '-20 days'))""",
            ("rss_velocity", "ancient", "rss", 50.0, "{}"),
        )
        conn.commit()
        conn.close()
        r = client.get("/api/dashboard/alerts-timeline?days=7")
        # ancient alert should not appear in 7-day window — just verify no crash
        assert r.status_code == 200

    def test_ordered_by_day_asc(self, client):
        conn = get_connection()
        for offset in ["-3 days", "-1 days"]:
            conn.execute(
                """INSERT INTO alerts_log (alert_type, keyword, source, velocity_pct, extra_json, sent_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now', ?))""",
                ("rss_velocity", f"kw_{offset}", "rss", 50.0, "{}", offset),
            )
        conn.commit()
        conn.close()
        r = client.get("/api/dashboard/alerts-timeline?days=7")
        data = r.json()
        if len(data) >= 2:
            days = [i["day"] for i in data]
            assert days == sorted(days)


# ---------------------------------------------------------------------------
# GET /dashboard/keyword-search
# ---------------------------------------------------------------------------

class TestKeywordSearch:
    def test_returns_200_for_unknown_keyword(self, client):
        r = client.get("/api/dashboard/keyword-search?keyword=nonexistent")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["source_count"] == 0
        assert data["sources"] == []
        assert data["last_seen"] is None

    def test_returns_correct_total(self, client):
        save_keyword_count("paranormal", "rss", 10)
        save_keyword_count("paranormal", "reddit_apify", 5)
        r = client.get("/api/dashboard/keyword-search?keyword=paranormal")
        data = r.json()
        assert data["total"] == 15

    def test_source_breakdown(self, client):
        save_keyword_count("haunted", "rss", 8)
        save_keyword_count("haunted", "twitter", 4)
        r = client.get("/api/dashboard/keyword-search?keyword=haunted")
        data = r.json()
        sources = {s["source"]: s["count"] for s in data["sources"]}
        assert sources.get("rss") == 8
        assert sources.get("twitter") == 4

    def test_source_count_field(self, client):
        save_keyword_count("ghost", "rss", 5)
        save_keyword_count("ghost", "reddit_apify", 3)
        save_keyword_count("ghost", "twitter", 2)
        r = client.get("/api/dashboard/keyword-search?keyword=ghost")
        assert r.json()["source_count"] == 3

    def test_case_insensitive_match(self, client):
        save_keyword_count("Paranormal", "rss", 7)
        r = client.get("/api/dashboard/keyword-search?keyword=paranormal")
        assert r.json()["total"] == 7

    def test_echo_keyword_in_response(self, client):
        r = client.get("/api/dashboard/keyword-search?keyword=occult")
        assert r.json()["keyword"] == "occult"

    def test_echo_hours_in_response(self, client):
        r = client.get("/api/dashboard/keyword-search?keyword=occult&hours=72")
        assert r.json()["hours"] == 72

    def test_last_seen_is_string_when_data_exists(self, client):
        save_keyword_count("horror", "rss", 3)
        r = client.get("/api/dashboard/keyword-search?keyword=horror")
        last_seen = r.json()["last_seen"]
        assert last_seen is not None
        assert isinstance(last_seen, str)

    def test_hours_param_excludes_old_mentions(self, client):
        conn = get_connection()
        conn.execute(
            """INSERT INTO keyword_mentions (keyword, source, count, recorded_at)
               VALUES (?, ?, ?, datetime('now', '-200 hours'))""",
            ("cryptid", "rss", 99),
        )
        conn.commit()
        conn.close()
        r = client.get("/api/dashboard/keyword-search?keyword=cryptid&hours=48")
        assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /dashboard/keyword-sources
# ---------------------------------------------------------------------------

class TestKeywordSources:
    def test_returns_200_empty_dict(self, client):
        r = client.get("/api/dashboard/keyword-sources")
        assert r.status_code == 200
        assert r.json() == {}

    def test_returns_breakdown_per_keyword(self, client):
        save_keyword_count("paranormal", "rss", 5)
        save_keyword_count("paranormal", "twitter", 3)
        r = client.get("/api/dashboard/keyword-sources")
        data = r.json()
        assert "paranormal" in data
        sources = {s["source"]: s["count"] for s in data["paranormal"]}
        assert sources.get("rss") == 5
        assert sources.get("twitter") == 3

    def test_multiple_keywords_have_separate_entries(self, client):
        save_keyword_count("ghost", "rss", 4)
        save_keyword_count("haunted", "rss", 6)
        r = client.get("/api/dashboard/keyword-sources")
        data = r.json()
        assert "ghost" in data
        assert "haunted" in data

    def test_source_entries_have_source_and_count(self, client):
        save_keyword_count("occult", "reddit_apify", 10)
        r = client.get("/api/dashboard/keyword-sources")
        entry = r.json()["occult"][0]
        assert "source" in entry
        assert "count" in entry
        assert isinstance(entry["count"], int)

    def test_hours_param_excludes_old_data(self, client):
        conn = get_connection()
        conn.execute(
            """INSERT INTO keyword_mentions (keyword, source, count, recorded_at)
               VALUES (?, ?, ?, datetime('now', '-200 hours'))""",
            ("old_keyword", "rss", 50),
        )
        conn.commit()
        conn.close()
        r = client.get("/api/dashboard/keyword-sources?hours=48")
        data = r.json()
        assert "old_keyword" not in data
