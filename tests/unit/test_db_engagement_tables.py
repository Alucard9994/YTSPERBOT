"""
Unit tests per le nuove funzioni DB:
  save_reddit_post / get_reddit_top_posts
  save_twitter_tweet / get_twitter_top_tweets
  save_pinterest_pin / get_pinterest_top_pins / get_pinterest_domain_counts
"""
from modules.database import (
    save_reddit_post,
    get_reddit_top_posts,
    save_twitter_tweet,
    get_twitter_top_tweets,
    save_pinterest_pin,
    get_pinterest_top_pins,
    get_pinterest_domain_counts,
)


# ---------------------------------------------------------------------------
# Reddit posts
# ---------------------------------------------------------------------------

class TestRedditPosts:
    def test_save_and_retrieve(self):
        save_reddit_post("p1", "paranormal", "Ghost story", "https://r.com/1", 300, 50)
        posts = get_reddit_top_posts(hours=48)
        assert len(posts) == 1
        assert posts[0]["post_id"] == "p1"
        assert posts[0]["upvotes"] == 300
        assert posts[0]["subreddit"] == "paranormal"

    def test_dedup_insert_or_ignore(self):
        save_reddit_post("p1", "paranormal", "Ghost story", "https://r.com/1", 300, 50)
        save_reddit_post("p1", "paranormal", "Ghost story", "https://r.com/1", 999, 99)
        posts = get_reddit_top_posts(hours=48)
        assert len(posts) == 1
        assert posts[0]["upvotes"] == 300  # primo valore preservato

    def test_ordered_by_upvotes_desc(self):
        save_reddit_post("a", "sub1", "Low", "", 10, 0)
        save_reddit_post("b", "sub2", "High", "", 500, 0)
        save_reddit_post("c", "sub3", "Mid", "", 100, 0)
        posts = get_reddit_top_posts(hours=48)
        assert posts[0]["upvotes"] == 500
        assert posts[1]["upvotes"] == 100

    def test_min_upvotes_filter(self):
        save_reddit_post("a", "sub", "Low", "", 5, 0)
        save_reddit_post("b", "sub", "High", "", 200, 0)
        posts = get_reddit_top_posts(hours=48, min_upvotes=50)
        assert len(posts) == 1
        assert posts[0]["post_id"] == "b"

    def test_limit_respected(self):
        for i in range(10):
            save_reddit_post(f"p{i}", "sub", f"Title {i}", "", i * 10, 0)
        posts = get_reddit_top_posts(hours=48, limit=3)
        assert len(posts) == 3


# ---------------------------------------------------------------------------
# Twitter tweets
# ---------------------------------------------------------------------------

class TestTwitterTweets:
    def _save(self, tweet_id="t1", keyword="paranormal", likes=100, retweets=20,
              replies=10, quotes=5):
        save_twitter_tweet(
            tweet_id=tweet_id, keyword=keyword,
            text="Test tweet text", url="https://x.com/t1",
            likes=likes, retweets=retweets, replies=replies, quotes=quotes,
            author_username="ghost_acc", author_followers=1000,
        )

    def test_save_and_retrieve(self):
        self._save()
        tweets = get_twitter_top_tweets(hours=48)
        assert len(tweets) == 1
        assert tweets[0]["tweet_id"] == "t1"
        assert tweets[0]["likes"] == 100

    def test_dedup_on_tweet_id_keyword(self):
        self._save()
        self._save(likes=999)  # same tweet_id + keyword
        tweets = get_twitter_top_tweets(hours=48)
        assert len(tweets) == 1

    def test_same_tweet_different_keywords(self):
        self._save(tweet_id="t1", keyword="paranormal")
        self._save(tweet_id="t1", keyword="occult")
        tweets = get_twitter_top_tweets(hours=48)
        # GROUP BY tweet_id → should collapse to 1
        assert len(tweets) == 1

    def test_engagement_computed_correctly(self):
        self._save(likes=100, retweets=20, quotes=5)
        tweets = get_twitter_top_tweets(hours=48)
        # engagement = likes + retweets + quotes = 125
        assert tweets[0]["engagement"] == 125

    def test_ordered_by_engagement_desc(self):
        self._save(tweet_id="low", keyword="a", likes=10, retweets=2, quotes=1)
        self._save(tweet_id="high", keyword="b", likes=500, retweets=100, quotes=50)
        tweets = get_twitter_top_tweets(hours=48)
        assert tweets[0]["tweet_id"] == "high"

    def test_limit_respected(self):
        for i in range(8):
            self._save(tweet_id=f"t{i}", keyword=f"kw{i}", likes=i * 10)
        tweets = get_twitter_top_tweets(hours=48, limit=3)
        assert len(tweets) == 3


# ---------------------------------------------------------------------------
# Pinterest pins
# ---------------------------------------------------------------------------

class TestPinterestPins:
    def _save(self, pin_hash="ph1", keyword="paranormal", repins=50, domain="example.com"):
        save_pinterest_pin(
            pin_hash=pin_hash, keyword=keyword, title="Haunted pin",
            url="https://pinterest.com/pin/1", repins=repins,
            creator_username="creator1", domain=domain,
        )

    def test_save_and_retrieve(self):
        self._save()
        pins = get_pinterest_top_pins(hours=168)
        assert len(pins) == 1
        assert pins[0]["pin_hash"] == "ph1"
        assert pins[0]["repins"] == 50

    def test_dedup_on_pin_hash_keyword(self):
        self._save()
        self._save(repins=999)  # same pin_hash + keyword
        pins = get_pinterest_top_pins(hours=168)
        assert len(pins) == 1
        assert pins[0]["repins"] == 50  # primo valore preservato

    def test_ordered_by_repins_desc(self):
        self._save(pin_hash="low", keyword="a", repins=5)
        self._save(pin_hash="high", keyword="b", repins=200)
        pins = get_pinterest_top_pins(hours=168)
        assert pins[0]["repins"] == 200

    def test_limit_respected(self):
        for i in range(8):
            self._save(pin_hash=f"ph{i}", keyword=f"kw{i}", repins=i * 10)
        pins = get_pinterest_top_pins(hours=168, limit=3)
        assert len(pins) == 3

    def test_domain_counts_aggregation(self):
        self._save(pin_hash="p1", keyword="a", repins=30, domain="horror.com")
        self._save(pin_hash="p2", keyword="b", repins=20, domain="horror.com")
        self._save(pin_hash="p3", keyword="c", repins=50, domain="occult.net")
        domains = get_pinterest_domain_counts(hours=168)
        assert len(domains) >= 2
        # horror.com deve avere 60 total_repins
        horror = next(d for d in domains if d["domain"] == "horror.com")
        assert horror["pin_count"] == 2
        assert horror["total_repins"] == 50

    def test_domain_counts_excludes_empty_domain(self):
        self._save(pin_hash="p1", keyword="a", repins=10, domain="")
        self._save(pin_hash="p2", keyword="b", repins=10, domain="real.com")
        domains = get_pinterest_domain_counts(hours=168)
        domain_names = [d["domain"] for d in domains]
        assert "" not in domain_names
        assert "real.com" in domain_names

    def test_domain_counts_ordered_by_repins_desc(self):
        self._save(pin_hash="p1", keyword="a", repins=10, domain="low.com")
        self._save(pin_hash="p2", keyword="b", repins=100, domain="high.com")
        domains = get_pinterest_domain_counts(hours=168)
        assert domains[0]["domain"] == "high.com"
