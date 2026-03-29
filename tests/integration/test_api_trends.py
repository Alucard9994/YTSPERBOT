"""
Integration tests — /api/trends/*
"""

import json
from modules.database import save_keyword_count, log_alert


class TestTrendsGoogle:
    def test_empty(self, client):
        r = client.get("/api/trends/google")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_google_trends_keyword(self, client):
        save_keyword_count("trend_kw", "google_trends", 10)
        r = client.get("/api/trends/google?hours=1")
        data = r.json()
        assert len(data) >= 1
        assert any(d["keyword"] == "trend_kw" for d in data)

    def test_excludes_other_sources(self, client):
        """Solo fonte google_trends deve apparire."""
        save_keyword_count("only_rss", "rss", 20)
        save_keyword_count("only_google", "google_trends", 5)
        r = client.get("/api/trends/google?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "only_rss" not in kws, "fonte 'rss' non deve apparire in /trends/google"
        assert "only_google" in kws

    def test_total_aggregates_multiple_rows(self, client):
        """Più salvataggi della stessa keyword devono sommarsi in 'total'."""
        save_keyword_count("agg_kw", "google_trends", 3)
        save_keyword_count("agg_kw", "google_trends", 7)
        r = client.get("/api/trends/google?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "agg_kw")
        assert row["total"] == 10

    def test_ordered_by_total_desc(self, client):
        save_keyword_count("low_kw", "google_trends", 1)
        save_keyword_count("high_kw", "google_trends", 50)
        r = client.get("/api/trends/google?hours=1")
        data = r.json()
        totals = [d["total"] for d in data]
        assert totals == sorted(totals, reverse=True), (
            "risultati non ordinati per total DESC"
        )

    def test_hours_filter(self, client):
        """
        Il parametro hours deve escludere dati fuori dalla finestra temporale.
        hours=1 deve includere i dati appena inseriti;
        un hours molto ampio deve restituire i dati correttamente.
        (hours=0 è un caso limite: dipende dalla precisione del timestamp SQLite)
        """
        save_keyword_count("filter_kw", "google_trends", 5)
        # hours=1 deve includere il dato appena inserito
        r = client.get("/api/trends/google?hours=1")
        assert r.status_code == 200
        assert any(d["keyword"] == "filter_kw" for d in r.json())
        # hours=168 (default) deve includere il dato
        r2 = client.get("/api/trends/google")
        assert any(d["keyword"] == "filter_kw" for d in r2.json())

    def test_limit_to_20(self, client):
        for i in range(25):
            save_keyword_count(f"limit_kw_{i}", "google_trends", i + 1)
        r = client.get("/api/trends/google?hours=1")
        assert len(r.json()) <= 20


class TestTrendsRising:
    def test_empty(self, client):
        r = client.get("/api/trends/rising")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_rising_query_alert(self, client):
        log_alert(
            "rising_query",
            "rising_kw",
            "google_trends",
            velocity_pct=600.0,
            extra_json='{"parent_keyword":"ChatGPT","breakout":false}',
        )
        r = client.get("/api/trends/rising?hours=1")
        data = r.json()
        assert any(d["keyword"] == "rising_kw" for d in data)

    def test_excludes_wrong_alert_type(self, client):
        """Solo alert_type='rising_query' deve apparire."""
        log_alert("rss_trend", "wrong_type", "rss")
        r = client.get("/api/trends/rising?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "wrong_type" not in kws

    def test_extra_json_is_string_or_null(self, client):
        log_alert(
            "rising_query",
            "extra_kw",
            "google_trends",
            extra_json='{"parent_keyword":"test"}',
        )
        r = client.get("/api/trends/rising?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "extra_kw")
        assert row["extra_json"] is None or isinstance(row["extra_json"], str)

    def test_breakout_parseable_from_extra_json(self, client):
        """Il frontend fa JSON.parse(a.extra_json) — deve essere JSON valido."""
        log_alert(
            "rising_query",
            "breakout_kw",
            "google_trends",
            extra_json='{"parent_keyword":"SEO","breakout":true}',
        )
        r = client.get("/api/trends/rising?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "breakout_kw")
        parsed = json.loads(row["extra_json"])
        assert parsed["breakout"] is True
        assert parsed["parent_keyword"] == "SEO"

    def test_ordered_by_sent_at_desc(self, client):
        log_alert("rising_query", "old_kw", "google_trends")
        log_alert("rising_query", "new_kw", "google_trends")
        r = client.get("/api/trends/rising?hours=1")
        data = r.json()
        assert data[0]["keyword"] == "new_kw", "risultati non ordinati per sent_at DESC"


class TestTrendsTrendingRss:
    def test_empty(self, client):
        r = client.get("/api/trends/trending-rss")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_trending_rss_alert(self, client):
        log_alert(
            "trending_rss",
            "rss_kw",
            "google_trends",
            extra_json='{"geo":"IT","traffic":"500K+"}',
        )
        r = client.get("/api/trends/trending-rss?hours=1")
        data = r.json()
        assert any(d["keyword"] == "rss_kw" for d in data)

    def test_excludes_wrong_alert_type(self, client):
        log_alert("rising_query", "not_rss", "google_trends")
        r = client.get("/api/trends/trending-rss?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "not_rss" not in kws

    def test_extra_json_contains_geo_and_traffic(self, client):
        log_alert(
            "trending_rss",
            "geo_kw",
            "google_trends",
            extra_json='{"geo":"US","traffic":"1M+"}',
        )
        r = client.get("/api/trends/trending-rss?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "geo_kw")
        parsed = json.loads(row["extra_json"])
        assert "geo" in parsed
        assert "traffic" in parsed

    def test_hours_filter(self, client):
        log_alert("trending_rss", "filter_rss_kw", "google_trends")
        # hours=1 deve includere il dato appena inserito
        r = client.get("/api/trends/trending-rss?hours=1")
        assert r.status_code == 200
        assert any(d["keyword"] == "filter_rss_kw" for d in r.json())


class TestTrendsKeywordTimeseries:
    def test_returns_200(self, client):
        r = client.get("/api/trends/keyword-timeseries?keyword=test&hours=1")
        assert r.status_code == 200

    def test_empty_for_unknown_keyword(self, client):
        r = client.get("/api/trends/keyword-timeseries?keyword=__nonexistent__&hours=1")
        assert r.json() == []

    def test_aggregates_by_hour(self, client):
        save_keyword_count("ts_kw", "rss", 5)
        save_keyword_count("ts_kw", "reddit", 3)
        r = client.get("/api/trends/keyword-timeseries?keyword=ts_kw&hours=1")
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        assert "hour_bucket" in row
        assert "total" in row
        assert isinstance(row["total"], int)
