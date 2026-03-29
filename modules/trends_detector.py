"""
YTSPERBOT - Modulo Google Trends Detector

Tre sistemi distinti:
  1. Velocity tracker (già attivo): monitora keyword note su Trends
  2. Trending RSS: top ricerche Google IT/US filtrate per nicchia (0 quota)
  3. Rising queries: scopre keyword emergenti correlate alle nostre (pytrends)
"""

import time
import feedparser
from datetime import datetime

from pytrends.request import TrendReq

from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
    log_alert,
)
from modules.telegram_bot import send_message


# ============================================================
# Parole semantiche della nicchia per filtrare trending RSS
# ============================================================
NICHE_SEMANTIC_WORDS = {
    "paranormal",
    "ghost",
    "haunted",
    "spirit",
    "apparition",
    "poltergeist",
    "demon",
    "demonic",
    "possession",
    "exorcism",
    "occult",
    "ritual",
    "cult",
    "witchcraft",
    "witch",
    "spell",
    "curse",
    "hex",
    "grimoire",
    "satanic",
    "ufo",
    "uap",
    "alien",
    "extraterrestrial",
    "abduction",
    "area51",
    "conspiracy",
    "illuminati",
    "freemason",
    "secret society",
    "nwo",
    "cryptid",
    "bigfoot",
    "skinwalker",
    "wendigo",
    "monster",
    "creature",
    "mystery",
    "unsolved",
    "unexplained",
    "phenomenon",
    "anomaly",
    "horror",
    "creepy",
    "scary",
    "dark",
    "evil",
    "forbidden",
    "legend",
    "folklore",
    "myth",
    "supernatural",
    "psychic",
    "medium",
    # italiano
    "paranormale",
    "fantasma",
    "strega",
    "streghe",
    "magia",
    "occulto",
    "demonio",
    "possessione",
    "rituale",
    "mistero",
    "misterioso",
    "alieni",
    "complotto",
    "cospirazione",
    "società segreta",
    "leggenda",
    "inspiegabile",
    "fenomeno",
    "creatura",
    "mostro",
    "maledizione",
}


def _matches_niche(text: str) -> bool:
    """True se il testo contiene almeno una parola della nicchia."""
    text_lower = text.lower()
    return any(word in text_lower for word in NICHE_SEMANTIC_WORDS)


# ============================================================
# Alert functions
# ============================================================


def send_trends_alert(
    keyword: str, velocity: float, interest_now: int, interest_before: int, geo: str
):
    emoji = "🔺" if velocity >= 200 else "📊"
    geo_label = f" ({geo})" if geo else " (Worldwide)"
    text = (
        f"{emoji} <b>TREND GOOGLE - YTSPERBOT</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"🌍 <b>Geo:</b>{geo_label}\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Interest:</b> {interest_before} → {interest_now} (scala 0-100)\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Segnale precoce: il pubblico sta cercando questo topic su Google.</i>"
    )
    return send_message(text)


def send_trending_rss_alert(term: str, geo: str, traffic: str, news_title: str = ""):
    flag = {"IT": "🇮🇹", "US": "🇺🇸", "GB": "🇬🇧"}.get(geo, f"[{geo}]")
    traffic_str = f" (~{traffic} ricerche/giorno)" if traffic else ""
    news_str = (
        f"\n📰 <b>Notizia correlata:</b> <i>{news_title[:120]}</i>"
        if news_title
        else ""
    )
    text = (
        f"🔥 <b>TRENDING GOOGLE {flag}</b>\n\n"
        f"📈 <b>Trending ora:</b> <code>{term}</code>{traffic_str}\n"
        f"🌍 <b>Paese:</b> {geo}{news_str}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Questo topic sta esplodendo su Google in questo momento.</i>"
    )
    return send_message(text)


def send_rising_query_alert(probe_keyword: str, rising_query: str, growth):
    growth_str = "🚀 Breakout (>5000%)" if str(growth) == "Breakout" else f"+{growth}%"
    text = (
        f"🚀 <b>NUOVA KEYWORD EMERGENTE</b>\n\n"
        f"🔍 <b>Correlata a:</b> <code>{probe_keyword}</code>\n"
        f"💡 <b>Query emergente:</b> <code>{rising_query}</code>\n"
        f"📊 <b>Crescita:</b> {growth_str}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Keyword non ancora monitorata — in forte crescita nelle ricerche correlate.\n"
        f"Aggiungila a config.yaml se rilevante, oppure ignorala con /block {rising_query}</i>"
    )
    return send_message(text)


