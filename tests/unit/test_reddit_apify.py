"""Unit tests for modules/reddit_apify.py"""
import os
from unittest.mock import patch

from modules.reddit_apify import (
    _fetch_subreddit_posts,
    _count_mentions,
    _select_subreddits,
    run_reddit_apify_detector,
)


# ---------------------------------------------------------------------------
# _fetch_subreddit_posts
# ---------------------------------------------------------------------------

class TestFetchSubredditPosts:
    def test_passes_timeout_300(self):
        """run_actor must be called with timeout=300 (not the 120s default)."""
        with patch("modules.reddit_apify.run_actor", return_value=[]) as mock_run:
            _fetch_subreddit_posts("paranormal", 40)
            _, kwargs = mock_run.call_args
            assert kwargs.get("timeout") == 300, "timeout must be 300 to avoid TIMED-OUT on slow actor"

    def test_strips_r_prefix(self):
        with patch("modules.reddit_apify.run_actor", return_value=[]) as mock_run:
            _fetch_subreddit_posts("r/paranormal", 10)
            input_data = mock_run.call_args[0][1]
            url = input_data["startUrls"][0]["url"]
            assert "/r/paranormal/" in url
            assert "/r/r/paranormal/" not in url

    def test_returns_mapped_posts(self):
        raw = [
            {"id": "abc", "title": "Haunted house", "text": "spooky"},
            {"postId": "def", "title": "Ghost", "selftext": "scary"},
        ]
        with patch("modules.reddit_apify.run_actor", return_value=raw):
            posts = _fetch_subreddit_posts("paranormal", 40)
        assert len(posts) == 2
        assert posts[0] == {"id": "abc", "title": "Haunted house", "text": "spooky"}
        assert posts[1]["id"] == "def"

    def test_skips_items_without_id(self):
        raw = [{"title": "No ID post", "text": "orphan"}]
        with patch("modules.reddit_apify.run_actor", return_value=raw):
            posts = _fetch_subreddit_posts("paranormal", 40)
        assert posts == []

    def test_empty_actor_response(self):
        with patch("modules.reddit_apify.run_actor", return_value=[]):
            posts = _fetch_subreddit_posts("paranormal", 40)
        assert posts == []

    def test_max_items_passed_to_actor(self):
        with patch("modules.reddit_apify.run_actor", return_value=[]) as mock_run:
            _fetch_subreddit_posts("paranormal", 25)
            input_data = mock_run.call_args[0][1]
            assert input_data["maxItems"] == 25


# ---------------------------------------------------------------------------
# _count_mentions
# ---------------------------------------------------------------------------

class TestCountMentions:
    def test_counts_keyword_in_title(self):
        posts = [{"title": "Paranormal activity", "text": ""}]
        assert _count_mentions(posts, "paranormal") == 1

    def test_counts_keyword_in_text(self):
        posts = [{"title": "Strange", "text": "real paranormal event"}]
        assert _count_mentions(posts, "paranormal") == 1

    def test_case_insensitive(self):
        posts = [
            {"title": "PARANORMAL", "text": ""},
            {"title": "other", "text": "Paranormal event"},
        ]
        assert _count_mentions(posts, "paranormal") == 2

    def test_no_match(self):
        posts = [{"title": "Football", "text": "goals"}]
        assert _count_mentions(posts, "ghost") == 0

    def test_empty_posts(self):
        assert _count_mentions([], "ghost") == 0


# ---------------------------------------------------------------------------
# _select_subreddits
# ---------------------------------------------------------------------------

class TestSelectSubreddits:
    def test_returns_all_when_per_run_gte_total(self):
        subs = ["a", "b", "c"]
        assert _select_subreddits(subs, 5) == subs

    def test_returns_chunk_of_correct_size(self):
        subs = list("abcdefghij")
        result = _select_sureddits_safe(subs, 4)
        assert len(result) == 4

    def test_per_run_zero_returns_all(self):
        subs = ["a", "b"]
        assert _select_subreddits(subs, 0) == subs

    def test_deterministic_for_same_week(self):
        subs = list("abcdefgh")
        r1 = _select_subreddits(subs, 3)
        r2 = _select_subreddits(subs, 3)
        assert r1 == r2


def _select_sureddits_safe(subs, per_run):
    """Alias to avoid typo in test."""
    return _select_subreddits(subs, per_run)


# ---------------------------------------------------------------------------
# run_reddit_apify_detector — guard: no APIFY_API_KEY
# ---------------------------------------------------------------------------

class TestRunRedditApifyDetector:
    def test_disabled_without_api_key(self, capsys):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APIFY_API_KEY", None)
            run_reddit_apify_detector({})
        out = capsys.readouterr().out
        assert "disabilitato" in out

    def test_runs_with_api_key(self, clean_db):
        config = {
            "trend_detector": {"velocity_threshold_longform": 300, "min_mentions_to_track": 1},
            "reddit": {"subreddits_per_run": 2, "posts_per_subreddit": 10},
            "keywords": ["paranormal"],
            "subreddits": ["paranormal", "occult"],
        }
        posts = [{"id": "x1", "title": "paranormal event", "text": ""}]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test-key"}):
            with patch("modules.reddit_apify.run_actor", return_value=posts):
                run_reddit_apify_detector(config)
        # No exception = pass

    def test_timeout_propagates_in_full_run(self, clean_db):
        """Verify timeout=300 is used in a real run (not just unit call)."""
        config = {
            "trend_detector": {"velocity_threshold_longform": 300, "min_mentions_to_track": 1},
            "reddit": {"subreddits_per_run": 1, "posts_per_subreddit": 5},
            "keywords": ["ghost"],
            "subreddits": ["Ghosts"],
        }
        with patch.dict(os.environ, {"APIFY_API_KEY": "test-key"}):
            with patch("modules.reddit_apify.run_actor", return_value=[]) as mock_run:
                run_reddit_apify_detector(config)
        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 300
