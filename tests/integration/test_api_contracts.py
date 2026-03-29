"""
Contract tests — verificano che ogni endpoint restituisca esattamente i campi
che il frontend si aspetta di leggere.

Ogni test porta un commento che indica il file JSX che legge quel campo,
così è immediato capire dove si rompe la UI se il test fallisce.
"""

import re
from modules.database import (
    log_alert,
    save_keyword_count,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

ISO_T_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
SQLITE_SPACE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} ")


def assert_parseable_date(value: str, field: str):
    """
    Verifica che una stringa data sia parseable da JS new Date():
    - formato ISO 8601 con 'T' come separatore, oppure
    - formato SQLite con spazio (gestito da parseDate() in date.js)
    Quello che NON vogliamo è un valore None, None-str, o formato strano.
    """
    assert value is not None, f"Campo data '{field}' è None"
    assert isinstance(value, str), f"Campo data '{field}' non è una stringa"
    assert len(value) >= 10, f"Campo data '{field}' troppo corto: {value!r}"
    # Deve iniziare con YYYY-MM-DD (con T o spazio come separatore)
    assert ISO_T_RE.match(value) or SQLITE_SPACE_RE.match(value), (
        f"Campo data '{field}' ha formato non riconosciuto: {value!r}. "
        "JS new Date() potrebbe non parsarlo correttamente in tutti i browser."
    )


# ─── /api/dashboard/alerts ────────────────────────────────────────────────────


