"""
Integration tests — /api/news/*
"""

from modules.database import save_keyword_count, log_alert


class TestNewsAlerts:
    def test_empty(self, client):
        r = client.get("/api/news/alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_news_trend_alert(self, client):
        log_alert("news_trend", "breaking_news", "news", velocity_pct=200.0)
        r = client.get("/api/news/alerts?hours=1")
        data = r.json()
        assert len(data) >= 1
        assert any(d["keyword"] == "breaking_news" for d in data)

    def test_excludes_wrong_alert_type(self, client):
        """Solo alert_type='news_trend' deve apparire."""
        log_alert("rss_trend", "rss_type", "rss")
        log_alert("twitter_trend", "twit_type", "twitter")
        r = client.get("/api/news/alerts?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "rss_type" not in kws
        assert "twit_type" not in kws

    def test_velocity_pct_value(self, client):
        log_alert("news_trend", "vel_news", "news", velocity_pct=350.5)
        r = client.get("/api/news/alerts?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "vel_news")
        assert row["velocity_pct"] == pytest_approx_or_equal(350.5)

    def test_hours_filter(self, client):
        log_alert("news_trend", "old_news", "news")
        # hours=1 deve includere il dato appena inserito
        r = client.get("/api/news/alerts?hours=1")
        assert r.status_code == 200
        assert any(d["keyword"] == "old_news" for d in r.json())

    def test_limit_to_30(self, client):
        for i in range(35):
            log_alert("news_trend", f"news_lim_{i}", "news")
        r = client.get("/api/news/alerts?hours=1")
        assert len(r.json()) <= 30

    def test_ordered_by_sent_at_desc(self, client):
        log_alert("news_trend", "old_news2", "news")
        log_alert("news_trend", "new_news2", "news")
        r = client.get("/api/news/alerts?hours=1")
        data = r.json()
        assert data[0]["keyword"] == "new_news2"


class TestNewsKeywordCounts:
    def test_empty(self, client):
        r = client.get("/api/news/keyword-counts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_news_source_keyword(self, client):
        save_keyword_count("news_count_kw", "news", 12)
        r = client.get("/api/news/keyword-counts?hours=1")
        data = r.json()
        assert any(d["keyword"] == "news_count_kw" for d in data)

    def test_excludes_non_news_sources(self, client):
        """Solo source='news' deve apparire."""
        save_keyword_count("only_rss2", "rss", 20)
        save_keyword_count("only_news", "news", 5)
        r = client.get("/api/news/keyword-counts?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "only_rss2" not in kws
        assert "only_news" in kws

    def test_total_aggregates(self, client):
        save_keyword_count("news_agg", "news", 6)
        save_keyword_count("news_agg", "news", 4)
        r = client.get("/api/news/keyword-counts?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "news_agg")
        assert row["total"] == 10

    def test_ordered_by_total_desc(self, client):
        save_keyword_count("news_low", "news", 1)
        save_keyword_count("news_high", "news", 100)
        r = client.get("/api/news/keyword-counts?hours=1")
        data = r.json()
        totals = [d["total"] for d in data]
        assert totals == sorted(totals, reverse=True)

    def test_limit_to_20(self, client):
        for i in range(25):
            save_keyword_count(f"news_lim_{i}", "news", i + 1)
        r = client.get("/api/news/keyword-counts?hours=1")
        assert len(r.json()) <= 20


class TestNewsTwitterCounts:
    def test_empty(self, client):
        r = client.get("/api/news/twitter-counts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_twitter_keyword(self, client):
        save_keyword_count("twit_cnt_kw", "twitter", 8)
        r = client.get("/api/news/twitter-counts?hours=1")
        data = r.json()
        assert any(d["keyword"] == "twit_cnt_kw" for d in data)

    def test_returns_twitter_apify_keyword(self, client):
        """Menzioni da 'twitter_apify' devono essere incluse."""
        save_keyword_count("apify_cnt_kw", "twitter_apify", 7)
        r = client.get("/api/news/twitter-counts?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "apify_cnt_kw" in kws

    def test_excludes_non_twitter_sources(self, client):
        save_keyword_count("reddit_excl", "reddit", 50)
        r = client.get("/api/news/twitter-counts?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "reddit_excl" not in kws

    def test_total_aggregates_twitter_and_apify(self, client):
        """twitter + twitter_apify devono sommarsi per la stessa keyword."""
        save_keyword_count("combined_kw", "twitter", 4)
        save_keyword_count("combined_kw", "twitter_apify", 6)
        r = client.get("/api/news/twitter-counts?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "combined_kw")
        assert row["total"] == 10

    def test_ordered_by_total_desc(self, client):
        save_keyword_count("twit_low", "twitter", 1)
        save_keyword_count("twit_high", "twitter", 80)
        r = client.get("/api/news/twitter-counts?hours=1")
        data = r.json()
        totals = [d["total"] for d in data]
        assert totals == sorted(totals, reverse=True)


class TestNewsTwitterAlerts:
    def test_empty(self, client):
        r = client.get("/api/news/twitter-alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_twitter_trend_alert(self, client):
        log_alert("twitter_trend", "twit_alert", "twitter", velocity_pct=500.0)
        r = client.get("/api/news/twitter-alerts?hours=1")
        data = r.json()
        assert any(d["keyword"] == "twit_alert" for d in data)

    def test_excludes_wrong_alert_type(self, client):
        log_alert("news_trend", "news_type", "news")
        r = client.get("/api/news/twitter-alerts?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "news_type" not in kws

    def test_hours_filter(self, client):
        log_alert("twitter_trend", "twit_filter", "twitter")
        # hours=1 deve includere il dato appena inserito
        r = client.get("/api/news/twitter-alerts?hours=1")
        assert r.status_code == 200
        assert any(d["keyword"] == "twit_filter" for d in r.json())

    def test_limit_to_30(self, client):
        for i in range(35):
            log_alert("twitter_trend", f"twit_lim_{i}", "twitter")
        r = client.get("/api/news/twitter-alerts?hours=1")
        assert len(r.json()) <= 30


# helper per compatibilità con pytest (evita import pytest.approx in module scope)
def pytest_approx_or_equal(val):
    try:
        import pytest

        return pytest.approx(val, rel=1e-3)
    except Exception:
        return val
