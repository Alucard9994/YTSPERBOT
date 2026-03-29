"""
Integration tests — /api/system/backup e /api/system/restore

Coprono il round-trip completo:
  1. Inserisci dati nel DB
  2. Scarica il backup SQL
  3. Svuota le tabelle
  4. Ripristina tramite POST /restore
  5. Verifica che i dati siano tornati
"""

import io
import pytest
from modules.database import log_alert, save_keyword_count


class TestBackupEndpoint:
    def test_returns_200(self, client):
        r = client.get("/api/system/backup")
        assert r.status_code == 200

    def test_content_type_is_sql(self, client):
        r = client.get("/api/system/backup")
        ct = r.headers.get("content-type", "")
        assert "sql" in ct or "octet-stream" in ct or "text" in ct, (
            f"Content-Type inatteso: {ct!r}"
        )

    def test_content_disposition_has_filename(self, client):
        r = client.get("/api/system/backup")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd, "manca 'attachment' in Content-Disposition"
        assert ".sql" in cd, "il filename nel Content-Disposition deve finire con .sql"

    def test_content_is_utf8_decodeable(self, client):
        r = client.get("/api/system/backup")
        try:
            text = r.content.decode("utf-8")
        except UnicodeDecodeError:
            pytest.fail("Il backup non è UTF-8 valido")
        assert len(text) > 0

    def test_backup_contains_sql_header(self, client):
        r = client.get("/api/system/backup")
        text = r.content.decode("utf-8")
        assert "YTSPERBOT" in text, "header YTSPERBOT mancante nel backup SQL"
        assert "BEGIN TRANSACTION" in text
        assert "COMMIT" in text

    def test_backup_contains_inserted_data(self, client):
        """Dati inseriti devono apparire nel dump SQL."""
        log_alert("rss_trend", "backup_test_kw", "rss", velocity_pct=123.0)
        r = client.get("/api/system/backup")
        text = r.content.decode("utf-8")
        assert "backup_test_kw" in text, "La keyword inserita non appare nel backup SQL"

    def test_backup_contains_insert_statements(self, client):
        log_alert("rss_trend", "insert_test_kw", "rss")
        r = client.get("/api/system/backup")
        text = r.content.decode("utf-8")
        assert "INSERT" in text, "Il backup non contiene statement INSERT"


class TestRestoreEndpoint:
    def test_rejects_non_sql_file(self, client):
        fake_file = io.BytesIO(b"not a sql file")
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.txt", fake_file, "text/plain")},
        )
        assert r.status_code == 400

    def test_rejects_empty_filename_without_sql_ext(self, client):
        fake_file = io.BytesIO(
            b"INSERT INTO alerts_log VALUES (1,'x','y','z',NULL,NULL,NULL,NULL,NULL,NULL);"
        )
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.csv", fake_file, "text/plain")},
        )
        assert r.status_code == 400

    def test_accepts_valid_sql_file(self, client):
        sql = b"-- test\nSELECT 1;\n"
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql), "application/sql")},
        )
        assert r.status_code == 200

    def test_response_shape(self, client):
        sql = b"-- test restore\n"
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql), "application/sql")},
        )
        data = r.json()
        assert "inserted" in data, "manca 'inserted' nella risposta restore"
        assert "skipped" in data, "manca 'skipped' nella risposta restore"
        assert "errors" in data, "manca 'errors' nella risposta restore"

    def test_inserted_and_skipped_are_integers(self, client):
        sql = b"-- test\n"
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql), "application/sql")},
        )
        data = r.json()
        assert isinstance(data["inserted"], int)
        assert isinstance(data["skipped"], int)
        assert isinstance(data["errors"], list)

    def test_rejects_non_utf8_content(self, client):
        bad_bytes = b"\xff\xfe invalid bytes"
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(bad_bytes), "application/sql")},
        )
        assert r.status_code == 400

    def test_handles_comments_and_blank_lines(self, client):
        """Statement di solo commento o linee vuote non devono causare errori."""
        sql = b"-- questo e' un commento\n\n-- altro commento\n"
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql), "application/sql")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["errors"] == []

    def test_handles_transaction_keywords(self, client):
        """BEGIN TRANSACTION e COMMIT non devono causare errori."""
        sql = b"BEGIN TRANSACTION;\nCOMMIT;\n"
        r = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql), "application/sql")},
        )
        assert r.status_code == 200
        assert r.json()["errors"] == []