class TestDashboardAlertsContract:
    """DashboardPage.jsx legge: keyword, alert_type, source, velocity_pct, priority, sent_at"""

    def test_required_fields_present(self, client):
        log_alert("rss_trend", "contract_kw", "rss", velocity_pct=120.0, priority=7)
        r = client.get("/api/dashboard/alerts?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # Campi letti dal frontend — DashboardPage.jsx righe 156-169
        assert "keyword" in row, "manca 'keyword' — DashboardPage.jsx:157"
        assert "alert_type" in row, "manca 'alert_type' — DashboardPage.jsx:156"
        assert "source" in row, "manca 'source' — DashboardPage.jsx:158"
        assert "velocity_pct" in row, "manca 'velocity_pct' — DashboardPage.jsx:160"
        assert "priority" in row, "manca 'priority' — DashboardPage.jsx:165"
        assert "sent_at" in row, "manca 'sent_at' — DashboardPage.jsx:169"

    def test_sent_at_is_parseable_date(self, client):
        log_alert("rss_trend", "date_kw", "rss")
        r = client.get("/api/dashboard/alerts?hours=1")
        row = r.json()[0]
        assert_parseable_date(row["sent_at"], "sent_at")

    def test_velocity_pct_is_number_or_null(self, client):
        log_alert("rss_trend", "vel_kw", "rss", velocity_pct=300.0)
        r = client.get("/api/dashboard/alerts?hours=1")
        row = r.json()[0]
        assert row["velocity_pct"] is None or isinstance(
            row["velocity_pct"], (int, float)
        )


# ─── /api/dashboard/convergences ─────────────────────────────────────────────


class TestDashboardConvergencesContract:
    """
    DashboardPage.jsx legge: keyword, sources (string comma-separated), last_seen
    BUG #1 FIXED: era 'sources_list', ora 'sources'
    BUG #2 FIXED: last_seen mancava dalla query SQL
    """

    def test_required_fields_present(self, client):
        for src in ("rss", "reddit", "google_trends"):
            save_keyword_count("conv_contract", src, 5)
        r = client.get("/api/dashboard/convergences?hours=1&min_sources=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = next(d for d in data if d["keyword"] == "conv_contract")

        # DashboardPage.jsx riga 110: const srcs = (c.sources ?? '').split(',')...
        assert "sources" in row, (
            "manca 'sources' — DashboardPage.jsx:110. "
            "Non deve chiamarsi 'sources_list' o 'platforms'."
        )
        # DashboardPage.jsx riga 120: fmtDate(c.last_seen)
        assert "last_seen" in row, (
            "manca 'last_seen' — DashboardPage.jsx:120. "
            "get_multi_source_keywords deve includere MAX(recorded_at) AS last_seen."
        )
        assert "keyword" in row, "manca 'keyword'"
        assert "source_count" in row, "manca 'source_count'"

    def test_sources_is_comma_separated_string(self, client):
        for src in ("rss", "reddit", "google_trends"):
            save_keyword_count("sources_fmt_kw", src, 3)
        r = client.get("/api/dashboard/convergences?hours=1&min_sources=2")
        row = next(d for d in r.json() if d["keyword"] == "sources_fmt_kw")
        sources = row["sources"]
        assert isinstance(sources, str), (
            f"'sources' deve essere una stringa, non {type(sources)}"
        )
        parts = [s for s in sources.split(",") if s]
        assert len(parts) >= 2, (
            f"'sources' deve contenere almeno 2 fonti, trovato: {sources!r}"
        )

    def test_last_seen_is_parseable_date(self, client):
        for src in ("rss", "twitter"):
            save_keyword_count("date_conv_kw", src, 2)
        r = client.get("/api/dashboard/convergences?hours=1&min_sources=2")
        matching = [d for d in r.json() if d["keyword"] == "date_conv_kw"]
        assert matching, "keyword non trovata nelle convergenze"
        assert_parseable_date(matching[0]["last_seen"], "last_seen")

    def test_source_count_is_integer(self, client):
        for src in ("rss", "reddit"):
            save_keyword_count("cnt_kw", src, 1)
        r = client.get("/api/dashboard/convergences?hours=1&min_sources=2")
        row = next(d for d in r.json() if d["keyword"] == "cnt_kw")
        assert isinstance(row["source_count"], int)
        assert row["source_count"] >= 2

    def test_no_field_named_sources_list(self, client):
        """Regressione: il vecchio nome 'sources_list' non deve più esistere."""
        for src in ("rss", "reddit"):
            save_keyword_count("reg_kw", src, 1)
        r = client.get("/api/dashboard/convergences?hours=1&min_sources=2")
        for row in r.json():
            assert "sources_list" not in row, (
                "'sources_list' trovato nella risposta — deve chiamarsi 'sources'"
            )


# ─── /api/dashboard/keywords ─────────────────────────────────────────────────


class TestDashboardKeywordsContract:
    """
    DashboardPage.jsx legge: keyword, total_mentions
    BUG #3 FIXED: era 'count', ora 'total_mentions'
    """

    def test_required_fields_present(self, client):
        save_keyword_count("kw_contract", "rss", 10)
        r = client.get("/api/dashboard/keywords?hours=1&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # DashboardPage.jsx riga 78: kw.total_mentions
        assert "total_mentions" in row, (
            "manca 'total_mentions' — DashboardPage.jsx:78. "
            "Non deve chiamarsi 'count' o 'mentions'."
        )
        assert "keyword" in row, "manca 'keyword'"

    def test_total_mentions_is_integer(self, client):
        save_keyword_count("int_kw", "rss", 7)
        r = client.get("/api/dashboard/keywords?hours=1&limit=10")
        row = next(d for d in r.json() if d["keyword"] == "int_kw")
        assert isinstance(row["total_mentions"], int)
        assert row["total_mentions"] >= 7

    def test_no_field_named_count(self, client):
        """Regressione: 'count' non deve apparire al posto di 'total_mentions'."""
        save_keyword_count("cnt_field_kw", "rss", 3)
        r = client.get("/api/dashboard/keywords?hours=1")
        for row in r.json():
            assert "count" not in row, (
                "trovato campo 'count' — deve chiamarsi 'total_mentions' (DashboardPage.jsx:78)"
            )


# ─── /api/trends/google ───────────────────────────────────────────────────────


class TestTrendsGoogleContract:
    """
    TrendsPage.jsx (tab Google) legge: keyword, total, last_seen
    BUG #4 FIXED: non esiste velocity_pct/sent_at qui, solo total e last_seen
    """

    def test_required_fields_present(self, client):
        save_keyword_count("gtrend_kw", "google_trends", 8)
        r = client.get("/api/trends/google?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # TrendsPage.jsx riga 88: a.total
        assert "total" in row, "manca 'total' — TrendsPage.jsx:88"
        # TrendsPage.jsx riga 89: fmtDate(a.last_seen)
        assert "last_seen" in row, "manca 'last_seen' — TrendsPage.jsx:89"
        assert "keyword" in row, "manca 'keyword'"

    def test_total_is_integer(self, client):
        save_keyword_count("gtrend_int", "google_trends", 5)
        r = client.get("/api/trends/google?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "gtrend_int")
        assert isinstance(row["total"], int)

    def test_last_seen_is_parseable_date(self, client):
        save_keyword_count("gtrend_date", "google_trends", 3)
        r = client.get("/api/trends/google?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "gtrend_date")
        assert_parseable_date(row["last_seen"], "last_seen")

    def test_no_velocity_pct_in_google_trends(self, client):
        """Google trends non ha velocity_pct — il frontend non lo deve aspettare."""
        save_keyword_count("vel_absent", "google_trends", 1)
        r = client.get("/api/trends/google?hours=1")
        # velocity_pct potrebbe non esserci — va bene, ma 'total' e 'last_seen' devono esserci
        row = next(d for d in r.json() if d["keyword"] == "vel_absent")
        assert "total" in row
        assert "last_seen" in row

    def test_no_field_named_count(self, client):
        """Regressione: 'count' non deve esistere — deve essere 'total'."""
        save_keyword_count("cnt_absent", "google_trends", 1)
        r = client.get("/api/trends/google?hours=1")
        for row in r.json():
            assert "count" not in row, (
                "trovato campo 'count' — TrendsPage.jsx si aspetta 'total'"
            )


# ─── /api/news/keyword-counts ─────────────────────────────────────────────────


class TestNewsKeywordCountsContract:
    """
    NewsPage.jsx (sezione News counts) legge: keyword, total
    BUG #5 FIXED: era 'count', ora 'total'
    """

    def test_required_fields_present(self, client):
        save_keyword_count("news_kw", "news", 6)
        r = client.get("/api/news/keyword-counts?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # NewsPage.jsx riga 80: kw.total
        assert "total" in row, "manca 'total' — NewsPage.jsx:80"
        assert "keyword" in row, "manca 'keyword'"
        assert "last_seen" in row, "manca 'last_seen'"

    def test_total_is_integer(self, client):
        save_keyword_count("news_int", "news", 4)
        r = client.get("/api/news/keyword-counts?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "news_int")
        assert isinstance(row["total"], int)
        assert row["total"] >= 4

    def test_no_field_named_count(self, client):
        save_keyword_count("news_noc", "news", 1)
        r = client.get("/api/news/keyword-counts?hours=1")
        for row in r.json():
            assert "count" not in row, (
                "trovato campo 'count' — NewsPage.jsx:80 si aspetta 'total'"
            )

    def test_last_seen_is_parseable_date(self, client):
        save_keyword_count("news_date", "news", 2)
        r = client.get("/api/news/keyword-counts?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "news_date")
        assert_parseable_date(row["last_seen"], "last_seen")


# ─── /api/news/twitter-counts ─────────────────────────────────────────────────


class TestNewsTwitterCountsContract:
    """
    NewsPage.jsx (sezione Twitter counts) legge: keyword, total
    Stesso contratto di /news/keyword-counts ma fonte twitter/twitter_apify
    """

    def test_required_fields_present(self, client):
        save_keyword_count("twit_kw", "twitter", 9)
        r = client.get("/api/news/twitter-counts?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        assert "total" in row, "manca 'total' — NewsPage.jsx:141"
        assert "keyword" in row, "manca 'keyword'"
        assert "last_seen" in row, "manca 'last_seen'"

    def test_twitter_apify_source_included(self, client):
        """Menzioni da 'twitter_apify' devono apparire nei conteggi Twitter."""
        save_keyword_count("apify_kw", "twitter_apify", 5)
        r = client.get("/api/news/twitter-counts?hours=1")
        kws = [d["keyword"] for d in r.json()]
        assert "apify_kw" in kws, (
            "menzioni 'twitter_apify' non incluse in /twitter-counts"
        )

    def test_no_field_named_count(self, client):
        save_keyword_count("twit_noc", "twitter", 1)
        r = client.get("/api/news/twitter-counts?hours=1")
        for row in r.json():
            assert "count" not in row


# ─── /api/news/alerts ─────────────────────────────────────────────────────────


class TestNewsAlertsContract:
    """NewsPage.jsx legge: keyword, velocity_pct, sent_at"""

    def test_required_fields_present(self, client):
        log_alert("news_trend", "news_alert_kw", "news", velocity_pct=80.0)
        r = client.get("/api/news/alerts?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # NewsPage.jsx righe 109-115
        assert "keyword" in row, "manca 'keyword'"
        assert "velocity_pct" in row, "manca 'velocity_pct' — NewsPage.jsx:111"
        assert "sent_at" in row, "manca 'sent_at' — NewsPage.jsx:115"

    def test_sent_at_is_parseable_date(self, client):
        log_alert("news_trend", "news_date_kw", "news")
        r = client.get("/api/news/alerts?hours=1")
        row = r.json()[0]
        assert_parseable_date(row["sent_at"], "sent_at")


# ─── /api/news/twitter-alerts ─────────────────────────────────────────────────


class TestNewsTwitterAlertsContract:
    """NewsPage.jsx legge: keyword, velocity_pct, sent_at"""

    def test_required_fields_present(self, client):
        log_alert("twitter_trend", "twit_alert_kw", "twitter", velocity_pct=150.0)
        r = client.get("/api/news/twitter-alerts?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        assert "keyword" in row, "manca 'keyword'"
        assert "velocity_pct" in row, "manca 'velocity_pct' — NewsPage.jsx:172"
        assert "sent_at" in row, "manca 'sent_at' — NewsPage.jsx:176"

    def test_sent_at_is_parseable_date(self, client):
        log_alert("twitter_trend", "twit_date_kw", "twitter")
        r = client.get("/api/news/twitter-alerts?hours=1")
        row = r.json()[0]
        assert_parseable_date(row["sent_at"], "sent_at")


# ─── /api/trends/rising ───────────────────────────────────────────────────────


class TestTrendsRisingContract:
    """TrendsPage.jsx (tab Rising) legge: keyword, velocity_pct, extra_json, sent_at"""

    def test_required_fields_present(self, client):
        log_alert(
            "rising_query",
            "rising_kw",
            "google_trends",
            velocity_pct=500.0,
            extra_json='{"parent_keyword":"AI","breakout":false}',
        )
        r = client.get("/api/trends/rising?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # TrendsPage.jsx righe 127-136
        assert "keyword" in row, "manca 'keyword'"
        assert "velocity_pct" in row, "manca 'velocity_pct' — TrendsPage.jsx:133"
        assert "extra_json" in row, "manca 'extra_json' — TrendsPage.jsx:124"
        assert "sent_at" in row, "manca 'sent_at' — TrendsPage.jsx:136"

    def test_sent_at_is_parseable_date(self, client):
        log_alert("rising_query", "rising_date_kw", "google_trends")
        r = client.get("/api/trends/rising?hours=1")
        row = r.json()[0]
        assert_parseable_date(row["sent_at"], "sent_at")

    def test_extra_json_contains_parent_keyword(self, client):
        """Il frontend tenta JSON.parse(a.extra_json) — deve contenere parent_keyword."""
        import json

        log_alert(
            "rising_query",
            "pkey_kw",
            "google_trends",
            extra_json='{"parent_keyword":"SEO","breakout":true}',
        )
        r = client.get("/api/trends/rising?hours=1")
        row = next(d for d in r.json() if d["keyword"] == "pkey_kw")
        parsed = json.loads(row["extra_json"] or "{}")
        assert "parent_keyword" in parsed


# ─── /api/trends/trending-rss ─────────────────────────────────────────────────


class TestTrendsTrendingRssContract:
    """TrendsPage.jsx (tab Trending RSS) legge: keyword, extra_json, sent_at"""

    def test_required_fields_present(self, client):
        log_alert(
            "trending_rss",
            "rss_kw",
            "google_trends",
            extra_json='{"geo":"IT","traffic":"100K+"}',
        )
        r = client.get("/api/trends/trending-rss?hours=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        row = data[0]
        # TrendsPage.jsx righe 171-175
        assert "keyword" in row, "manca 'keyword'"
        assert "extra_json" in row, "manca 'extra_json' — TrendsPage.jsx:169"
        assert "sent_at" in row, "manca 'sent_at' — TrendsPage.jsx:175"

    def test_sent_at_is_parseable_date(self, client):
        log_alert("trending_rss", "rss_date_kw", "google_trends")
        r = client.get("/api/trends/trending-rss?hours=1")
        row = r.json()[0]
        assert_parseable_date(row["sent_at"], "sent_at")
