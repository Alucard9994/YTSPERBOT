from fastapi import APIRouter
from modules.database import get_connection as _get_conn

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/google")
def google_trends(hours: int = 168):
    """Velocity keyword da Google Trends nelle ultime N ore."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source = 'google_trends'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/rising")
def rising_queries(hours: int = 168):
    """Alert rising queries (keyword correlate emergenti)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, velocity_pct, extra_json, sent_at
        FROM alerts_log
        WHERE alert_type = 'rising_query'
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 20
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/trending-rss")
def trending_rss(hours: int = 48):
    """Alert Google Trending RSS (top ricerche IT/US filtrate)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, extra_json, sent_at
        FROM alerts_log
        WHERE alert_type = 'trending_rss'
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 20
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword-timeseries")
def keyword_timeseries(keyword: str, hours: int = 168):
    """Serie temporale per una specifica keyword (tutte le fonti)."""
    conn = _get_conn()
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
