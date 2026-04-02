"""
Integration tests — /api/pinterest/* endpoints
"""
from modules.database import save_keyword_count, log_alert, get_connection


# ---------------------------------------------------------------------------
# GET /pinterest/trends
# ---------------------------------------------------------------------------

class TestPinterestTrends:
    def test_returns_200_empty(self, client):
        r = client.get("/api/pinterest/trends")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_trend_after_mentions(self, client):
        save_keyword_count("paranormal", "pinterest_apify", 15)
        r = client.get("/api/pinterest/trends")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_response_has_required_fields(self, client):
        save_keyword_count("haunted", "pinterest_apify", 10)
        r = client.get("/api/pinterest/trends")
        item = r.json()[0]
        assert "keyword" in item
        assert "saves" in item
        assert "growth_pct" in item
        assert "last_seen" in item
        assert "trend_type" in item

    def test_growth_pct_is_number(self, client):
        save_keyword_count("occult", "pinterest_apify", 20)
        r = client.get("/api/pinterest/trends")
        item = next(i for i in r.json() if i["keyword"] == "occult")
        assert isinstance(item["growth_pct"], (int, float))

    def test_trend_type_is_emerging_or_growing(self, client):
        save_keyword_count("horror", "pinterest_apify", 5)
        r = client.get("/api/pinterest/trends")
        for item in r.json():
            assert item["trend_type"] in ("emerging", "growing")

    def test_ordered_by_saves_desc(self, client):
        save_keyword_count("ghost", "pinterest_apify", 5)
        save_keyword_count("witchcraft", "pinterest_apify", 50)
        r = client.get("/api/pinterest/trends")
        saves = [i["saves"] for i in r.json()]
        assert saves == sorted(saves, reverse=True)

    def test_excludes_non_pinterest_sources(self, client):
        save_keyword_count("cryptid", "reddit_apify", 100)
        r = client.get("/api/pinterest/trends")
        keywords = [i["keyword"] for i in r.json()]
        # reddit_apify source should not appear in pinterest trends
        # (depends on no other pinterest data — just verify no crash and correct filtering)
        for kw in keywords:
            assert kw != "cryptid"  # unless it was also saved via pinterest source

    def test_hours_param_excludes_old_data(self, client):
        conn = get_connection()
        conn.execute(
            """INSERT INTO keyword_mentions (keyword, source, count, recorded_at)
               VALUES (?, ?, ?, datetime('now', '-200 hours'))""",
            ("ancient_rune", "pinterest_apify", 99),
        )
        conn.commit()
        conn.close()
        r = client.get("/api/pinterest/trends?hours=48")
        keywords = [i["keyword"] for i in r.json()]
        assert "ancient_rune" not in keywords

    def test_growth_pct_zero_when_single_data_point(self, client):
        """With only one data point, val_first == val_last → growth = 0."""
        save_keyword_count("sigil", "pinterest_apify", 10)
        r = client.get("/api/pinterest/trends")
        item = next((i for i in r.json() if i["keyword"] == "sigil"), None)
        assert item is not None
        assert item["growth_pct"] == 0.0


# ---------------------------------------------------------------------------
# GET /pinterest/alerts
# ---------------------------------------------------------------------------

class TestPinterestAlerts:
    def test_returns_200_empty(self, client):
        r = client.get("/api/pinterest/alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_pinterest_trend_alert(self, client):
        log_alert("pinterest_trend", "paranormal", "pinterest_apify", velocity_pct=120.0)
        r = client.get("/api/pinterest/alerts")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_excludes_non_pinterest_alert_types(self, client):
        log_alert("reddit_apify_trend", "ghost", "reddit_apify", velocity_pct=200.0)
        r = client.get("/api/pinterest/alerts")
        for item in r.json():
            assert item["alert_type"] in ("pinterest_trend", "pinterest_emerging", "pinterest_velocity")

    def test_response_has_required_fields(self, client):
        log_alert("pinterest_trend", "haunted", "pinterest_apify", velocity_pct=80.0)
        r = client.get("/api/pinterest/alerts")
        item = r.json()[0]
        assert "keyword" in item
        assert "alert_type" in item
        assert "velocity_pct" in item
        assert "sent_at" in item

    def test_hours_param_excludes_old_alerts(self, client):
        conn = get_connection()
        conn.execute(
            """INSERT INTO alerts_log (alert_type, keyword, source_platform, velocity_pct, extra_json, sent_at)
               VALUES (?, ?, ?, ?, ?, datetime('now', '-200 hours'))""",
            ("pinterest_trend", "old_kw", "pinterest_apify", 50.0, "{}"),
        )
        conn.commit()
        conn.close()
        r = client.get("/api/pinterest/alerts?hours=48")
        keywords = [i["keyword"] for i in r.json()]
        assert "old_kw" not in keywords

    def test_ordered_by_sent_at_desc(self, client):
        conn = get_connection()
        for i, kw in enumerate(["first", "second", "third"]):
            conn.execute(
                """INSERT INTO alerts_log (alert_type, keyword, source_platform, velocity_pct, extra_json, sent_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now', ? || ' minutes'))""",
                ("pinterest_trend", kw, "pinterest_apify", float(i * 10), "{}", f"-{10 - i}"),
            )
        conn.commit()
        conn.close()
        r = client.get("/api/pinterest/alerts")
        kws = [i["keyword"] for i in r.json()]
        assert kws[0] == "third"  # most recent first


# ---------------------------------------------------------------------------
# GET /pinterest/keyword-counts
# ---------------------------------------------------------------------------

class TestPinterestKeywordCounts:
    def test_returns_200_empty(self, client):
        r = client.get("/api/pinterest/keyword-counts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_counts_for_pinterest_source(self, client):
        save_keyword_count("paranormal", "pinterest_apify", 12)
        r = client.get("/api/pinterest/keyword-counts")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_excludes_non_pinterest_sources(self, client):
        save_keyword_count("ghost", "reddit_apify", 50)
        r = client.get("/api/pinterest/keyword-counts")
        keywords = [i["keyword"] for i in r.json()]
        assert "ghost" not in keywords

    def test_response_has_required_fields(self, client):
        save_keyword_count("occult", "pinterest_apify", 7)
        r = client.get("/api/pinterest/keyword-counts")
        item = r.json()[0]
        assert "keyword" in item
        assert "total" in item
        assert "last_seen" in item

    def test_total_is_integer(self, client):
        save_keyword_count("witchy", "pinterest_apify", 5)
        r = client.get("/api/pinterest/keyword-counts")
        item = next(i for i in r.json() if i["keyword"] == "witchy")
        assert isinstance(item["total"], int)

    def test_aggregates_multiple_counts(self, client):
        save_keyword_count("haunted", "pinterest_apify", 10)
        save_keyword_count("haunted", "pinterest_apify", 15)
        r = client.get("/api/pinterest/keyword-counts")
        item = next(i for i in r.json() if i["keyword"] == "haunted")
        assert item["total"] == 25

    def test_ordered_by_total_desc(self, client):
        save_keyword_count("low", "pinterest_apify", 3)
        save_keyword_count("high", "pinterest_apify", 100)
        r = client.get("/api/pinterest/keyword-counts")
        totals = [i["total"] for i in r.json()]
        assert totals == sorted(totals, reverse=True)
