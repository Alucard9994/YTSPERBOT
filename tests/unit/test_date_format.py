"""
Unit tests — formato delle date restituite dal DB/API.

Il frontend usa utils/date.js → parseDate() che normalizza il separatore
da spazio a 'T'. Questi test verificano che:
  1. SQLite restituisca date nel formato atteso (con o senza 'T')
  2. Tutte le date presenti nelle risposte API siano parseable da new Date() JS
  3. I campi data critici non siano None/stringa vuota

Modella il comportamento di parseDate() e fmtDate() di date.js in Python,
così possiamo catturare regressioni server-side prima che arrivino al browser.
"""

import re
from datetime import datetime


from modules.database import get_connection, log_alert, save_keyword_count


# ─── Replica Python di parseDate() / fmtDate() da webapp/src/utils/date.js ───

ISO_T_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
SQLITE_SPACE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def py_parse_date(s):
    """
    Replica di parseDate() in date.js.
    Restituisce un datetime se parseable, None altrimenti.
    """
    if not s:
        return None
    # Normalizza il separatore spazio→T (stesso di date.js riga 12)
    normalized = re.sub(r"^(\d{4}-\d{2}-\d{2}) ", r"\1T", str(s))
    try:
        # Python non gestisce il '+00:00' in alcuni formati, usiamo fromisoformat
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def assert_js_parseable(value, field_name="date"):
    """
    Verifica che una stringa sia leggibile da new Date() in JS.
    In pratica: deve avere il formato YYYY-MM-DD[T ]HH:MM:SS...
    """
    assert value is not None, f"'{field_name}' è None"
    assert isinstance(value, str) and value.strip(), (
        f"'{field_name}' è vuoto o non-stringa"
    )
    parsed = py_parse_date(value)
    assert parsed is not None, (
        f"'{field_name}' = {value!r} non è parseable. "
        "Formati accettati: 'YYYY-MM-DDTHH:MM:SS...' o 'YYYY-MM-DD HH:MM:SS...' "
        "(il secondo è gestito da parseDate() in date.js)"
    )


# ─── Test su py_parse_date() stesso ───────────────────────────────────────────


class TestPyParseDate:
    """Verifica che la nostra replica di parseDate() funzioni correttamente."""

    def test_iso_with_T(self):
        assert py_parse_date("2026-03-27T03:43:23") is not None

    def test_sqlite_space_separator(self):
        """Formato SQLite con spazio — il caso critico del bug #5."""
        result = py_parse_date("2026-03-27 03:43:23.225770+00:00")
        assert result is not None, "il formato SQLite con spazio deve essere parseable"

    def test_sqlite_with_timezone(self):
        result = py_parse_date("2026-03-28 15:00:00+00:00")
        assert result is not None

    def test_none_returns_none(self):
        assert py_parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert py_parse_date("") is None

    def test_invalid_format_returns_none(self):
        assert py_parse_date("not-a-date") is None
        assert py_parse_date("27/03/2026") is None

    def test_microseconds_handled(self):
        result = py_parse_date("2026-03-27T03:43:23.225770+00:00")
        assert result is not None


# ─── Test sulle date restituite dal DB ────────────────────────────────────────


