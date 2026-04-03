"""Unit tests for modules/pinterest_apify.py"""
from __future__ import annotations

import os
from unittest.mock import patch


from modules.pinterest_apify import (
    _search_pins,
    _select_keywords,
    _send_alert,
    run_pinterest_apify_detector,
)


# ---------------------------------------------------------------------------
# _search_pins
# ---------------------------------------------------------------------------


class TestSearchPins:
    def test_calls_run_actor_with_correct_input(self):
        with patch("modules.pinterest_apify.run_actor", return_value=[]) as mock_ra:
            _search_pins("paranormal", 12)
            actor_id, input_data = mock_ra.call_args[0]
            assert actor_id == "fatihtahta~pinterest-scraper-search"
            assert input_data["queries"] == ["paranormal"]
            assert input_data["limit"] == 12
            assert input_data["type"] == "all-pins"

    def test_enforces_minimum_limit_10(self):
        with patch("modules.pinterest_apify.run_actor", return_value=[]) as mock_ra:
            _search_pins("ghost", 5)
            _, input_data = mock_ra.call_args[0]
            assert input_data["limit"] == 10

    def test_filters_out_profile_type(self):
        items = [
            {"type": "pin", "pin": {"repin_count": 5}, "title": "Pin A", "url": "https://pin.it/1"},
            {"type": "profile", "pin": {}, "title": "Profile", "url": "https://pin.it/2"},
        ]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("ghost", 10)
        assert len(pins) == 1
        assert pins[0]["title"] == "Pin A"

    def test_items_without_type_are_kept(self):
        """Items without 'type' field should NOT be discarded — only type=='profile' is skipped."""
        items = [
            {"pin": {"repin_count": 3}, "title": "No type pin", "url": "https://pin.it/x"},
        ]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("occult", 10)
        assert len(pins) == 1

    def test_extracts_title_from_top_level(self):
        items = [{"type": "pin", "title": "Top Title", "pin": {"title": "Nested"}, "url": "u"}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins[0]["title"] == "Top Title"

    def test_extracts_title_from_pin_nested(self):
        items = [{"type": "pin", "pin": {"title": "Nested Title"}, "url": "u"}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins[0]["title"] == "Nested Title"

    def test_extracts_description_fallback_to_closeup(self):
        items = [{"type": "pin", "pin": {"closeup_description": "Closeup desc"}, "url": "u"}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins[0]["description"] == "Closeup desc"

    def test_extracts_repins_from_repin_count(self):
        items = [{"type": "pin", "pin": {"repin_count": 42}, "url": "u"}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins[0]["repins"] == 42

    def test_repins_fallback_to_aggregated_saves(self):
        items = [
            {
                "type": "pin",
                "pin": {
                    "repin_count": 0,
                    "aggregated_pin_data": {"aggregated_stats": {"saves": 99}},
                },
                "url": "u",
            }
        ]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins[0]["repins"] == 99

    def test_link_from_item_url(self):
        items = [{"type": "pin", "pin": {}, "url": "https://pin.it/abc"}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins[0]["link"] == "https://pin.it/abc"

    def test_external_link_stored_in_external_link_field(self):
        items = [{"type": "pin", "pin": {"link": "https://ext.example.com"}}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        # external_link contiene l'URL esterno; link contiene l'URL del pin Pinterest
        assert pins[0]["external_link"] == "https://ext.example.com"
        assert pins[0]["link"] == ""  # item["url"] non presente

    def test_returns_empty_on_empty_response(self):
        with patch("modules.pinterest_apify.run_actor", return_value=[]):
            assert _search_pins("k", 10) == []

    def test_all_profiles_returns_empty_with_warning(self, capsys):
        items = [{"type": "profile"}, {"type": "profile"}]
        with patch("modules.pinterest_apify.run_actor", return_value=items):
            pins = _search_pins("k", 10)
        assert pins == []
        out = capsys.readouterr().out
        assert "WARN" in out or "0 pin" in out


# ---------------------------------------------------------------------------
# _select_keywords
# ---------------------------------------------------------------------------


class TestSelectKeywords:
    def test_returns_all_when_per_run_gte_len(self):
        kws = ["a", "b", "c"]
        result = _select_keywords(kws, 10)
        assert set(result) == {"a", "b", "c"}

    def test_returns_per_run_count(self):
        kws = list("abcdefghij")  # 10 keywords
        result = _select_keywords(kws, 4)
        assert len(result) == 4

    def test_returns_all_when_per_run_zero(self):
        kws = ["a", "b", "c"]
        result = _select_keywords(kws, 0)
        assert result == kws

    def test_wraps_around_when_chunk_short(self):
        """Last slot may be short — should be padded from the beginning."""
        kws = list("abcde")  # 5 keywords, per_run=3 → slots=2
        # Depending on week number the offset is 0 or 3.
        # When offset=3 the chunk is kws[3:6] = ['d','e'] → pad with kws[0] = 'a'
        result = _select_keywords(kws, 3)
        assert len(result) == 3

    def test_covers_all_keywords_across_slots(self):
        """Over ceil(N/per_run) calls (different weeks) all keywords are covered."""
        kws = list("abcdef")
        per_run = 2
        import math
        slots = math.ceil(len(kws) / per_run)
        all_covered = set()
        for week in range(slots):
            offset = (week % slots) * per_run
            chunk = kws[offset: offset + per_run]
            all_covered.update(chunk)
        assert all_covered == set(kws)


# ---------------------------------------------------------------------------
# _send_alert
# ---------------------------------------------------------------------------


class TestSendAlert:
    def test_calls_send_message(self):
        with patch("modules.pinterest_apify.send_message", return_value=True) as mock_sm:
            result = _send_alert("paranormal", 20, 10, 100.0)
        mock_sm.assert_called_once()
        assert result is True

    def test_message_contains_keyword(self):
        with patch("modules.pinterest_apify.send_message") as mock_sm:
            _send_alert("haunted", 20, 10, 100.0)
            text = mock_sm.call_args[0][0]
        assert "haunted" in text

    def test_message_contains_velocity(self):
        with patch("modules.pinterest_apify.send_message") as mock_sm:
            _send_alert("occult", 20, 10, 150.0)
            text = mock_sm.call_args[0][0]
        assert "150" in text


# ---------------------------------------------------------------------------
# run_pinterest_apify_detector
# ---------------------------------------------------------------------------


class TestRunPinterestApifyDetector:
    def _cfg(self, **overrides):
        cfg = {
            "keywords": ["paranormal", "haunted"],
            "pinterest": {
                "keywords_per_run": 5,
                "pins_per_keyword": 10,
                "velocity_threshold": 30,
            },
        }
        cfg.update(overrides)
        return cfg

    def test_disabled_when_no_apify_key(self, capsys):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APIFY_API_KEY", None)
            with patch("modules.pinterest_apify.run_actor") as mock_ra:
                run_pinterest_apify_detector(self._cfg())
        mock_ra.assert_not_called()
        assert "disabilitato" in capsys.readouterr().out

    def test_skips_keyword_with_zero_pins(self):
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.pinterest_apify._search_pins", return_value=[]):
                with patch("modules.pinterest_apify.save_keyword_count") as mock_save:
                    run_pinterest_apify_detector(
                        {**self._cfg(), "keywords": ["ghost"]}
                    )
        mock_save.assert_not_called()

    def test_saves_count_when_pins_found(self):
        pins = [{"title": "t", "description": "d", "repins": 5, "link": "l"}] * 8
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.pinterest_apify._search_pins", return_value=pins):
                with patch("modules.pinterest_apify.get_keyword_counts", return_value=[]):
                    with patch("modules.pinterest_apify.save_keyword_count") as mock_save:
                        with patch("modules.pinterest_apify.send_message"):
                            run_pinterest_apify_detector(
                                {**self._cfg(), "keywords": ["ghost"]}
                            )
        mock_save.assert_called_once_with("ghost", "pinterest_apify", 40)  # 8 pins × 5 repins

    def test_no_alert_on_first_run_no_baseline(self):
        pins = [{"title": "t", "description": "", "repins": 5, "link": ""}] * 10
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.pinterest_apify._search_pins", return_value=pins):
                with patch("modules.pinterest_apify.get_keyword_counts", return_value=[]):
                    with patch("modules.pinterest_apify.save_keyword_count"):
                        with patch("modules.pinterest_apify.send_message") as mock_sm:
                            run_pinterest_apify_detector(
                                {**self._cfg(), "keywords": ["ghost"]}
                            )
        mock_sm.assert_not_called()

    def test_sends_alert_when_velocity_above_threshold(self):
        pins_now = [{"title": "t", "description": "", "repins": 5, "link": ""}] * 20
        prev = [{"count": 10}]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.pinterest_apify._search_pins", return_value=pins_now):
                with patch("modules.pinterest_apify.get_keyword_counts", return_value=prev):
                    with patch("modules.pinterest_apify.save_keyword_count"):
                        with patch("modules.pinterest_apify.was_alert_sent_recently", return_value=False):
                            with patch("modules.pinterest_apify.mark_alert_sent"):
                                with patch("modules.pinterest_apify.send_message") as mock_sm:
                                    run_pinterest_apify_detector(
                                        {**self._cfg(), "keywords": ["ghost"]}
                                    )
        mock_sm.assert_called_once()

    def test_no_alert_below_threshold(self):
        pins_now = [{"title": "t", "description": "", "repins": 1, "link": ""}] * 11
        prev = [{"count": 10}]  # velocity = (11 saves - 10) / 10 * 100 = 10% < 30
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.pinterest_apify._search_pins", return_value=pins_now):
                with patch("modules.pinterest_apify.get_keyword_counts", return_value=prev):
                    with patch("modules.pinterest_apify.save_keyword_count"):
                        with patch("modules.pinterest_apify.send_message") as mock_sm:
                            run_pinterest_apify_detector(
                                {**self._cfg(), "keywords": ["ghost"]}
                            )
        mock_sm.assert_not_called()

    def test_no_duplicate_alert_within_cooldown(self):
        pins_now = [{"title": "t", "description": "", "repins": 5, "link": ""}] * 20
        prev = [{"count": 10}]
        with patch.dict(os.environ, {"APIFY_API_KEY": "test"}):
            with patch("modules.pinterest_apify._search_pins", return_value=pins_now):
                with patch("modules.pinterest_apify.get_keyword_counts", return_value=prev):
                    with patch("modules.pinterest_apify.save_keyword_count"):
                        with patch("modules.pinterest_apify.was_alert_sent_recently", return_value=True):
                            with patch("modules.pinterest_apify.send_message") as mock_sm:
                                run_pinterest_apify_detector(
                                    {**self._cfg(), "keywords": ["ghost"]}
                                )
        mock_sm.assert_not_called()
