from fastapi import APIRouter
from typing import Optional
from modules.database import (
    get_youtube_outperformer_log,
    get_competitor_video_log,
    get_comment_intel,
    get_daily_brief_data,
    get_connection as _get_conn,
)

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/outperformer")
def outperformer(days: int = 30, limit: int = 50, video_type: Optional[str] = None):
    """Video YouTube outperformer rilevati negli ultimi N giorni. Filtrabile per video_type=short|long."""
    rows = get_youtube_outperformer_log(days=days, limit=limit)
    if video_type:
        rows = [r for r in rows if (r.get("video_type") or "long") == video_type]
    return rows


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


@router.get("/subscriber-sparkline")
def subscriber_sparkline(days: int = 10):
    """Storico iscritti per ogni canale competitor (per sparkline)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT channel_id, channel_name, subscribers,
               DATE(recorded_at) AS day
        FROM channel_subscribers_history
        WHERE recorded_at >= datetime('now', ? || ' days')
        ORDER BY channel_id, recorded_at ASC
    """, (f"-{days}",)).fetchall()
    conn.close()
    channels = {}
    for r in rows:
        r = dict(r)
        cid = r["channel_id"]
        if cid not in channels:
            channels[cid] = {"channel_id": cid, "channel_name": r["channel_name"], "points": []}
        # One point per day (last value of the day)
        pts = channels[cid]["points"]
        if pts and pts[-1]["day"] == r["day"]:
            pts[-1]["subscribers"] = r["subscribers"]
        else:
            pts.append({"day": r["day"], "subscribers": r["subscribers"]})
    return list(channels.values())


@router.get("/competitor-videos/by-keyword")
def competitor_videos_by_keyword(days: int = 7, limit: int = 150):
    """Video competitor raggruppati per keyword matchata (ultimi N giorni)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT video_id, title, channel_name, channel_id,
               matched_keyword, published_at, detected_at
        FROM competitor_video_log
        WHERE detected_at >= datetime('now', ? || ' days')
          AND matched_keyword IS NOT NULL AND matched_keyword != ''
        ORDER BY detected_at DESC
        LIMIT ?
    """, (f"-{days}", limit)).fetchall()
    conn.close()
    groups = {}
    for r in rows:
        r = dict(r)
        kw = r["matched_keyword"]
        if kw not in groups:
            groups[kw] = {"keyword": kw, "count": 0, "videos": []}
        groups[kw]["count"] += 1
        groups[kw]["videos"].append(r)
    return sorted(groups.values(), key=lambda x: x["count"], reverse=True)


@router.get("/comments/category-stats")
def comments_category_stats(hours: int = 168):
    """Distribuzione aggregata delle categorie dei commenti."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT category, COUNT(*) AS count
        FROM youtube_comment_intel
        WHERE detected_at >= datetime('now', ? || ' hours')
          AND category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY count DESC
    """, (f"-{hours}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
