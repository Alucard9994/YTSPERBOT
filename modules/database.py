"""
YTSPERBOT - Modulo Database
Gestisce la persistenza locale via SQLite
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.getenv(
    "YTSPERBOT_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "ytsperbot.db"),
)

os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inizializza il database con tutte le tabelle necessarie."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            source TEXT NOT NULL,
            count INTEGER NOT NULL,
            recorded_at TIMESTAMP NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reddit_seen_posts (
            post_id TEXT PRIMARY KEY,
            subreddit TEXT NOT NULL,
            seen_at TIMESTAMP NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sent_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            identifier TEXT NOT NULL,
            sent_at TIMESTAMP NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS youtube_seen_channels (
            channel_id TEXT NOT NULL,
            video_id TEXT NOT NULL,
            sent_at TIMESTAMP NOT NULL,
            PRIMARY KEY (channel_id, video_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS keyword_blacklist (
            keyword TEXT PRIMARY KEY,
            added_at TIMESTAMP NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_id_cache (
            handle TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            cached_at TIMESTAMP NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_subscribers_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            subscribers INTEGER NOT NULL,
            recorded_at TIMESTAMP NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS apify_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT,
            followers INTEGER DEFAULT 0,
            avg_views REAL DEFAULT 0,
            first_seen TIMESTAMP NOT NULL,
            last_analyzed TIMESTAMP,
            is_pinned INTEGER NOT NULL DEFAULT 0,
            UNIQUE(platform, username)
        )
    """)
    # Migrazione: aggiunge is_pinned ai DB esistenti (operazione idempotente)
    try:
        c.execute(
            "ALTER TABLE apify_profiles ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0"
        )
    except Exception:
        pass  # colonna già presente

    c.execute("""
        CREATE TABLE IF NOT EXISTS apify_seen_videos (
            platform TEXT NOT NULL,
            video_id TEXT NOT NULL,
            sent_at TIMESTAMP NOT NULL,
            PRIMARY KEY (platform, video_id)
        )
    """)

    # apify_outperformer_videos: video social outperformer con dettagli
    c.execute("""
        CREATE TABLE IF NOT EXISTS apify_outperformer_videos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform    TEXT NOT NULL,
            video_id    TEXT NOT NULL UNIQUE,
            username    TEXT NOT NULL,
            title       TEXT,
            views       INTEGER DEFAULT 0,
            url         TEXT,
            multiplier  REAL DEFAULT 0,
            detected_at TIMESTAMP NOT NULL
        )
    """)

    # alerts_log: storico completo degli alert mandati via Telegram
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type   TEXT NOT NULL,
            keyword      TEXT NOT NULL,
            source       TEXT NOT NULL,
            velocity_pct REAL,
            sources_list TEXT,
            priority     INTEGER DEFAULT 5,
            extra_json   TEXT,
            sent_at      TIMESTAMP NOT NULL
        )
    """)

    # youtube_outperformer_log: video YouTube outperformer rilevati
    c.execute("""
        CREATE TABLE IF NOT EXISTS youtube_outperformer_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id         TEXT NOT NULL UNIQUE,
            title            TEXT NOT NULL,
            channel_name     TEXT NOT NULL,
            channel_id       TEXT,
            subscribers      INTEGER DEFAULT 0,
            views            INTEGER DEFAULT 0,
            avg_views        REAL DEFAULT 0,
            multiplier_avg   REAL DEFAULT 0,
            multiplier_subs  REAL DEFAULT 0,
            video_type       TEXT DEFAULT 'long',
            duration_seconds INTEGER DEFAULT 0,
            published_at     TIMESTAMP,
            detected_at      TIMESTAMP NOT NULL
        )
    """)

    # competitor_video_log: nuovi video dei canali competitor
    c.execute("""
        CREATE TABLE IF NOT EXISTS competitor_video_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id         TEXT NOT NULL UNIQUE,
            title            TEXT NOT NULL,
            channel_name     TEXT NOT NULL,
            channel_id       TEXT,
            matched_keyword  TEXT,
            published_at     TIMESTAMP,
            detected_at      TIMESTAMP NOT NULL
        )
    """)

    # youtube_comment_intel: commenti individuali da video competitor
    c.execute("""
        CREATE TABLE IF NOT EXISTS youtube_comment_intel (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id      TEXT,
            video_title   TEXT,
            channel_name  TEXT,
            comment_text  TEXT NOT NULL,
            likes         INTEGER DEFAULT 0,
            category      TEXT DEFAULT NULL,
            detected_at   TIMESTAMP NOT NULL
        )
    """)

    # bot_logs: log di sistema intercettati dallo stdout del bot
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            level      TEXT NOT NULL DEFAULT 'INFO',
            module     TEXT NOT NULL DEFAULT 'system',
            message    TEXT NOT NULL,
            logged_at  TIMESTAMP NOT NULL
        )
    """)

    # scheduler_runs: traccia l'ultimo run di ogni job (persiste tra restart)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_runs (
            job_name   TEXT PRIMARY KEY,
            last_run   TIMESTAMP NOT NULL
        )
    """)
    # ── Pulizia automatica tabelle (retention policy) ──────────────────────
    _cleanups = [
        # (tabella, colonna_data, giorni_retention)
        ("bot_logs",                "logged_at",   7),
        ("keyword_mentions",        "recorded_at", 90),
        ("alerts_log",              "sent_at",     90),
        ("youtube_outperformer_log","detected_at", 180),
        ("competitor_video_log",    "detected_at", 180),
        ("youtube_comment_intel",   "detected_at", 180),
    ]
    for _table, _col, _days in _cleanups:
        try:
            c.execute(
                f"DELETE FROM {_table} WHERE {_col} < datetime('now', '-{_days} days')"
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    config_lists_table_init()
    config_table_init()
    print(f"[DB] Database inizializzato in {DB_PATH}")


def save_keyword_count(keyword: str, source: str, count: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO keyword_mentions (keyword, source, count, recorded_at) VALUES (?, ?, ?, ?)",
        (keyword, source, count, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def get_keyword_counts(keyword: str, source: str, hours_ago: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT count, recorded_at FROM keyword_mentions
        WHERE keyword = ? AND source = ?
        AND recorded_at >= datetime('now', ? || ' hours')
        ORDER BY recorded_at ASC
    """,
        (keyword, source, f"-{hours_ago}"),
    ).fetchall()
    conn.close()
    return rows


