from fastapi import APIRouter, HTTPException
from modules.database import (
    get_discovery_suggestions,
    get_discovery_pending_count,
    update_discovery_suggestion_status,
    config_list_add,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])

# Mapping tipo → list_key in config_lists
_TYPE_TO_LIST_KEY = {
    "tiktok_hashtag": "tiktok_hashtags",
    "instagram_hashtag": "instagram_hashtags",
    "subreddit": "subreddits",
    "keyword": "keywords",
}


@router.get("/suggestions")
def list_suggestions(status: str = "pending", limit: int = 200):
    """Restituisce i suggerimenti discovery filtrati per status."""
    return {
        "suggestions": get_discovery_suggestions(status=status, limit=limit),
        "pending_count": get_discovery_pending_count(),
    }


@router.post("/suggestions/{suggestion_id}/accept")
def accept_suggestion(suggestion_id: int):
    """
    Accetta un suggerimento: lo aggiunge alla config_list corrispondente
    e ne marca lo status come 'accepted'.
    """
    rows = get_discovery_suggestions(status="all", limit=10000)
    suggestion = next((r for r in rows if r["id"] == suggestion_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")

    list_key = _TYPE_TO_LIST_KEY.get(suggestion["type"])
    if not list_key:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo '{suggestion['type']}' non mappabile a una lista",
        )

    config_list_add(list_key, suggestion["value"])
    update_discovery_suggestion_status(suggestion_id, "accepted")
    return {"ok": True, "added_to": list_key, "value": suggestion["value"]}


@router.post("/suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: int):
    """Rifiuta un suggerimento (non viene più mostrato come pending)."""
    update_discovery_suggestion_status(suggestion_id, "rejected")
    return {"ok": True}
