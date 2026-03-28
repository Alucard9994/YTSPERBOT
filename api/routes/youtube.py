from fastapi import APIRouter
from modules.database import (
    get_youtube_outperformer_log,
    get_competitor_video_log,
    get_daily_brief_data,
    get_connection as _get_conn,
)

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/outperformer")
def outperformer(days: int = 30, limit: int = 50):
    """Video YouTube outperformer rilevati negli ultimi N giorni."""
    return get_youtube_outperformer_log(days=days, limit=limit)


@router.get("/competitor-videos")
def competitor_videos(hours: int = 48, limit: int = 50):
    """Nuovi video dai canali competitor nelle ultime N ore."""
    return get_competitor_video_log(hours=hours, limit=limit)


@router.get("/competitors")
def competitors():
    """Canali competitor con storico iscritti (ultimi 8 giorni)."""
    conn = _get_conn()
    # Prendi l'ultimo valore per ogni canale + il primo degli ultimi 8 giorni per calcolare crescita
    rows = conn.execute("""
        SELECT
            channel_id,
            channel_name,
            MAX(subscribers) AS subscribers_now,
            MIN(subscribers) AS subscribers_week_ago,
            COUNT(*) AS data_points
        FROM channel_subscribers_history
        WHERE recorded_at >= datetime('now', '-8 days')
        GROUP BY channel_id
        ORDER BY subscribers_now DESC
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        r = dict(r)
        if r["subscribers_week_ago"] and r["subscribers_week_ago"] > 0:
            growth = ((r["subscribers_now"] - r["subscribers_week_ago"]) / r["subscribers_week_ago"]) * 100
        else:
            growth = 0
        r["growth_pct"] = round(growth, 1)
        result.append(r)
    return result


@router.get("/comments/keywords")
def comments_keywords(hours: int = 168, limit: int = 10):
    """Top keyword dai commenti YouTube (source=yt_comments)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT keyword, SUM(count) AS total
        FROM keyword_mentions
        WHERE source LIKE '%comment%'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT ?
    """, (f"-{hours}", limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
