from fastapi import APIRouter
from modules.database import get_connection as _get_conn

router = APIRouter(prefix="/pinterest", tags=["pinterest"])


@router.get("/alerts")
def pinterest_alerts(hours: int = 168):
    """Alert Pinterest (growing + emerging + velocity)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, alert_type, velocity_pct, extra_json, sent_at
        FROM alerts_log
        WHERE alert_type IN ('pinterest_trend', 'pinterest_emerging', 'pinterest_velocity')
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 30
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword-counts")
def keyword_counts(hours: int = 168):
    """Menzioni keyword dalla fonte Pinterest."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source LIKE '%pinterest%'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
