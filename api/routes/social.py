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


def _normalize_profile(row: dict) -> dict:
    """Rinomina i campi DB nei nomi attesi dal frontend."""
    row = dict(row)
    # username → handle, display_name → name, last_analyzed → scraped_at
    if "username" in row:
        row["handle"] = row.pop("username")
    if "display_name" in row:
        row["name"] = row.pop("display_name")
    if "last_analyzed" in row:
        row["scraped_at"] = row.pop("last_analyzed")
    return row


@router.get("/profiles")
def profiles(platform: str = None, limit: int = 200):
    """Tutti i profili TikTok/Instagram scoperti."""
    conn = _get_conn()
    if platform:
        rows = conn.execute(
            """
            SELECT platform, username, display_name, followers, avg_views,
                   is_pinned, first_seen, last_analyzed
            FROM apify_profiles WHERE platform = ?
            ORDER BY avg_views DESC NULLS LAST
            LIMIT ?
            """,
            (platform, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT platform, username, display_name, followers, avg_views,
                   is_pinned, first_seen, last_analyzed
            FROM apify_profiles
            ORDER BY platform, avg_views DESC NULLS LAST
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    conn.close()
    return [_normalize_profile(r) for r in rows]


@router.get("/watchlist")
def watchlist(platform: str = None):
    """Profili nella watchlist (pinned)."""
    rows = list_pinned_profiles(platform=platform)
    return [_normalize_profile(r) for r in rows]


class WatchlistItem(BaseModel):
    platform: str
    # Il frontend manda 'handle'; supportiamo anche 'username' per retrocompatibilità
    handle: str = None
    username: str = None

    def resolved_username(self) -> str:
        return self.username or self.handle or ""


@router.post("/watchlist")
def add_to_watchlist(item: WatchlistItem):
    if item.platform not in ("tiktok", "instagram"):
        raise HTTPException(
            status_code=400, detail="platform deve essere 'tiktok' o 'instagram'"
        )
    upsert_pinned_profile(item.platform, item.resolved_username())
    return {"ok": True}


@router.delete("/watchlist")
def remove_from_watchlist(item: WatchlistItem):
    remove_pinned_profile(item.platform, item.resolved_username())
    return {"ok": True}


@router.get("/outperformer-videos")
def outperformer_videos(days: int = 30, limit: int = 50):
    """Video TikTok/Instagram outperformer rilevati."""
    return get_outperformer_videos(days=days, limit=limit)
