"""
Unit tests per le nuove funzionalità di reddit_apify.py:
  - Hot post immediato
  - Cross-subreddit signal
  - run_reddit_digest
"""
from unittest.mock import patch

from modules.reddit_apify import (
    _fetch_subreddit_posts,
    run_reddit_digest,
)


# ---------------------------------------------------------------------------
# _fetch_subreddit_posts — campi arricchiti
# ---------------------------------------------------------------------------

class TestFetchSubredditPostsEnriched:
    def test_returns_enriched_fields(self):
        items = [{
            "id": "abc123",
            "title": "Ghost spotted",
            "body": "incredible EVP",
            "url": "https://reddit.com/r/paranormal/abc",
            "upVotes": 250,
            "numberOfComments": 42,
            "createdAt": "2026-04-03T10:00:00.000Z",
        }]
        with patch("modules.reddit_apify.run_actor", return_value=items):
            posts = _fetch_subreddit_posts("paranormal", 40)
        assert len(posts) == 1
        p = posts[0]
        assert p["id"] == "abc123"
        assert p["upvotes"] == 250
        assert p["num_comments"] == 42
        assert p["url"] == "https://reddit.com/r/paranormal/abc"
        assert p["created_at"] == "2026-04-03T10:00:00.000Z"
        assert p["subreddit"] == "paranormal"

    def test_upvotes_defaults_to_zero_when_missing(self):
        items = [{"id": "x1", "title": "test", "body": "text"}]
        with patch("modules.reddit_apify.run_actor", return_value=items):
            posts = _fetch_subreddit_posts("occult", 10)
        assert posts[0]["upvotes"] == 0
        assert posts[0]["num_comments"] == 0

    def test_strips_r_prefix_from_subreddit(self):
        items = [{"id": "y1", "title": "hello", "body": ""}]
        with patch("modules.reddit_apify.run_actor", return_value=items):
            posts = _fetch_subreddit_posts("r/Ghosts", 10)
        assert posts[0]["subreddit"] == "Ghosts"


# ---------------------------------------------------------------------------
# run_reddit_digest
# ---------------------------------------------------------------------------

class TestRunRedditDigest:
    def _config(self, threshold=10):
        return {"reddit": {"hot_post_threshold": threshold}}

    def test_digest_skipped_when_no_posts(self):
        with (
            patch("modules.reddit_apify.get_reddit_top_posts", return_value=[]),
            patch("modules.reddit_apify.was_alert_sent_recently", return_value=False),
            patch("modules.reddit_apify.send_message") as mock_send,
            patch("modules.reddit_apify.mark_alert_sent"),
        ):
            run_reddit_digest(self._config())
        mock_send.assert_not_called()

    def test_digest_skipped_when_cooldown_active(self):
        with (
            patch("modules.reddit_apify.was_alert_sent_recently", return_value=True),
            patch("modules.reddit_apify.get_reddit_top_posts") as mock_get,
            patch("modules.reddit_apify.send_message") as mock_send,
        ):
            run_reddit_digest(self._config())
        mock_get.assert_not_called()
        mock_send.assert_not_called()

    def test_digest_sends_when_posts_exist(self):
        posts = [
            {"post_id": "1", "subreddit": "paranormal", "title": "Haunted house",
             "url": "https://reddit.com/1", "upvotes": 500, "num_comments": 30},
            {"post_id": "2", "subreddit": "Ghosts", "title": "EVP recording",
             "url": "https://reddit.com/2", "upvotes": 200, "num_comments": 15},
        ]
        with (
            patch.dict("os.environ", {"APIFY_API_KEY": "fake"}),
            patch("modules.reddit_apify.was_alert_sent_recently", return_value=False),
            patch("modules.reddit_apify.get_reddit_top_posts", return_value=posts),
            patch("modules.reddit_apify.send_message") as mock_send,
            patch("modules.reddit_apify.mark_alert_sent") as mock_mark,
        ):
            run_reddit_digest(self._config())
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "REDDIT DIGEST" in msg
        assert "Haunted house" in msg
        assert "500" in msg
        mock_mark.assert_called_once_with("reddit_daily_digest", "reddit_digest")

    def test_digest_message_contains_subreddit(self):
        posts = [
            {"post_id": "1", "subreddit": "occult", "title": "Dark ritual",
             "url": "", "upvotes": 100, "num_comments": 5},
        ]
        with (
            patch.dict("os.environ", {"APIFY_API_KEY": "fake"}),
            patch("modules.reddit_apify.was_alert_sent_recently", return_value=False),
            patch("modules.reddit_apify.get_reddit_top_posts", return_value=posts),
            patch("modules.reddit_apify.send_message") as mock_send,
            patch("modules.reddit_apify.mark_alert_sent"),
        ):
            run_reddit_digest(self._config())
        msg = mock_send.call_args[0][0]
        assert "r/occult" in msg

    def test_digest_skipped_when_no_apify_key(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("modules.reddit_apify.os.getenv", return_value=""),
            patch("modules.reddit_apify.send_message") as mock_send,
        ):
            run_reddit_digest(self._config())
        mock_send.assert_not_called()