def fetch_trends_interest(keywords: list, timeframe: str, geo: str) -> dict:
    """
    Recupera l'interest medio degli ultimi 7 giorni per una lista di keyword.
    Restituisce dict {keyword: avg_interest}.
    pytrends accetta max 5 keyword per richiesta.
    """
    pytrends = TrendReq(
        hl="it-IT", tz=60, timeout=(10, 30), retries=2, backoff_factor=0.5
    )
    results = {}

    # pytrends limita a 5 keyword per chiamata
    for i in range(0, len(keywords), 5):
        batch = keywords[i : i + 5]
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
    print(
        f"\n[TRENDS] Avvio Google Trends detector - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    trends_cfg = config.get("google_trends", {})
    timeframe = trends_cfg.get("timeframe", "now 7-d")
    geo = trends_cfg.get("geo", "")
    velocity_threshold = trends_cfg.get("velocity_threshold", 50)
    top_n = trends_cfg.get("top_n_keywords", 20)

    keywords = config.get("keywords", [])

    # Limita a top_n per evitare rate limit eccessivi
    keywords_to_check = keywords[:top_n]

    print(
        f"[TRENDS] Keyword da controllare: {len(keywords_to_check)} | geo: '{geo or 'Worldwide'}' | timeframe: {timeframe}"
    )

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

            print(
                f"[TRENDS] SPIKE: '{keyword}' interest {previous_interest} → {interest_now} (+{velocity:.0f}%)"
            )
            send_trends_alert(keyword, velocity, interest_now, previous_interest, geo)
            mark_alert_sent(keyword, "google_trends")
            log_alert("google_trends", keyword, "google_trends", velocity_pct=velocity)

    print("[TRENDS] Google Trends detector completato.")


# ============================================================
# 2. Trending RSS — top ricerche Google IT/US (0 quota API)
# ============================================================


def run_trending_rss_monitor(config: dict):
    """Legge il feed RSS delle ricerche trending Google e filtra per nicchia."""
    print(f"\n[TRENDS-RSS] Avvio trending RSS — {datetime.now().strftime('%H:%M')}")

    rss_cfg = config.get("trending_rss", {})
    geos = rss_cfg.get("geos", ["IT", "US"])
    extra_words = {w.lower() for w in rss_cfg.get("extra_filter_words", [])}
    filter_words = NICHE_SEMANTIC_WORDS | extra_words

    found = 0

    for geo in geos:
        url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[TRENDS-RSS] Errore fetch {geo}: {e}")
            continue

        for entry in feed.entries:
            term = entry.get("title", "").strip()
            if not term:
                continue

            # Filtra per nicchia
            term_lower = term.lower()
            matched = any(w in term_lower for w in filter_words)
            if not matched:
                continue

            # Evita alert duplicati nelle ultime 12h
            alert_id = f"trending_rss_{geo}_{term.lower()[:40]}"
            if was_alert_sent_recently(alert_id, "trending_rss", hours=12):
                continue

            # Traffico approssimativo (campo custom Google RSS)
            traffic = entry.get("ht_approx_traffic", "")

            # Prima notizia correlata (se presente)
            news_title = ""
            news_items = entry.get("ht_news_item_title", "")
            if news_items:
                news_title = (
                    news_items if isinstance(news_items, str) else str(news_items[0])
                )

            print(f"[TRENDS-RSS] Match {geo}: '{term}' (~{traffic})")
            send_trending_rss_alert(term, geo, traffic, news_title)
            mark_alert_sent(alert_id, "trending_rss")
            log_alert(
                "trending_rss",
                term,
                "trending_rss",
                extra_json=f'{{"geo":"{geo}","traffic":"{traffic}"}}',
            )
            found += 1

        time.sleep(1)

    print(f"[TRENDS-RSS] Completato. Match trovati: {found}")


# ============================================================
# 3. Rising queries — keyword emergenti correlate (pytrends)
# ============================================================


def run_rising_queries_detector(config: dict):
    """Scopre nuove keyword emergenti nelle query correlate su Google Trends."""
    print(
        f"\n[TRENDS-RISING] Avvio rising queries — {datetime.now().strftime('%H:%M')}"
    )

    rising_cfg = config.get("rising_queries", {})
    keywords_per_run = rising_cfg.get("keywords_per_run", 8)
    min_growth = rising_cfg.get(
        "min_growth", 500
    )  # % minimo (ignora "Breakout" = sempre inviato)
    geo = rising_cfg.get("geo", "")
    timeframe = rising_cfg.get("timeframe", "now 7-d")

    # Prende un campione rotante delle keyword monitorate
    all_keywords = config.get("keywords", [])
    probe_keywords = all_keywords[:keywords_per_run]

    pytrends = TrendReq(
        hl="it-IT", tz=60, timeout=(10, 30), retries=2, backoff_factor=0.5
    )

    for keyword in probe_keywords:
        try:
            pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            related = pytrends.related_queries()

            rising_df = related.get(keyword, {}).get("rising")
            if rising_df is None or rising_df.empty:
                time.sleep(2)
                continue

            for _, row in rising_df.iterrows():
                query = str(row.get("query", "")).strip()
                value = row.get("value", 0)

                is_breakout = str(value) == "Breakout"
                is_high_growth = isinstance(value, (int, float)) and value >= min_growth

                if not (is_breakout or is_high_growth):
                    continue

                # Salta se è già una keyword monitorata
                if any(
                    query.lower() in kw.lower() or kw.lower() in query.lower()
                    for kw in all_keywords
                ):
                    continue

                alert_id = f"rising_{query.lower()[:50]}"
                if was_alert_sent_recently(alert_id, "rising_query", hours=48):
                    continue

                print(f"[TRENDS-RISING] '{keyword}' → '{query}' ({value})")
                send_rising_query_alert(keyword, query, value)
                mark_alert_sent(alert_id, "rising_query")
                velocity_val = None if str(value) == "Breakout" else float(value)
                log_alert(
                    "rising_query",
                    query,
                    "rising_query",
                    velocity_pct=velocity_val,
                    extra_json=f'{{"parent_keyword":"{keyword}","breakout":{str(str(value) == "Breakout").lower()}}}',
                )

            time.sleep(3)  # rispetta rate limit pytrends

        except Exception as e:
            print(f"[TRENDS-RISING] Errore '{keyword}': {e}")
            time.sleep(5)

    print("[TRENDS-RISING] Rising queries completato.")
