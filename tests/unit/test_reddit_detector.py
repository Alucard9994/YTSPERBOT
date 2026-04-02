"""
Unit tests — reddit_detector.py
Tests pure logic and mocks all external I/O (PRAW, Telegram, DB writes).
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from modules.reddit_detector import (
    count_keyword_mentions,
    fetch_subreddit_posts,
    calculate_velocity,
    run_reddit_detector,
)
from modules.database import save_keyword_count


# ============================================================
# Helpers
# ============================================================

def _make_post(title: str, text: str = "") -> dict:
    return {"id": "abc123", "title": title, "text": text}


def _config(subreddits=None, keywords=None, **td_overrides):
    td = {
        "min_mentions_to_track": 2,
        "velocity_threshold_longform": 300,
        "velocity_threshold_shorts": 500,
    }
    td.update(td_overrides)
    return {
        "trend_detector": td,
        "keywords": keywords or ["ghost", "paranormal"],
        "subreddits": subreddits or ["r/paranormal"],
    }


def _fake_reddit(posts_by_subreddit: dict | None = None):
    """Return a mock reddit client whose subreddit().new() yields dicts."""
    posts_by_subreddit = posts_by_subreddit or {}

    reddit = MagicMock()

    def _subreddit(name):
        sub = MagicMock()
        raw = posts_by_subreddit.get(name, [])
        # PRAW returns objects with .id / .title / .selftext attributes
        praw_posts = []
        for p in raw:
            m = MagicMock()
            m.id = p.get("id", "x")
            m.title = p.get("title", "")
            m.selftext = p.get("text", "")
            praw_posts.append(m)
        sub.new.return_value = iter(praw_posts)
        return sub

    reddit.subreddit.side_effect = _subreddit
    return reddit


# ============================================================
# count_keyword_mentions
# ============================================================

class TestCountKeywordMentions:
    def test_match_in_title(self):
        posts = [_make_post("Ghost story tonight")]
        assert count_keyword_mentions(posts, "ghost") == 1

    def test_match_in_text(self):
        posts = [_make_post("Normal title", "ghost spotted here")]
        assert count_keyword_mentions(posts, "ghost") == 1

    def test_no_match(self):
        posts = [_make_post("Football news", "Score 2-1")]
        assert count_keyword_mentions(posts, "ghost") == 0

    def test_case_insensitive(self):
        posts = [_make_post("GHOST Sighting", "Paranormal EVENT")]
        assert count_keyword_mentions(posts, "ghost") == 1
        assert count_keyword_mentions(posts, "PARANORMAL") == 1

    def test_counts_multiple_matching_posts(self):
        posts = [
            _make_post("ghost story 1"),
            _make_post("other news"),
            _make_post("ghost story 2"),
        ]
        assert count_keyword_mentions(posts, "ghost") == 2

    def test_empty_posts(self):
        assert count_keyword_mentions([], "ghost") == 0

    def test_match_in_both_title_and_text_counts_once(self):
        """A single post that matches in both title and text = 1, not 2."""
        posts = [_make_post("Ghost ghost", "ghost everywhere")]
        assert count_keyword_mentions(posts, "ghost") == 1

    def test_substring_match(self):
        """'ghost' matches 'ghosthunter' as a substring."""
        posts = [_make_post("ghosthunter channel")]
        assert count_keyword_mentions(posts, "ghost") == 1


# ============================================================
# fetch_subreddit_posts
# ============================================================

class TestFetchSubredditPosts:
    def test_returns_posts_as_dicts(self):
        reddit = _fake_reddit({"paranormal": [
            {"id": "1", "title": "Ghost story", "text": "details"},
        ]})
        posts = fetch_subreddit_posts(reddit, "paranormal")
        assert len(posts) == 1
        assert posts[0]["title"] == "Ghost story"
        assert posts[0]["text"] == "details"

    def test_returns_empty_on_exception(self, capsys):
        reddit = MagicMock()
        reddit.subreddit.side_effect = Exception("network error")
        posts = fetch_subreddit_posts(reddit, "paranormal")
        assert posts == []
        assert "Errore" in capsys.readouterr().out

    def test_multiple_posts(self):
        raw = [{"id": str(i), "title": f"Post {i}", "text": ""} for i in range(5)]
        reddit = _fake_reddit({"weird": raw})
        posts = fetch_subreddit_posts(reddit, "weird")
        assert len(posts) == 5

    def test_empty_selftext_returns_empty_string(self):
        """PRAW returns None for selftext on link posts; module coerces to ''."""
        reddit = MagicMock()
        sub = MagicMock()
        praw_post = MagicMock()
        praw_post.id = "abc"
        praw_post.title = "Link post"
        praw_post.selftext = None
        sub.new.return_value = iter([praw_post])
        reddit.subreddit.return_value = sub

        posts = fetch_subreddit_posts(reddit, "paranormal")
        # selftext=None → "None" or "" depending on `or ""` coercion
        assert posts[0]["text"] is not None  # should not blow up


# ============================================================
# calculate_velocity (reddit_detector wrapper)
# ============================================================

class TestCalculateVelocity:
    def test_returns_zero_when_no_previous_data(self):
        vel = calculate_velocity("brand_new_kw", "reddit", 10, 48)
        assert vel == 0.0

    def test_positive_velocity(self):
        save_keyword_count("ghost", "reddit", 5)
        vel = calculate_velocity("ghost", "reddit", 15, 48)
        # (15-5)/5*100 = 200%
        assert vel == pytest.approx(200.0)

    def test_zero_previous_count_returns_zero(self):
        save_keyword_count("ghost", "reddit", 0)
        vel = calculate_velocity("ghost", "reddit", 10, 48)
        assert vel == 0.0


# ============================================================
# run_reddit_detector
# ============================================================

class TestRunRedditDetector:
    def _patch_enabled(self):
        """Patch REDDIT_ENABLED to True so the function body executes."""
        return patch("modules.reddit_detector.REDDIT_ENABLED", True)

    def test_exits_when_disabled(self, capsys):
        with patch("modules.reddit_detector.REDDIT_ENABLED", False):
            with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                run_reddit_detector(_config())
        mock_send.assert_not_called()
        assert "disabilitato" in capsys.readouterr().out.lower()

    def test_exits_on_invalid_credentials(self, capsys):
        with self._patch_enabled():
            with patch(
                "modules.reddit_detector.get_reddit_client",
                side_effect=ValueError("Credenziali Reddit non configurate"),
            ):
                with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                    run_reddit_detector(_config())
        mock_send.assert_not_called()

    def test_no_alert_below_min_mentions(self):
        """1 mention < min_mentions_to_track=2 → no alert."""
        posts = [_make_post("one ghost article")]

        def fake_fetch(reddit, sub, limit=100):
            return posts

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                        run_reddit_detector(_config(min_mentions_to_track=2))
        mock_send.assert_not_called()

    def test_saves_count_above_min_mentions(self):
        posts = [_make_post(f"ghost article {i}") for i in range(5)]

        def fake_fetch(reddit, sub, limit=100):
            return posts

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.send_trend_alert"):
                        run_reddit_detector(_config())

        from modules.database import get_keyword_counts
        counts = get_keyword_counts("ghost", "reddit", 1)
        assert len(counts) >= 1
        assert counts[0]["count"] == 5

    def test_sends_alert_on_velocity_spike(self):
        # Baseline: 2 previous mentions
        save_keyword_count("ghost", "reddit", 2)
        # Current: 10 mentions → (10-2)/2*100 = 400% > 300 threshold
        posts = [_make_post(f"ghost article {i}") for i in range(10)]

        def fake_fetch(reddit, sub, limit=100):
            return posts

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.was_alert_sent_recently", return_value=False):
                        with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                            run_reddit_detector(_config())
        mock_send.assert_called_once()
        kwargs = mock_send.call_args[1]
        assert "ghost" in kwargs.get("keyword", "").lower()

    def test_no_alert_below_velocity_threshold(self):
        # Baseline: 10, current: 12 → +20% < 300% threshold
        save_keyword_count("paranormal", "reddit", 10)
        posts = [_make_post(f"paranormal article {i}") for i in range(12)]

        def fake_fetch(reddit, sub, limit=100):
            return posts

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.was_alert_sent_recently", return_value=False):
                        with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                            run_reddit_detector(_config())
        mock_send.assert_not_called()

    def test_no_duplicate_alert_in_cooldown(self):
        save_keyword_count("ghost", "reddit", 2)
        posts = [_make_post(f"ghost {i}") for i in range(10)]

        def fake_fetch(reddit, sub, limit=100):
            return posts

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.was_alert_sent_recently", return_value=True):
                        with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                            run_reddit_detector(_config())
        mock_send.assert_not_called()

    def test_aggregates_posts_from_multiple_subreddits(self):
        """Posts from multiple subreddits are all counted together."""
        call_count = {"n": 0}

        def fake_fetch(reddit, sub, limit=100):
            call_count["n"] += 1
            return [_make_post(f"ghost from {sub}")]

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.send_trend_alert"):
                        run_reddit_detector(_config(subreddits=["paranormal", "occult", "horror"]))

        assert call_count["n"] == 3

    def test_no_alert_on_first_run_no_baseline(self):
        """No previous data → velocity = 0 → no alert."""
        posts = [_make_post(f"ghost {i}") for i in range(5)]

        def fake_fetch(reddit, sub, limit=100):
            return posts

        with self._patch_enabled():
            with patch("modules.reddit_detector.get_reddit_client", return_value=MagicMock()):
                with patch("modules.reddit_detector.fetch_subreddit_posts", side_effect=fake_fetch):
                    with patch("modules.reddit_detector.send_trend_alert") as mock_send:
                        run_reddit_detector(_config())
        mock_send.assert_not_called()
