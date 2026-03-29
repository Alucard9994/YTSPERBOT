"""
Unit tests — config_manager.py
Verifica VALID_KEYS, _flatten_scalars e init_config_from_yaml.
"""

from modules.config_manager import VALID_KEYS, _flatten_scalars


class TestValidKeys:
    """Contratti strutturali su VALID_KEYS — se un test fallisce
    significa che una chiave è stata rimossa o rinominata per errore."""

    CRITICAL_KEYS = [
        # reddit
        "reddit.use_apify",
        "reddit.check_interval_hours",
        # pinterest
        "pinterest.use_apify",
        "pinterest.check_interval_hours",
        # twitter
        "twitter.use_apify",
        "twitter.check_interval_hours",
        # trend_detector
        "trend_detector.check_interval_hours",
        "trend_detector.velocity_threshold_longform",
        "trend_detector.velocity_threshold_shorts",
        # apify
        "apify_scraper.run_interval_days",
        "apify_scraper.results_per_profile",
        # cross_signal
        "cross_signal.min_sources",
        "cross_signal.lookback_hours",
        # scraper
        "scraper.multiplier_threshold",
        "scraper.min_views_absolute",
    ]

    def test_all_critical_keys_present(self):
        missing = [k for k in self.CRITICAL_KEYS if k not in VALID_KEYS]
        assert missing == [], f"Chiavi mancanti in VALID_KEYS: {missing}"

    def test_every_entry_has_type(self):
        for key, meta in VALID_KEYS.items():
            assert "type" in meta, f"VALID_KEYS[{key!r}] manca 'type'"

    def test_every_entry_has_desc(self):
        for key, meta in VALID_KEYS.items():
            assert "desc" in meta, f"VALID_KEYS[{key!r}] manca 'desc'"
            assert len(meta["desc"]) > 3, f"VALID_KEYS[{key!r}].desc troppo corta"

    def test_type_values_are_valid(self):
        ALLOWED = {"int", "float", "str", "bool"}
        for key, meta in VALID_KEYS.items():
            assert meta["type"] in ALLOWED, (
                f"VALID_KEYS[{key!r}].type={meta['type']!r} non valido"
            )

    def test_int_keys_with_min_max_consistent(self):
        for key, meta in VALID_KEYS.items():
            if meta["type"] == "int" and "min" in meta and "max" in meta:
                assert meta["min"] <= meta["max"], (
                    f"VALID_KEYS[{key!r}]: min > max"
                )

    def test_use_apify_keys_are_bool(self):
        apify_keys = [k for k in VALID_KEYS if k.endswith(".use_apify")]
        assert len(apify_keys) >= 3, "Attesi almeno 3 tasti use_apify (reddit, twitter, pinterest)"
        for k in apify_keys:
            assert VALID_KEYS[k]["type"] == "bool", f"{k} dovrebbe essere bool"


class TestFlattenScalars:
    def test_returns_only_valid_keys(self):
        config = {
            "trend_detector": {"check_interval_hours": 4, "velocity_threshold_longform": 300},
            "unknown_section": {"foo": "bar"},
        }
        result = _flatten_scalars(config)
        for k in result:
            assert k in VALID_KEYS, f"Chiave non valida restituita: {k!r}"

    def test_nested_to_dotted(self):
        config = {"trend_detector": {"check_interval_hours": 8}}
        result = _flatten_scalars(config)
        assert "trend_detector.check_interval_hours" in result
        assert result["trend_detector.check_interval_hours"] == 8

    def test_lists_excluded(self):
        """Liste e dict annidati non devono apparire nel risultato."""
        config = {
            "apify_scraper": {
                "tiktok_hashtags": ["paranormal", "haunted"],
                "run_interval_days": 14,
            }
        }
        result = _flatten_scalars(config)
        assert "apify_scraper.tiktok_hashtags" not in result
        # Il valore scalare deve esserci
        assert "apify_scraper.run_interval_days" in result

    def test_unknown_keys_excluded(self):
        config = {"nonexistent_section": {"some_key": 42}}
        result = _flatten_scalars(config)
        assert result == {}

    def test_bool_value_preserved(self):
        config = {"reddit": {"use_apify": True}}
        result = _flatten_scalars(config)
        assert result.get("reddit.use_apify") is True

    def test_empty_config_returns_empty(self):
        assert _flatten_scalars({}) == {}
