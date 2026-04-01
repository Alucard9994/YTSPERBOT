"""
YTSPERBOT - Pinterest via Apify
Usa fatihtahta~pinterest-scraper-search ($3.99/1k risultati).

Actor: fatihtahta/pinterest-scraper-search
  URL: https://apify.com/fatihtahta/pinterest-scraper-search
  Rating: 5.0 ⭐ (2 recensioni) | 450 utenti | issues response: 8.5h
  Pricing: $3.99/1k risultati
  Input:  { "queries": [str], "limit": int, "type": "all-pins"|"videos"|"boards"|"profiles" }
  Output: record con type="pin" o type="profile". Struttura nested:
    {
      "type": "pin",
      "id": int,
      "url": str,          ← URL canonico del pin
      "title": str,        ← titolo top-level (alias di pin.title)
      "pin": {
        "title": str,
        "description": str,
        "closeup_description": str,
        "link": str,       ← URL destinazione esterno
        "repin_count": int,           ← salvataggi (= saves)
        "comment_count": int,
        "share_count": int,
        "is_video": bool,
        "created_at": str,
        "domain": str,
        "aggregated_pin_data": {
          "aggregated_stats": { "saves": int }  ← alternativa a repin_count
        }
      },
      "creator": { "username": str, "full_name": str, "follower_count": int, ... },
      "board_ref": { "name": str, "url": str, ... },
      "media": { "images": { "thumb": {...}, "original": {...} } }
    }

Logica:
  - Cerca pin su Pinterest per keyword monitorate (rotazione per contenere i costi)
  - Conta i pin trovati come proxy dell'interesse → calcola velocity nel tempo
  - Invia alert Telegram se la crescita supera la soglia

Configurazione consigliata per restare nel free tier Apify ($5/mese):
  pinterest.keywords_per_run: 5       # keyword per run (ruota su tutte quelle monitorate)
  pinterest.pins_per_keyword: 10      # pin per keyword (minimo: 10)
  pinterest.check_interval_hours: 360 # 2x/mese (ogni ~15 giorni)
  → 5 × 10 × 2 run/mese = 100 pin/mese × $0.00399 = $0.40/mese ✅

Costo in modalità Starter ($29/mese):
  pinterest.keywords_per_run: 12
  pinterest.pins_per_keyword: 12
  pinterest.check_interval_hours: 120  (5 run/mese)
  → 12 × 12 × 5 = 720 pin/mese × $0.00399 = $2.87/mese

Richiede APIFY_API_KEY nel .env.
"""

import os
import time
import math
from datetime import datetime

from modules.apify_scraper import run_actor
from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
)
from modules.telegram_bot import send_message

PINTEREST_ACTOR = "fatihtahta~pinterest-scraper-search"


def _search_pins(keyword: str, limit: int) -> list:
    """
    Cerca pin su Pinterest per una keyword via Apify (fatihtahta/pinterest-scraper-search).

    Input actor: queries (array), limit (min 10), type ("all-pins").
    L'actor ritorna record misti (type="pin" e type="profile"); filtriamo solo i pin.
    I campi engagement sono nested sotto item["pin"]:
      - repin_count          → saves primario
      - aggregated_pin_data.aggregated_stats.saves → fallback
    Il link esterno è in item["pin"]["link"]; item["url"] è l'URL del pin stesso.
    """
    items = run_actor(
        PINTEREST_ACTOR,
        {
            "queries": [keyword],
            "limit": max(limit, 10),  # minimo imposto dall'actor
            "type": "all-pins",
        },
    )
    pins = []
    raw_count = len(items)
    skipped_profiles = 0
    for item in items:
        # Salta esplicitamente i record di tipo "profile".
        # Non usare `!= "pin"` perché alcuni item potrebbero non avere il campo "type"
        # e verrebbero scartati erroneamente.
        if item.get("type") == "profile":
            skipped_profiles += 1
            continue

        pin_data = item.get("pin") or {}
        agg_stats = ((pin_data.get("aggregated_pin_data") or {})
                     .get("aggregated_stats") or {})

        title = item.get("title") or pin_data.get("title") or ""
        description = (pin_data.get("description")
                       or pin_data.get("closeup_description") or "")
        repins = (pin_data.get("repin_count")
                  or agg_stats.get("saves") or 0)
        # url = URL del pin Pinterest; link = URL esterno destinazione
        link = item.get("url") or pin_data.get("link") or ""

        pins.append({
            "title": title,
            "description": description,
            "repins": repins,
            "link": link,
        })

    if raw_count > 0 and not pins:
        # Tutti gli item sono stati scartati — logga i tipi per diagnostica
        types_found = [item.get("type", "NO_TYPE") for item in items[:5]]
        print(
            f"[PINTEREST-APIFY] WARN: {raw_count} item ricevuti ma 0 pin estratti "
            f"(profiles skip: {skipped_profiles}). Tipi campione: {types_found}"
        )
    return pins


