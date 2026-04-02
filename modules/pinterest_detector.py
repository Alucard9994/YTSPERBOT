"""
YTSPERBOT - Pinterest Detector
Monitora trend su Pinterest via API v5 ufficiale.

Setup:
  1. Vai su https://developers.pinterest.com → crea un'app
  2. Genera un access token con scope: pins:read, user_accounts:read
  3. Aggiungi al .env: PINTEREST_ACCESS_TOKEN=il_tuo_token

Endpoint usati:
  - GET /v5/trends/keywords/growing  → keyword in crescita su Pinterest
  - GET /v5/trends/keywords/emerging → keyword emergenti (nuove)
"""
from __future__ import annotations

import os
import time
import requests
from datetime import datetime

from modules.utils import calculate_velocity
from modules.database import (
    save_keyword_count,
    was_alert_sent_recently,
    mark_alert_sent,
)
from modules.telegram_bot import send_message

PINTEREST_API_BASE = "https://api.pinterest.com/v5"

# Categorie Pinterest rilevanti per la nicchia
PINTEREST_INTERESTS = [
    "ENTERTAINMENT",
    "HUMOR",
    "HISTORY",
    "SCIENCE",
    "EDUCATION",
]

PINTEREST_ENABLED = bool(os.getenv("PINTEREST_ACCESS_TOKEN"))


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.getenv('PINTEREST_ACCESS_TOKEN')}"}


