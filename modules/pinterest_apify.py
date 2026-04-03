"""
YTSPERBOT - Pinterest via Apify
Usa fatihtahta~pinterest-scraper-search ($3.99/1k risultati).

Funzionalità:
  - Velocity detector: calcola crescita saves e invia alert se supera soglia
  - Domain tracker: alla fine di ogni run invia i siti esterni più pinnati
  - Digest settimanale: ogni lunedì alle 10:00 invia top 5 pin + top domini

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

Richiede APIFY_API_KEY nel .env.
"""
from __future__ import annotations

import os
import time
import math
from datetime import datetime
from urllib.parse import urlparse

from modules.apify_scraper import run_actor
from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
    save_pinterest_pin,
    get_pinterest_top_pins,
    get_pinterest_domain_counts,
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
        pin_url = item.get("url") or ""
        external_link = pin_data.get("link") or ""

        # Estrai dominio dall'URL esterno
        try:
            parsed = urlparse(external_link)
            domain = parsed.netloc.lower().replace("www.", "") if parsed.netloc else ""
        except Exception:
            domain = ""

        # pin_hash: usa id se disponibile, altrimenti hash dell'url del pin
        raw_id = item.get("id")
        pin_hash = str(raw_id) if raw_id else str(abs(hash(pin_url)))[:16]

        creator = item.get("creator") or {}

        pins.append({
            "pin_hash": pin_hash,
            "title": title,
            "description": description,
            "repins": repins,
            "link": pin_url,       # URL del pin Pinterest
            "external_link": external_link,
            "domain": domain,
            "creator_username": creator.get("username") or "",
        })

    if raw_count > 0 and not pins:
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
        f"📊 <b>Saves:</b> {count_before} → {count_now}\n"
        f"⚡ <b>Crescita:</b> +{velocity:.0f}%\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Questo topic sta crescendo nelle ricerche Pinterest. (via Apify)</i>"
    )
    return send_message(text)


def _send_domain_alert(domains: list) -> None:
    """Invia alert con i siti esterni più pinnati nella nicchia."""
    lines = []
    for d in domains:
        lines.append(
            f"🌐 <b>{d['domain']}</b> — {d['pin_count']} pin, {d['total_repins']:,} saves"
        )
    text = (
        "🔗 <b>PINTEREST DOMAIN TRACKER</b>\n"
        "<i>Siti più condivisi nella nicchia (ultimi 7 giorni)</i>\n\n"
        + "\n".join(lines)
        + "\n\n<i>Questi domini producono contenuto che Pinterest amplifica.</i>"
    )
    send_message(text)


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
    domain_top_n = pinterest_cfg.get("domain_top_n", 3)

    active = _select_keywords(all_keywords, per_run)
    print(f"[PINTEREST-APIFY] Keyword attive questa run ({len(active)}): {active}")

    for keyword in active:
        print(f"[PINTEREST-APIFY] Ricerca pin: '{keyword}'")
        pins = _search_pins(keyword, pins_per_kw)
        count_now = sum(p.get("repins", 0) for p in pins)
        print(f"[PINTEREST-APIFY] '{keyword}': {len(pins)} pin trovati, {count_now} saves totali")

        # Salva ogni pin in DB per digest e domain tracker
        for pin in pins:
            save_pinterest_pin(
                pin_hash=pin.get("pin_hash", ""),
                keyword=keyword,
                title=pin.get("title", ""),
                url=pin.get("link", ""),
                repins=pin.get("repins", 0),
                creator_username=pin.get("creator_username", ""),
                domain=pin.get("domain", ""),
            )

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

    # Domain tracker: analizza i top domini a fine run
    domains = get_pinterest_domain_counts(hours=168, limit=domain_top_n)
    top_domains = [d for d in domains if d.get("domain") and (d.get("total_repins") or 0) >= 5]
    if top_domains:
        domain_alert_id = "pinterest_domain_tracker"
        if not was_alert_sent_recently(domain_alert_id, "pinterest_domain", hours=120):
            print(f"[PINTEREST-APIFY] Domain tracker: {len(top_domains)} domini rilevati")
            _send_domain_alert(top_domains)
            mark_alert_sent(domain_alert_id, "pinterest_domain")

    print("[PINTEREST-APIFY] Detector completato.")


def run_pinterest_digest(config: dict):
    """Invia il digest settimanale con i top pin per saves + top domini."""
    if not os.getenv("APIFY_API_KEY"):
        return

    if was_alert_sent_recently("pinterest_weekly_digest", "pinterest_digest", hours=144):
        print("[PINTEREST-DIGEST] Digest già inviato negli ultimi 6 giorni — skip.")
        return

    pinterest_cfg = config.get("pinterest", {})
    domain_top_n = pinterest_cfg.get("domain_top_n", 3)

    pins = get_pinterest_top_pins(hours=168, limit=5)
    domains = get_pinterest_domain_counts(hours=168, limit=domain_top_n)

    if not pins:
        print("[PINTEREST-DIGEST] Nessun pin nelle ultime 7 giorni.")
        return

    lines = []
    for i, p in enumerate(pins, 1):
        title = (p.get("title") or "Nessun titolo")[:60]
        repins = p.get("repins", 0)
        kw = p.get("keyword", "")
        url = p.get("url", "")
        domain = p.get("domain", "")
        line = f"{i}. [{kw}] {title}\n   📌 {repins:,} saves"
        if domain:
            line += f" — {domain}"
        if url:
            line += f'  <a href="{url}">↗</a>'
        lines.append(line)

    domain_section = ""
    if domains:
        domain_section = "\n\n🔗 <b>Domini più salvati:</b>\n"
        domain_section += "\n".join(
            f"• {d['domain']} ({d['pin_count']} pin, {d.get('total_repins', 0):,} saves)"
            for d in domains
        )

    text = (
        f"📌 <b>PINTEREST DIGEST SETTIMANALE</b>\n"
        f"<i>Top pin per saves — {datetime.now().strftime('%d/%m/%Y')}</i>\n\n"
        + "\n\n".join(lines)
        + domain_section
        + "\n\n<i>Fonte: monitoraggio keyword nicchia paranormale/occulto</i>"
    )
    send_message(text)
    mark_alert_sent("pinterest_weekly_digest", "pinterest_digest")
    print(f"[PINTEREST-DIGEST] Digest inviato — {len(pins)} pin.")
