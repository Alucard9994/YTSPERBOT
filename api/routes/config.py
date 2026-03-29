from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from modules.database import (
    config_get_all, config_get, config_set,
    config_lists_get_all, config_list_add, config_list_remove,
    get_blacklist, add_to_blacklist, remove_from_blacklist,
)
from modules.config_manager import get_config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/params")
def get_params():
    """Tutti i parametri di configurazione del bot."""
    return config_get_all()


class ParamUpdate(BaseModel):
    value: str


@router.put("/params/{key:path}")
def set_param(key: str, body: ParamUpdate):
    """Aggiorna un parametro di configurazione."""
    row = config_get(key)
    if not row:
        raise HTTPException(status_code=404, detail=f"Chiave '{key}' non trovata")
    config_set(key, body.value, row["type"])
    return {"ok": True, "key": key, "value": body.value}


@router.get("/lists")
def get_lists():
    """Tutte le liste configurabili (keywords, hashtag, subreddits, feed, canali)."""
    return config_lists_get_all()


class ListItem(BaseModel):
    list_key: str
    value: str
    label: Optional[str] = None


@router.post("/lists")
def add_list_item(item: ListItem):
    config_list_add(item.list_key, item.value, item.label)
    return {"ok": True}


@router.delete("/lists")
def remove_list_item(item: ListItem):
    config_list_remove(item.list_key, item.value)
    return {"ok": True}


@router.get("/blacklist")
def blacklist():
    return get_blacklist()


class BlacklistItem(BaseModel):
    keyword: str


@router.post("/blacklist")
def block(item: BlacklistItem):
    add_to_blacklist(item.keyword)
    return {"ok": True}


@router.delete("/blacklist/{keyword}")
def unblock(keyword: str):
    remove_from_blacklist(keyword)
    return {"ok": True}
