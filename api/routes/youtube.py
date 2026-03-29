from fastapi import APIRouter
from modules.database import (
    get_youtube_outperformer_log,
    get_competitor_video_log,
    get_comment_intel,
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
    # Usa window functions per ottenere il PRIMO e l'ULTIMO valore cronologico per ogni canale
    rows = conn.execute("""
        WITH ranked AS (
            SELECT
                channel_id,
                channel_name,
                subscribers,
                recorded_at,
                ROW_NUMBER() OVER (PARTITION BY channel_id ORDER BY recorded_at ASC)  AS rn_asc,
                ROW_NUMBER() OVER (PARTITION BY channel_id ORDER BY recorded_at DESC) AS rn_desc,
                COUNT(*) OVER (PARTITION BY channel_id) AS data_points
            FROM channel_subscribers_history
            WHERE recorded_at >= datetime('now', '-8 days')
        )
        SELECT
            channel_id,
            channel_name,
            MAX(CASE WHEN rn_desc = 1 THEN subscribers END) AS subscribers_now,
            MAX(CASE WHEN rn_asc  = 1 THEN subscribers END) AS subscribers_week_ago,
            MAX(data_points) AS data_points
        FROM ranked
        GROUP BY channel_id
        ORDER BY subscribers_now DESC
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        r = dict(r)
        week_ago = r.get("subscribers_week_ago") or 0
        now_val  = r.get("subscribers_now") or 0
        if week_ago > 0 and r.get("data_points", 1) >= 2:
            growth = ((now_val - week_ago) / week_ago) * 100
        else:
            growth = 0
        r["growth_pct"] = round(growth, 1)
        result.append(r)
    return result


@router.get("/comments/intel")
def comments_intel(hours: int = 168, limit: int = 200):
    """Commenti individuali classificati dai video competitor (ultimi N ore)."""
    return get_comment_intel(hours=hours, limit=limit)


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
