"""
YTSPERBOT - Modulo Database
Gestisce la persistenza locale via SQLite
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ytsperbot.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


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

    conn.commit()
    conn.close()
    print(f"[DB] Database inizializzato in {DB_PATH}")


def save_keyword_count(keyword: str, source: str, count: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO keyword_mentions (keyword, source, count, recorded_at) VALUES (?, ?, ?, ?)",
        (keyword, source, count, datetime.now(timezone.utc))
    )
    conn.commit()
    conn.close()


def get_keyword_counts(keyword: str, source: str, hours_ago: int) -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT count, recorded_at FROM keyword_mentions
        WHERE keyword = ? AND source = ?
        AND recorded_at >= datetime('now', ? || ' hours')
        ORDER BY recorded_at ASC
    """, (keyword, source, f"-{hours_ago}")).fetchall()
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
        (post_id, subreddit, datetime.now(timezone.utc))
    )
    conn.commit()
    conn.close()


def is_channel_video_sent(channel_id: str, video_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM youtube_seen_channels WHERE channel_id = ? AND video_id = ?",
        (channel_id, video_id)
    ).fetchone()
    conn.close()
    return row is not None


def mark_channel_video_sent(channel_id: str, video_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO youtube_seen_channels (channel_id, video_id, sent_at) VALUES (?, ?, ?)",
        (channel_id, video_id, datetime.now(timezone.utc))
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
        (keyword, datetime.now(timezone.utc))
    )
    conn.commit()
    conn.close()


def remove_from_blacklist(keyword: str):
    conn = get_connection()
    conn.execute("DELETE FROM keyword_blacklist WHERE LOWER(keyword) = LOWER(?)", (keyword,))
    conn.commit()
    conn.close()


def get_blacklist() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT keyword FROM keyword_blacklist ORDER BY keyword").fetchall()
    conn.close()
    return [r["keyword"] for r in rows]


# --- Daily Brief ---

def get_daily_brief_data(hours: int = 24) -> list:
    """Restituisce le top keyword per menzioni nelle ultime N ore, con conteggio fonti."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            keyword,
            SUM(count) AS total_mentions,
            COUNT(DISTINCT source) AS source_count,
            GROUP_CONCAT(DISTINCT source) AS sources
        FROM keyword_mentions
        WHERE recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total_mentions DESC
        LIMIT 15
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Score ---

def get_keyword_source_count(keyword: str, hours: int = 24) -> int:
    """Quante fonti diverse hanno menzionato questa keyword nelle ultime N ore."""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(DISTINCT source) AS cnt
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
        AND recorded_at >= datetime('now', ? || ' hours')
    """, (keyword, f"-{hours}")).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# --- Channel ID Cache ---

def get_channel_id_cache(handle: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT channel_id FROM channel_id_cache WHERE LOWER(handle) = LOWER(?)", (handle,)
    ).fetchone()
    conn.close()
    return row["channel_id"] if row else None


def set_channel_id_cache(handle: str, channel_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO channel_id_cache (handle, channel_id, cached_at) VALUES (LOWER(?), ?, ?)",
        (handle, channel_id, datetime.now(timezone.utc))
    )
    conn.commit()
    conn.close()


# --- Subscriber History ---

def save_subscriber_count(channel_id: str, channel_name: str, subscribers: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO channel_subscribers_history (channel_id, channel_name, subscribers, recorded_at) VALUES (?, ?, ?, ?)",
        (channel_id, channel_name, subscribers, datetime.now(timezone.utc))
    )
    conn.commit()
    conn.close()


def get_subscriber_history(channel_id: str, days: int = 8) -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT subscribers, recorded_at FROM channel_subscribers_history
        WHERE channel_id = ?
        AND recorded_at >= datetime('now', ? || ' days')
        ORDER BY recorded_at DESC
    """, (channel_id, f"-{days}")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Keyword mentions per /cerca e /graph ---

def get_keyword_all_mentions(keyword: str, hours: int = 168) -> list:
    """Menzioni per keyword aggregate per fonte — usato da /cerca."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT source, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY source
        ORDER BY total DESC
    """, (keyword, f"-{hours}")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_keyword_timeseries(keyword: str, hours: int = 168) -> list:
    """Serie temporale menzioni per keyword — usato da /graph."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            strftime('%Y-%m-%d %H:00', recorded_at) AS hour_bucket,
            SUM(count) AS total
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY hour_bucket
        ORDER BY hour_bucket ASC
    """, (keyword, f"-{hours}")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def was_alert_sent_recently(identifier: str, alert_type: str, hours: int = 24) -> bool:
    conn = get_connection()
    row = conn.execute("""
        SELECT 1 FROM sent_alerts
        WHERE identifier = ? AND alert_type = ?
        AND sent_at >= datetime('now', ? || ' hours')
    """, (identifier, alert_type, f"-{hours}")).fetchone()
    conn.close()
    return row is not None


def mark_alert_sent(identifier: str, alert_type: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO sent_alerts (alert_type, identifier, sent_at) VALUES (?, ?, ?)",
        (alert_type, identifier, datetime.now(timezone.utc))
    )
    conn.commit()
    conn.close()
