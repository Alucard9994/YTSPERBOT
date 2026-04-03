"""
Unit tests per le nuove funzionalità di twitter_apify.py:
  - Campi arricchiti in _search_tweets
  - Quote storm detection
  - Engagement ratio / controversial detection
  - Thread detection (replyCount/likeCount >= thread_ratio)
  - run_twitter_digest
"""
from unittest.mock import patch
import os

from modules.twitter_apify import _search_tweets, run_twitter_apify_detector, run_twitter_digest


# ---------------------------------------------------------------------------
# _search_tweets — campi arricchiti
# ---------------------------------------------------------------------------

class TestSearchTweetsEnriched:
    def _item(self, **kwargs):
        base = {
            "id": "t1",
            "text": "paranormal sighting",
            "likeCount": 100,
            "retweetCount": 20,
            "replyCount": 15,
            "quoteCount": 8,
            "url": "https://x.com/tweet/1",
            "createdAt": "2026-04-03T10:00:00.000Z",
            "author": {"userName": "ghost_hunter", "followers": 5000},
        }
        base.update(kwargs)
        return base

    def test_enriched_fields_present(self):
        with patch("modules.twitter_apify.run_actor", return_value=[self._item()]):
            tweets = _search_tweets("paranormal", 50)
        t = tweets[0]
        assert t["likes"] == 100
        assert t["retweets"] == 20
        assert t["replies"] == 15
        assert t["quotes"] == 8
        assert t["url"] == "https://x.com/tweet/1"
        assert t["author_username"] == "ghost_hunter"
        assert t["author_followers"] == 5000
        assert t["created_at"] == "2026-04-03T10:00:00.000Z"

    def test_missing_engagement_defaults_to_zero(self):
        item = {"id": "t2", "text": "haunted", "author": {}}
        with patch("modules.twitter_apify.run_actor", return_value=[item]):
            tweets = _search_tweets("haunted", 50)
        t = tweets[0]
        assert t["likes"] == 0
        assert t["retweets"] == 0
        assert t["replies"] == 0
        assert t["quotes"] == 0

    def test_author_username_fallback(self):
        item = {"id": "t3", "text": "occult", "author": {"username": "witch_acc"}}
        with patch("modules.twitter_apify.run_actor", return_value=[item]):
            tweets = _search_tweets("occult", 50)
        assert tweets[0]["author_username"] == "witch_acc"


# ---------------------------------------------------------------------------
# run_twitter_digest
# ---------------------------------------------------------------------------

class TestRunTwitterDigest:
    def _config(self):
        return {"twitter": {}}

    def test_digest_skipped_when_no_tweets(self):
        with (
            patch("modules.twitter_apify.was_alert_sent_recently", return_value=False),
            patch("modules.twitter_apify.get_twitter_top_tweets", return_value=[]),
            patch("modules.twitter_apify.send_message") as mock_send,
        ):
            run_twitter_digest(self._config())
        mock_send.assert_not_called()

    def test_digest_skipped_when_cooldown_active(self):
        with (
            patch("modules.twitter_apify.was_alert_sent_recently", return_value=True),
            patch("modules.twitter_apify.get_twitter_top_tweets") as mock_get,
            patch("modules.twitter_apify.send_message") as mock_send,
        ):
            run_twitter_digest(self._config())
        mock_get.assert_not_called()
        mock_send.assert_not_called()

    def test_digest_sends_when_tweets_exist(self):
        tweets = [
            {"tweet_id": "t1", "keyword": "paranormal", "text": "Ghost spotted near graveyard",
             "url": "https://x.com/1", "likes": 500, "retweets": 100, "engagement": 620},
            {"tweet_id": "t2", "keyword": "occult", "text": "Dark ritual revealed",
             "url": "", "likes": 200, "retweets": 50, "engagement": 260},
        ]
        with (
            patch("modules.twitter_apify.was_alert_sent_recently", return_value=False),
            patch("modules.twitter_apify.get_twitter_top_tweets", return_value=tweets),
            patch("modules.twitter_apify.send_message") as mock_send,
            patch("modules.twitter_apify.mark_alert_sent") as mock_mark,
            patch("modules.twitter_apify.os.getenv", return_value="fake_key"),
        ):
            run_twitter_digest(self._config())
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "TWITTER" in msg
        assert "paranormal" in msg
        assert "500" in msg
        mock_mark.assert_called_once_with("twitter_daily_digest", "twitter_digest")

    def test_digest_skipped_when_no_apify_key(self):
        with (
            patch("modules.twitter_apify.os.getenv", return_value=""),
            patch("modules.twitter_apify.send_message") as mock_send,
        ):
            run_twitter_digest(self._config())
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Thread detection (replyCount/likeCount >= thread_ratio)
# ---------------------------------------------------------------------------


