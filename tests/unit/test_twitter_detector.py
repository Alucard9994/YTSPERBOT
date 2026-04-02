"""
Unit tests — twitter_detector.py
Tests pure logic and mocks all external I/O (Tweepy, Telegram, DB writes).
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from modules.twitter_detector import (
    get_twitter_client,
    search_recent_tweets,
    send_twitter_alert,
    run_twitter_detector,
)
from modules.database import save_keyword_count


# ============================================================
# Helpers
# ============================================================

def _config(keywords=None, **td_overrides):
    td = {
        "min_mentions_to_track": 2,
        "velocity_threshold_longform": 300,
    }
    td.update(td_overrides)
    return {
        "trend_detector": td,
        "keywords": keywords or ["ghost", "paranormal"],
        "priority_score": {"min_score": 1},
    }


def _make_tweet(tweet_id: str, text: str) -> MagicMock:
    t = MagicMock()
    t.id = int(tweet_id)
    t.text = text
    return t


def _make_tweepy_response(tweets: list) -> MagicMock:
    resp = MagicMock()
    resp.data = tweets if tweets else None
    return resp


# ============================================================
# get_twitter_client
# ============================================================

class TestGetTwitterClient:
    def test_raises_when_no_token(self):
        with patch("modules.twitter_detector.BEARER_TOKEN", None):
            with pytest.raises(ValueError, match="TWITTER_BEARER_TOKEN"):
                get_twitter_client()

    def test_raises_when_placeholder_token(self):
        with patch("modules.twitter_detector.BEARER_TOKEN", "inserisci_qui"):
            with pytest.raises(ValueError):
                get_twitter_client()

    def test_returns_tweepy_client_when_token_set(self):
        with patch("modules.twitter_detector.BEARER_TOKEN", "valid_token_abc"):
            with patch("modules.twitter_detector.tweepy.Client") as mock_client:
                mock_client.return_value = MagicMock()
                get_twitter_client()
        mock_client.assert_called_once_with(bearer_token="valid_token_abc", wait_on_rate_limit=True)


# ============================================================
# search_recent_tweets
# ============================================================

class TestSearchRecentTweets:
    def test_returns_tweets_as_dicts(self):
        tweets = [_make_tweet("1", "ghost sighting tonight")]
        client = MagicMock()
        client.search_recent_tweets.return_value = _make_tweepy_response(tweets)
        result = search_recent_tweets(client, "ghost")
        assert len(result) == 1
        assert result[0]["text"] == "ghost sighting tonight"
        assert result[0]["id"] == "1"

    def test_returns_empty_when_no_data(self):
        client = MagicMock()
        client.search_recent_tweets.return_value = _make_tweepy_response([])
        result = search_recent_tweets(client, "ghost")
        assert result == []

    def test_returns_empty_on_tweepy_exception(self, capsys):
        import tweepy
        client = MagicMock()
        client.search_recent_tweets.side_effect = tweepy.errors.TweepyException("rate limit")
        result = search_recent_tweets(client, "ghost")
        assert result == []
        assert "Errore" in capsys.readouterr().out

    def test_max_results_capped_at_100(self):
        client = MagicMock()
        client.search_recent_tweets.return_value = _make_tweepy_response([])
        search_recent_tweets(client, "ghost", max_results=200)
        call_kwargs = client.search_recent_tweets.call_args[1]
        assert call_kwargs["max_results"] <= 100

    def test_query_excludes_retweets_and_replies(self):
        client = MagicMock()
        client.search_recent_tweets.return_value = _make_tweepy_response([])
        search_recent_tweets(client, "ghost")
        call_kwargs = client.search_recent_tweets.call_args[1]
        assert "-is:retweet" in call_kwargs["query"]
        assert "-is:reply" in call_kwargs["query"]

    def test_multiple_tweets_returned(self):
        tweets = [_make_tweet(str(i), f"ghost post {i}") for i in range(5)]
        client = MagicMock()
        client.search_recent_tweets.return_value = _make_tweepy_response(tweets)
        result = search_recent_tweets(client, "ghost")
        assert len(result) == 5


# ============================================================
# send_twitter_alert
# ============================================================

class TestSendTwitterAlert:
    def test_does_not_send_when_alert_not_allowed(self):
        with patch("modules.twitter_detector.alert_allowed", return_value=False):
            with patch("modules.twitter_detector.send_message") as mock_send:
                result = send_twitter_alert("ghost", 400.0, 10, 2, [])
        mock_send.assert_not_called()
        assert result is False

    def test_sends_message_when_alert_allowed(self):
        with patch("modules.twitter_detector.alert_allowed", return_value=True):
            with patch("modules.twitter_detector.send_message", return_value=True) as mock_send:
                with patch("modules.twitter_detector.calculate_priority_score", return_value=7):
                    with patch("modules.twitter_detector.score_bar", return_value="███"):
                        result = send_twitter_alert("ghost", 400.0, 10, 2, [])
        mock_send.assert_called_once()
        assert result is True

    def test_message_contains_keyword(self):
        captured = {}

        def fake_send(text):
            captured["text"] = text
            return True

        with patch("modules.twitter_detector.alert_allowed", return_value=True):
            with patch("modules.twitter_detector.send_message", side_effect=fake_send):
                with patch("modules.twitter_detector.calculate_priority_score", return_value=5):
                    with patch("modules.twitter_detector.score_bar", return_value="██"):
                        send_twitter_alert("ghost", 400.0, 10, 2, [])

        assert "ghost" in captured["text"].lower()

    def test_message_includes_tweet_previews(self):
        captured = {}
        tweets = [{"text": "Sample ghost tweet " + str(i)} for i in range(3)]

        def fake_send(text):
            captured["text"] = text
            return True

        with patch("modules.twitter_detector.alert_allowed", return_value=True):
            with patch("modules.twitter_detector.send_message", side_effect=fake_send):
                with patch("modules.twitter_detector.calculate_priority_score", return_value=5):
                    with patch("modules.twitter_detector.score_bar", return_value="██"):
                        send_twitter_alert("ghost", 400.0, 10, 2, tweets)

        assert "Sample ghost tweet" in captured["text"]

    def test_at_most_3_tweet_previews_shown(self):
        captured = {}
        tweets = [{"text": f"tweet number {i}"} for i in range(10)]

        def fake_send(text):
            captured["text"] = text
            return True

        with patch("modules.twitter_detector.alert_allowed", return_value=True):
            with patch("modules.twitter_detector.send_message", side_effect=fake_send):
                with patch("modules.twitter_detector.calculate_priority_score", return_value=5):
                    with patch("modules.twitter_detector.score_bar", return_value="██"):
                        send_twitter_alert("ghost", 400.0, 10, 2, tweets)

        # Count bullet points (•) in message — there should be ≤ 3
        assert captured["text"].count("•") <= 3

    def test_high_velocity_uses_rocket_emoji(self):
        captured = {}

        def fake_send(text):
            captured["text"] = text
            return True

        with patch("modules.twitter_detector.alert_allowed", return_value=True):
            with patch("modules.twitter_detector.send_message", side_effect=fake_send):
                with patch("modules.twitter_detector.calculate_priority_score", return_value=8):
                    with patch("modules.twitter_detector.score_bar", return_value="████"):
                        send_twitter_alert("ghost", 600.0, 20, 2, [])

        assert "🔺" in captured["text"]


# ============================================================
# run_twitter_detector
# ============================================================

class TestRunTwitterDetector:
    def test_exits_when_disabled(self, capsys):
        with patch("modules.twitter_detector.TWITTER_ENABLED", False):
            with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                run_twitter_detector(_config())
        mock_send.assert_not_called()
        assert "disabilitato" in capsys.readouterr().out.lower()

    def test_exits_on_missing_token(self, capsys):
        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch(
                "modules.twitter_detector.get_twitter_client",
                side_effect=ValueError("TWITTER_BEARER_TOKEN non configurato"),
            ):
                with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                    run_twitter_detector(_config())
        mock_send.assert_not_called()

    def test_no_alert_below_min_mentions(self):
        """Only 1 tweet for 'ghost' < min_mentions=2 → no alert."""
        tweets = [{"id": "1", "text": "ghost story"}]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                        with patch("modules.twitter_detector.time.sleep"):
                            run_twitter_detector(_config(min_mentions_to_track=2))
        mock_send.assert_not_called()

    def test_saves_keyword_count_when_above_min_mentions(self):
        tweets = [{"id": str(i), "text": f"ghost tweet {i}"} for i in range(5)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.send_twitter_alert"):
                        with patch("modules.twitter_detector.time.sleep"):
                            run_twitter_detector(_config())

        from modules.database import get_keyword_counts
        counts = get_keyword_counts("ghost", "twitter", 1)
        assert len(counts) >= 1
        assert counts[0]["count"] == 5

    def test_sends_alert_on_velocity_spike(self):
        # Baseline 2, now 10 → +400% > 300% threshold
        save_keyword_count("ghost", "twitter", 2)
        tweets = [{"id": str(i), "text": f"ghost tweet {i}"} for i in range(10)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.was_alert_sent_recently", return_value=False):
                        with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                            with patch("modules.twitter_detector.time.sleep"):
                                run_twitter_detector(_config())

        mock_send.assert_called_once()
        assert "ghost" in str(mock_send.call_args)

    def test_no_alert_below_velocity_threshold(self):
        # Baseline 10, now 12 → +20% < 300% threshold
        save_keyword_count("paranormal", "twitter", 10)
        tweets = [{"id": str(i), "text": f"paranormal tweet {i}"} for i in range(12)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.was_alert_sent_recently", return_value=False):
                        with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                            with patch("modules.twitter_detector.time.sleep"):
                                run_twitter_detector(_config(keywords=["paranormal"]))

        mock_send.assert_not_called()

    def test_no_alert_on_first_run(self):
        """No previous data → previous_count=0 → velocity=None → skip."""
        tweets = [{"id": str(i), "text": f"ghost tweet {i}"} for i in range(5)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                        with patch("modules.twitter_detector.time.sleep"):
                            run_twitter_detector(_config())

        mock_send.assert_not_called()

    def test_no_duplicate_alert_within_cooldown(self):
        save_keyword_count("ghost", "twitter", 2)
        tweets = [{"id": str(i), "text": f"ghost {i}"} for i in range(10)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.was_alert_sent_recently", return_value=True):
                        with patch("modules.twitter_detector.send_twitter_alert") as mock_send:
                            with patch("modules.twitter_detector.time.sleep"):
                                run_twitter_detector(_config())

        mock_send.assert_not_called()

    def test_sleep_called_between_keywords(self):
        """time.sleep(1) is called once per keyword (when count >= min_mentions and velocity is defined)."""
        # Set a baseline so calculate_velocity returns a float, not None
        save_keyword_count("ghost", "twitter", 3)
        save_keyword_count("paranormal", "twitter", 3)
        # 5 tweets per keyword, threshold=2 → sleep is reached for both keywords
        tweets = [{"id": str(i), "text": f"tweet {i}"} for i in range(5)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.send_twitter_alert"):
                        with patch("modules.twitter_detector.was_alert_sent_recently", return_value=True):
                            with patch("modules.twitter_detector.time.sleep") as mock_sleep:
                                run_twitter_detector(_config(keywords=["ghost", "paranormal"], min_mentions_to_track=2))

        assert mock_sleep.call_count == 2

    def test_logs_alert_in_db_on_spike(self):
        save_keyword_count("ghost", "twitter", 2)
        tweets = [{"id": str(i), "text": f"ghost {i}"} for i in range(10)]

        with patch("modules.twitter_detector.TWITTER_ENABLED", True):
            with patch("modules.twitter_detector.get_twitter_client", return_value=MagicMock()):
                with patch("modules.twitter_detector.search_recent_tweets", return_value=tweets):
                    with patch("modules.twitter_detector.was_alert_sent_recently", return_value=False):
                        with patch("modules.twitter_detector.send_twitter_alert", return_value=True):
                            with patch("modules.twitter_detector.log_alert") as mock_log:
                                with patch("modules.twitter_detector.time.sleep"):
                                    run_twitter_detector(_config())

        mock_log.assert_called_once()
        args = mock_log.call_args[0]
        assert args[0] == "twitter_trend"
        assert args[1] == "ghost"
