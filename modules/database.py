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