class TestThreadDetection:
    """
    Verifica che run_twitter_apify_detector invii:
      - alert "thread"       se replies/likes >= thread_ratio (0.8)
      - alert "controversial" se replies/likes in [engagement_ratio, thread_ratio)
      - nessun alert se replies/likes < engagement_ratio (0.5)
    e che thread e controversial siano mutualmente esclusivi.
    """

    def _cfg(self, thread_ratio=0.8, engagement_ratio=0.5, min_eng=20):
        return {
            "keywords": ["paranormal"],
            "twitter": {
                "tweets_per_keyword": 50,
                "quote_storm_ratio": 0.3,
                "engagement_ratio": engagement_ratio,
                "thread_ratio": thread_ratio,
                "min_engagement_for_ratios": min_eng,
                "digest_send_time": "19:00",
            },
            "trend_detector": {
                "min_mentions_to_track": 1,
                "velocity_threshold_longform": 300,
            },
            "priority_score": {"min_score": 1},
        }

    def _tweet(self, tweet_id="tw1", likes=100, replies=0, quotes=0):
        return {
            "id": tweet_id,
            "text": f"Paranormal tweet {tweet_id}",
            "url": f"https://x.com/{tweet_id}",
            "likes": likes,
            "retweets": 5,
            "replies": replies,
            "quotes": quotes,
            "author_username": "user1",
            "author_followers": 1000,
            "created_at": "2026-04-03T10:00:00Z",
        }

    def _run(self, tweets, cfg=None):
        if cfg is None:
            cfg = self._cfg()
        with (
            patch.dict(os.environ, {"APIFY_API_KEY": "fake"}),
            patch("modules.twitter_apify._search_tweets", return_value=tweets),
            patch("modules.twitter_apify.save_twitter_tweet"),
            patch("modules.twitter_apify.get_keyword_counts", return_value=[{"count": 5}]),
            patch("modules.twitter_apify.save_keyword_count"),
            patch("modules.twitter_apify.was_alert_sent_recently", return_value=False),
            patch("modules.twitter_apify.mark_alert_sent"),
            patch("modules.twitter_apify.send_message") as mock_send,
        ):
            run_twitter_apify_detector(cfg)
        return mock_send

    def test_thread_alert_fires_at_high_reply_ratio(self):
        """replies/likes = 0.9 >= 0.8 → alert type 'thread' (🧵)."""
        tweet = self._tweet(likes=100, replies=90)  # ratio 0.9
        mock_send = self._run([tweet])
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "🧵" in msg
        assert "THREAD" in msg

    def test_thread_alert_at_exact_threshold(self):
        """replies/likes = 0.8 (esatto boundary) → alert 'thread'."""
        tweet = self._tweet(likes=100, replies=80)  # ratio exactly 0.8
        mock_send = self._run([tweet])
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "THREAD" in msg

    def test_controversial_alert_between_thresholds(self):
        """replies/likes = 0.6 ∈ [0.5, 0.8) → alert 'controversial' (🔥), NOT thread."""
        tweet = self._tweet(likes=100, replies=60)  # ratio 0.6
        mock_send = self._run([tweet])
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "🔥" in msg
        assert "CONTROVERSIALE" in msg
        assert "🧵" not in msg

    def test_no_alert_below_engagement_ratio(self):
        """replies/likes = 0.3 < 0.5 → nessun alert ratio."""
        tweet = self._tweet(likes=100, replies=30)  # ratio 0.3
        mock_send = self._run([tweet])
        mock_send.assert_not_called()

    def test_thread_and_controversial_mutually_exclusive(self):
        """Un tweet non deve mai ricevere sia 'thread' che 'controversial'."""
        tweet = self._tweet(likes=100, replies=85)  # ratio 0.85 → thread only
        mock_send = self._run([tweet])
        # deve essere al massimo 1 chiamata
        assert mock_send.call_count <= 1
        if mock_send.called:
            msg = mock_send.call_args[0][0]
            # solo uno dei due header
            assert not ("🧵" in msg and "🔥" in msg)

    def test_no_alert_below_min_engagement(self):
        """Se likes < min_engagement_for_ratios il check ratio è saltato."""
        tweet = self._tweet(likes=10, replies=9)  # ratio 0.9 ma likes troppo bassi
        mock_send = self._run([tweet])
        mock_send.assert_not_called()

    def test_thread_includes_tweet_stats(self):
        """Il messaggio thread deve includere contatori replies e likes."""
        tweet = self._tweet(likes=200, replies=170)  # ratio 0.85
        mock_send = self._run([tweet])
        msg = mock_send.call_args[0][0]
        assert "170" in msg  # replies
        assert "200" in msg  # likes

    def test_no_thread_alert_when_cooldown_active(self):
        """Se was_alert_sent_recently → True per il tweet, non invia duplicati."""
        tweet = self._tweet(likes=100, replies=90)
        with (
            patch.dict(os.environ, {"APIFY_API_KEY": "fake"}),
            patch("modules.twitter_apify._search_tweets", return_value=[tweet]),
            patch("modules.twitter_apify.save_twitter_tweet"),
            patch("modules.twitter_apify.get_keyword_counts", return_value=[{"count": 5}]),
            patch("modules.twitter_apify.save_keyword_count"),
            patch("modules.twitter_apify.was_alert_sent_recently", return_value=True),
            patch("modules.twitter_apify.mark_alert_sent"),
            patch("modules.twitter_apify.send_message") as mock_send,
        ):
            run_twitter_apify_detector(self._cfg())
        mock_send.assert_not_called()