class TestSqliteDateFormat:
    """
    Verifica che le date scritte/lette da SQLite abbiano il formato
    che il frontend può parsare.
    """

    def test_recorded_at_format_in_keyword_mentions(self):
        """save_keyword_count deve salvare recorded_at parseable da JS."""
        save_keyword_count("date_fmt_kw", "rss", 1)
        conn = get_connection()
        row = conn.execute(
            "SELECT recorded_at FROM keyword_mentions WHERE keyword = 'date_fmt_kw'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert_js_parseable(row["recorded_at"], "recorded_at")

    def test_sent_at_format_in_alerts_log(self):
        """log_alert deve salvare sent_at parseable da JS."""
        log_alert("rss_trend", "date_alert_kw", "rss")
        conn = get_connection()
        row = conn.execute(
            "SELECT sent_at FROM alerts_log WHERE keyword = 'date_alert_kw'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert_js_parseable(row["sent_at"], "sent_at")

    def test_datetime_now_utc_format(self):
        """
        Il formato usato da SQLite datetime('now') deve essere compatibile.
        Questo test documenta il formato esatto che arriva al frontend.
        """
        conn = get_connection()
        row = conn.execute("SELECT datetime('now') AS now").fetchone()
        conn.close()
        val = row["now"]
        # SQLite restituisce 'YYYY-MM-DD HH:MM:SS' (con spazio)
        assert SQLITE_SPACE_PATTERN.match(val) or re.match(
            r"^\d{4}-\d{2}-\d{2}T", val
        ), f"datetime('now') ha formato inatteso: {val!r}"
        # Deve essere parseable da parseDate()
        assert_js_parseable(val, "datetime('now')")


# ─── Test date nei risultati API ──────────────────────────────────────────────


class TestApiDateFields:
    """
    Verifica che tutti i campi data nelle risposte API siano parseable.
    Usa il client FastAPI in modo standalone (senza fixture) tramite imports diretti.
    """

    def test_alerts_log_sent_at_parseable(self):
        """alerts_log.sent_at deve essere parseable da parseDate() in date.js"""
        log_alert("rss_trend", "api_date_kw", "rss")
        conn = get_connection()
        rows = conn.execute(
            "SELECT sent_at FROM alerts_log WHERE keyword = 'api_date_kw'"
        ).fetchall()
        conn.close()
        assert rows, "nessuna riga trovata"
        for row in rows:
            assert_js_parseable(row["sent_at"], "alerts_log.sent_at")

    def test_keyword_mentions_recorded_at_parseable(self):
        save_keyword_count("rec_at_kw", "google_trends", 3)
        conn = get_connection()
        rows = conn.execute(
            "SELECT recorded_at FROM keyword_mentions WHERE keyword = 'rec_at_kw'"
        ).fetchall()
        conn.close()
        assert rows
        for row in rows:
            assert_js_parseable(row["recorded_at"], "keyword_mentions.recorded_at")

    def test_get_multi_source_keywords_last_seen_parseable(self):
        """
        get_multi_source_keywords() deve restituire last_seen parseable.
        BUG FIXATO: prima mancava MAX(recorded_at) AS last_seen nel SELECT.
        """
        from modules.database import get_multi_source_keywords

        save_keyword_count("multi_src_kw", "rss", 2)
        save_keyword_count("multi_src_kw", "reddit", 2)
        results = get_multi_source_keywords(hours=1, min_sources=2)
        matching = [r for r in results if r.get("keyword") == "multi_src_kw"]
        assert matching, "keyword non trovata in get_multi_source_keywords"
        row = matching[0]
        assert "last_seen" in row, (
            "get_multi_source_keywords non restituisce 'last_seen'. "
            "Il frontend (DashboardPage.jsx:120) chiama fmtDate(c.last_seen)."
        )
        assert_js_parseable(row["last_seen"], "get_multi_source_keywords.last_seen")


# ─── Test regressioni specifiche bug storici ──────────────────────────────────


class TestDateRegressions:
    """Test mirati ai bug esatti scoperti dopo il restore del 28/03/2026."""

    def test_convergences_last_seen_not_none(self):
        """
        BUG: get_multi_source_keywords non aveva last_seen → fmtDate(undefined) → 'Invalid Date'
        """
        from modules.database import get_multi_source_keywords

        for src in ("rss", "reddit", "twitter"):
            save_keyword_count("reg_conv_kw", src, 1)
        results = get_multi_source_keywords(hours=1, min_sources=2)
        matching = [r for r in results if r["keyword"] == "reg_conv_kw"]
        assert matching
        assert matching[0].get("last_seen") is not None, (
            "last_seen è None — questo causa 'Invalid Date' nel frontend"
        )

    def test_no_invalid_date_in_alerts_log(self):
        """
        Tutte le righe in alerts_log devono avere sent_at non-None e parseable.
        """
        log_alert("rss_trend", "inv_date_kw1", "rss")
        log_alert("news_trend", "inv_date_kw2", "news")
        conn = get_connection()
        rows = conn.execute(
            "SELECT keyword, sent_at FROM alerts_log WHERE keyword LIKE 'inv_date_kw%'"
        ).fetchall()
        conn.close()
        assert len(rows) == 2
        for row in rows:
            assert row["sent_at"] is not None, (
                f"sent_at è NULL per keyword={row['keyword']}"
            )
            assert_js_parseable(
                row["sent_at"], f"alerts_log.sent_at ({row['keyword']})"
            )

    def test_space_separator_handled_by_parse_date(self):
        """
        SQLite usa spazio come separatore data-ora.
        parseDate() in date.js lo converte in 'T' prima di passarlo a new Date().
        Questo test verifica che la nostra replica Python funzioni come JS.
        """
        sqlite_format = "2026-03-27 03:43:23.225770+00:00"
        result = py_parse_date(sqlite_format)
        assert result is not None, (
            f"Il formato SQLite {sqlite_format!r} non è parseable. "
            "Questo provocherebbe 'Invalid Date' in Safari/Firefox."
        )
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 27
