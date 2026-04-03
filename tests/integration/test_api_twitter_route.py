"""Integration tests for api/routes/twitter.py"""
from modules.database import save_twitter_tweet, log_alert, save_keyword_count


def _save_tweet(tweet_id="t1", keyword="paranormal", likes=100, retweets=20, replies=10, quotes=5):
    save_twitter_tweet(
        tweet_id=tweet_id, keyword=keyword,
        text="Test tweet text", url=f"https://x.com/{tweet_id}",
        likes=likes, retweets=retweets, replies=replies, quotes=quotes,
        author_username="ghost_hunter", author_followers=5000,
    )


class TestTopTweets:
    def test_empty_returns_list(self, client):
        r = client.get("/api/twitter/tweets")
        assert r.status_code == 200
        assert r.json() == []

    def test_insert_and_retrieve(self, client):
        _save_tweet()
        data = client.get("/api/twitter/tweets", params={"hours": 48}).json()
        assert len(data) == 1
        assert data[0]["tweet_id"] == "t1"
        assert data[0]["likes"] == 100

    def test_ordered_by_engagement_desc(self, client):
        _save_tweet(tweet_id="low", keyword="a", likes=10, retweets=2, quotes=1)
        _save_tweet(tweet_id="high", keyword="b", likes=500, retweets=100, quotes=50)
        data = client.get("/api/twitter/tweets", params={"hours": 48}).json()
        assert data[0]["tweet_id"] == "high"

    def test_engagement_field_computed(self, client):
        _save_tweet(likes=100, retweets=20, quotes=5)
        data = client.get("/api/twitter/tweets").json()
        # engagement = likes + retweets + quotes = 125
        assert data[0]["engagement"] == 125

    def test_limit_respected(self, client):
        for i in range(10):
            _save_tweet(tweet_id=f"t{i}", keyword=f"kw{i}", likes=i * 10)
        data = client.get("/api/twitter/tweets", params={"hours": 48, "limit": 3}).json()
        assert len(data) == 3

    def test_required_fields_present(self, client):
        _save_tweet()
        data = client.get("/api/twitter/tweets").json()
        fields = {"tweet_id", "keyword", "text", "url", "likes", "retweets", "replies", "quotes", "engagement"}
        assert fields.issubset(data[0].keys())

    def test_dedup_by_tweet_id(self, client):
        _save_tweet(tweet_id="t1", keyword="a")
        _save_tweet(tweet_id="t1", keyword="b")
        data = client.get("/api/twitter/tweets").json()
        # GROUP BY tweet_id → 1 result
        assert len(data) == 1


class TestTwitterAlerts:
    def test_empty_returns_list(self, client):
        r = client.get("/api/twitter/alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_velocity_trend_included(self, client):
        log_alert("twitter_trend", "paranormal", "Twitter/X (via Apify)", velocity_pct=350.0)
        data = client.get("/api/twitter/alerts", params={"hours": 48}).json()
        assert any(a["alert_type"] == "twitter_trend" for a in data)

    def test_quote_storm_included(self, client):
        log_alert("twitter_quote_storm", "paranormal", "Twitter/X (via Apify)")
        data = client.get("/api/twitter/alerts").json()
        assert any(a["alert_type"] == "twitter_quote_storm" for a in data)

    def test_thread_included(self, client):
        log_alert("twitter_thread", "haunted", "Twitter/X (via Apify)")
        data = client.get("/api/twitter/alerts").json()
        assert any(a["alert_type"] == "twitter_thread" for a in data)

    def test_controversial_included(self, client):
        log_alert("twitter_controversial", "occult", "Twitter/X (via Apify)")
        data = client.get("/api/twitter/alerts").json()
        assert any(a["alert_type"] == "twitter_controversial" for a in data)

    def test_excludes_reddit_alerts(self, client):
        log_alert("reddit_apify_trend", "paranormal", "Reddit (via Apify)")
        data = client.get("/api/twitter/alerts").json()
        assert all("reddit" not in a["alert_type"] for a in data)

    def test_required_fields(self, client):
        log_alert("twitter_trend", "haunted", "Twitter/X (via Apify)", velocity_pct=400.0)
        data = client.get("/api/twitter/alerts").json()
        assert "keyword" in data[0]
        assert "alert_type" in data[0]
        assert "sent_at" in data[0]


class TestTwitterKeywordCounts:
    def test_empty_returns_list(self, client):
        r = client.get("/api/twitter/keyword-counts")
        assert r.status_code == 200
        assert r.json() == []

    def test_includes_twitter_and_twitter_apify(self, client):
        save_keyword_count("paranormal", "twitter", 8)
        save_keyword_count("paranormal", "twitter_apify", 4)
        data = client.get("/api/twitter/keyword-counts", params={"hours": 48}).json()
        assert len(data) == 1
        assert data[0]["total"] == 12

    def test_excludes_reddit_source(self, client):
        save_keyword_count("occult", "reddit_apify", 10)
        data = client.get("/api/twitter/keyword-counts").json()
        assert data == []
