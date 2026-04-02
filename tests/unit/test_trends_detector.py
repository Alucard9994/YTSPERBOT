"""
Unit tests — trends_detector.py
Tests pure logic functions and mocks all external I/O (HTTP, pytrends, Telegram).
"""
from __future__ import annotations

import urllib.error
from unittest.mock import patch, MagicMock


from modules.trends_detector import (
    _matches_niche,
    _is_429,
    _trends_is_blocked,
    run_trends_detector,
    run_trending_rss_monitor,
    run_rising_queries_detector,
    NICHE_SEMANTIC_WORDS,
    _TRENDS_BLOCK_KEY,
    _TRENDS_COOLDOWN_HOURS,
)
from modules.database import (
    save_keyword_count,
    mark_job_run,
)


# ============================================================
# _matches_niche
# ============================================================

class TestMatchesNiche:
    def test_exact_word_matches(self):
        assert _matches_niche("ghost sighting in Italy") is True

    def test_word_as_substring_matches(self):
        assert _matches_niche("the paranormal investigator") is True

    def test_niche_word_case_insensitive(self):
        assert _matches_niche("GHOST story") is True
        assert _matches_niche("Haunted house") is True

    def test_unrelated_text_no_match(self):
        assert _matches_niche("football results season 2025") is False

    def test_empty_string_no_match(self):
        assert _matches_niche("") is False

    def test_italian_word_matches(self):
        assert _matches_niche("Un caso di paranormale a Milano") is True
        assert _matches_niche("Fantasma avvistato in centro") is True

    def test_all_niche_words_individually(self):
        """Every word in NICHE_SEMANTIC_WORDS must match when presented alone."""
        for word in NICHE_SEMANTIC_WORDS:
            assert _matches_niche(word) is True, f"'{word}' should match niche"

    def test_multi_word_phrase_matches(self):
        assert _matches_niche("secret society meetings revealed") is True

    def test_ufo_matches(self):
        assert _matches_niche("UAP sighting over Nevada") is True


# ============================================================
# _is_429
# ============================================================

class TestIs429:
    def test_detects_429_in_message(self):
        assert _is_429(Exception("Response code 429")) is True

    def test_detects_too_many_requests(self):
        assert _is_429(Exception("Too many requests")) is True

    def test_case_insensitive(self):
        assert _is_429(Exception("TOO MANY REQUESTS from Google")) is True

    def test_other_errors_return_false(self):
        assert _is_429(Exception("Connection refused")) is False
        assert _is_429(Exception("500 Internal Server Error")) is False
        assert _is_429(ValueError("random error")) is False


# ============================================================
# _trends_is_blocked
# ============================================================

class TestTrendsIsBlocked:
    def test_not_blocked_initially(self):
        assert _trends_is_blocked() is False

    def test_blocked_immediately_after_mark(self):
        mark_job_run(_TRENDS_BLOCK_KEY)
        assert _trends_is_blocked() is True

    def test_unblocked_after_cooldown(self):
        """Simulate a mark_job_run that happened > cooldown hours ago."""
        from datetime import datetime, timezone, timedelta
        from modules.database import get_connection
        past = datetime.now(timezone.utc) - timedelta(hours=_TRENDS_COOLDOWN_HOURS + 1)
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO scheduler_runs (job_name, last_run) VALUES (?, ?)",
            (_TRENDS_BLOCK_KEY, past.isoformat()),
        )
        conn.commit()
        conn.close()
        assert _trends_is_blocked() is False


# ============================================================
# run_trends_detector
# ============================================================

def _trends_config(**overrides):
    cfg = {
        "google_trends": {
            "velocity_threshold": 50,
            "timeframe": "now 7-d",
            "geo": "",
            "top_n_keywords": 5,
        },
        "keywords": ["ghost", "paranormal", "occult"],
        "priority_score": {"min_score": 1},
    }
    cfg["google_trends"].update(overrides)
    return cfg


