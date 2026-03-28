from fastapi import APIRouter
from modules.database import get_daily_brief_data, get_alerts_log, get_multi_source_keywords

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
