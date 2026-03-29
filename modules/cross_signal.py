"""
YTSPERBOT - Cross Signal Detector
Feature: Alert convergenza multi-piattaforma

Quando la stessa keyword emerge su 3+ fonti diverse in poche ore
viene inviato un alert speciale ad alta priorità.
Se ANTHROPIC_API_KEY è configurata, genera anche suggerimenti titoli video.
"""

import os
from datetime import datetime

from modules.database import (
    get_multi_source_keywords,
    was_alert_sent_recently,
    mark_alert_sent,
    log_alert,
    is_blacklisted,
)
from modules.telegram_bot import send_convergence_alert


# ============================================================
# AI Title Generator (opzionale — richiede ANTHROPIC_API_KEY)
# ============================================================


def generate_title_suggestions(keyword: str) -> str | None:
    """Genera 5 titoli video YouTube ottimizzati tramite Claude API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import requests

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 400,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Sei un esperto di YouTube nella nicchia paranormale/horror/occulto.\n"
                            f"Il topic '{keyword}' sta emergendo in tendenza su più piattaforme.\n"
                            f"Genera 5 titoli video YouTube ottimizzati per questo topic.\n"
                            f"I titoli devono essere in italiano, coinvolgenti e ottimizzati per il CTR.\n"
                            f"Rispondi SOLO con i 5 titoli numerati, nessun testo aggiuntivo."
                        ),
                    }
                ],
            },
            timeout=20,
        )
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"]
        else:
            print(f"[CROSS-SIGNAL] AI titles errore HTTP {resp.status_code}")
    except Exception as e:
        print(f"[CROSS-SIGNAL] AI titles errore: {e}")
    return None


# ============================================================
# Detector principale
# ============================================================


def run_cross_signal_detector(config: dict):
    """
    Controlla se qualche keyword è emersa su N+ fonti nelle ultime N ore.
    Se sì, invia alert di convergenza (e suggerimenti titoli se AI configurata).
    """
    print(
        f"\n[CROSS-SIGNAL] Controllo convergenza — {datetime.now().strftime('%H:%M')}"
    )

    cfg = config.get("cross_signal", {})
    min_sources = cfg.get("min_sources", 3)
    lookback_hours = cfg.get("lookback_hours", 6)
    cooldown_hours = cfg.get("cooldown_hours", 12)
    ai_titles = cfg.get("ai_titles", True)

    keywords = get_multi_source_keywords(hours=lookback_hours, min_sources=min_sources)
    found = 0

    for kw in keywords:
        keyword = kw["keyword"]
        source_count = kw["source_count"]
        total_mentions = kw["total_mentions"]
        sources = [s.strip() for s in kw["sources"].split(",")]

        if is_blacklisted(keyword):
            continue

        alert_id = f"cross_{keyword}"
        if was_alert_sent_recently(alert_id, "cross_signal", hours=cooldown_hours):
            continue

        print(
            f"[CROSS-SIGNAL] Convergenza: '{keyword}' su {source_count} fonti ({', '.join(sources)})"
        )

        titles = None
        if ai_titles:
            titles = generate_title_suggestions(keyword)

        send_convergence_alert(
            keyword, sources, total_mentions, source_count, title_suggestions=titles
        )
        mark_alert_sent(alert_id, "cross_signal")
        log_alert(
            "cross_signal",
            keyword,
            "cross_signal",
            sources_list=",".join(sources),
            priority=min(10, source_count * 2 + 2),
        )
        found += 1

    print(f"[CROSS-SIGNAL] Completato. Convergenze trovate: {found}")