class TestRunTrendsDetector:
    def test_skips_when_blocked(self, capsys):
        mark_job_run(_TRENDS_BLOCK_KEY)
        with patch("modules.trends_detector.fetch_trends_interest") as mock_fetch:
            run_trends_detector(_trends_config())
        mock_fetch.assert_not_called()
        assert "skip" in capsys.readouterr().out.lower()

    def test_sends_alert_on_velocity_spike(self):
        save_keyword_count("ghost", "google_trends", 10)  # baseline
        interest_map = {"ghost": 60, "paranormal": 0, "occult": 0}
        with patch("modules.trends_detector.fetch_trends_interest", return_value=interest_map):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_trends_detector(_trends_config())
        mock_send.assert_called_once()
        alert_text = mock_send.call_args[0][0]
        assert "ghost" in alert_text.lower()

    def test_no_alert_when_velocity_below_threshold(self):
        save_keyword_count("paranormal", "google_trends", 50)  # baseline = 50
        interest_map = {"ghost": 0, "paranormal": 55, "occult": 0}  # +10% < 50% threshold
        with patch("modules.trends_detector.fetch_trends_interest", return_value=interest_map):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_trends_detector(_trends_config())
        mock_send.assert_not_called()

    def test_no_alert_when_no_previous_data(self):
        """First run: previous_interest == 0 → skip velocity calc."""
        interest_map = {"ghost": 80, "paranormal": 0, "occult": 0}
        with patch("modules.trends_detector.fetch_trends_interest", return_value=interest_map):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_trends_detector(_trends_config())
        mock_send.assert_not_called()

    def test_no_alert_when_interest_now_zero(self):
        save_keyword_count("ghost", "google_trends", 20)
        interest_map = {"ghost": 0, "paranormal": 0, "occult": 0}
        with patch("modules.trends_detector.fetch_trends_interest", return_value=interest_map):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_trends_detector(_trends_config())
        mock_send.assert_not_called()

    def test_no_duplicate_alert_within_cooldown(self):
        save_keyword_count("occult", "google_trends", 10)
        interest_map = {"ghost": 0, "paranormal": 0, "occult": 80}
        with patch("modules.trends_detector.fetch_trends_interest", return_value=interest_map):
            with patch("modules.trends_detector.send_message"):
                run_trends_detector(_trends_config())
            # Second run: same interest → cooldown should suppress
            with patch("modules.trends_detector.send_message") as mock_send2:
                run_trends_detector(_trends_config())
        mock_send2.assert_not_called()

    def test_marks_cooldown_on_429(self):
        with patch("modules.trends_detector.fetch_trends_interest",
                   side_effect=Exception("429 Too many requests")):
            run_trends_detector(_trends_config())
        assert _trends_is_blocked() is True

    def test_handles_non_429_exception_gracefully(self, capsys):
        with patch("modules.trends_detector.fetch_trends_interest",
                   side_effect=Exception("Connection reset")):
            run_trends_detector(_trends_config())  # must not raise
        assert "Errore" in capsys.readouterr().out


# ============================================================
# run_trending_rss_monitor
# ============================================================

class _MockFeed:
    """Minimal feedparser result mock."""
    def __init__(self, entries=None, bozo=False):
        self.entries = entries or []
        self.bozo = bozo


def _make_rss_config(**overrides):
    cfg = {
        "trending_rss": {
            "geos": ["IT", "US"],
            "extra_filter_words": [],
        }
    }
    if overrides:
        cfg["trending_rss"].update(overrides)
    return cfg


class TestRunTrendingRssMonitor:
    def test_sends_alert_on_niche_match(self):
        entry = {
            "title": "Ghost sighting goes viral",
            "ht_approx_traffic": "200+",
            "ht_news_item_title": "Paranormal event shocks experts",
        }
        feed = _MockFeed(entries=[entry])

        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>"):
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = feed
                with patch("modules.trends_detector.send_message") as mock_send:
                    run_trending_rss_monitor(_make_rss_config(geos=["US"]))
        mock_send.assert_called_once()
        assert "Ghost" in mock_send.call_args[0][0]

    def test_does_not_alert_on_non_niche_term(self):
        entry = {"title": "Football World Cup results", "ht_approx_traffic": "500+"}
        feed = _MockFeed(entries=[entry])
        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>"):
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = feed
                with patch("modules.trends_detector.send_message") as mock_send:
                    run_trending_rss_monitor(_make_rss_config(geos=["US"]))
        mock_send.assert_not_called()

    def test_skips_on_http_error(self, capsys):
        with patch("modules.trends_detector._fetch_rss_bytes",
                   side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None)):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_trending_rss_monitor(_make_rss_config(geos=["IT"]))
        mock_send.assert_not_called()
        assert "404" in capsys.readouterr().out

    def test_skips_on_empty_feed(self, capsys):
        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>"):
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = _MockFeed(entries=[])
                with patch("modules.trends_detector.send_message") as mock_send:
                    run_trending_rss_monitor(_make_rss_config(geos=["IT"]))
        mock_send.assert_not_called()

    def test_deduplicates_within_cooldown(self):
        entry = {"title": "Spirit haunting reported", "ht_approx_traffic": "100+"}
        feed = _MockFeed(entries=[entry])
        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>"):
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = feed
                with patch("modules.trends_detector.send_message"):
                    run_trending_rss_monitor(_make_rss_config(geos=["US"]))
                with patch("modules.trends_detector.send_message") as mock_send2:
                    run_trending_rss_monitor(_make_rss_config(geos=["US"]))
        mock_send2.assert_not_called()

    def test_extra_filter_words_extend_niche(self):
        """Words in extra_filter_words should also trigger alerts."""
        entry = {"title": "SCP Foundation document leaked", "ht_approx_traffic": "50+"}
        feed = _MockFeed(entries=[entry])
        config = _make_rss_config(geos=["US"], extra_filter_words=["scp"])
        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>"):
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = feed
                with patch("modules.trends_detector.send_message") as mock_send:
                    run_trending_rss_monitor(config)
        mock_send.assert_called_once()

    def test_iterates_all_geos(self):
        """Each geo should generate an independent fetch call."""
        feed = _MockFeed(entries=[])
        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>") as mock_fetch:
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = feed
                run_trending_rss_monitor(_make_rss_config(geos=["IT", "US", "GB"]))
        assert mock_fetch.call_count == 3

    def test_skips_entry_with_empty_title(self):
        entries = [{"title": "", "ht_approx_traffic": "100+"},
                   {"title": "ghost mystery", "ht_approx_traffic": "50+"}]
        feed = _MockFeed(entries=entries)
        with patch("modules.trends_detector._fetch_rss_bytes", return_value=b"<rss/>"):
            with patch("modules.trends_detector.feedparser") as mock_fp:
                mock_fp.parse.return_value = feed
                with patch("modules.trends_detector.send_message") as mock_send:
                    run_trending_rss_monitor(_make_rss_config(geos=["US"]))
        mock_send.assert_called_once()
        assert "ghost" in mock_send.call_args[0][0].lower()


