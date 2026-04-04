"""Unit tests for modules/discovery_advisor.py"""
from unittest.mock import patch
from modules.database import (
    get_connection,
    save_discovery_suggestion,
    get_discovery_suggestions,
    get_discovery_pending_count,
    update_discovery_suggestion_status,
)
from modules.discovery_advisor import (
    _extract_hashtags_from_captions,
    _extract_subreddits_from_posts,
    _extract_hashtags_from_tweets,
    _build_and_save_suggestions,
    _send_telegram_discovery_digest,
    run_discovery_advisor,
)


# ── DB helper ────────────────────────────────────────────────────────────────

def _insert_outperformer(platform, title):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO apify_outperformer_videos (platform, video_id, username, title, detected_at) "
        "VALUES (?, ?, 'user', ?, datetime('now'))",
        (platform, f"vid_{abs(hash(title))}_{platform}", title),
    )
    conn.commit()
    conn.close()


def _insert_reddit_post(post_id, title):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO reddit_posts (post_id, subreddit, title, url, scraped_at) "
        "VALUES (?, 'paranormal', ?, '', datetime('now'))",
        (post_id, title),
    )
    conn.commit()
    conn.close()


def _insert_tweet(tweet_id, text):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO twitter_tweets "
        "(tweet_id, keyword, text, url, scraped_at) "
        "VALUES (?, 'paranormal', ?, '', datetime('now'))",
        (tweet_id, text),
    )
    conn.commit()
    conn.close()


def _seed_config_list(list_key, *values):
    from modules.database import config_list_add
    for v in values:
        config_list_add(list_key, v)


# ── DB functions ─────────────────────────────────────────────────────────────

class TestSaveDiscoverySuggestion:
    def test_inserts_pending(self):
        save_discovery_suggestion("tiktok_hashtag", "ghosthunter", "tiktok_caption", 5)
        rows = get_discovery_suggestions(status="pending")
        assert any(r["value"] == "ghosthunter" for r in rows)

    def test_accumulates_score_on_conflict(self):
        save_discovery_suggestion("tiktok_hashtag", "haunted", "tiktok_caption", 3)
        save_discovery_suggestion("tiktok_hashtag", "haunted", "tiktok_caption", 4)
        rows = get_discovery_suggestions(status="pending")
        row = next(r for r in rows if r["value"] == "haunted")
        assert row["score"] == 7

    def test_does_not_reset_status_on_conflict(self):
        save_discovery_suggestion("subreddit", "paranormal", "reddit_post", 2)
        update_discovery_suggestion_status(
            get_discovery_suggestions()[0]["id"], "accepted"
        )
        save_discovery_suggestion("subreddit", "paranormal", "reddit_post", 1)
        rows = get_discovery_suggestions(status="all")
        row = next(r for r in rows if r["value"] == "paranormal")
        assert row["status"] == "accepted"

    def test_normalises_value_lowercase(self):
        save_discovery_suggestion("subreddit", "Ghosts", "reddit_post", 2)
        rows = get_discovery_suggestions(status="pending")
        assert any(r["value"] == "ghosts" for r in rows)


class TestGetDiscoverySuggestions:
    def test_empty_returns_list(self):
        assert get_discovery_suggestions() == []

    def test_filters_by_status(self):
        save_discovery_suggestion("keyword", "occult", "twitter_tweet", 3)
        pending = get_discovery_suggestions(status="pending")
        assert len(pending) == 1
        accepted = get_discovery_suggestions(status="accepted")
        assert len(accepted) == 0

    def test_ordered_by_score_desc(self):
        save_discovery_suggestion("keyword", "low", "twitter_tweet", 2)
        save_discovery_suggestion("keyword", "high", "twitter_tweet", 10)
        rows = get_discovery_suggestions()
        assert rows[0]["value"] == "high"

    def test_all_status_returns_everything(self):
        save_discovery_suggestion("keyword", "kw1", "twitter_tweet", 1)
        update_discovery_suggestion_status(get_discovery_suggestions()[0]["id"], "rejected")
        save_discovery_suggestion("keyword", "kw2", "twitter_tweet", 2)
        rows = get_discovery_suggestions(status="all")
        assert len(rows) == 2


