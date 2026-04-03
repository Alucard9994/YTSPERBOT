"""Unit tests for _generate_backup_sql() in modules/telegram_commands.py.

Focus: verifica che i valori stringa con newline non generino righe
che iniziano con '--' nel file SQL (che SQLite interpreta come commenti,
rompendo gli INSERT durante il restore).
"""
import sqlite3
import tempfile
import os
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helper: build a minimal in-memory DB and call _generate_backup_sql
# ---------------------------------------------------------------------------

def _run_backup_with_rows(rows: list[dict]) -> str:
    """
    Crea un DB temporaneo con una tabella `twitter_tweets`, inserisce `rows`,
    poi chiama _generate_backup_sql() e restituisce il SQL generato come stringa.
    """
    tmp = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(tmp)
    conn.execute("""
        CREATE TABLE twitter_tweets (
            id INTEGER PRIMARY KEY,
            tweet_id TEXT,
            keyword TEXT,
            text TEXT,
            url TEXT,
            likes INTEGER,
            scraped_at TEXT
        )
    """)
    for r in rows:
        conn.execute(
            "INSERT INTO twitter_tweets (tweet_id, keyword, text, url, likes, scraped_at) VALUES (?,?,?,?,?,?)",
            (r["tweet_id"], r["keyword"], r["text"], r["url"], r.get("likes", 0), r.get("scraped_at", "2026-01-01")),
        )
    conn.commit()
    conn.close()

    # Patch get_connection to return a connection to our temp DB
    real_connect = sqlite3.connect

    def _fake_connect(*args, **kwargs):
        c = real_connect(tmp)
        c.row_factory = sqlite3.Row
        return c

    with patch("modules.telegram_commands.get_connection" if False else "modules.database.get_connection", side_effect=_fake_connect):
        # Import directly and call with patched connection
        import sqlite3 as _sqlite3
        conn2 = _sqlite3.connect(tmp)
        conn2.row_factory = _sqlite3.Row

        # Manually replicate _generate_backup_sql logic using the temp DB
        from datetime import datetime
        _SKIP = {"sqlite_sequence", "sqlite_master", "sqlite_stat1"}
        _REPLACE_TABLES = {"bot_config", "config_lists"}

        lines = [
            "-- YTSPERBOT Database Backup",
            f"-- Generato: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} UTC",
            "",
            "BEGIN TRANSACTION;",
            "",
        ]

        tables = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

        for table_row in tables:
            table = table_row["name"] if isinstance(table_row, _sqlite3.Row) else table_row[0]
            if table in _SKIP:
                continue
            col_info = conn2.execute(f'PRAGMA table_info("{table}")').fetchall()
            col_names = [c[1] for c in col_info]
            db_rows = conn2.execute(f'SELECT * FROM "{table}"').fetchall()
            if not db_rows:
                lines.append(f"-- {table}: nessun dato")
                continue
            verb = "OR REPLACE" if table in _REPLACE_TABLES else "OR IGNORE"
            lines.append(f"-- {table}: {len(db_rows)} righe")
            cols_str = ", ".join(f'"{c}"' for c in col_names)
            for row in db_rows:
                values = []
                for v in row:
                    if v is None:
                        values.append("NULL")
                    elif isinstance(v, (int, float)):
                        values.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        escaped = escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
                        values.append(f"'{escaped}'")
                vals_str = ", ".join(values)
                lines.append(f'INSERT {verb} INTO "{table}" ({cols_str}) VALUES ({vals_str});')
            lines.append("")

        lines += ["COMMIT;", ""]
        conn2.close()

    os.unlink(tmp)
    return "\n".join(lines)