def get_trending_keywords(
    trend_type: str = "growing", region: str = "IT", limit: int = 50
) -> list:
    """
    Recupera keyword trending su Pinterest.
    trend_type: 'growing' | 'emerging' | 'top' | 'seasonal'
    """
    try:
        resp = requests.get(
            f"{PINTEREST_API_BASE}/trends/keywords/{trend_type}",
            headers=_headers(),
            params={
                "region": region,
                "limit": limit,
                "interests[]": PINTEREST_INTERESTS,
                "normalized": "true",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("trends", [])
        else:
            print(
                f"[PINTEREST] Errore API trends ({trend_type}): {resp.status_code} — {resp.text[:200]}"
            )
            return []
    except Exception as e:
        print(f"[PINTEREST] Errore richiesta trends: {e}")
        return []


def get_keyword_trend_data(keyword: str, region: str = "IT") -> dict | None:
    """Recupera il trend di una singola keyword (weekly interest)."""
    try:
        resp = requests.get(
            f"{PINTEREST_API_BASE}/trends/keywords/top",
            headers=_headers(),
            params={
                "region": region,
                "keywords[]": [keyword],
                "limit": 1,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            trends = resp.json().get("trends", [])
            return trends[0] if trends else None
    except Exception as e:
        print(f"[PINTEREST] Errore trend keyword '{keyword}': {e}")
    return None


def send_pinterest_trend_alert(
    keyword: str, trend_type: str, weekly_trend: list, region: str
):
    """Invia alert per keyword trending su Pinterest."""
    flag = {"IT": "🇮🇹", "US": "🇺🇸", "GB": "🇬🇧"}.get(region, region)
    type_label = {
        "growing": "📈 In crescita",
        "emerging": "🚀 Emergente (nuova)",
        "top": "🔝 Top ricercata",
    }.get(trend_type, trend_type)

    # Calcola variazione se abbiamo dati settimanali
    trend_str = ""
    if weekly_trend and len(weekly_trend) >= 2:
        first = weekly_trend[0].get("value", 0)
        last = weekly_trend[-1].get("value", 0)
        if first > 0:
            change = ((last - first) / first) * 100
            trend_str = f"\n📊 <b>Variazione:</b> {'+' if change >= 0 else ''}{change:.0f}% (7 giorni)"

    text = (
        f"📌 <b>PINTEREST TREND {flag}</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"📈 <b>Tipo:</b> {type_label}{trend_str}\n"
        f"🌍 <b>Regione:</b> {region}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Questo topic sta crescendo nelle ricerche Pinterest — forte segnale visuale/editoriale.</i>"
    )
    return send_message(text)


def send_pinterest_new_keyword_alert(keyword: str, region: str):
    """Alert per keyword completamente nuova su Pinterest (emerging)."""
    flag = {"IT": "🇮🇹", "US": "🇺🇸"}.get(region, region)
    text = (
        f"🌱 <b>NUOVA KEYWORD PINTEREST {flag}</b>\n\n"
        f"💡 <b>Keyword emergente:</b> <code>{keyword}</code>\n"
        f"🌍 <b>Regione:</b> {region}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Keyword nuova in forte crescita su Pinterest — potenziale topic video inaspettato.</i>"
    )
    return send_message(text)


def _keyword_matches_niche(keyword: str, niche_keywords: list) -> bool:
    """True se la keyword Pinterest è semanticamente vicina alla nostra nicchia."""
    keyword_lower = keyword.lower()

    # Match diretto con keyword monitorate
    if any(
        kw.lower() in keyword_lower or keyword_lower in kw.lower()
        for kw in niche_keywords
    ):
        return True

    # Match semantico con parole chiave della nicchia
    niche_words = {
        "ghost",
        "haunted",
        "paranormal",
        "occult",
        "witch",
        "witchcraft",
        "demon",
        "spirit",
        "horror",
        "dark",
        "mystery",
        "mystical",
        "magic",
        "spell",
        "ritual",
        "folklore",
        "legend",
        "cryptid",
        "alien",
        "ufo",
        "conspiracy",
        "secret",
        "forbidden",
        "curse",
        "gothic",
        "supernatural",
        "fantasma",
        "strega",
        "magia",
        "occulto",
        "demonio",
        "mistero",
        "paranormale",
        "oscuro",
        "leggenda",
        "creatura",
        "horror",
    }
    return any(word in keyword_lower for word in niche_words)


# ============================================================
# Funzione principale
# ============================================================


def run_pinterest_detector(config: dict):
    """Esegue il Pinterest trend detector."""

    if not PINTEREST_ENABLED:
        print(
            "[PINTEREST] Modulo disabilitato. Aggiungere PINTEREST_ACCESS_TOKEN al .env per attivarlo."
        )
        return

    print(f"\n[PINTEREST] Avvio detector — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    pinterest_cfg = config.get("pinterest", {})
    regions = pinterest_cfg.get("regions", ["IT", "US"])
    velocity_threshold = pinterest_cfg.get("velocity_threshold", 30)
    niche_keywords = config.get("keywords", [])

    for region in regions:
        print(f"[PINTEREST] Analisi regione: {region}")

        # --- Growing trends ---
        growing = get_trending_keywords("growing", region=region, limit=50)
        for trend in growing:
            keyword = trend.get("keyword", "").strip()
            if not keyword or not _keyword_matches_niche(keyword, niche_keywords):
                continue

            weekly = trend.get("weekly_trend_info", {}).get("weekly_data", [])
            alert_id = f"pinterest_growing_{region}_{keyword[:40].lower()}"

            if was_alert_sent_recently(alert_id, "pinterest_trend", hours=24):
                continue

            print(f"[PINTEREST] Growing match ({region}): '{keyword}'")
            send_pinterest_trend_alert(keyword, "growing", weekly, region)
            mark_alert_sent(alert_id, "pinterest_trend")
            time.sleep(0.5)

        time.sleep(2)

        # --- Emerging trends ---
        emerging = get_trending_keywords("emerging", region=region, limit=50)
        for trend in emerging:
            keyword = trend.get("keyword", "").strip()
            if not keyword or not _keyword_matches_niche(keyword, niche_keywords):
                continue

            alert_id = f"pinterest_emerging_{region}_{keyword[:40].lower()}"
            if was_alert_sent_recently(alert_id, "pinterest_emerging", hours=48):
                continue

            print(f"[PINTEREST] Emerging match ({region}): '{keyword}'")
            send_pinterest_new_keyword_alert(keyword, region)
            mark_alert_sent(alert_id, "pinterest_emerging")
            time.sleep(0.5)

        # --- Velocity tracking sulle keyword monitorate ---
        for keyword in niche_keywords[:20]:
            trend_data = get_keyword_trend_data(keyword, region)
            if not trend_data:
                continue

            weekly = trend_data.get("weekly_trend_info", {}).get("weekly_data", [])
            if len(weekly) < 2:
                continue

            interest_now = weekly[-1].get("value", 0)
            interest_before = weekly[-2].get("value", 0) if len(weekly) >= 2 else 0

            if interest_now == 0 or interest_before == 0:
                continue

            save_keyword_count(keyword, f"pinterest_{region}", interest_now)
            velocity = calculate_velocity(interest_now, interest_before)
            if velocity is None:
                continue

            if velocity >= velocity_threshold:
                alert_id = f"pinterest_velocity_{region}_{keyword[:40].lower()}"
                if was_alert_sent_recently(alert_id, "pinterest_velocity", hours=12):
                    continue
                print(f"[PINTEREST] Velocity ({region}): '{keyword}' +{velocity:.0f}%")
                send_pinterest_trend_alert(keyword, "growing", weekly, region)
                mark_alert_sent(alert_id, "pinterest_velocity")

            time.sleep(1)

    print("[PINTEREST] Detector completato.")
