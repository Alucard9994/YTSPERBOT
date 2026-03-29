from fastapi import APIRouter
from modules.database import (
    get_daily_brief_data,
    get_alerts_log,
    get_multi_source_keywords,
    get_connection as _get_conn,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/keywords")
def keywords(hours: int = 168, limit: int = 15):
    """Top keyword per menzioni nelle ultime N ore con serie temporale."""
    data = get_daily_brief_data(hours=hours)
    return data[:limit]


@router.get("/alerts")
def alerts(hours: int = 24, limit: int = 50):
    """Storico alert inviati via Telegram."""
    return get_alerts_log(hours=hours, limit=limit)


@router.get("/convergences")
def convergences(hours: int = 6, min_sources: int = 3):
    """Keyword presenti su N+ fonti nelle ultime N ore (cross-signal)."""
    return get_multi_source_keywords(hours=hours, min_sources=min_sources)


@router.get("/alerts-timeline")
def alerts_timeline(days: int = 14):
    """Volume di alert per giorno negli ultimi N giorni."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT DATE(sent_at) AS day, COUNT(*) AS count
        FROM alerts_log
        WHERE sent_at >= datetime('now', ? || ' days')
        GROUP BY day
        ORDER BY day ASC
    """,
        (f"-{days}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword-sources")
def keyword_sources(hours: int = 168, limit: int = 15):
    """Per-source breakdown per le top keyword (menzioni per fonte)."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, source, SUM(count) AS count
        FROM keyword_mentions
        WHERE recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword, source
        ORDER BY keyword, count DESC
    """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    breakdown = {}
    for r in rows:
        r = dict(r)
        kw = r["keyword"]
        if kw not in breakdown:
            breakdown[kw] = []
        breakdown[kw].append({"source": r["source"], "count": r["count"]})
    return breakdown
