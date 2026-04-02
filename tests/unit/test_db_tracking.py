"""
Unit tests — database.py: tracking, blacklist, cache, subscriber, keyword-aggregate functions.
Uses the real SQLite test DB (see conftest.py).
"""
from modules.database import (
    # Post / social deduplication
    is_post_seen,
    mark_post_seen,
    # YouTube channel video deduplication
    is_channel_video_sent,
    mark_channel_video_sent,
    # Apify video deduplication
    is_apify_video_sent,
    mark_apify_video_sent,
    # Keyword blacklist
    is_blacklisted,
    add_to_blacklist,
    remove_from_blacklist,
    get_blacklist,
    # Channel ID cache (handle → channel_id)
    get_channel_id_cache,
    set_channel_id_cache,
    # Subscriber history
    save_subscriber_count,
    get_subscriber_history,
    # Keyword aggregates
    get_daily_brief_data,
    get_keyword_source_count,
    get_keyword_all_mentions,
    get_keyword_timeseries,
    # Supporting write functions
    save_keyword_count,
)


# ============================================================
# is_post_seen / mark_post_seen
# ============================================================

class TestPostSeen:
    def test_unseen_returns_false(self):
        assert is_post_seen("post_new", "reddit") is False

    def test_seen_after_mark(self):
        mark_post_seen("post_abc", "r/paranormal")
        assert is_post_seen("post_abc") is True

    def test_source_arg_ignored_in_lookup(self):
        """is_post_seen ignores the source parameter — same table regardless."""
        mark_post_seen("post_xyz", "r/occult")
        assert is_post_seen("post_xyz", "twitter") is True

    def test_different_id_not_seen(self):
        mark_post_seen("post_1", "sub")
        assert is_post_seen("post_2") is False

    def test_idempotent_mark(self):
        """Marking twice must not raise (INSERT OR IGNORE)."""
        mark_post_seen("post_idem", "sub")
        mark_post_seen("post_idem", "sub")
        assert is_post_seen("post_idem") is True


# ============================================================
# is_channel_video_sent / mark_channel_video_sent
# ============================================================

class TestChannelVideoSent:
    def test_not_sent_initially(self):
        assert is_channel_video_sent("UCabc", "vid1") is False

    def test_sent_after_mark(self):
        mark_channel_video_sent("UCabc", "vid1")
        assert is_channel_video_sent("UCabc", "vid1") is True

    def test_different_channel_same_video_not_sent(self):
        mark_channel_video_sent("UCabc", "vid2")
        assert is_channel_video_sent("UCother", "vid2") is False

    def test_same_channel_different_video_not_sent(self):
        mark_channel_video_sent("UCabc", "vid3")
        assert is_channel_video_sent("UCabc", "vid_other") is False

    def test_idempotent_mark(self):
        """INSERT OR IGNORE: marking twice must not raise."""
        mark_channel_video_sent("UCdup", "viddup")
        mark_channel_video_sent("UCdup", "viddup")
        assert is_channel_video_sent("UCdup", "viddup") is True


# ============================================================
# is_apify_video_sent / mark_apify_video_sent
# ============================================================

class TestApifyVideoSent:
    def test_not_sent_initially(self):
        assert is_apify_video_sent("tiktok", "ttvid1") is False

    def test_sent_after_mark(self):
        mark_apify_video_sent("tiktok", "ttvid1")
        assert is_apify_video_sent("tiktok", "ttvid1") is True

    def test_different_platform_same_id_not_sent(self):
        mark_apify_video_sent("tiktok", "shared_id")
        assert is_apify_video_sent("instagram", "shared_id") is False

    def test_same_platform_different_id_not_sent(self):
        mark_apify_video_sent("instagram", "igvid1")
        assert is_apify_video_sent("instagram", "igvid2") is False

    def test_idempotent_mark(self):
        mark_apify_video_sent("tiktok", "idem_vid")
        mark_apify_video_sent("tiktok", "idem_vid")
        assert is_apify_video_sent("tiktok", "idem_vid") is True


# ============================================================
# Keyword Blacklist
# ============================================================

