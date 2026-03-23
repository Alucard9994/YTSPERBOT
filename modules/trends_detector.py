"""
TheVeil Monitor - Modulo Google Trends Detector
Monitora le keyword della nicchia su Google Trends via pytrends
e calcola velocity rispetto al check precedente.

Dipendenza: pip install pytrends
"""

import time
from datetime import datetime

from pytrends.request import TrendReq

from modules.database import (
    save_keyword_count, get_keyword_counts,
    was_alert_sent_recently, mark_alert_sent
)
from modules.telegram_bot import send_message


def send_trends_alert(keyword: str, velocity: float, interest_now: int, interest_before: int, geo: str):
    emoji = "🔺" if velocity >= 200 else "📊"
    geo_label = f" ({geo})" if geo else " (Worldwide)"
    text = (
        f"{emoji} <b>TREND GOOGLE - TheVeil Monitor</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"🌍 <b>Geo:</b>{geo_label}\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Interest:</b> {interest_before} → {interest_now} (scala 0-100)\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Segnale precoce: il pubblico sta cercando questo topic su Google.</i>"
    )
    return send_message(text)


def fetch_trends_interest(keywords: list, timeframe: str, geo: str) -> dict:
    """
    Recupera l'interest medio degli ultimi 7 giorni per una lista di keyword.
    Restituisce dict {keyword: avg_interest}.
    pytrends accetta max 5 keyword per richiesta.
    """
    pytrends = TrendReq(hl="it-IT", tz=60, timeout=(10, 30), retries=2, backoff_factor=0.5)
    results = {}

    # pytrends limita a 5 keyword per chiamata
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()

            if df.empty:
                for kw in batch:
                    results[kw] = 0
                continue

            for kw in batch:
                if kw in df.columns:
                    results[kw] = int(df[kw].mean())
                else:
                    results[kw] = 0

            time.sleep(2)  # rispetta rate limit Google

        except Exception as e:
            print(f"[TRENDS] Errore batch {batch}: {e}")
            for kw in batch:
                results[kw] = 0
            time.sleep(5)

    return results


def run_trends_detector(config: dict):
    """Esegue il detector Google Trends."""
    print(f"\n[TRENDS] Avvio Google Trends detector - {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    trends_cfg = config.get("google_trends", {})
    timeframe = trends_cfg.get("timeframe", "now 7-d")
    geo = trends_cfg.get("geo", "")
    velocity_threshold = trends_cfg.get("velocity_threshold", 50)
    top_n = trends_cfg.get("top_n_keywords", 20)

    keywords = config.get("keywords", [])

    # Limita a top_n per evitare rate limit eccessivi
    keywords_to_check = keywords[:top_n]

    print(f"[TRENDS] Keyword da controllare: {len(keywords_to_check)} | geo: '{geo or 'Worldwide'}' | timeframe: {timeframe}")

    interest_map = fetch_trends_interest(keywords_to_check, timeframe, geo)

    for keyword, interest_now in interest_map.items():
        if interest_now == 0:
            continue

        previous_records = get_keyword_counts(keyword, "google_trends", 48)
        previous_interest = previous_records[0]["count"] if previous_records else 0

        save_keyword_count(keyword, "google_trends", interest_now)

        if previous_interest == 0:
            continue

        velocity = ((interest_now - previous_interest) / previous_interest) * 100

        if velocity >= velocity_threshold:
            if was_alert_sent_recently(keyword, "google_trends", hours=12):
                continue

            print(f"[TRENDS] SPIKE: '{keyword}' interest {previous_interest} → {interest_now} (+{velocity:.0f}%)")
            send_trends_alert(keyword, velocity, interest_now, previous_interest, geo)
            mark_alert_sent(keyword, "google_trends")

    print("[TRENDS] Google Trends detector completato.")
