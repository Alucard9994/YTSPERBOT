from fastapi import APIRouter
from modules.database import get_connection as _get_conn

router = APIRouter(prefix="/twitter", tags=["twitter"])


@router.get("/tweets")
def top_tweets(hours: int = 48, limit: int = 20):
    """Top tweet per engagement (dalla tabella twitter_tweets)."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT tweet_id, keyword, text, url,
               likes, retweets, replies, quotes, author_username, author_followers,
               created_at, scraped_at,
               (likes + retweets + quotes) AS engagement
        FROM twitter_tweets
        WHERE scraped_at >= datetime('now', ? || ' hours')
        GROUP BY tweet_id
        ORDER BY engagement DESC
        LIMIT ?
        """,
        (f"-{hours}", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/alerts")
def twitter_alerts(hours: int = 168):
    """Alert Twitter/X: velocity + quote storm + thread + controversial."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, alert_type, velocity_pct, source, extra_json, sent_at
        FROM alerts_log
        WHERE alert_type IN (
            'twitter_trend', 'twitter_quote_storm',
            'twitter_thread', 'twitter_controversial'
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
    """Menzioni keyword da Twitter/X."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source IN ('twitter', 'twitter_apify')
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
        """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