# ============================================================
# run_rising_queries_detector
# ============================================================

def _rising_config(**overrides):
    cfg = {
        "rising_queries": {
            "keywords_per_run": 3,
            "min_growth": 500,
            "geo": "",
            "timeframe": "now 7-d",
        },
        "keywords": ["ghost", "paranormal", "occult"],
    }
    cfg["rising_queries"].update(overrides)
    return cfg


def _make_rising_df(rows):
    """Build a fake DataFrame-like object from a list of (query, value) tuples."""
    df = MagicMock()
    df.empty = len(rows) == 0
    df.iterrows.return_value = iter(
        (i, {"query": q, "value": v}) for i, (q, v) in enumerate(rows)
    )
    return df


class TestRunRisingQueriesDetector:
    def test_skips_when_blocked(self, capsys):
        mark_job_run(_TRENDS_BLOCK_KEY)
        mock_pt = MagicMock()
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            run_rising_queries_detector(_rising_config())
        mock_pt.build_payload.assert_not_called()

    def test_sends_alert_on_breakout(self):
        df = _make_rising_df([("skinwalker ranch", "Breakout")])
        mock_pt = MagicMock()
        mock_pt.related_queries.return_value = {
            "ghost": {"rising": df}
        }
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
        mock_send.assert_called_once()
        assert "skinwalker ranch" in mock_send.call_args[0][0].lower()

    def test_sends_alert_on_high_growth(self):
        df = _make_rising_df([("haunted location", 800)])
        mock_pt = MagicMock()
        mock_pt.related_queries.return_value = {"ghost": {"rising": df}}
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
        mock_send.assert_called_once()

    def test_does_not_alert_on_low_growth(self):
        df = _make_rising_df([("minor query", 100)])   # < min_growth=500
        mock_pt = MagicMock()
        mock_pt.related_queries.return_value = {"ghost": {"rising": df}}
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
        mock_send.assert_not_called()

    def test_skips_already_monitored_keywords(self):
        df = _make_rising_df([("ghost hunting", 900)])  # "ghost" is in all_keywords
        mock_pt = MagicMock()
        mock_pt.related_queries.return_value = {"paranormal": {"rising": df}}
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
        # "ghost hunting" contains "ghost" which is monitored → skip
        mock_send.assert_not_called()

    def test_deduplicates_alert(self):
        df = _make_rising_df([("shadow beings", "Breakout")])
        mock_pt = MagicMock()
        mock_pt.related_queries.return_value = {"ghost": {"rising": df}}
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            with patch("modules.trends_detector.send_message"):
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
            with patch("modules.trends_detector.send_message") as mock_send2:
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
        mock_send2.assert_not_called()

    def test_marks_cooldown_and_breaks_on_429(self):
        mock_pt = MagicMock()
        mock_pt.build_payload.side_effect = Exception("429 Too many requests")
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            run_rising_queries_detector(_rising_config(keywords_per_run=3))
        # build_payload called once then breaks
        mock_pt.build_payload.assert_called_once()
        assert _trends_is_blocked() is True

    def test_skips_keyword_with_none_rising_df(self):
        mock_pt = MagicMock()
        mock_pt.related_queries.return_value = {"ghost": {"rising": None}}
        with patch("modules.trends_detector.TrendReq", return_value=mock_pt):
            with patch("modules.trends_detector.send_message") as mock_send:
                run_rising_queries_detector(_rising_config(keywords_per_run=1))
        mock_send.assert_not_called()