class TestBackupRestoreRoundtrip:
    """
    Test end-to-end: backup → clear → restore → verifica.
    Simula esattamente il caso d'uso reale di ripristino del DB.
    """

    def test_keyword_mentions_roundtrip(self, client):
        from modules.database import get_connection

        # 1. Inserisci dati
        save_keyword_count("roundtrip_kw", "rss", 42)

        # 2. Verifica che il dato esista
        conn = get_connection()
        count_before = conn.execute(
            "SELECT COUNT(*) AS n FROM keyword_mentions WHERE keyword = 'roundtrip_kw'"
        ).fetchone()["n"]
        conn.close()
        assert count_before >= 1, "il dato non è stato inserito"

        # 3. Scarica il backup
        r_backup = client.get("/api/system/backup")
        assert r_backup.status_code == 200
        sql_content = r_backup.content
        # Verifica che il backup contenga la keyword
        assert b"roundtrip_kw" in sql_content, "la keyword non è nel backup SQL"

        # 4. Svuota la tabella
        conn = get_connection()
        conn.execute("DELETE FROM keyword_mentions WHERE keyword = 'roundtrip_kw'")
        conn.commit()
        conn.close()

        # 5. Verifica che il dato non ci sia più
        conn = get_connection()
        count_deleted = conn.execute(
            "SELECT COUNT(*) AS n FROM keyword_mentions WHERE keyword = 'roundtrip_kw'"
        ).fetchone()["n"]
        conn.close()
        assert count_deleted == 0, "la keyword non è stata eliminata correttamente"

        # 6. Ripristina
        r_restore = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql_content), "application/sql")},
        )
        assert r_restore.status_code == 200
        restore_data = r_restore.json()
        assert restore_data["errors"] == [], (
            f"Errori durante il restore: {restore_data['errors']}"
        )

        # 7. Verifica che il dato sia tornato (query diretta al DB)
        conn = get_connection()
        count_after = conn.execute(
            "SELECT COUNT(*) AS n FROM keyword_mentions WHERE keyword = 'roundtrip_kw'"
        ).fetchone()["n"]
        conn.close()
        assert count_after >= 1, (
            "la keyword non è stata ripristinata — "
            f"inserted={restore_data['inserted']}, skipped={restore_data['skipped']}, "
            f"errors={restore_data['errors']}"
        )

    def test_alerts_log_roundtrip(self, client):
        from modules.database import get_connection

        # 1. Inserisci un alert
        log_alert("rss_trend", "rt_alert_kw", "rss", velocity_pct=99.9)

        # 2. Verifica inserimento
        conn = get_connection()
        count_start = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts_log WHERE keyword = 'rt_alert_kw'"
        ).fetchone()["n"]
        conn.close()
        assert count_start >= 1, "alert non inserito"

        # 3. Backup — verifica che la keyword sia nel backup
        r_backup = client.get("/api/system/backup")
        assert r_backup.status_code == 200
        sql_content = r_backup.content
        assert b"rt_alert_kw" in sql_content, "la keyword non è nel backup SQL"

        # 4. Svuota
        conn = get_connection()
        conn.execute("DELETE FROM alerts_log WHERE keyword = 'rt_alert_kw'")
        conn.commit()
        conn.close()

        # 5. Verifica eliminazione
        conn = get_connection()
        count_del = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts_log WHERE keyword = 'rt_alert_kw'"
        ).fetchone()["n"]
        conn.close()
        assert count_del == 0

        # 6. Ripristina
        r_restore = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql_content), "application/sql")},
        )
        assert r_restore.status_code == 200
        assert r_restore.json()["errors"] == [], (
            f"Errori durante il restore: {r_restore.json()['errors']}"
        )

        # 7. Verifica via query diretta al DB (più affidabile di hours=1 API)
        conn = get_connection()
        count_after = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts_log WHERE keyword = 'rt_alert_kw'"
        ).fetchone()["n"]
        conn.close()
        assert count_after >= 1, (
            "alert non trovato nel DB dopo il restore. "
            f"restore stats: {r_restore.json()}"
        )

    def test_duplicate_restore_uses_or_ignore(self, client):
        """
        Un secondo restore sullo stesso SQL non deve fallire né duplicare dati.
        INSERT OR IGNORE è il comportamento atteso per le tabelle dati.
        """
        save_keyword_count("dup_kw", "rss", 5)
        r_backup = client.get("/api/system/backup")
        sql_content = r_backup.content

        # Prima restore
        r1 = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql_content), "application/sql")},
        )
        assert r1.status_code == 200

        # Seconda restore con gli stessi dati
        r2 = client.post(
            "/api/system/restore",
            files={"file": ("backup.sql", io.BytesIO(sql_content), "application/sql")},
        )
        assert r2.status_code == 200
        # Non devono esserci errori (UNIQUE violation gestita come skipped)
        data2 = r2.json()
        assert data2["errors"] == [], (
            f"Il secondo restore ha generato errori: {data2['errors']}"
        )
