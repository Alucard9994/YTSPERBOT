"""Unit tests for modules/twitter_apify.py"""
from __future__ import annotations

import os
from unittest.mock import patch


from modules.twitter_apify import (
    _search_tweets,
    _send_twitter_apify_alert,
    run_twitter_apify_detector,
)


# ---------------------------------------------------------------------------
# _search_tweets
# ---------------------------------------------------------------------------


class TestSearchTweets:
    def test_calls_run_actor_with_correct_input(self):
        with patch("modules.twitter_apify.run_actor", return_value=[]) as mock_ra:
            _search_tweets("paranormal", 50)
            actor_id, input_data = mock_ra.call_args[0]
            assert actor_id == "apidojo~tweet-scraper"
            assert input_data["searchTerms"] == ["paranormal"]
            assert input_data["sort"] == "Latest"

    def test_enforces_minimum_50_items(self):
        with patch("modules.twitter_apify.run_actor", return_value=[]) as mock_ra:
            _search_tweets("ghost", 10)
            _, input_data = mock_ra.call_args[0]
            assert input_data["maxItems"] == 50

    def test_does_not_cap_above_50(self):
        with patch("modules.twitter_apify.run_actor", return_value=[]) as mock_ra:
            _search_tweets("ghost", 100)
            _, input_data = mock_ra.call_args[0]
            assert input_data["maxItems"] == 100

    def test_maps_id_from_top_level_id(self):
        items = [{"id": "123", "text": "haunted house"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("haunted", 50)
        assert tweets[0]["id"] == "123"

    def test_maps_id_from_tweet_id_fallback(self):
        items = [{"tweetId": "456", "text": "ghost sighting"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("ghost", 50)
        assert tweets[0]["id"] == "456"

    def test_maps_id_from_tweet_id_snake_fallback(self):
        items = [{"tweet_id": "789", "text": "occult ritual"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("occult", 50)
        assert tweets[0]["id"] == "789"

    def test_maps_text_from_full_text_fallback(self):
        items = [{"id": "1", "full_text": "Full text version"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("k", 50)
        assert tweets[0]["text"] == "Full text version"

    def test_maps_text_from_embedded_text_fallback(self):
        items = [{"id": "1", "Embedded_text": "Embedded version"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("k", 50)
        assert tweets[0]["text"] == "Embedded version"

    def test_maps_text_from_nested_tweet_object(self):
        items = [{"id": "1", "tweet": {"text": "Nested tweet text"}}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("k", 50)
        assert tweets[0]["text"] == "Nested tweet text"

    def test_skips_items_without_id(self):
        items = [{"text": "no id tweet"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("k", 50)
        assert tweets == []

    def test_skips_items_without_text(self):
        items = [{"id": "99"}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("k", 50)
        assert tweets == []

    def test_returns_empty_on_empty_response(self):
        with patch("modules.twitter_apify.run_actor", return_value=[]):
            assert _search_tweets("k", 50) == []

    def test_result_has_required_fields(self):
        items = [{"id": "1", "text": "hi", "likeCount": 99, "author": {"userName": "x"}}]
        with patch("modules.twitter_apify.run_actor", return_value=items):
            tweets = _search_tweets("k", 50)
        expected = {"id", "text", "url", "likes", "retweets", "replies", "quotes",
                    "author_username", "author_followers", "created_at"}
        assert set(tweets[0].keys()) == expected


# ---------------------------------------------------------------------------
# _send_twitter_apify_alert
# ---------------------------------------------------------------------------


class TestSendTwitterApifyAlert:
    def _tweets(self, n=3):
        return [{"id": str(i), "text": f"Tweet number {i} about paranormal events"} for i in range(n)]

    def test_returns_false_when_alert_not_allowed(self):
        with patch("modules.twitter_apify.alert_allowed", return_value=False):
            result = _send_twitter_apify_alert("ghost", 300.0, 10, 5, self._tweets())
        assert result is False

    def test_uses_rocket_emoji_for_high_velocity(self):
        with patch("modules.twitter_apify.alert_allowed", return_value=True):
            with patch("modules.twitter_apify.calculate_priority_score", return_value=8):
                with patch("modules.twitter_apify.score_bar", return_value="████"):
                    with patch("modules.database.get_keyword_source_count", return_value=3):
                        with patch("modules.twitter_apify.send_message") as mock_sm:
                            _send_twitter_apify_alert("ghost", 600.0, 20, 5, self._tweets())
                            text = mock_sm.call_args[0][0]
        assert "🔺" in text

    def test_uses_bird_emoji_for_normal_velocity(self):
        with patch("modules.twitter_apify.alert_allowed", return_value=True):
            with patch("modules.twitter_apify.calculate_priority_score", return_value=5):
                with patch("modules.twitter_apify.score_bar", return_value="███"):
                    with patch("modules.database.get_keyword_source_count", return_value=2):
                        with patch("modules.twitter_apify.send_message") as mock_sm:
                            _send_twitter_apify_alert("ghost", 200.0, 10, 5, self._tweets())
                            text = mock_sm.call_args[0][0]
        assert "🐦" in text

    def test_includes_up_to_3_tweet_previews(self):
        tweets = self._tweets(5)
        with patch("modules.twitter_apify.alert_allowed", return_value=True):
            with patch("modules.twitter_apify.calculate_priority_score", return_value=5):
                with patch("modules.twitter_apify.score_bar", return_value=""):
                    with patch("modules.database.get_keyword_source_count", return_value=1):
                        with patch("modules.twitter_apify.send_message") as mock_sm:
                            _send_twitter_apify_alert("ghost", 300.0, 10, 5, tweets)
                            text = mock_sm.call_args[0][0]
        # Count bullet points for tweet previews
        assert text.count("• ") == 3

    def test_returns_send_message_result(self):
        with patch("modules.twitter_apify.alert_allowed", return_value=True):
            with patch("modules.twitter_apify.calculate_priority_score", return_value=5):
                with patch("modules.twitter_apify.score_bar", return_value=""):
                    with patch("modules.database.get_keyword_source_count", return_value=1):
                        with patch("modules.twitter_apify.send_message", return_value=True):
                            result = _send_twitter_apify_alert("ghost", 300.0, 10, 5, self._tweets())
        assert result is True


# ---------------------------------------------------------------------------
# run_twitter_apify_detector
# ---------------------------------------------------------------------------


class TestRunTwitterApifyDetector:
    def _cfg(self, keywords=None, **overrides):
        return {
            "keywords": keywords or ["paranormal", "haunted"],
            "twitter": {"tweets_per_keyword": 50},
            "trend_detector": {
                "min_mentions_to_track": 3,
                "velocity_threshold_longform": 300,
            },
            "priority_score": {"min_score": 1},
            **overrides,
        }

    def test_disabled_when_no_apify_key(self, capsys):
        os.environ.pop("APIFY_API_KEY", None)
        with patch.dict(os.environ, {}, clear=True):
            with patch("modules.twitter_apify.run_actor") as mock_ra:
                run_twitter_apify_detector(self._cfg())
        mock_ra.assert_not_called()

    def test_skips_keyword_below_min_mentions(self):
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            # Only 2 tweets returned, min_mentions=3
            with patch("modules.twitter_apify._search_tweets", return_value=[{"id": "1", "text": "a"}, {"id": "2", "text": "b"}]):
                with patch("modules.twitter_apify.save_keyword_count") as mock_save:
                    run_twitter_apify_detector(self._cfg(keywords=["ghost"]))
        mock_save.assert_not_called()

    def test_saves_keyword_count(self):
        tweets = [{"id": str(i), "text": "t"} for i in range(5)]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.twitter_apify._search_tweets", return_value=tweets):
                with patch("modules.twitter_apify.get_keyword_counts", return_value=[]):
                    with patch("modules.twitter_apify.save_keyword_count") as mock_save:
                        run_twitter_apify_detector(self._cfg(keywords=["ghost"]))
        mock_save.assert_called_once_with("ghost", "twitter", 5)

    def test_no_alert_on_first_run_no_baseline(self):
        tweets = [{"id": str(i), "text": "t"} for i in range(5)]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.twitter_apify._search_tweets", return_value=tweets):
                with patch("modules.twitter_apify.get_keyword_counts", return_value=[]):
                    with patch("modules.twitter_apify.save_keyword_count"):
                        with patch("modules.twitter_apify._send_twitter_apify_alert") as mock_alert:
                            run_twitter_apify_detector(self._cfg(keywords=["ghost"]))
        mock_alert.assert_not_called()

    def test_sends_alert_when_velocity_above_threshold(self):
        tweets = [{"id": str(i), "text": "t"} for i in range(10)]
        prev = [{"count": 3}]  # velocity = (10-3)/3*100 = 233% < 300 — let me use 1 → (10-1)/1=900%
        prev = [{"count": 1}]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.twitter_apify._search_tweets", return_value=tweets):
                with patch("modules.twitter_apify.get_keyword_counts", return_value=prev):
                    with patch("modules.twitter_apify.save_keyword_count"):
                        with patch("modules.twitter_apify.was_alert_sent_recently", return_value=False):
                            with patch("modules.twitter_apify.mark_alert_sent"):
                                with patch("modules.twitter_apify._send_twitter_apify_alert") as mock_alert:
                                    run_twitter_apify_detector(self._cfg(keywords=["ghost"]))
        mock_alert.assert_called_once()

    def test_no_alert_below_threshold(self):
        tweets = [{"id": str(i), "text": "t"} for i in range(4)]
        prev = [{"count": 3}]  # velocity = (4-3)/3*100 = 33% < 300
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.twitter_apify._search_tweets", return_value=tweets):
                with patch("modules.twitter_apify.get_keyword_counts", return_value=prev):
                    with patch("modules.twitter_apify.save_keyword_count"):
                        with patch("modules.twitter_apify._send_twitter_apify_alert") as mock_alert:
                            run_twitter_apify_detector(self._cfg(keywords=["ghost"]))
        mock_alert.assert_not_called()

    def test_no_duplicate_alert_within_cooldown(self):
        tweets = [{"id": str(i), "text": "t"} for i in range(10)]
        prev = [{"count": 1}]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.twitter_apify._search_tweets", return_value=tweets):
                with patch("modules.twitter_apify.get_keyword_counts", return_value=prev):
                    with patch("modules.twitter_apify.save_keyword_count"):
                        with patch("modules.twitter_apify.was_alert_sent_recently", return_value=True):
                            with patch("modules.twitter_apify._send_twitter_apify_alert") as mock_alert:
                                run_twitter_apify_detector(self._cfg(keywords=["ghost"]))
        mock_alert.assert_not_called()

    def test_processes_multiple_keywords(self):
        tweets = [{"id": str(i), "text": "t"} for i in range(5)]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.twitter_apify._search_tweets", return_value=tweets) as mock_st:
                with patch("modules.twitter_apify.get_keyword_counts", return_value=[]):
                    with patch("modules.twitter_apify.save_keyword_count"):
                        run_twitter_apify_detector(self._cfg(keywords=["ghost", "paranormal", "occult"]))
        assert mock_st.call_count == 3
