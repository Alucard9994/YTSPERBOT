from fastapi import APIRouter
from modules.database import get_connection as _get_conn

router = APIRouter(prefix="/reddit", tags=["reddit"])


@router.get("/posts")
def reddit_posts(hours: int = 48, limit: int = 20, min_upvotes: int = 0):
    """Top Reddit post per upvotes (dalla tabella reddit_posts)."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT post_id, subreddit, title, url, upvotes, num_comments, created_at, scraped_at
        FROM reddit_posts
        WHERE scraped_at >= datetime('now', ? || ' hours')
          AND upvotes >= ?
        ORDER BY upvotes DESC
        LIMIT ?
        """,
        (f"-{hours}", min_upvotes, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/alerts")
def reddit_alerts(hours: int = 168):
    """Alert Reddit: velocity trend + hot post + cross-subreddit signal."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, alert_type, velocity_pct, source, extra_json, sent_at
        FROM alerts_log
        WHERE alert_type IN (
            'reddit_apify_trend', 'reddit_hot_post', 'reddit_cross_signal'
        )
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 50
        """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword-counts")
def keyword_counts(hours: int = 168):
    """Menzioni keyword da Reddit."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source = 'reddit_apify'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
        """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
