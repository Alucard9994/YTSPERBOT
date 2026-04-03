"""Integration tests for api/routes/reddit.py"""
from modules.database import save_reddit_post, log_alert


class TestRedditPosts:
    def test_empty_returns_list(self, client):
        r = client.get("/api/reddit/posts")
        assert r.status_code == 200
        assert r.json() == []

    def test_insert_and_retrieve(self, client):
        save_reddit_post("p1", "paranormal", "Ghost spotted", "https://r.com/1", 250, 30)
        r = client.get("/api/reddit/posts", params={"hours": 48})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["post_id"] == "p1"
        assert data[0]["upvotes"] == 250
        assert data[0]["subreddit"] == "paranormal"

    def test_min_upvotes_filter(self, client):
        save_reddit_post("a", "sub", "Low", "", 5, 0)
        save_reddit_post("b", "sub", "High", "", 300, 0)
        r = client.get("/api/reddit/posts", params={"hours": 48, "min_upvotes": 100})
        data = r.json()
        assert len(data) == 1
        assert data[0]["post_id"] == "b"

    def test_limit_respected(self, client):
        for i in range(10):
            save_reddit_post(f"p{i}", "sub", f"Title {i}", "", i * 10, 0)
        r = client.get("/api/reddit/posts", params={"hours": 48, "limit": 3})
        assert len(r.json()) == 3

    def test_ordered_by_upvotes_desc(self, client):
        save_reddit_post("low", "sub", "Low", "", 10, 0)
        save_reddit_post("high", "sub", "High", "", 500, 0)
        data = client.get("/api/reddit/posts", params={"hours": 48}).json()
        assert data[0]["post_id"] == "high"

    def test_required_fields_present(self, client):
        save_reddit_post("p1", "paranormal", "Ghost", "https://r.com", 100, 5)
        data = client.get("/api/reddit/posts").json()
        fields = {"post_id", "subreddit", "title", "url", "upvotes", "num_comments"}
        assert fields.issubset(data[0].keys())


class TestRedditAlerts:
    def test_empty_returns_list(self, client):
        r = client.get("/api/reddit/alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_velocity_alert_included(self, client):
        log_alert("reddit_apify_trend", "paranormal", "Reddit (via Apify)", velocity_pct=350.0)
        data = client.get("/api/reddit/alerts", params={"hours": 48}).json()
        assert len(data) == 1
        assert data[0]["alert_type"] == "reddit_apify_trend"

    def test_hot_post_alert_included(self, client):
        log_alert("reddit_hot_post", "Ghost spotted!", "Reddit (via Apify)")
        data = client.get("/api/reddit/alerts", params={"hours": 48}).json()
        assert any(a["alert_type"] == "reddit_hot_post" for a in data)

    def test_cross_signal_alert_included(self, client):
        log_alert("reddit_cross_signal", "occult", "Reddit (via Apify)")
        data = client.get("/api/reddit/alerts", params={"hours": 48}).json()
        assert any(a["alert_type"] == "reddit_cross_signal" for a in data)

    def test_excludes_other_alert_types(self, client):
        log_alert("twitter_trend", "paranormal", "Twitter/X (via Apify)", velocity_pct=400.0)
        data = client.get("/api/reddit/alerts", params={"hours": 48}).json()
        assert all(a["alert_type"] in ("reddit_apify_trend", "reddit_hot_post", "reddit_cross_signal") for a in data)

    def test_required_fields(self, client):
        log_alert("reddit_apify_trend", "haunted", "Reddit (via Apify)", velocity_pct=300.0)
        data = client.get("/api/reddit/alerts").json()
        assert "keyword" in data[0]
        assert "alert_type" in data[0]
        assert "sent_at" in data[0]


class TestRedditKeywordCounts:
    def test_empty_returns_list(self, client):
        r = client.get("/api/reddit/keyword-counts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_reddit_apify_source_only(self, client):
        from modules.database import save_keyword_count
        save_keyword_count("paranormal", "reddit_apify", 10)
        save_keyword_count("paranormal", "twitter", 5)  # deve essere escluso
        data = client.get("/api/reddit/keyword-counts", params={"hours": 48}).json()
        assert len(data) == 1
        assert data[0]["keyword"] == "paranormal"
        assert data[0]["total"] == 10
