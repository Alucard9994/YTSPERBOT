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


@router.get("/keyword-search")
def keyword_search(keyword: str, hours: int = 168):
    """Per-source breakdown + totale per una singola keyword."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT source, SUM(count) AS count
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
          AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY source
        ORDER BY count DESC
        """,
        (keyword, f"-{hours}"),
    ).fetchall()
    total_row = conn.execute(
        """
        SELECT SUM(count) AS total,
               COUNT(DISTINCT source) AS source_count,
               MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE LOWER(keyword) = LOWER(?)
          AND recorded_at >= datetime('now', ? || ' hours')
        """,
        (keyword, f"-{hours}"),
    ).fetchone()
    conn.close()

    sources = [{"source": r["source"], "count": r["count"]} for r in rows]
    return {
        "keyword": keyword,
        "hours": hours,
        "total": (total_row["total"] or 0) if total_row else 0,
        "source_count": (total_row["source_count"] or 0) if total_row else 0,
        "last_seen": (total_row["last_seen"]) if total_row else None,
        "sources": sources,
    }


@router.get("/highlights")
def highlights():
    """
    Aggregato dei migliori contenuti per categoria:
    - Top 3 video YouTube outperformer (per multiplier)
    - Top 3 video TikTok/Instagram outperformer (per multiplier)
    - Top 3 commenti YouTube con più likes (ultimi 30 giorni)
    - Miglior segnale Reddit, Twitter, Pinterest, News (per velocity)
    """
    conn = _get_conn()

    yt = conn.execute(
        """
        SELECT video_id, title, channel_name, views, multiplier_avg,
               video_type, published_at, detected_at
        FROM youtube_outperformer_log
        ORDER BY multiplier_avg DESC
        LIMIT 3
        """
    ).fetchall()

    social = conn.execute(
        """
        SELECT platform, video_id, username, title, views, url, multiplier, detected_at
        FROM apify_outperformer_videos
        ORDER BY multiplier DESC
        LIMIT 3
        """
    ).fetchall()

    comments = conn.execute(
        """
        SELECT video_id, video_title, channel_name, comment_text, likes, category, detected_at
        FROM youtube_comment_intel
        WHERE detected_at >= datetime('now', '-30 days')
        ORDER BY likes DESC
        LIMIT 3
        """
    ).fetchall()

    def _best_signal(source_pattern: str, use_like: bool = False):
        """
        Cerca prima un velocity alert negli ultimi 7 giorni in alerts_log.
        Se non trovato, fa fallback alla keyword più menzionata in keyword_mentions
        (ultimi 7 giorni) per quella fonte — così la card mostra sempre attività.
        """
        op = "LIKE" if use_like else "="
        row = conn.execute(
            f"""
            SELECT keyword, velocity_pct, sent_at, alert_type
            FROM alerts_log
            WHERE source {op} ?
              AND sent_at >= datetime('now', '-7 days')
            ORDER BY velocity_pct DESC NULLS LAST, sent_at DESC
            LIMIT 1
            """,
            (source_pattern,),
        ).fetchone()
        if row:
            return dict(row)

        # Fallback: keyword_mentions — keyword più attiva per questa fonte
        fb = conn.execute(
            f"""
            SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS sent_at
            FROM keyword_mentions
            WHERE source {op} ?
              AND recorded_at >= datetime('now', '-7 days')
            GROUP BY keyword
            ORDER BY total DESC
            LIMIT 1
            """,
            (source_pattern,),
        ).fetchone()
        if fb:
            return {
                "keyword":      fb["keyword"],
                "velocity_pct": None,
                "sent_at":      fb["sent_at"],
                "alert_type":   "mention",
            }
        return None

    reddit_top    = _best_signal("reddit%",    use_like=True)
    twitter_top   = _best_signal("twitter%",   use_like=True)
    pinterest_top = _best_signal("pinterest%", use_like=True)
    news_top      = _best_signal("news")

    conn.close()

    return {
        "youtube_top":   [dict(r) for r in yt],
        "social_top":    [dict(r) for r in social],
        "comments_top":  [dict(r) for r in comments],
        "reddit_top":    reddit_top,
        "twitter_top":   twitter_top,
        "pinterest_top": pinterest_top,
        "news_top":      news_top,
    }
