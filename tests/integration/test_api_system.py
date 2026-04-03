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


class TestRunServices:
    def _fake_main(self, called):
        """Returns a fake __main__ module with run_service that records calls."""
        import types
        def fake_run_service(name):
            called.append(name)
        return types.SimpleNamespace(run_service=fake_run_service)

    def _fake_main_failing(self, called, fail_on):
        import types
        def fake_run_service(name):
            if name == fail_on:
                raise RuntimeError("simulated failure")
            called.append(name)
        return types.SimpleNamespace(run_service=fake_run_service)

    def test_empty_services_returns_error(self, client):
        r = client.post("/api/system/run-services", json={"services": []})
        assert r.status_code == 200
        assert r.json()["triggered"] is False

    def test_single_service_triggered(self, client, monkeypatch):
        import sys
        import time
        called = []
        monkeypatch.setitem(sys.modules, "__main__", self._fake_main(called))
        r = client.post("/api/system/run-services", json={"services": ["rss"]})
        assert r.status_code == 200
        assert r.json()["triggered"] is True
        assert r.json()["services"] == ["rss"]
        time.sleep(0.3)
        assert called == ["rss"]

    def test_multiple_services_all_triggered(self, client, monkeypatch):
        """All selected services must be started — the original bug was only the first ran."""
        import sys
        import time
        called = []
        monkeypatch.setitem(sys.modules, "__main__", self._fake_main(called))
        r = client.post("/api/system/run-services", json={"services": ["rss", "reddit", "twitter"]})
        assert r.status_code == 200
        assert r.json()["triggered"] is True
        time.sleep(0.3)
        assert set(called) == {"rss", "reddit", "twitter"}

    def test_one_failing_service_does_not_block_others(self, client, monkeypatch):
        """If service 1 raises an exception, services 2 and 3 still run."""
        import sys
        import time
        called = []
        monkeypatch.setitem(sys.modules, "__main__", self._fake_main_failing(called, fail_on="reddit"))
        r = client.post("/api/system/run-services", json={"services": ["reddit", "rss", "twitter"]})
        assert r.status_code == 200
        time.sleep(0.3)
        assert "rss" in called
        assert "twitter" in called
        assert "reddit" not in called


class TestHealthEndpoint:
    def test_health_json_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_json_shape(self, client):
        data = client.get("/api/health").json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_health_root_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_health_head_200(self, client):
        r = client.head("/")
        assert r.status_code == 200


class TestLogsEndpoint:
    def test_logs_empty(self, client):
        r = client.get("/api/system/logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_logs_after_insert(self, client):
        from modules.database import save_bot_log

        save_bot_log("INFO", "Test log message", "test_module")
        r = client.get("/api/system/logs?minutes=1&level=ALL&limit=10")
        data = r.json()
        assert len(data) >= 1
        assert data[0]["message"] == "Test log message"

    def test_logs_level_filter(self, client):
        from modules.database import save_bot_log

        save_bot_log("ERROR", "Error log", "mod")
        save_bot_log("INFO",  "Info log",  "mod")
        r = client.get("/api/system/logs?minutes=1&level=ERROR&limit=10")
        data = r.json()
        assert all(d["level"] == "ERROR" for d in data)

    def test_logs_response_shape(self, client):
        from modules.database import save_bot_log

        save_bot_log("WARNING", "Shape test", "mod")
        r = client.get("/api/system/logs?minutes=1")
        row = r.json()[0]
        assert "level" in row
        assert "message" in row
        assert "module" in row
        assert "logged_at" in row

    def test_schedule_returns_list(self, client):
        r = client.get("/api/system/schedule")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_schedule_items_have_required_fields(self, client):
        data = client.get("/api/system/schedule").json()
        for item in data:
            assert "name" in item
            assert "freq" in item
            assert "active" in item
            assert isinstance(item["active"], bool)