class TestGetDiscoveryPendingCount:
    def test_zero_when_empty(self):
        assert get_discovery_pending_count() == 0

    def test_counts_only_pending(self):
        save_discovery_suggestion("keyword", "a", "twitter_tweet", 1)
        save_discovery_suggestion("keyword", "b", "twitter_tweet", 2)
        assert get_discovery_pending_count() == 2
        update_discovery_suggestion_status(get_discovery_suggestions()[0]["id"], "accepted")
        assert get_discovery_pending_count() == 1


# ── Extraction helpers ────────────────────────────────────────────────────────

class TestExtractHashtagsFromCaptions:
    def test_empty_table(self):
        counter = _extract_hashtags_from_captions("tiktok")
        assert len(counter) == 0

    def test_extracts_hashtags(self):
        _insert_outperformer("tiktok", "Check this out #paranormal #haunted visit now")
        counter = _extract_hashtags_from_captions("tiktok")
        assert counter["paranormal"] == 1
        assert counter["haunted"] == 1

    def test_ignores_other_platform(self):
        _insert_outperformer("instagram", "#ghosthunter content")
        counter = _extract_hashtags_from_captions("tiktok")
        assert "ghosthunter" not in counter

    def test_case_normalised(self):
        _insert_outperformer("tiktok", "#Paranormal #HAUNTED")
        counter = _extract_hashtags_from_captions("tiktok")
        assert "paranormal" in counter
        assert "haunted" in counter

    def test_skips_short_tags(self):
        _insert_outperformer("tiktok", "#ok #ab #longertag")
        counter = _extract_hashtags_from_captions("tiktok")
        assert "ok" not in counter
        assert "ab" not in counter
        assert "longertag" in counter

    def test_counts_multiple_occurrences(self):
        _insert_outperformer("tiktok", "#haunted place")
        _insert_outperformer("tiktok", "#haunted house again")
        counter = _extract_hashtags_from_captions("tiktok")
        assert counter["haunted"] == 2


class TestExtractSubredditsFromPosts:
    def test_empty_table(self):
        assert len(_extract_subreddits_from_posts()) == 0

    def test_extracts_from_title(self):
        _insert_reddit_post("p1", "Check r/paranormal and r/Ghosts")
        counter = _extract_subreddits_from_posts()
        assert "paranormal" in counter
        assert "Ghosts" in counter

    def test_counts_repeated(self):
        _insert_reddit_post("p3", "r/haunted is great")
        _insert_reddit_post("p4", "Join r/haunted now")
        counter = _extract_subreddits_from_posts()
        assert counter["haunted"] == 2


class TestExtractHashtagsFromTweets:
    def test_empty_table(self):
        assert len(_extract_hashtags_from_tweets()) == 0

    def test_extracts_hashtags(self):
        _insert_tweet("t1", "Amazing content #paranormal #occult")
        counter = _extract_hashtags_from_tweets()
        assert "paranormal" in counter
        assert "occult" in counter

    def test_skips_short_tags(self):
        _insert_tweet("t2", "#ok #abc #longkeyword")
        counter = _extract_hashtags_from_tweets()
        assert "ok" not in counter

    def test_skips_stopwords(self):
        _insert_tweet("t3", "#that #with #paranormalactivity")
        counter = _extract_hashtags_from_tweets()
        assert "that" not in counter
        assert "with" not in counter
        assert "paranormalactivity" in counter


# ── Build and save ────────────────────────────────────────────────────────────