def is_post_seen(post_id: str, source: str = "") -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM reddit_seen_posts WHERE post_id = ?", (post_id,)
    ).fetchone()
    conn.close()
    return row is not None


def mark_post_seen(post_id: str, subreddit: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO reddit_seen_posts (post_id, subreddit, seen_at) VALUES (?, ?, ?)",
        (post_id, subreddit, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def is_channel_video_sent(channel_id: str, video_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM youtube_seen_channels WHERE channel_id = ? AND video_id = ?",
        (channel_id, video_id),
    ).fetchone()
    conn.close()
    return row is not None


def mark_channel_video_sent(channel_id: str, video_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO youtube_seen_channels (channel_id, video_id, sent_at) VALUES (?, ?, ?)",
        (channel_id, video_id, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


# --- Blacklist ---


def is_blacklisted(keyword: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM keyword_blacklist WHERE LOWER(keyword) = LOWER(?)", (keyword,)
    ).fetchone()
    conn.close()
    return row is not None


def add_to_blacklist(keyword: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO keyword_blacklist (keyword, added_at) VALUES (LOWER(?), ?)",
        (keyword, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def remove_from_blacklist(keyword: str):
    conn = get_connection()
    conn.execute(
        "DELETE FROM keyword_blacklist WHERE LOWER(keyword) = LOWER(?)", (keyword,)
    )
    conn.commit()
    conn.close()


def get_blacklist() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT keyword FROM keyword_blacklist ORDER BY keyword"
    ).fetchall()
    conn.close()
    return [r["keyword"] for r in rows]


# --- Daily Brief ---


def get_daily_brief_data(hours: int = 24) -> list:
    """Restituisce le top keyword per menzioni nelle ultime N ore, con conteggio fonti."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            keyword,
            SUM(count) AS total_mentions,
            COUNT(DISTINCT source) AS source_count,
            GROUP_CONCAT(DISTINCT source) AS sources,
            MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total_mentions DESC
        LIMIT 15
    """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Score ---


def get_keyword_source_count(keyword: str, hours: int = 24) -> int:
    """Quante fonti diverse hanno menzionato questa keyword nelle ultime N ore."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT source) AS cnt
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
        AND recorded_at >= datetime('now', ? || ' hours')
    """,
        (keyword, f"-{hours}"),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# --- Channel ID Cache ---


def get_channel_id_cache(handle: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT channel_id FROM channel_id_cache WHERE LOWER(handle) = LOWER(?)",
        (handle,),
    ).fetchone()
    conn.close()
    return row["channel_id"] if row else None


def set_channel_id_cache(handle: str, channel_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO channel_id_cache (handle, channel_id, cached_at) VALUES (LOWER(?), ?, ?)",
        (handle, channel_id, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


# --- Subscriber History ---


def save_subscriber_count(channel_id: str, channel_name: str, subscribers: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO channel_subscribers_history (channel_id, channel_name, subscribers, recorded_at) VALUES (?, ?, ?, ?)",
        (channel_id, channel_name, subscribers, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def get_subscriber_history(channel_id: str, days: int = 8) -> list:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT subscribers, recorded_at FROM channel_subscribers_history
        WHERE channel_id = ?
        AND recorded_at >= datetime('now', ? || ' days')
        ORDER BY recorded_at DESC
    """,
        (channel_id, f"-{days}"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Keyword mentions per /cerca e /graph ---


def get_keyword_all_mentions(keyword: str, hours: int = 168) -> list:
    """Menzioni per keyword aggregate per fonte — usato da /cerca."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT source, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY source
        ORDER BY total DESC
    """,
        (keyword, f"-{hours}"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_keyword_timeseries(keyword: str, hours: int = 168) -> list:
    """Serie temporale menzioni per keyword — usato da /graph."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            strftime('%Y-%m-%d %H:00', recorded_at) AS hour_bucket,
            SUM(count) AS total
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY hour_bucket
        ORDER BY hour_bucket ASC
    """,
        (keyword, f"-{hours}"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Apify Profiles ---


def upsert_apify_profile(
    platform: str, username: str, display_name: str, followers: int
):
    """Inserisce un nuovo profilo o lo aggiorna se già esiste."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO apify_profiles (platform, username, display_name, followers, first_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(platform, username) DO UPDATE SET
            display_name = excluded.display_name,
            followers = excluded.followers
    """,
        (platform, username, display_name, followers, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def apify_profile_exists(platform: str, username: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM apify_profiles WHERE platform = ? AND LOWER(username) = LOWER(?)",
        (platform, username),
    ).fetchone()
    conn.close()
    return row is not None


def count_apify_profiles_added_today(platform: str) -> int:
    """Quanti profili sono stati aggiunti oggi per questa piattaforma."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt FROM apify_profiles
        WHERE platform = ? AND DATE(first_seen) = DATE('now')
    """,
        (platform,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_apify_profiles_to_analyze(platform: str, recheck_days: int, limit: int) -> list:
    """
    Non-pinned profiles to analyze:
    - never analyzed (last_analyzed IS NULL)
    - not analyzed in the last N days
    - OR followers=0 (always re-analyzed to recover the missing count)
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT username, display_name, followers, 0 AS is_pinned FROM apify_profiles
        WHERE platform = ?
        AND COALESCE(is_pinned, 0) = 0
        AND (
            last_analyzed IS NULL
            OR last_analyzed < datetime('now', ? || ' days')
            OR COALESCE(followers, 0) = 0
        )
        ORDER BY last_analyzed ASC NULLS FIRST
        LIMIT ?
    """,
        (platform, f"-{recheck_days}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_pinned_profile(platform: str, username: str, display_name: str = ""):
    """Aggiunge o segna come pinned un profilo da monitorare sempre."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO apify_profiles (platform, username, display_name, followers, is_pinned, first_seen)
        VALUES (?, ?, ?, 0, 1, ?)
        ON CONFLICT(platform, username) DO UPDATE SET
            is_pinned = 1,
            display_name = CASE WHEN excluded.display_name != '' THEN excluded.display_name ELSE display_name END
    """,
        (platform, username, display_name or username, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def remove_pinned_profile(platform: str, username: str):
    """Rimuove il flag pinned (il profilo rimane in DB come normale)."""
    conn = get_connection()
    conn.execute(
        """
        UPDATE apify_profiles SET is_pinned = 0
        WHERE platform = ? AND LOWER(username) = LOWER(?)
    """,
        (platform, username),
    )
    conn.commit()
    conn.close()


def list_pinned_profiles(platform: str = None) -> list:
    """Restituisce tutti i profili pinned, opzionalmente filtrati per piattaforma."""
    conn = get_connection()
    if platform:
        rows = conn.execute(
            """
            SELECT platform, username, display_name, followers, last_analyzed
            FROM apify_profiles WHERE COALESCE(is_pinned, 0) = 1 AND platform = ?
            ORDER BY username
        """,
            (platform,),
        ).fetchall()
    else:
        rows = conn.execute("""
            SELECT platform, username, display_name, followers, last_analyzed
            FROM apify_profiles WHERE COALESCE(is_pinned, 0) = 1
            ORDER BY platform, username
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_apify_profile_analyzed(
    platform: str, username: str, avg_views: float, followers: int = None
):
    conn = get_connection()
    if followers is not None and followers > 0:
        conn.execute(
            """
            UPDATE apify_profiles SET last_analyzed = ?, avg_views = ?, followers = ?
            WHERE platform = ? AND LOWER(username) = LOWER(?)
            """,
            (datetime.now(timezone.utc), avg_views, followers, platform, username),
        )
    else:
        conn.execute(
            """
            UPDATE apify_profiles SET last_analyzed = ?, avg_views = ?
            WHERE platform = ? AND LOWER(username) = LOWER(?)
            """,
            (datetime.now(timezone.utc), avg_views, platform, username),
        )
    conn.commit()
    conn.close()


def is_apify_video_sent(platform: str, video_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM apify_seen_videos WHERE platform = ? AND video_id = ?",
        (platform, video_id),
    ).fetchone()
    conn.close()
    return row is not None


def mark_apify_video_sent(platform: str, video_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO apify_seen_videos (platform, video_id, sent_at) VALUES (?, ?, ?)",
        (platform, video_id, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def save_outperformer_video(
    platform: str,
    video_id: str,
    username: str,
    title: str,
    views: int,
    url: str,
    multiplier: float,
):
    """Salva i dettagli di un video outperformer social."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO apify_outperformer_videos
            (platform, video_id, username, title, views, url, multiplier, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            platform,
            video_id,
            username,
            title,
            views,
            url,
            multiplier,
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    conn.close()


def get_outperformer_videos(days: int = 30, limit: int = 50) -> list:
    """Ultimi video outperformer TikTok/Instagram."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT platform, video_id, username, title, views, url, multiplier, detected_at
        FROM apify_outperformer_videos
        WHERE detected_at >= datetime('now', ? || ' days')
        ORDER BY multiplier DESC, detected_at DESC
        LIMIT ?
    """,
        (f"-{days}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Bot Config (override via Telegram)
# ============================================================


def config_table_init():
    """Crea la tabella bot_config se non esiste."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            type        TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT 'yaml',
            updated_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def config_load_defaults(flat_config: dict):
    """
    Inserisce i valori di default (dal config.yaml) nel DB.
    Usa INSERT OR IGNORE: i valori già presenti (override utente) non vengono sovrascritti.
    flat_config: {key: (value_str, type_str)}
    """
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    for key, (value_str, type_str) in flat_config.items():
        conn.execute(
            "INSERT OR IGNORE INTO bot_config (key, value, type, source, updated_at) VALUES (?, ?, ?, 'yaml', ?)",
            (key, value_str, type_str, now),
        )
    conn.commit()
    conn.close()


def config_get_all() -> list:
    """Restituisce tutte le righe di bot_config, ordinate per chiave."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT key, value, type, source, updated_at FROM bot_config ORDER BY key"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def config_get(key: str) -> dict | None:
    """Restituisce una singola chiave di configurazione (o None se non esiste)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT key, value, type, source, updated_at FROM bot_config WHERE key = ?",
        (key,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def config_set(key: str, value_str: str, type_str: str):
    """Aggiorna o inserisce un valore di configurazione (source = 'user')."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO bot_config (key, value, type, source, updated_at) VALUES (?, ?, ?, 'user', ?)
        ON CONFLICT(key) DO UPDATE SET
            value      = excluded.value,
            source     = 'user',
            updated_at = excluded.updated_at
    """,
        (key, value_str, type_str, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_multi_source_keywords(hours: int = 6, min_sources: int = 3) -> list:
    """Trova keyword che appaiono su N+ fonti diverse nelle ultime N ore (cross-signal)."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            keyword,
            COUNT(DISTINCT source) AS source_count,
            SUM(count) AS total_mentions,
            GROUP_CONCAT(DISTINCT source) AS sources,
            MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        HAVING COUNT(DISTINCT source) >= ?
        ORDER BY source_count DESC, total_mentions DESC
    """,
        (f"-{hours}", min_sources),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def was_alert_sent_recently(identifier: str, alert_type: str, hours: int = 24) -> bool:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT 1 FROM sent_alerts
        WHERE identifier = ? AND alert_type = ?
        AND sent_at >= datetime('now', ? || ' hours')
    """,
        (identifier, alert_type, f"-{hours}"),
    ).fetchone()
    conn.close()
    return row is not None


def mark_alert_sent(identifier: str, alert_type: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO sent_alerts (alert_type, identifier, sent_at) VALUES (?, ?, ?)",
        (alert_type, identifier, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


# ============================================================
# Config Lists (liste configurabili via Telegram)
# ============================================================


def config_lists_table_init():
    """Crea la tabella config_lists se non esiste."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_lists (
            list_key  TEXT NOT NULL,
            value     TEXT NOT NULL,
            label     TEXT DEFAULT NULL,
            PRIMARY KEY (list_key, value)
        )
    """)
    conn.commit()
    conn.close()


def config_list_seed(list_key: str, items: list):
    """
    Seed iniziale da config.yaml: popola il DB se la lista è vuota.
    items: lista di str (simple/channel) o dict {name, url} (feed)
    """
    if not items:
        return
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM config_lists WHERE list_key = ?", (list_key,)
    ).fetchone()["n"]

    if count == 0:
        inserted = 0
        for item in items:
            if isinstance(item, dict):
                value = item.get("url") or item.get("handle", "")
                label = item.get("name") or None
            else:
                value = str(item)
                label = None
            if value:
                conn.execute(
                    "INSERT OR IGNORE INTO config_lists (list_key, value, label) VALUES (?, ?, ?)",
                    (list_key, value, label),
                )
                inserted += 1
        conn.commit()
        if inserted:
            print(
                f"[DB] config_lists: seeded '{list_key}' con {inserted} voci",
                flush=True,
            )
    conn.close()


def config_list_add(list_key: str, value: str, label: str = None):
    """Aggiunge un elemento alla lista. Ignora duplicati."""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO config_lists (list_key, value, label) VALUES (?, ?, ?)",
        (list_key, value, label),
    )
    conn.commit()
    conn.close()


def config_list_remove(list_key: str, value: str):
    """Rimuove un elemento dalla lista (match esatto sul value)."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM config_lists WHERE list_key = ? AND value = ?", (list_key, value)
    )
    conn.commit()
    conn.close()


def config_list_get(list_key: str) -> list:
    """Restituisce tutti gli elementi di una lista come [{value, label}, ...]."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT value, label FROM config_lists WHERE list_key = ? ORDER BY ROWID",
        (list_key,),
    ).fetchall()
    conn.close()
    return [{"value": r["value"], "label": r["label"]} for r in rows]


# ============================================================
# Alerts Log
# ============================================================


def log_alert(
    alert_type: str,
    keyword: str,
    source: str,
    velocity_pct: float = None,
    sources_list: str = None,
    priority: int = 5,
    extra_json: str = None,
):
    """Registra un alert nel log storico (chiamato insieme a mark_alert_sent)."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO alerts_log
            (alert_type, keyword, source, velocity_pct, sources_list, priority, extra_json, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            alert_type,
            keyword,
            source,
            velocity_pct,
            sources_list,
            priority,
            extra_json,
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    conn.close()


def get_alerts_log(hours: int = 24, limit: int = 50) -> list:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, alert_type, keyword, source, velocity_pct, sources_list, priority, extra_json, sent_at
        FROM alerts_log
        WHERE sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT ?
    """,
        (f"-{hours}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# YouTube Outperformer Log
# ============================================================


def log_youtube_outperformer(
    video_id: str,
    title: str,
    channel_name: str,
    channel_id: str,
    subscribers: int,
    views: int,
    avg_views: float,
    multiplier_avg: float,
    multiplier_subs: float,
    video_type: str,
    duration_seconds: int,
    published_at,
):
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO youtube_outperformer_log
            (video_id, title, channel_name, channel_id, subscribers, views, avg_views,
             multiplier_avg, multiplier_subs, video_type, duration_seconds, published_at, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            video_id,
            title,
            channel_name,
            channel_id,
            subscribers,
            views,
            avg_views,
            multiplier_avg,
            multiplier_subs,
            video_type,
            duration_seconds,
            published_at,
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    conn.close()


def get_youtube_outperformer_log(days: int = 30, limit: int = 200) -> list:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM youtube_outperformer_log
        WHERE detected_at >= datetime('now', ? || ' days')
        ORDER BY detected_at DESC, multiplier_avg DESC
        LIMIT ?
    """,
        (f"-{days}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Competitor Video Log
# ============================================================


def log_competitor_video(
    video_id: str,
    title: str,
    channel_name: str,
    channel_id: str,
    matched_keyword: str = None,
    published_at=None,
):
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO competitor_video_log
            (video_id, title, channel_name, channel_id, matched_keyword, published_at, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            video_id,
            title,
            channel_name,
            channel_id,
            matched_keyword,
            published_at,
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    conn.close()


def save_comment_intel(
    video_id: str, video_title: str, channel_name: str, comments: list
):
    """
    Salva commenti individuali analizzati da un video competitor.
    comments: [{"text": str, "likes": int, "category": str}, ...]
    """
    if not comments:
        return
    conn = get_connection()
    now = datetime.now(timezone.utc)
    for c in comments:
        conn.execute(
            """INSERT INTO youtube_comment_intel
               (video_id, video_title, channel_name, comment_text, likes, category, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                video_id,
                video_title,
                channel_name,
                c.get("text", "")[:1000],
                int(c.get("likes", 0)),
                c.get("category"),
                now,
            ),
        )
    conn.commit()
    conn.close()


def get_comment_intel(hours: int = 168, limit: int = 200) -> list:
    """Restituisce i commenti competitor salvati, raggruppati per video."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, video_id, video_title, channel_name, comment_text, likes, category, detected_at
        FROM youtube_comment_intel
        WHERE detected_at >= datetime('now', ? || ' hours')
        ORDER BY detected_at DESC, likes DESC
        LIMIT ?
    """,
        (f"-{hours}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_competitor_video_log(hours: int = 48, limit: int = 50) -> list:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM competitor_video_log
        WHERE detected_at >= datetime('now', ? || ' hours')
        ORDER BY detected_at DESC
        LIMIT ?
    """,
        (f"-{hours}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def config_lists_get_all() -> dict:
    """Restituisce tutte le config_lists raggruppate per list_key (1 query)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT list_key, value, label FROM config_lists ORDER BY list_key, ROWID"
    ).fetchall()
    conn.close()
    result: dict[str, list] = {}
    for r in rows:
        result.setdefault(r["list_key"], []).append(
            {"value": r["value"], "label": r["label"]}
        )
    return result


# ── Bot logs ─────────────────────────────────────────────────────────────────


def save_bot_log(level: str, message: str, module: str = "system"):
    """Salva un log di sistema nel DB (chiamato dall'interceptor stdout)."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO bot_logs (level, module, message, logged_at) VALUES (?, ?, ?, ?)",
            (level.upper(), module[:40], message[:1000], datetime.now(timezone.utc)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # non propagare mai errori dal logger


def get_bot_logs(minutes: int = 60, level: str = "ALL", limit: int = 200) -> list:
    """Recupera i log di sistema con filtro opzionale per level e finestra temporale."""
    conn = get_connection()
    if level and level.upper() != "ALL":
        rows = conn.execute(
            """
            SELECT id, level, module, message, logged_at
            FROM bot_logs
            WHERE logged_at >= datetime('now', ? || ' minutes')
              AND level = ?
            ORDER BY logged_at DESC
            LIMIT ?
        """,
            (f"-{minutes}", level.upper(), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, level, module, message, logged_at
            FROM bot_logs
            WHERE logged_at >= datetime('now', ? || ' minutes')
            ORDER BY logged_at DESC
            LIMIT ?
        """,
            (f"-{minutes}", limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cleanup_db(retention_days: dict = None) -> dict:
    """
    Pulisce le tabelle analytics/operative eliminando record più vecchi del retention configurato.

    Non tocca mai:
    - bot_config, config_lists, keyword_blacklist, scheduler_runs  → configurazione utente
    - channel_id_cache                                              → cache API (non ha timestamp)
    - reddit_seen_posts, sent_alerts, youtube_seen_channels,
      apify_seen_videos                                             → deduplication (se pulite causano re-notifiche)

    Parametri:
        retention_days: dict {nome_tabella: giorni} — sovrascrive i default se fornito

    Restituisce:
        dict {nome_tabella: righe_eliminate}
    """
    defaults = {
        "keyword_mentions":           ("recorded_at",   90),
        "alerts_log":                 ("sent_at",        90),
        "bot_logs":                   ("logged_at",       7),
        "youtube_outperformer_log":   ("detected_at",   180),
        "competitor_video_log":       ("detected_at",   180),
        "youtube_comment_intel":      ("detected_at",   180),
        "channel_subscribers_history":("recorded_at",   180),
        "apify_outperformer_videos":  ("detected_at",    90),
    }

    # Merge retention personalizzata sopra i default
    plan: dict[str, tuple[str, int]] = {}
    for table, (col, default_days) in defaults.items():
        if retention_days and table in retention_days:
            plan[table] = (col, int(retention_days[table]))
        else:
            plan[table] = (col, default_days)

    conn = get_connection()
    results = {}
    for table, (col, days) in plan.items():
        try:
            before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.execute(
                f"DELETE FROM {table} WHERE {col} < datetime('now', '-{days} days')"
            )
            after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            results[table] = before - after
        except Exception as e:
            results[table] = f"errore: {e}"
    # Commit the DELETEs before VACUUM — SQLite forbids VACUUM inside a transaction
    conn.commit()
    # Switch to autocommit mode: VACUUM cannot run inside any transaction
    conn.isolation_level = None
    conn.execute("VACUUM")
    conn.close()
    return results


def mark_job_run(job_name: str):
    """Registra il timestamp corrente come ultimo run del job specificato."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO scheduler_runs (job_name, last_run) VALUES (?, ?)",
        (job_name, datetime.now(timezone.utc)),
    )
    conn.commit()
    conn.close()


def get_last_job_run(job_name: str) -> datetime | None:
    """Restituisce il datetime dell'ultimo run del job, o None se mai eseguito."""
    conn = get_connection()
    row = conn.execute(
        "SELECT last_run FROM scheduler_runs WHERE job_name = ?", (job_name,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    val = row["last_run"]
    if isinstance(val, str):
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    return val
