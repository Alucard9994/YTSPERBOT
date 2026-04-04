"""Integration tests for api/routes/discovery.py"""
from modules.database import (
    save_discovery_suggestion,
    get_discovery_suggestions,
    config_list_get,
    update_discovery_suggestion_status,
)


class TestListSuggestions:
    def test_empty_returns_structure(self, client):
        r = client.get("/api/discovery/suggestions")
        assert r.status_code == 200
        data = r.json()
        assert "suggestions" in data
        assert "pending_count" in data
        assert data["suggestions"] == []
        assert data["pending_count"] == 0

    def test_returns_pending_by_default(self, client):
        save_discovery_suggestion("tiktok_hashtag", "ghosthunter", "tiktok_caption", 5)
        data = client.get("/api/discovery/suggestions").json()
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["value"] == "ghosthunter"
        assert data["pending_count"] == 1

    def test_status_accepted_filter(self, client):
        save_discovery_suggestion("subreddit", "haunted", "reddit_post", 3)
        rows = get_discovery_suggestions(status="all")
        update_discovery_suggestion_status(rows[0]["id"], "accepted")
        data = client.get("/api/discovery/suggestions", params={"status": "accepted"}).json()
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["status"] == "accepted"

    def test_status_all_returns_everything(self, client):
        save_discovery_suggestion("keyword", "occult", "twitter_tweet", 2)
        save_discovery_suggestion("keyword", "mystery", "twitter_tweet", 4)
        rows = get_discovery_suggestions(status="all")
        update_discovery_suggestion_status(rows[0]["id"], "rejected")
        data = client.get("/api/discovery/suggestions", params={"status": "all"}).json()
        assert len(data["suggestions"]) == 2

    def test_required_fields_present(self, client):
        save_discovery_suggestion("tiktok_hashtag", "paranormal", "tiktok_caption", 7)
        s = client.get("/api/discovery/suggestions").json()["suggestions"][0]
        for field in ("id", "type", "value", "source", "score", "status", "created_at"):
            assert field in s, f"missing field: {field}"

    def test_ordered_by_score_desc(self, client):
        save_discovery_suggestion("keyword", "low", "twitter_tweet", 2)
        save_discovery_suggestion("keyword", "high", "twitter_tweet", 10)
        suggestions = client.get("/api/discovery/suggestions").json()["suggestions"]
        assert suggestions[0]["value"] == "high"

    def test_pending_count_correct(self, client):
        save_discovery_suggestion("keyword", "a", "twitter_tweet", 1)
        save_discovery_suggestion("keyword", "b", "twitter_tweet", 2)
        data = client.get("/api/discovery/suggestions").json()
        assert data["pending_count"] == 2


class TestAcceptSuggestion:
    def test_accept_adds_to_config_list(self, client):
        save_discovery_suggestion("tiktok_hashtag", "spookyszn", "tiktok_caption", 4)
        row = get_discovery_suggestions()[0]
        r = client.post(f"/api/discovery/suggestions/{row['id']}/accept")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["added_to"] == "tiktok_hashtags"
        assert data["value"] == "spookyszn"
        # verify it's in config_lists
        items = config_list_get("tiktok_hashtags")
        assert any(i["value"] == "spookyszn" for i in items)

    def test_accept_marks_status_accepted(self, client):
        save_discovery_suggestion("instagram_hashtag", "darkvibes", "instagram_caption", 3)
        row = get_discovery_suggestions()[0]
        client.post(f"/api/discovery/suggestions/{row['id']}/accept")
        rows = get_discovery_suggestions(status="all")
        updated = next(r for r in rows if r["id"] == row["id"])
        assert updated["status"] == "accepted"

    def test_accept_subreddit_maps_to_subreddits(self, client):
        save_discovery_suggestion("subreddit", "darkfolklore", "reddit_post", 2)
        row = get_discovery_suggestions()[0]
        r = client.post(f"/api/discovery/suggestions/{row['id']}/accept")
        assert r.json()["added_to"] == "subreddits"

    def test_accept_keyword_maps_to_keywords(self, client):
        save_discovery_suggestion("keyword", "witchyvibes", "twitter_tweet", 5)
        row = get_discovery_suggestions()[0]
        r = client.post(f"/api/discovery/suggestions/{row['id']}/accept")
        assert r.json()["added_to"] == "keywords"

    def test_accept_nonexistent_returns_404(self, client):
        r = client.post("/api/discovery/suggestions/99999/accept")
        assert r.status_code == 404

    def test_accept_decrements_pending_count(self, client):
        save_discovery_suggestion("keyword", "pendingkw", "twitter_tweet", 3)
        row = get_discovery_suggestions()[0]
        before = client.get("/api/discovery/suggestions").json()["pending_count"]
        client.post(f"/api/discovery/suggestions/{row['id']}/accept")
        after = client.get("/api/discovery/suggestions").json()["pending_count"]
        assert after == before - 1


class TestRejectSuggestion:
    def test_reject_marks_status_rejected(self, client):
        save_discovery_suggestion("subreddit", "tooreject", "reddit_post", 2)
        row = get_discovery_suggestions()[0]
        r = client.post(f"/api/discovery/suggestions/{row['id']}/reject")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        rows = get_discovery_suggestions(status="all")
        updated = next(x for x in rows if x["id"] == row["id"])
        assert updated["status"] == "rejected"

    def test_reject_removes_from_pending(self, client):
        save_discovery_suggestion("keyword", "rejectkw", "twitter_tweet", 2)
        row = get_discovery_suggestions()[0]
        client.post(f"/api/discovery/suggestions/{row['id']}/reject")
        pending = client.get("/api/discovery/suggestions").json()["suggestions"]
        assert not any(s["id"] == row["id"] for s in pending)

    def test_reject_does_not_add_to_config_list(self, client):
        save_discovery_suggestion("tiktok_hashtag", "shouldnotadd", "tiktok_caption", 2)
        row = get_discovery_suggestions()[0]
        client.post(f"/api/discovery/suggestions/{row['id']}/reject")
        items = config_list_get("tiktok_hashtags")
        assert not any(i["value"] == "shouldnotadd" for i in items)
