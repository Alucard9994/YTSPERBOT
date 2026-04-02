"""
Unit tests — rss_detector.py
Tests pure logic and mocks all external I/O (feedparser HTTP, Telegram).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


from modules.rss_detector import (
    fetch_feed,
    count_keyword_in_articles,
    run_rss_detector,
)
from modules.database import save_keyword_count


# ============================================================
# Helpers
# ============================================================

def _make_entry(title: str, summary: str = "", published_dt: datetime | None = None) -> MagicMock:
    """Build a fake feedparser entry."""
    entry = MagicMock()
    entry.get.side_effect = lambda key, default="": {
        "title": title,
        "summary": summary,
        "link": f"https://example.com/{title[:10].replace(' ', '-')}",
    }.get(key, default)

    if published_dt is not None:
        # feedparser stores published_parsed as a time.struct_time-compatible tuple
        entry.published_parsed = published_dt.timetuple()
    else:
        entry.published_parsed = None

    # hasattr check in fetch_feed uses hasattr(entry, "published_parsed")
    return entry


def _make_feed(entries=None) -> MagicMock:
    feed = MagicMock()
    feed.entries = entries or []
    return feed


def _rss_config(feeds=None, **overrides):
    """Minimal config dict for run_rss_detector."""
    default_feeds = [{"name": "TestFeed", "url": "https://example.com/feed.rss"}]
    cfg = {
        "trend_detector": {
            "min_mentions_to_track": 2,
            "velocity_threshold_longform": 300,
        },
        "keywords": ["ghost", "paranormal", "occult"],
        "rss_feeds": {"en": feeds if feeds is not None else default_feeds},
        "priority_score": {"min_score": 1},
    }
    cfg["trend_detector"].update(overrides)
    return cfg


# ============================================================
# fetch_feed
# ============================================================

class TestFetchFeed:
    def test_returns_recent_articles(self):
        now = datetime.now(timezone.utc)
        entry = _make_entry("Ghost sighting reported", "Paranormal activity...", now)
        with patch("modules.rss_detector.feedparser") as mock_fp:
            mock_fp.parse.return_value = _make_feed([entry])
            articles = fetch_feed("TestFeed", "https://example.com/feed.rss", lookback_hours=48)
        assert len(articles) == 1
        assert articles[0]["title"] == "Ghost sighting reported"
        assert articles[0]["source"] == "TestFeed"

    def test_excludes_old_articles(self):
        old_date = datetime.now(timezone.utc) - timedelta(hours=72)
        entry = _make_entry("Old article", published_dt=old_date)
        with patch("modules.rss_detector.feedparser") as mock_fp:
            mock_fp.parse.return_value = _make_feed([entry])
            articles = fetch_feed("TestFeed", "https://example.com/feed.rss", lookback_hours=48)
        assert articles == []

    def test_includes_article_with_no_date(self):
        """Articles without a date are included (can't be filtered)."""
        entry = _make_entry("Undated article", published_dt=None)
        with patch("modules.rss_detector.feedparser") as mock_fp:
            mock_fp.parse.return_value = _make_feed([entry])
            articles = fetch_feed("TestFeed", "https://example.com/feed.rss")
        assert len(articles) == 1

    def test_returns_empty_on_exception(self, capsys):
        with patch("modules.rss_detector.feedparser") as mock_fp:
            mock_fp.parse.side_effect = Exception("Connection refused")
            articles = fetch_feed("BrokenFeed", "https://broken.url/feed.rss")
        assert articles == []
        assert "Errore" in capsys.readouterr().out

    def test_article_has_required_fields(self):
        now = datetime.now(timezone.utc)
        entry = _make_entry("Shape check", "Body text", now)
        with patch("modules.rss_detector.feedparser") as mock_fp:
            mock_fp.parse.return_value = _make_feed([entry])
            articles = fetch_feed("TestFeed", "https://example.com/feed.rss")
        art = articles[0]
        assert "title" in art
        assert "summary" in art
        assert "link" in art
        assert "published" in art
        assert "source" in art

    def test_multiple_articles_mixed_dates(self):
        now = datetime.now(timezone.utc)
        recent = _make_entry("Recent", published_dt=now - timedelta(hours=1))
        old = _make_entry("Old", published_dt=now - timedelta(hours=100))
        no_date = _make_entry("No date", published_dt=None)
        with patch("modules.rss_detector.feedparser") as mock_fp:
            mock_fp.parse.return_value = _make_feed([recent, old, no_date])
            articles = fetch_feed("TestFeed", "https://example.com/feed.rss", lookback_hours=48)
        titles = [a["title"] for a in articles]
        assert "Recent" in titles
        assert "No date" in titles
        assert "Old" not in titles


# ============================================================
# count_keyword_in_articles
# ============================================================

class TestCountKeywordInArticles:
    def _make_articles(self, data: list[tuple[str, str]]) -> list[dict]:
        return [{"title": t, "summary": s, "link": "", "published": None, "source": "test"}
                for t, s in data]

    def test_match_in_title(self):
        articles = self._make_articles([("Ghost story", "normal content")])
        matches = count_keyword_in_articles(articles, "ghost")
        assert len(matches) == 1

    def test_match_in_summary(self):
        articles = self._make_articles([("Regular title", "paranormal activity detected")])
        matches = count_keyword_in_articles(articles, "paranormal")
        assert len(matches) == 1

    def test_no_match(self):
        articles = self._make_articles([("Football results", "Score 2-1")])
        matches = count_keyword_in_articles(articles, "ghost")
        assert matches == []

    def test_case_insensitive(self):
        articles = self._make_articles([("GHOST sighting", "Paranormal EVENT")])
        assert len(count_keyword_in_articles(articles, "ghost")) == 1
        assert len(count_keyword_in_articles(articles, "PARANORMAL")) == 1

    def test_multiple_articles_multiple_matches(self):
        articles = self._make_articles([
            ("Ghost story 1", ""),
            ("Football news", ""),
            ("Ghost story 2", ""),
        ])
        matches = count_keyword_in_articles(articles, "ghost")
        assert len(matches) == 2

    def test_returns_the_matching_article(self):
        articles = self._make_articles([("Ghost story", "content"), ("Other", "content")])
        matches = count_keyword_in_articles(articles, "ghost")
        assert matches[0]["title"] == "Ghost story"

    def test_empty_articles_returns_empty(self):
        assert count_keyword_in_articles([], "ghost") == []

    def test_substring_match(self):
        """'ghost' should match 'ghosthunter' as substring."""
        articles = self._make_articles([("ghosthunter channel", "")])
        matches = count_keyword_in_articles(articles, "ghost")
        assert len(matches) == 1


# ============================================================
# run_rss_detector
# ============================================================

class TestRunRssDetector:
    def _fake_fetch(self, titles: list[str]):
        """Return a fetch_feed mock that returns articles with given titles."""
        now = datetime.now(timezone.utc)
        articles = [{"title": t, "summary": "", "link": "", "published": now, "source": "TestFeed"}
                    for t in titles]

        def fetch(name, url, lookback_hours=48):
            return articles

        return fetch

    def test_no_alert_when_no_feeds_configured(self, capsys):
        config = _rss_config(feeds=[])
        with patch("modules.rss_detector.send_message") as mock_send:
            run_rss_detector(config)
        mock_send.assert_not_called()
        assert "Nessun feed" in capsys.readouterr().out

    def test_no_alert_when_below_min_mentions(self):
        """Only 1 match but min_mentions_to_track=2 → no save, no alert."""
        articles = [{"title": "one ghost article", "summary": "", "link": "",
                     "published": None, "source": "T"}]
        with patch("modules.rss_detector.fetch_feed", return_value=articles):
            with patch("modules.rss_detector.send_message") as mock_send:
                run_rss_detector(_rss_config())  # min_mentions=2
        mock_send.assert_not_called()

    def test_saves_keyword_count_above_threshold(self):
        """When count >= min_mentions, save_keyword_count must be called."""
        articles = [{"title": f"ghost article {i}", "summary": "", "link": "",
                     "published": None, "source": "T"} for i in range(5)]
        with patch("modules.rss_detector.fetch_feed", return_value=articles):
            with patch("modules.rss_detector.send_message"):
                with patch("modules.rss_detector.alert_allowed", return_value=False):
                    run_rss_detector(_rss_config())
        from modules.database import get_keyword_counts
        counts = get_keyword_counts("ghost", "rss", 1)
        assert len(counts) >= 1
        assert counts[0]["count"] == 5

    def test_sends_alert_on_velocity_spike(self):
        # Baseline: 2 mentions already in DB
        save_keyword_count("ghost", "rss", 2)
        articles = [{"title": f"ghost story {i}", "summary": "", "link": "",
                     "published": None, "source": "T"} for i in range(10)]
        with patch("modules.rss_detector.fetch_feed", return_value=articles):
            with patch("modules.rss_detector.send_message") as mock_send:
                with patch("modules.rss_detector.alert_allowed", return_value=True):
                    run_rss_detector(_rss_config())  # velocity = (10-2)/2*100 = 400% > 300 threshold
        mock_send.assert_called_once()
        text = mock_send.call_args[0][0]
        assert "ghost" in text.lower()

    def test_no_alert_when_velocity_below_threshold(self):
        # Baseline 10, now 12 → +20% < 300% threshold
        save_keyword_count("occult", "rss", 10)
        articles = [{"title": f"occult article {i}", "summary": "", "link": "",
                     "published": None, "source": "T"} for i in range(12)]
        with patch("modules.rss_detector.fetch_feed", return_value=articles):
            with patch("modules.rss_detector.send_message") as mock_send:
                with patch("modules.rss_detector.alert_allowed", return_value=True):
                    run_rss_detector(_rss_config())
        mock_send.assert_not_called()

    def test_no_alert_on_first_run_no_baseline(self):
        """No previous data → previous_count == 0 → skip velocity calc."""
        articles = [{"title": f"paranormal {i}", "summary": "", "link": "",
                     "published": None, "source": "T"} for i in range(5)]
        with patch("modules.rss_detector.fetch_feed", return_value=articles):
            with patch("modules.rss_detector.send_message") as mock_send:
                with patch("modules.rss_detector.alert_allowed", return_value=True):
                    run_rss_detector(_rss_config())
        mock_send.assert_not_called()

    def test_no_duplicate_alert_within_cooldown(self):
        save_keyword_count("ghost", "rss", 2)
        articles = [{"title": f"ghost {i}", "summary": "", "link": "",
                     "published": None, "source": "T"} for i in range(10)]
        with patch("modules.rss_detector.fetch_feed", return_value=articles):
            with patch("modules.rss_detector.alert_allowed", return_value=True):
                with patch("modules.rss_detector.send_message"):
                    run_rss_detector(_rss_config())
                with patch("modules.rss_detector.send_message") as mock_send2:
                    run_rss_detector(_rss_config())
        mock_send2.assert_not_called()

    def test_aggregates_articles_from_multiple_feeds(self):
        feeds = [
            {"name": "Feed1", "url": "https://example1.com/rss"},
            {"name": "Feed2", "url": "https://example2.com/rss"},
        ]
        # Feed1: 3 ghost articles, Feed2: 3 ghost articles = 6 total > min_mentions=2
        def fake_fetch(name, url, lookback_hours=48):
            return [{"title": f"ghost from {name}", "summary": "", "link": "",
                     "published": None, "source": name}
                    for _ in range(3)]

        save_keyword_count("ghost", "rss", 3)  # baseline
        with patch("modules.rss_detector.fetch_feed", side_effect=fake_fetch):
            with patch("modules.rss_detector.alert_allowed", return_value=True):
                with patch("modules.rss_detector.send_message"):
                    run_rss_detector(_rss_config(feeds=feeds))  # 6/3 = +100% < 300 → no alert (ok)
        from modules.database import get_keyword_counts
        counts = get_keyword_counts("ghost", "rss", 1)
        # Should have saved the aggregated count (6)
        assert any(c["count"] == 6 for c in counts)
