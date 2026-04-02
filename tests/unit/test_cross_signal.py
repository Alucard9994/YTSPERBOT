"""Unit tests for modules/cross_signal.py"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock


from modules.cross_signal import (
    generate_title_suggestions,
    run_cross_signal_detector,
)


# ---------------------------------------------------------------------------
# generate_title_suggestions
# ---------------------------------------------------------------------------


class TestGenerateTitleSuggestions:
    def test_returns_none_when_no_anthropic_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = generate_title_suggestions("paranormal")
        assert result is None

    def test_returns_text_on_success(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "content": [{"text": "1. Titolo A\n2. Titolo B\n3. Titolo C\n4. D\n5. E"}]
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("requests.post", return_value=fake_response):
                result = generate_title_suggestions("paranormal")
        assert result is not None
        assert "Titolo" in result

    def test_returns_none_on_http_error(self, capsys):
        fake_response = MagicMock()
        fake_response.status_code = 429
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("requests.post", return_value=fake_response):
                result = generate_title_suggestions("paranormal")
        assert result is None
        assert "429" in capsys.readouterr().out

    def test_returns_none_on_exception(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("requests.post", side_effect=Exception("timeout")):
                result = generate_title_suggestions("paranormal")
        assert result is None

    def test_returns_none_when_empty_content(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"content": []}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("requests.post", return_value=fake_response):
                result = generate_title_suggestions("paranormal")
        assert result is None


# ---------------------------------------------------------------------------
# run_cross_signal_detector
# ---------------------------------------------------------------------------


def _kw(keyword="paranormal", source_count=3, total_mentions=15, sources="reddit,twitter,rss"):
    return {
        "keyword": keyword,
        "source_count": source_count,
        "total_mentions": total_mentions,
        "sources": sources,
    }


def _cfg(min_sources=3, lookback_hours=6, cooldown_hours=12, ai_titles=False):
    return {
        "cross_signal": {
            "min_sources": min_sources,
            "lookback_hours": lookback_hours,
            "cooldown_hours": cooldown_hours,
            "ai_titles": ai_titles,
        }
    }


class TestRunCrossSignalDetector:
    def test_no_alert_when_no_convergences(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[]):
            with patch("modules.cross_signal.send_convergence_alert") as mock_alert:
                run_cross_signal_detector(_cfg())
        mock_alert.assert_not_called()

    def test_skips_blacklisted_keyword(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=True):
                with patch("modules.cross_signal.send_convergence_alert") as mock_alert:
                    run_cross_signal_detector(_cfg())
        mock_alert.assert_not_called()

    def test_skips_keyword_within_cooldown(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=True):
                    with patch("modules.cross_signal.send_convergence_alert") as mock_alert:
                        run_cross_signal_detector(_cfg())
        mock_alert.assert_not_called()

    def test_sends_convergence_alert_for_qualifying_keyword(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.mark_alert_sent"):
                        with patch("modules.cross_signal.log_alert"):
                            with patch("modules.cross_signal.send_convergence_alert") as mock_alert:
                                run_cross_signal_detector(_cfg())
        mock_alert.assert_called_once()
        args = mock_alert.call_args[0]
        assert args[0] == "paranormal"

    def test_marks_alert_sent_after_firing(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.send_convergence_alert"):
                        with patch("modules.cross_signal.log_alert"):
                            with patch("modules.cross_signal.mark_alert_sent") as mock_mark:
                                run_cross_signal_detector(_cfg())
        mock_mark.assert_called_once()
        alert_id, alert_type = mock_mark.call_args[0]
        assert "paranormal" in alert_id
        assert alert_type == "cross_signal"

    def test_logs_alert_after_firing(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.send_convergence_alert"):
                        with patch("modules.cross_signal.mark_alert_sent"):
                            with patch("modules.cross_signal.log_alert") as mock_log:
                                run_cross_signal_detector(_cfg())
        mock_log.assert_called_once()
        assert mock_log.call_args[0][0] == "cross_signal"
        assert mock_log.call_args[0][1] == "paranormal"

    def test_does_not_call_ai_titles_when_disabled(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.send_convergence_alert"):
                        with patch("modules.cross_signal.mark_alert_sent"):
                            with patch("modules.cross_signal.log_alert"):
                                with patch("modules.cross_signal.generate_title_suggestions") as mock_ai:
                                    run_cross_signal_detector(_cfg(ai_titles=False))
        mock_ai.assert_not_called()

    def test_calls_ai_titles_when_enabled(self):
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[_kw()]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.send_convergence_alert"):
                        with patch("modules.cross_signal.mark_alert_sent"):
                            with patch("modules.cross_signal.log_alert"):
                                with patch("modules.cross_signal.generate_title_suggestions", return_value="1. Title") as mock_ai:
                                    run_cross_signal_detector(_cfg(ai_titles=True))
        mock_ai.assert_called_once_with("paranormal")

    def test_passes_sources_list_to_alert(self):
        kw = _kw(sources="reddit_apify, twitter, rss")
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=[kw]):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.mark_alert_sent"):
                        with patch("modules.cross_signal.log_alert"):
                            with patch("modules.cross_signal.send_convergence_alert") as mock_alert:
                                run_cross_signal_detector(_cfg())
        sources_arg = mock_alert.call_args[0][1]
        assert isinstance(sources_arg, list)
        assert "reddit_apify" in sources_arg

    def test_counts_found_convergences(self, capsys):
        kws = [_kw("ghost"), _kw("paranormal")]
        with patch("modules.cross_signal.get_multi_source_keywords", return_value=kws):
            with patch("modules.cross_signal.is_blacklisted", return_value=False):
                with patch("modules.cross_signal.was_alert_sent_recently", return_value=False):
                    with patch("modules.cross_signal.send_convergence_alert"):
                        with patch("modules.cross_signal.mark_alert_sent"):
                            with patch("modules.cross_signal.log_alert"):
                                run_cross_signal_detector(_cfg())
        out = capsys.readouterr().out
        assert "2" in out
