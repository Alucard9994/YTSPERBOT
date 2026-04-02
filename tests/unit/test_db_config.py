"""
Unit tests — database.py: config table (bot_config) and config_lists table.
Uses the real SQLite test DB (see conftest.py).
"""
from modules.database import (
    config_load_defaults,
    config_get,
    config_get_all,
    config_set,
    config_list_seed,
    config_list_add,
    config_list_remove,
    config_list_get,
    config_lists_get_all,
)


# ============================================================
# bot_config: config_load_defaults / config_get / config_get_all
# ============================================================

class TestConfigLoadAndGet:
    def test_get_returns_none_for_unknown_key(self):
        assert config_get("does.not.exist") is None

    def test_load_defaults_inserts_values(self):
        config_load_defaults({
            "google_trends.velocity_threshold": ("50", "int"),
            "twitter.check_interval_hours": ("8", "int"),
        })
        row = config_get("google_trends.velocity_threshold")
        assert row is not None
        assert row["value"] == "50"
        assert row["type"] == "int"
        assert row["source"] == "yaml"

    def test_load_defaults_ignore_existing(self):
        """INSERT OR IGNORE: existing user override must not be overwritten."""
        config_set("apify_scraper.run_interval_days", "3", "int")
        config_load_defaults({"apify_scraper.run_interval_days": ("5", "int")})
        row = config_get("apify_scraper.run_interval_days")
        assert row["value"] == "3"   # user value preserved
        assert row["source"] == "user"

    def test_config_get_returns_required_fields(self):
        config_load_defaults({"test.key": ("hello", "str")})
        row = config_get("test.key")
        assert "key" in row
        assert "value" in row
        assert "type" in row
        assert "source" in row
        assert "updated_at" in row

    def test_config_get_all_returns_all_rows(self):
        config_load_defaults({
            "a.key": ("1", "int"),
            "b.key": ("2", "int"),
        })
        rows = config_get_all()
        keys = [r["key"] for r in rows]
        assert "a.key" in keys
        assert "b.key" in keys

    def test_config_get_all_ordered_by_key(self):
        config_load_defaults({
            "z.last": ("1", "int"),
            "a.first": ("2", "int"),
        })
        rows = config_get_all()
        keys = [r["key"] for r in rows]
        assert keys == sorted(keys)


# ============================================================
# config_set (upsert with source=user)
# ============================================================

class TestConfigSet:
    def test_insert_new_key(self):
        config_set("new.setting", "99", "int")
        row = config_get("new.setting")
        assert row["value"] == "99"
        assert row["source"] == "user"

    def test_update_existing_key(self):
        config_set("update.me", "10", "int")
        config_set("update.me", "20", "int")
        row = config_get("update.me")
        assert row["value"] == "20"

    def test_source_always_user(self):
        config_set("src.check", "true", "bool")
        assert config_get("src.check")["source"] == "user"

    def test_type_preserved(self):
        config_set("type.check", "3.14", "float")
        assert config_get("type.check")["type"] == "float"

    def test_bool_value_stored_as_string(self):
        config_set("bool.key", "true", "bool")
        row = config_get("bool.key")
        assert row["value"] == "true"


# ============================================================
# config_list_seed / config_list_add / config_list_remove / config_list_get
# ============================================================

class TestConfigListSeed:
    def test_seeds_empty_list(self):
        config_list_seed("keywords", ["ghost", "paranormal", "ufo"])
        items = config_list_get("keywords")
        values = [i["value"] for i in items]
        assert "ghost" in values
        assert "paranormal" in values
        assert "ufo" in values

    def test_seed_does_not_overwrite_existing(self):
        config_list_seed("keywords2", ["original"])
        config_list_seed("keywords2", ["should_not_appear"])
        items = config_list_get("keywords2")
        values = [i["value"] for i in items]
        assert "original" in values
        assert "should_not_appear" not in values

    def test_seed_with_dict_items_extracts_url(self):
        config_list_seed("rss_feeds", [
            {"url": "https://example.com/feed.rss", "name": "Example Feed"},
        ])
        items = config_list_get("rss_feeds")
        assert items[0]["value"] == "https://example.com/feed.rss"
        assert items[0]["label"] == "Example Feed"

    def test_seed_with_dict_items_extracts_handle(self):
        config_list_seed("competitors", [
            {"handle": "@ghosthunter", "name": "Ghost Hunter"},
        ])
        items = config_list_get("competitors")
        assert items[0]["value"] == "@ghosthunter"

    def test_seed_noop_on_empty_items(self):
        config_list_seed("empty_list", [])
        assert config_list_get("empty_list") == []

    def test_seed_skips_items_with_no_url_or_handle(self):
        config_list_seed("partial", [
            {"name": "only_name"},
            {"url": "https://valid.com", "name": "Valid"},
        ])
        items = config_list_get("partial")
        assert len(items) == 1
        assert items[0]["value"] == "https://valid.com"


