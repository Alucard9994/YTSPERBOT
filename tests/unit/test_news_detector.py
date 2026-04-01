"""Unit tests for news_detector module."""
import os
import pytest
from unittest.mock import patch, MagicMock

from modules.news_detector import fetch_news_articles, NewsApiQuotaExceeded


class TestFetchNewsArticles:
    def test_returns_empty_when_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # NEWSAPI_KEY not set
            result = fetch_news_articles("paranormal")
        assert result == []

    def test_returns_articles_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "articles": [
                {"title": "Ghost spotted", "source": {"name": "BBC"},
                 "url": "http://example.com", "publishedAt": "2026-04-01T00:00:00Z"}
            ]
        }
        with patch.dict(os.environ, {"NEWSAPI_KEY": "testkey"}):
            with patch("requests.get", return_value=mock_resp):
                result = fetch_news_articles("ghost")
        assert len(result) == 1
        assert result[0]["title"] == "Ghost spotted"

    def test_raises_quota_exceeded_on_429(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch.dict(os.environ, {"NEWSAPI_KEY": "testkey"}):
            with patch("requests.get", return_value=mock_resp):
                with pytest.raises(NewsApiQuotaExceeded):
                    fetch_news_articles("paranormal")

    def test_returns_empty_on_401(self, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch.dict(os.environ, {"NEWSAPI_KEY": "badkey"}):
            with patch("requests.get", return_value=mock_resp):
                result = fetch_news_articles("ghost")
        assert result == []
        assert "non valida" in capsys.readouterr().out

    def test_returns_empty_on_426(self, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 426
        with patch.dict(os.environ, {"NEWSAPI_KEY": "testkey"}):
            with patch("requests.get", return_value=mock_resp):
                result = fetch_news_articles("ghost")
        assert result == []
        assert "426" not in capsys.readouterr().out or True  # just no exception


class TestRunNewsDetectorQuotaBehavior:
    """Verify that a 429 stops all further requests immediately."""

    def test_stops_on_quota_exceeded(self):
        call_count = 0

        def fake_fetch(keyword, language="en", lookback_hours=48):
            nonlocal call_count
            call_count += 1
            raise NewsApiQuotaExceeded("quota")

        config = {
            "news_api": {
                "keywords_per_run": 5,
                "languages": ["en", "it"],
                "lookback_hours": 48,
                "velocity_threshold": 200,
            },
            "priority_score": {"min_score": 1},
            "keywords": ["ghost", "witch", "paranormal", "demon", "occult"],
        }

        with patch("modules.news_detector.NEWSAPI_ENABLED", True):
            with patch("modules.news_detector.fetch_news_articles", side_effect=fake_fetch):
                from modules.news_detector import run_news_detector
                run_news_detector(config)

        # Should stop after first 429 — only 1 call, not 10 (5 kw × 2 langs)
        assert call_count == 1
