from fastapi import APIRouter
from modules.database import get_connection as _get_conn

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/alerts")
def news_alerts(hours: int = 48):
    """Alert news detector."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, velocity_pct, sent_at
        FROM alerts_log
        WHERE alert_type = 'news_trend'
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 30
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword-counts")
def keyword_counts(hours: int = 168):
    """Menzioni keyword dalla fonte news."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source = 'news'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/twitter-counts")
def twitter_counts(hours: int = 168):
    """Menzioni keyword da Twitter/X."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source IN ('twitter', 'twitter_apify')
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/twitter-alerts")
def twitter_alerts(hours: int = 168):
    """Alert Twitter/X."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, velocity_pct, sent_at
        FROM alerts_log
        WHERE alert_type = 'twitter_trend'
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 30
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