class TestConfigListAdd:
    def test_add_single_item(self):
        config_list_add("test_list", "item_a")
        items = config_list_get("test_list")
        assert any(i["value"] == "item_a" for i in items)

    def test_add_with_label(self):
        config_list_add("labeled_list", "https://example.com", "Example")
        items = config_list_get("labeled_list")
        assert items[0]["label"] == "Example"

    def test_add_without_label_stores_none(self):
        config_list_add("no_label_list", "value_no_label")
        items = config_list_get("no_label_list")
        assert items[0]["label"] is None

    def test_idempotent_add(self):
        """INSERT OR IGNORE: adding the same value twice must not duplicate."""
        config_list_add("idem_list", "unique_value")
        config_list_add("idem_list", "unique_value")
        items = config_list_get("idem_list")
        assert len([i for i in items if i["value"] == "unique_value"]) == 1

    def test_different_values_in_same_list(self):
        config_list_add("multi_list", "val1")
        config_list_add("multi_list", "val2")
        items = config_list_get("multi_list")
        values = [i["value"] for i in items]
        assert "val1" in values
        assert "val2" in values


class TestConfigListRemove:
    def test_remove_existing_item(self):
        config_list_add("rem_list", "to_remove")
        config_list_remove("rem_list", "to_remove")
        items = config_list_get("rem_list")
        assert not any(i["value"] == "to_remove" for i in items)

    def test_remove_nonexistent_does_not_raise(self):
        config_list_remove("nonexistent_list", "nonexistent_value")

    def test_remove_only_target_item(self):
        config_list_add("selective_list", "keep_me")
        config_list_add("selective_list", "remove_me")
        config_list_remove("selective_list", "remove_me")
        items = config_list_get("selective_list")
        values = [i["value"] for i in items]
        assert "keep_me" in values
        assert "remove_me" not in values

    def test_exact_match_required(self):
        """Remove must match the exact value string."""
        config_list_add("exact_list", "ghost-stories")
        config_list_remove("exact_list", "ghost")   # partial — must NOT remove
        items = config_list_get("exact_list")
        assert any(i["value"] == "ghost-stories" for i in items)


class TestConfigListGet:
    def test_empty_list_returns_empty(self):
        assert config_list_get("empty_list_never_added") == []

    def test_returns_value_and_label_keys(self):
        config_list_add("shape_list", "v1", "L1")
        item = config_list_get("shape_list")[0]
        assert "value" in item
        assert "label" in item

    def test_order_preserved_insertion_order(self):
        config_list_add("order_list", "first")
        config_list_add("order_list", "second")
        config_list_add("order_list", "third")
        values = [i["value"] for i in config_list_get("order_list")]
        assert values == ["first", "second", "third"]


class TestConfigListsGetAll:
    def test_empty_returns_empty_dict(self):
        result = config_lists_get_all()
        assert isinstance(result, dict)

    def test_groups_by_list_key(self):
        config_list_add("fruits", "apple")
        config_list_add("fruits", "banana")
        config_list_add("vegs", "carrot")
        result = config_lists_get_all()
        assert "fruits" in result
        assert "vegs" in result
        assert len(result["fruits"]) == 2
        assert len(result["vegs"]) == 1

    def test_items_have_value_and_label(self):
        config_list_add("shape_all", "x", "X Label")
        result = config_lists_get_all()
        item = result["shape_all"][0]
        assert item["value"] == "x"
        assert item["label"] == "X Label"
