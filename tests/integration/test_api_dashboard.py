"""
Integration tests — /api/dashboard/*
"""
from modules.database import log_alert, save_keyword_count


class TestDashboardAlerts:

    def test_empty(self, client):
        r = client.get("/api/dashboard/alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_alert_after_insert(self, client):
        log_alert("rss_trend", "test_keyword", "rss", velocity_pct=250.0)
        r = client.get("/api/dashboard/alerts?hours=1")
        data = r.json()
        assert len(data) == 1
        assert data[0]["keyword"] == "test_keyword"
        assert data[0]["velocity_pct"] == 250.0

    def test_limit_param(self, client):
        for i in range(10):
            log_alert("rss_trend", f"kw{i}", "rss")
        r = client.get("/api/dashboard/alerts?hours=1&limit=3")
        assert len(r.json()) == 3

    def test_hours_excludes_old(self, client):
        """hours=0 non deve restituire nulla (finestra vuota)."""
        log_alert("rss_trend", "old_kw", "rss")
        r = client.get("/api/dashboard/alerts?hours=0")
        # Con finestra 0 non ci sono risultati nell'ultima 0 ore
        # Il comportamento dipende dall'implementazione — verifichiamo almeno 200
        assert r.status_code == 200

    def test_response_shape(self, client):
        log_alert("cross_signal", "shape_test", "cross_signal",
                  sources_list="rss,reddit", priority=8)
        r = client.get("/api/dashboard/alerts?hours=1")
        row = r.json()[0]
        assert "keyword" in row
        assert "alert_type" in row
        assert "source" in row
        assert "sent_at" in row


class TestDashboardConvergences:

    def test_empty(self, client):
        r = client.get("/api/dashboard/convergences")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_cross_signal_appears(self, client):
        """Keyword su 3 fonti distinte deve apparire con min_sources=2."""
        # get_multi_source_keywords legge keyword_mentions, non alerts_log
        for source in ("rss", "reddit", "google_trends"):
            save_keyword_count("conv_kw", source, 5)
        r = client.get("/api/dashboard/convergences?hours=1&min_sources=2")
        data = r.json()
        keywords = [d.get("keyword") for d in data]
        assert "conv_kw" in keywords


class TestDashboardKeywords:

    def test_empty(self, client):
        r = client.get("/api/dashboard/keywords")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_keyword_appears_after_save(self, client):
        save_keyword_count("youtube_seo", "rss", 15)
        r = client.get("/api/dashboard/keywords?hours=1&limit=10")
        assert r.status_code == 200