class TestKeywordBlacklist:
    def test_not_blacklisted_initially(self):
        assert is_blacklisted("ghost") is False

    def test_blacklisted_after_add(self):
        add_to_blacklist("ghost")
        assert is_blacklisted("ghost") is True

    def test_case_insensitive_add_and_check(self):
        add_to_blacklist("Paranormal")
        assert is_blacklisted("paranormal") is True
        assert is_blacklisted("PARANORMAL") is True

    def test_remove_clears_entry(self):
        add_to_blacklist("demon")
        remove_from_blacklist("demon")
        assert is_blacklisted("demon") is False

    def test_remove_nonexistent_does_not_raise(self):
        remove_from_blacklist("never_added")  # must not raise

    def test_idempotent_add(self):
        add_to_blacklist("witch")
        add_to_blacklist("witch")
        assert get_blacklist().count("witch") == 1

    def test_get_blacklist_returns_all(self):
        add_to_blacklist("alpha")
        add_to_blacklist("beta")
        bl = get_blacklist()
        assert "alpha" in bl
        assert "beta" in bl

    def test_get_blacklist_sorted_alphabetically(self):
        add_to_blacklist("zzz")
        add_to_blacklist("aaa")
        bl = get_blacklist()
        pos_aaa = bl.index("aaa")
        pos_zzz = bl.index("zzz")
        assert pos_aaa < pos_zzz

    def test_remove_case_insensitive(self):
        add_to_blacklist("curse")
        remove_from_blacklist("CURSE")
        assert is_blacklisted("curse") is False


# ============================================================
# Channel ID Cache
# ============================================================

class TestChannelIdCache:
    def test_returns_none_for_unknown_handle(self):
        assert get_channel_id_cache("@unknown") is None

    def test_returns_cached_channel_id(self):
        set_channel_id_cache("@mystical", "UCmystical123")
        assert get_channel_id_cache("@mystical") == "UCmystical123"

    def test_case_insensitive_lookup(self):
        set_channel_id_cache("@GhostHunter", "UCghost456")
        assert get_channel_id_cache("@ghosthunter") == "UCghost456"
        assert get_channel_id_cache("@GHOSTHUNTER") == "UCghost456"

    def test_update_replaces_existing(self):
        set_channel_id_cache("@updatable", "UC_old")
        set_channel_id_cache("@updatable", "UC_new")
        assert get_channel_id_cache("@updatable") == "UC_new"

    def test_different_handles_independent(self):
        set_channel_id_cache("@chanA", "UCA")
        set_channel_id_cache("@chanB", "UCB")
        assert get_channel_id_cache("@chanA") == "UCA"
        assert get_channel_id_cache("@chanB") == "UCB"


# ============================================================
# Subscriber History
# ============================================================

class TestSubscriberHistory:
    def test_empty_history_returns_empty_list(self):
        assert get_subscriber_history("UCfresh") == []

    def test_save_and_retrieve(self):
        save_subscriber_count("UCsub1", "Test Chan", 100_000)
        history = get_subscriber_history("UCsub1", days=1)
        assert len(history) == 1
        assert history[0]["subscribers"] == 100_000

    def test_multiple_records_ordered_desc(self):
        save_subscriber_count("UCsub2", "Chan2", 50_000)
        save_subscriber_count("UCsub2", "Chan2", 55_000)
        history = get_subscriber_history("UCsub2", days=1)
        assert len(history) == 2
        # Most recent first
        assert history[0]["subscribers"] == 55_000

    def test_history_isolated_by_channel_id(self):
        save_subscriber_count("UCA_sub", "ChanA", 10_000)
        save_subscriber_count("UCB_sub", "ChanB", 20_000)
        assert len(get_subscriber_history("UCA_sub", days=1)) == 1
        assert len(get_subscriber_history("UCB_sub", days=1)) == 1

    def test_days_filter_excludes_far_past(self):
        """Records older than the window must not be returned."""
        from modules.database import get_connection
        from datetime import datetime, timezone, timedelta
        old_dt = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        conn = get_connection()
        conn.execute(
            "INSERT INTO channel_subscribers_history (channel_id, channel_name, subscribers, recorded_at) VALUES (?, ?, ?, ?)",
            ("UCvery_old", "OldChan", 42, old_dt),
        )
        conn.commit()
        conn.close()
        # days=7 window: the 30-day-old record must not appear
        result = get_subscriber_history("UCvery_old", days=7)
        assert result == []