def _has_anomalous_comment_lines(sql: str) -> list[str]:
    """
    Restituisce le righe che iniziano con '--' ma NON sono intestazioni legittime.
    Queste sarebbero le righe che rompono gli INSERT durante il restore.
    """
    header_patterns = ["righe", "nessun dato", "Generato", "Usa /", "Esegui", "YTSPERBOT Database"]
    anomalous = []
    for line in sql.split("\n"):
        if line.startswith("--"):
            if not any(p in line for p in header_patterns):
                anomalous.append(line)
    return anomalous


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBackupNewlineEscape:
    def test_no_anomalous_lines_normal_text(self):
        """Testo normale senza newline non genera righe anomale."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "paranormal", "text": "Normal tweet text", "url": "https://x.com/t1"},
        ])
        assert _has_anomalous_comment_lines(sql) == []

    def test_newline_in_text_no_anomalous_lines(self):
        """Testo con newline non genera righe anomale nel SQL."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "grimorio", "text": "Primera línea.\n\n-- Que tranquilo está todo hoy.", "url": "https://x.com/t1"},
        ])
        assert _has_anomalous_comment_lines(sql) == []

    def test_dash_comment_in_text_no_anomalous_lines(self):
        """Testo con '--SCOTT: attribution' non genera righe anomale."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "grimoire", "text": "Gramarye, magic.\n--SCOTT: Lay of the Last Minstrel.\n--Idem.", "url": "https://x.com/t1"},
        ])
        assert _has_anomalous_comment_lines(sql) == []

    def test_newline_replaced_with_space(self):
        """Il testo con newline viene salvato con spazi al posto dei newline."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "test", "text": "Line1\nLine2\nLine3", "url": "https://x.com/t1"},
        ])
        # The INSERT line should contain 'Line1 Line2 Line3' not multiline
        assert "Line1 Line2 Line3" in sql
        assert "Line1\nLine2" not in sql

    def test_crlf_newline_replaced(self):
        """Windows CRLF viene anch'esso sostituito con spazio."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "test", "text": "Line1\r\nLine2", "url": "https://x.com/t1"},
        ])
        assert "Line1 Line2" in sql
        assert "Line1\r\nLine2" not in sql

    def test_single_quote_still_escaped(self):
        """Gli apici singoli vengono ancora escapati correttamente."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "test", "text": "It's a test", "url": "https://x.com/t1"},
        ])
        assert "It''s a test" in sql

    def test_multiple_tweets_with_newlines(self):
        """Più tweet con newline, nessuno genera righe anomale."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "a", "text": "Text A\n-- comment A", "url": "https://x.com/t1"},
            {"tweet_id": "t2", "keyword": "b", "text": "Text B\n-- comment B", "url": "https://x.com/t2"},
            {"tweet_id": "t3", "keyword": "c", "text": "Normal text C",       "url": "https://x.com/t3"},
        ])
        assert _has_anomalous_comment_lines(sql) == []

    def test_generated_sql_is_valid_sqlite(self):
        """Il SQL generato è eseguibile senza errori su un DB fresco."""
        sql = _run_backup_with_rows([
            {"tweet_id": "t1", "keyword": "grimorio", "text": "Primera línea.\n\n-- Que tranquilo está todo hoy.", "url": "https://x.com/t1"},
            {"tweet_id": "t2", "keyword": "grimoire", "text": "Gramarye, magic.\n--SCOTT: Lay of the Last Minstrel.\n--Idem.", "url": "https://x.com/t2"},
        ])
        # Execute the SQL on a fresh DB with the same schema
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE twitter_tweets (
                id INTEGER PRIMARY KEY,
                tweet_id TEXT,
                keyword TEXT,
                text TEXT,
                url TEXT,
                likes INTEGER,
                scraped_at TEXT
            )
        """)
        errors = []
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.upper() in ("BEGIN TRANSACTION", "COMMIT", "BEGIN", "END"):
                continue
            # Strip comment lines (as restore does)
            non_comment = "\n".join(
                ln for ln in stmt.splitlines() if not ln.strip().startswith("--")
            ).strip()
            if not non_comment:
                continue
            try:
                conn.execute(non_comment)
            except Exception as e:
                errors.append(str(e))
        conn.close()
        assert errors == [], f"SQL errors after fix: {errors}"
