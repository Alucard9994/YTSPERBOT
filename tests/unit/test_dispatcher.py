"""
Unit tests — run_twitter_auto()
Verifica che il dispatcher scelga Apify o Bearer Token in base a config.
I due detector vengono mockati: non vogliamo chiamate di rete.
"""
from unittest.mock import MagicMock
from modules.dispatcher import run_twitter_auto


def _mocks():
    return MagicMock(), MagicMock()


class TestRunTwitterAuto:

    def test_uses_apify_when_flag_true(self):
        apify, bearer = _mocks()
        run_twitter_auto({"twitter": {"use_apify": True}}, apify_fn=apify, bearer_fn=bearer)
        apify.assert_called_once()
        bearer.assert_not_called()

    def test_uses_bearer_when_flag_false(self):
        apify, bearer = _mocks()
        run_twitter_auto({"twitter": {"use_apify": False}}, apify_fn=apify, bearer_fn=bearer)
        bearer.assert_called_once()
        apify.assert_not_called()

    def test_defaults_to_bearer_when_key_missing(self):
        """Se la chiave use_apify non c'è, usa Bearer (default sicuro)."""
        apify, bearer = _mocks()
        run_twitter_auto({"twitter": {}}, apify_fn=apify, bearer_fn=bearer)
        bearer.assert_called_once()
        apify.assert_not_called()

    def test_defaults_to_bearer_when_twitter_section_missing(self):
        """Config senza sezione twitter → Bearer."""
        apify, bearer = _mocks()
        run_twitter_auto({}, apify_fn=apify, bearer_fn=bearer)
        bearer.assert_called_once()
        apify.assert_not_called()

    def test_passes_config_unchanged(self):
        """Il config viene passato as-is al detector scelto."""
        apify, bearer = _mocks()
        config = {"twitter": {"use_apify": True, "extra": "data"}}
        run_twitter_auto(config, apify_fn=apify, bearer_fn=bearer)
        args, _ = apify.call_args
        assert args[0] is config
