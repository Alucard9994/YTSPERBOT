"""
Unit tests per le nuove funzionalità di pinterest_apify.py:
  - Domain extraction in _search_pins
  - Domain tracker in run_pinterest_apify_detector
  - run_pinterest_digest
"""
from unittest.mock import patch

from modules.pinterest_apify import _search_pins, run_pinterest_digest


# ---------------------------------------------------------------------------
# _search_pins — domain extraction
# ---------------------------------------------------------------------------

class TestSearchPinsDomain:
    def _item(self, link="https://www.example.com/page", pin_id=42):
        return {
            "type": "pin",
            "id": pin_id,
            "url": "https://pinterest.com/pin/42",
            "title": "Paranormal pin",
            "pin": {
                "repin_count": 30,
                "link": link,
                "description": "haunted",
            },
            "creator": {"username": "ghost_creator"},
        }

    def test_domain_extracted_from_external_link(self):
        with patch("modules.pinterest_apify.run_actor", return_value=[self._item()]):
            pins = _search_pins("paranormal", 10)
        assert pins[0]["domain"] == "example.com"

    def test_www_stripped_from_domain(self):
        item = self._item(link="https://www.mysteriousuniverse.org/article")
        with patch("modules.pinterest_apify.run_actor", return_value=[item]):
            pins = _search_pins("occult", 10)
        assert pins[0]["domain"] == "mysteriousuniverse.org"

    def test_domain_empty_when_no_external_link(self):
        item = self._item(link="")
        with patch("modules.pinterest_apify.run_actor", return_value=[item]):
            pins = _search_pins("horror", 10)
        assert pins[0]["domain"] == ""

    def test_pin_hash_uses_item_id(self):
        with patch("modules.pinterest_apify.run_actor", return_value=[self._item(pin_id=99)]):
            pins = _search_pins("paranormal", 10)
        assert pins[0]["pin_hash"] == "99"

    def test_creator_username_extracted(self):
        with patch("modules.pinterest_apify.run_actor", return_value=[self._item()]):
            pins = _search_pins("paranormal", 10)
        assert pins[0]["creator_username"] == "ghost_creator"


# ---------------------------------------------------------------------------
# run_pinterest_digest
# ---------------------------------------------------------------------------

class TestRunPinterestDigest:
    def _config(self):
        return {"pinterest": {"domain_top_n": 3}}

    def test_digest_skipped_when_no_pins(self):
        with (
            patch("modules.pinterest_apify.was_alert_sent_recently", return_value=False),
            patch("modules.pinterest_apify.get_pinterest_top_pins", return_value=[]),
            patch("modules.pinterest_apify.get_pinterest_domain_counts", return_value=[]),
            patch("modules.pinterest_apify.send_message") as mock_send,
        ):
            run_pinterest_digest(self._config())
        mock_send.assert_not_called()

    def test_digest_skipped_when_cooldown_active(self):
        with (
            patch("modules.pinterest_apify.was_alert_sent_recently", return_value=True),
            patch("modules.pinterest_apify.get_pinterest_top_pins") as mock_get,
            patch("modules.pinterest_apify.send_message") as mock_send,
        ):
            run_pinterest_digest(self._config())
        mock_get.assert_not_called()
        mock_send.assert_not_called()

    def test_digest_sends_when_pins_exist(self):
        pins = [
            {"pin_hash": "1", "keyword": "paranormal", "title": "Ghost in old house",
             "url": "https://pinterest.com/1", "repins": 150, "domain": "example.com"},
            {"pin_hash": "2", "keyword": "occult", "title": "Dark ritual board",
             "url": "", "repins": 80, "domain": ""},
        ]
        domains = [{"domain": "example.com", "pin_count": 5, "total_repins": 200}]
        with (
            patch("modules.pinterest_apify.was_alert_sent_recently", return_value=False),
            patch("modules.pinterest_apify.get_pinterest_top_pins", return_value=pins),
            patch("modules.pinterest_apify.get_pinterest_domain_counts", return_value=domains),
            patch("modules.pinterest_apify.send_message") as mock_send,
            patch("modules.pinterest_apify.mark_alert_sent") as mock_mark,
            patch("modules.pinterest_apify.os.getenv", return_value="fake_key"),
        ):
            run_pinterest_digest(self._config())
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "PINTEREST DIGEST" in msg
        assert "Ghost in old house" in msg
        assert "150" in msg
        assert "example.com" in msg
        mock_mark.assert_called_once_with("pinterest_weekly_digest", "pinterest_digest")

    def test_digest_includes_domain_section(self):
        pins = [{"pin_hash": "1", "keyword": "horror", "title": "Haunted",
                 "url": "", "repins": 50, "domain": "horror.com"}]
        domains = [
            {"domain": "horror.com", "pin_count": 3, "total_repins": 90},
            {"domain": "occult.net", "pin_count": 2, "total_repins": 60},
        ]
        with (
            patch("modules.pinterest_apify.was_alert_sent_recently", return_value=False),
            patch("modules.pinterest_apify.get_pinterest_top_pins", return_value=pins),
            patch("modules.pinterest_apify.get_pinterest_domain_counts", return_value=domains),
            patch("modules.pinterest_apify.send_message") as mock_send,
            patch("modules.pinterest_apify.mark_alert_sent"),
            patch("modules.pinterest_apify.os.getenv", return_value="fake_key"),
        ):
            run_pinterest_digest(self._config())
        msg = mock_send.call_args[0][0]
        assert "Domini più salvati" in msg
        assert "horror.com" in msg
        assert "occult.net" in msg

    def test_digest_skipped_when_no_apify_key(self):
        with (
            patch("modules.pinterest_apify.os.getenv", return_value=""),
            patch("modules.pinterest_apify.send_message") as mock_send,
        ):
            run_pinterest_digest(self._config())
        mock_send.assert_not_called()
