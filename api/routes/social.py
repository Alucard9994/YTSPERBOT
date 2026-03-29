from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.database import (
    list_pinned_profiles,
    upsert_pinned_profile,
    remove_pinned_profile,
    get_outperformer_videos,
    get_connection as _get_conn,
)

router = APIRouter(prefix="/social", tags=["social"])


@router.get("/profiles")
def profiles(platform: str = None):
    """Tutti i profili TikTok/Instagram scoperti."""
    conn = _get_conn()
    if platform:
        rows = conn.execute(
            """
            SELECT platform, username, display_name, followers, avg_views,
                   is_pinned, first_seen, last_analyzed
            FROM apify_profiles WHERE platform = ?
            ORDER BY avg_views DESC NULLS LAST
        """,
            (platform,),
        ).fetchall()
    else:
        rows = conn.execute("""
            SELECT platform, username, display_name, followers, avg_views,
                   is_pinned, first_seen, last_analyzed
            FROM apify_profiles
            ORDER BY platform, avg_views DESC NULLS LAST
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/watchlist")
def watchlist(platform: str = None):
    """Profili nella watchlist (pinned)."""
    return list_pinned_profiles(platform=platform)


class WatchlistItem(BaseModel):
    platform: str
    username: str


@router.post("/watchlist")
def add_to_watchlist(item: WatchlistItem):
    if item.platform not in ("tiktok", "instagram"):
        raise HTTPException(
            status_code=400, detail="platform deve essere 'tiktok' o 'instagram'"
        )
    upsert_pinned_profile(item.platform, item.username)
    return {"ok": True}


@router.delete("/watchlist")
def remove_from_watchlist(item: WatchlistItem):
    remove_pinned_profile(item.platform, item.username)
    return {"ok": True}


@router.get("/outperformer-videos")
def outperformer_videos(days: int = 30, limit: int = 50):
    """Video TikTok/Instagram outperformer rilevati."""
    return get_outperformer_videos(days=days, limit=limit)