class TestBuildAndSaveSuggestions:
    def test_returns_empty_when_no_data(self):
        result = _build_and_save_suggestions()
        assert all(len(v) == 0 for v in result.values())

    def test_skips_already_existing_hashtag(self):
        _seed_config_list("tiktok_hashtags", "paranormal")
        _insert_outperformer("tiktok", "#paranormal #paranormal")  # only 1 video but 2 tags
        result = _build_and_save_suggestions()
        values = [r["value"] for r in result["tiktok_hashtag"]]
        assert "paranormal" not in values

    def test_suggests_new_hashtag_above_min_score(self):
        _insert_outperformer("tiktok", "#newhashtag content")
        _insert_outperformer("tiktok", "#newhashtag more content")
        result = _build_and_save_suggestions()
        values = [r["value"] for r in result["tiktok_hashtag"]]
        assert "newhashtag" in values

    def test_does_not_suggest_below_min_score(self):
        _insert_outperformer("tiktok", "#rarehashtag once only")
        result = _build_and_save_suggestions()
        values = [r["value"] for r in result["tiktok_hashtag"]]
        assert "rarehashtag" not in values

    def test_persists_subreddit_suggestion(self):
        _insert_reddit_post("p1", "r/newsubreddit link")
        _insert_reddit_post("p2", "r/newsubreddit again")
        _build_and_save_suggestions()
        rows = get_discovery_suggestions(status="pending")
        assert any(r["type"] == "subreddit" and r["value"] == "newsubreddit" for r in rows)

    def test_persists_keyword_suggestion_from_tweets(self):
        _insert_tweet("t1", "#spookyszn vibes")
        _insert_tweet("t2", "#spookyszn trending")
        _build_and_save_suggestions()
        rows = get_discovery_suggestions(status="pending")
        assert any(r["type"] == "keyword" and r["value"] == "spookyszn" for r in rows)


# ── Telegram digest ───────────────────────────────────────────────────────────

class TestSendTelegramDiscoveryDigest:
    @patch("modules.discovery_advisor.send_message")
    def test_sends_nothing_when_empty(self, mock_send):
        _send_telegram_discovery_digest({
            "tiktok_hashtag": [], "instagram_hashtag": [], "subreddit": [], "keyword": []
        })
        mock_send.assert_not_called()

    @patch("modules.discovery_advisor.send_message")
    def test_sends_telegram_with_suggestions(self, mock_send):
        suggestions = {
            "tiktok_hashtag": [{"value": "ghosthunter", "score": 5}],
            "instagram_hashtag": [],
            "subreddit": [{"value": "darkmystery", "score": 3}],
            "keyword": [],
        }
        _send_telegram_discovery_digest(suggestions)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "ghosthunter" in msg
        assert "darkmystery" in msg
        assert "DISCOVERY" in msg

    @patch("modules.discovery_advisor.send_message")
    def test_caps_at_8_per_type(self, mock_send):
        items = [{"value": f"tag{i}", "score": i + 1} for i in range(15)]
        suggestions = {
            "tiktok_hashtag": items, "instagram_hashtag": [], "subreddit": [], "keyword": []
        }
        _send_telegram_discovery_digest(suggestions)
        msg = mock_send.call_args[0][0]
        assert "e altri 7" in msg


# ── run_discovery_advisor ─────────────────────────────────────────────────────

class TestRunDiscoveryAdvisor:
    @patch("modules.discovery_advisor.send_message")
    def test_disabled_in_config_skips(self, mock_send):
        run_discovery_advisor({"discovery_advisor": {"enabled": False}})
        mock_send.assert_not_called()
        assert get_discovery_pending_count() == 0

    @patch("modules.discovery_advisor.send_message")
    def test_runs_with_empty_data(self, mock_send):
        run_discovery_advisor({})
        mock_send.assert_not_called()  # nessun suggerimento → nessun messaggio

    @patch("modules.discovery_advisor.send_message")
    def test_builds_and_sends_when_data_available(self, mock_send):
        _insert_outperformer("tiktok", "#newtag content A")
        _insert_outperformer("tiktok", "#newtag content B")
        run_discovery_advisor({})
        assert get_discovery_pending_count() > 0
        mock_send.assert_called_once()

    @patch("modules.discovery_advisor.send_message")
    def test_default_enabled_true(self, mock_send):
        """Config vuota → enabled default True → esegue."""
        run_discovery_advisor({})
        # Nessun crash