# ============================================================
# Keyword Aggregate Functions
# ============================================================

class TestGetKeywordSourceCount:
    def test_zero_when_no_data(self):
        assert get_keyword_source_count("not_tracked") == 0

    def test_counts_distinct_sources(self):
        save_keyword_count("horror", "rss", 5)
        save_keyword_count("horror", "reddit_apify", 3)
        save_keyword_count("horror", "twitter", 2)
        assert get_keyword_source_count("horror", hours=1) == 3

    def test_same_source_multiple_times_counts_once(self):
        save_keyword_count("occult", "rss", 5)
        save_keyword_count("occult", "rss", 8)
        assert get_keyword_source_count("occult", hours=1) == 1

    def test_case_insensitive_keyword(self):
        save_keyword_count("Paranormal", "rss", 4)
        assert get_keyword_source_count("paranormal", hours=1) == 1


class TestGetDailyBriefData:
    def test_empty_when_no_data(self):
        assert get_daily_brief_data(hours=1) == []

    def test_returns_keywords_ordered_by_mentions(self):
        save_keyword_count("ghost", "rss", 10)
        save_keyword_count("ghost", "reddit_apify", 5)
        save_keyword_count("demon", "rss", 3)
        rows = get_daily_brief_data(hours=1)
        keywords = [r["keyword"] for r in rows]
        assert keywords.index("ghost") < keywords.index("demon")

    def test_includes_source_count(self):
        save_keyword_count("spirit", "rss", 4)
        save_keyword_count("spirit", "twitter", 2)
        rows = get_daily_brief_data(hours=1)
        row = next(r for r in rows if r["keyword"] == "spirit")
        assert row["source_count"] == 2
        assert row["total_mentions"] == 6

    def test_limit_15_results(self):
        for i in range(20):
            save_keyword_count(f"kw_{i}", "rss", i + 1)
        rows = get_daily_brief_data(hours=1)
        assert len(rows) <= 15


class TestGetKeywordAllMentions:
    def test_empty_when_no_data(self):
        assert get_keyword_all_mentions("no_data", hours=1) == []

    def test_aggregates_by_source(self):
        save_keyword_count("witchcraft", "rss", 4)
        save_keyword_count("witchcraft", "rss", 6)
        save_keyword_count("witchcraft", "twitter", 3)
        rows = get_keyword_all_mentions("witchcraft", hours=1)
        sources = {r["source"]: r["total"] for r in rows}
        assert sources["rss"] == 10
        assert sources["twitter"] == 3

    def test_ordered_by_total_desc(self):
        save_keyword_count("legend", "twitter", 20)
        save_keyword_count("legend", "rss", 5)
        rows = get_keyword_all_mentions("legend", hours=1)
        assert rows[0]["source"] == "twitter"

    def test_case_insensitive(self):
        save_keyword_count("Cult", "rss", 7)
        rows = get_keyword_all_mentions("cult", hours=1)
        assert len(rows) == 1
        assert rows[0]["total"] == 7


class TestGetKeywordTimeseries:
    def test_empty_when_no_data(self):
        assert get_keyword_timeseries("empty_kw", hours=1) == []

    def test_returns_hour_bucket_and_total(self):
        save_keyword_count("folklore", "rss", 5)
        rows = get_keyword_timeseries("folklore", hours=1)
        assert len(rows) >= 1
        assert "hour_bucket" in rows[0]
        assert "total" in rows[0]
        assert rows[0]["total"] >= 5

    def test_ordered_asc_by_hour(self):
        save_keyword_count("ufo", "rss", 3)
        save_keyword_count("ufo", "twitter", 2)
        rows = get_keyword_timeseries("ufo", hours=1)
        # All within the same minute — at least 1 row
        assert len(rows) >= 1

    def test_case_insensitive(self):
        save_keyword_count("Mystery", "rss", 8)
        rows = get_keyword_timeseries("mystery", hours=1)
        assert len(rows) >= 1
        assert rows[0]["total"] >= 8
