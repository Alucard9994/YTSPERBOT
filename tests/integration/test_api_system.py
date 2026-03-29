"""
Integration tests — /api/system/*
"""


class TestSystemStatus:
    def test_returns_200(self, client):
        r = client.get("/api/system/status")
        assert r.status_code == 200

    def test_response_shape(self, client):
        data = client.get("/api/system/status").json()
        assert "credentials" in data
        assert "tables" in data
        assert "db_size_mb" in data

    def test_credentials_are_booleans(self, client):
        creds = client.get("/api/system/status").json()["credentials"]
        assert isinstance(creds, dict)
        for key, val in creds.items():
            assert isinstance(val, bool), f"credentials[{key!r}] non è bool"

    def test_tables_are_integers(self, client):
        tables = client.get("/api/system/status").json()["tables"]
        for table, count in tables.items():
            assert isinstance(count, int), f"tables[{table!r}] non è int"

    def test_db_size_is_number(self, client):
        size = client.get("/api/system/status").json()["db_size_mb"]
        assert isinstance(size, (int, float))
        assert size >= 0

    def test_table_counts_increase_after_insert(self, client):
        from modules.database import log_alert

        before = client.get("/api/system/status").json()["tables"]["alerts_log"]
        log_alert("rss_trend", "count_test", "rss")
        after = client.get("/api/system/status").json()["tables"]["alerts_log"]
        assert after == before + 1


class TestDbStats:
    def test_returns_200(self, client):
        r = client.get("/api/system/db-stats")
        assert r.status_code == 200

    def test_has_db_size(self, client):
        data = client.get("/api/system/db-stats").json()
        assert "db_size_mb" in data
        assert data["db_size_mb"] >= 0