def _select_keywords(keywords: list, per_run: int) -> list:
    """
    Seleziona un sottoinsieme di keyword ruotando in base alla settimana.
    Copre tutte le keyword nel giro di ceil(N/per_run) run.
    """
    n = len(keywords)
    if per_run <= 0 or per_run >= n:
        return keywords[:per_run] if per_run > 0 else keywords
    slots = math.ceil(n / per_run)
    offset = (datetime.now().isocalendar()[1] % slots) * per_run
    chunk = keywords[offset : offset + per_run]
    if len(chunk) < per_run:
        chunk += keywords[: per_run - len(chunk)]
    return chunk


def _send_alert(
    keyword: str, count_now: int, count_before: int, velocity: float
) -> bool:
    text = (
        f"📌 <b>PINTEREST TREND</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"📊 <b>Pin trovati:</b> {count_before} → {count_now}\n"
        f"⚡ <b>Crescita:</b> +{velocity:.0f}%\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Questo topic sta crescendo nelle ricerche Pinterest. (via Apify)</i>"
    )
    return send_message(text)


def run_pinterest_apify_detector(config: dict):
    """Esegue il Pinterest trend detector via Apify."""
    if not os.getenv("APIFY_API_KEY"):
        print("[PINTEREST-APIFY] APIFY_API_KEY non configurata — modulo disabilitato.")
        return

    print(
        f"\n[PINTEREST-APIFY] Avvio detector — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    pinterest_cfg = config.get("pinterest", {})
    all_keywords = config.get("keywords", [])

    per_run = pinterest_cfg.get("keywords_per_run", 5)
    pins_per_kw = pinterest_cfg.get("pins_per_keyword", 10)
    vel_threshold = pinterest_cfg.get("velocity_threshold", 30)

    active = _select_keywords(all_keywords, per_run)
    print(f"[PINTEREST-APIFY] Keyword attive questa run ({len(active)}): {active}")

    for keyword in active:
        print(f"[PINTEREST-APIFY] Ricerca pin: '{keyword}'")
        pins = _search_pins(keyword, pins_per_kw)
        count_now = len(pins)
        print(f"[PINTEREST-APIFY] '{keyword}': {count_now} pin trovati")

        if count_now == 0:
            time.sleep(1)
            continue

        # Lookback di 14 giorni (336h) — allineato con la frequenza 2×/mese
        previous = get_keyword_counts(keyword, "pinterest_apify", 336)
        prev_count = previous[0]["count"] if previous else 0
        save_keyword_count(keyword, "pinterest_apify", count_now)

        if prev_count == 0:
            time.sleep(1)
            continue

        velocity = ((count_now - prev_count) / prev_count) * 100
        if velocity >= vel_threshold:
            alert_id = f"pinterest_apify_{keyword[:40].lower()}"
            if was_alert_sent_recently(alert_id, "pinterest_apify", hours=72):
                time.sleep(1)
                continue
            print(f"[PINTEREST-APIFY] TREND: '{keyword}' +{velocity:.0f}%")
            _send_alert(keyword, count_now, prev_count, velocity)
            mark_alert_sent(alert_id, "pinterest_apify")

        time.sleep(1)

    print("[PINTEREST-APIFY] Detector completato.")
