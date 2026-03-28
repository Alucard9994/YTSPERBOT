import os
from fastapi import APIRouter
from modules.database import get_connection as _get_conn, DB_PATH

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def status():
    """Stato del bot: credenziali, dimensione DB, contatori tabelle."""
    credentials = {
        "youtube":   bool(os.getenv("YOUTUBE_API_KEY")),
        "twitter":   bool(os.getenv("TWITTER_BEARER_TOKEN")),
        "reddit":    bool(os.getenv("REDDIT_CLIENT_ID")) and bool(os.getenv("REDDIT_CLIENT_SECRET")),
        "apify":     bool(os.getenv("APIFY_API_KEY")),
        "news":      bool(os.getenv("NEWSAPI_KEY")),
        "pinterest": bool(os.getenv("PINTEREST_ACCESS_TOKEN")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }

    conn = _get_conn()
    tables = {}
    for table in [
        "keyword_mentions", "apify_profiles", "channel_subscribers_history",
        "alerts_log", "youtube_outperformer_log", "competitor_video_log",
        "reddit_seen_posts", "keyword_blacklist", "sent_alerts",
    ]:
        try:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            tables[table] = row["n"]
        except Exception:
            tables[table] = 0
    conn.close()

    db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

    return {
        "credentials": credentials,
        "tables": tables,
        "db_size_mb": round(db_size_bytes / 1024 / 1024, 2),
    }


@router.get("/db-stats")
def db_stats():
    """Statistiche sintetiche del database."""
    conn = _get_conn()
    result = {}
    for table in [
        "keyword_mentions", "apify_profiles", "channel_subscribers_history",
        "alerts_log", "youtube_outperformer_log", "competitor_video_log",
    ]:
        try:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            result[table] = row["n"]
        except Exception:
            result[table] = 0
    conn.close()
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    result["db_size_mb"] = round(db_size / 1024 / 1024, 2)
    return result
