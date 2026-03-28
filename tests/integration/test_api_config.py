"""
Integration tests — /api/config/*
Testa parametri, liste e blacklist.
"""


class TestConfigParams:

    def test_get_params_returns_list(self, client):
        r = client.get("/api/config/params")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_put_existing_param(self, client):
        """Modifica un parametro esistente (caricato da config.yaml all'avvio)."""
        params = client.get("/api/config/params").json()
        if not params:
            return  # nessun parametro configurato → skip
        key = params[0]["key"]
        original_value = params[0]["value"]

        r = client.put(f"/api/config/params/{key}", json={"value": "99"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # Ripristina
        client.put(f"/api/config/params/{key}", json={"value": str(original_value)})

    def test_put_nonexistent_param_returns_404(self, client):
        r = client.put("/api/config/params/does.not.exist", json={"value": "1"})
        assert r.status_code == 404


class TestConfigLists:

    def test_get_lists_returns_dict(self, client):
        r = client.get("/api/config/lists")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_add_and_remove_item(self, client):
        lists = client.get("/api/config/lists").json()
        if not lists:
            return  # nessuna lista → skip
        list_key = next(iter(lists))

        # Aggiungi
        r = client.post("/api/config/lists", json={"list_key": list_key, "value": "__test_val__"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # Verifica presenza
        lists_after = client.get("/api/config/lists").json()
        values = [i["value"] for i in lists_after.get(list_key, [])]
        assert "__test_val__" in values

        # Rimuovi
        r = client.request("DELETE", "/api/config/lists",
                           json={"list_key": list_key, "value": "__test_val__"})
        assert r.status_code == 200

        # Verifica assenza
        lists_final = client.get("/api/config/lists").json()
        values_final = [i["value"] for i in lists_final.get(list_key, [])]
        assert "__test_val__" not in values_final


class TestBlacklist:

    def test_get_blacklist_empty(self, client):
        r = client.get("/api/config/blacklist")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_keyword(self, client):
        r = client.post("/api/config/blacklist", json={"keyword": "__test_block__"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # get_blacklist() restituisce list[str]
        bl = client.get("/api/config/blacklist").json()
        assert "__test_block__" in bl

    def test_remove_keyword(self, client):
        client.post("/api/config/blacklist", json={"keyword": "__to_remove__"})
        r = client.delete("/api/config/blacklist/__to_remove__")
        assert r.status_code == 200

        bl = client.get("/api/config/blacklist").json()
        assert "__to_remove__" not in bl

    def test_remove_nonexistent_is_ok(self, client):
        """Rimuovere una keyword non presente non deve dare errore."""
        r = client.delete("/api/config/blacklist/nonexistent_keyword_xyz")
        assert r.status_code == 200
