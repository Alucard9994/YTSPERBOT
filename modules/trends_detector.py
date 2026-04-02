"""
YTSPERBOT - Modulo Google Trends Detector

Tre sistemi distinti:
  1. Velocity tracker (già attivo): monitora keyword note su Trends
  2. Trending RSS: top ricerche Google IT/US filtrate per nicchia (0 quota)
  3. Rising queries: scopre keyword emergenti correlate alle nostre (pytrends)
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
import feedparser
from datetime import datetime, timezone

from pytrends.request import TrendReq

from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
    log_alert,
    mark_job_run,
    get_last_job_run,
)
from modules.telegram_bot import send_message

# ============================================================
# Cooldown 429: evita run inutili quando Google blocca l'IP
# ============================================================
_TRENDS_BLOCK_KEY = "trends_429_cooldown"
_TRENDS_COOLDOWN_HOURS = 2


def _trends_is_blocked() -> bool:
    """Restituisce True se siamo stati bloccati da Google 429 nelle ultime 2 ore."""
    last = get_last_job_run(_TRENDS_BLOCK_KEY)
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed_h = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    return elapsed_h < _TRENDS_COOLDOWN_HOURS


def _is_429(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "too many" in s


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
        hl="it-IT", tz=60, timeout=(10, 45), retries=3, backoff_factor=3.0
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

            time.sleep(15)  # rispetta rate limit Google

        except Exception as e:
            if _is_429(e):
                # Propaga immediatamente — inutile tentare i batch rimanenti
                raise
            print(f"[TRENDS] Errore batch {batch}: {e}")
            for kw in batch:
                results[kw] = 0
            time.sleep(30)

    return results


def run_trends_detector(config: dict):
    """Esegue il detector Google Trends."""
    if _trends_is_blocked():
        print(
            f"[TRENDS] IP bloccato da Google (429 recente) — skip. "
            f"Cooldown {_TRENDS_COOLDOWN_HOURS}h, prossimo tentativo automatico."
        )
        return

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

    try:
        interest_map = fetch_trends_interest(keywords_to_check, timeframe, geo)
    except Exception as e:
        if _is_429(e):
            print(
                f"[TRENDS] Google Trends bloccato da Google (429 — IP datacenter). "
                f"Cooldown {_TRENDS_COOLDOWN_HOURS}h."
            )
            mark_job_run(_TRENDS_BLOCK_KEY)
        else:
            print(f"[TRENDS] Errore inatteso: {e}")
        print("[TRENDS] Google Trends detector completato.")
        return

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


def _fetch_rss_bytes(url: str, timeout: int = 15) -> bytes:
    """Scarica un feed RSS con User-Agent browser e SSL permissivo.

    feedparser.parse(url) non supporta User-Agent e usa il contesto SSL di
    default, che su alcuni ambienti fallisce silenziosamente restituendo 0
    entry. Pre-fetchare con urllib restituisce bytes grezzi che feedparser
    parsifica senza toccare la rete.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; YTSPERBOT/1.0)"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        if resp.status >= 400:
            raise urllib.error.HTTPError(url, resp.status, resp.reason, {}, None)
        return resp.read()


def run_trending_rss_monitor(config: dict):
    """Legge il feed RSS delle ricerche trending Google e filtra per nicchia."""
    print(f"\n[TRENDS-RSS] Avvio trending RSS — {datetime.now().strftime('%H:%M')}")

    rss_cfg = config.get("trending_rss", {})
    geos = rss_cfg.get("geos", ["IT", "US"])
    extra_words = {w.lower() for w in rss_cfg.get("extra_filter_words", [])}
    filter_words = NICHE_SEMANTIC_WORDS | extra_words

    found = 0

    for geo in geos:
        # New Google Trends RSS endpoint (old /trendingsearches/daily/rss → 404)
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        try:
            raw = _fetch_rss_bytes(url)
            feed = feedparser.parse(raw)
        except urllib.error.HTTPError as e:
            print(f"[TRENDS-RSS] {geo} — HTTP {e.code} {e.reason}, skip")
            time.sleep(1)
            continue
        except Exception as e:
            print(f"[TRENDS-RSS] Errore fetch {geo}: {e}")
            continue

        if not feed.entries:
            print(f"[TRENDS-RSS] {geo} — nessun entry ricevuto (bozo={feed.bozo})")
            time.sleep(1)
            continue

        print(f"[TRENDS-RSS] {geo} — {len(feed.entries)} entry ricevute")

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
                extra_json=json.dumps({"geo": geo, "traffic": traffic}),
            )
            found += 1

        time.sleep(1)

    print(f"[TRENDS-RSS] Completato. Match trovati: {found}")


# ============================================================
# 3. Rising queries — keyword emergenti correlate (pytrends)
# ============================================================


def run_rising_queries_detector(config: dict):
    """Scopre nuove keyword emergenti nelle query correlate su Google Trends."""
    if _trends_is_blocked():
        print(
            f"[TRENDS-RISING] IP bloccato da Google (429 recente) — skip. "
            f"Cooldown {_TRENDS_COOLDOWN_HOURS}h."
        )
        return

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
        hl="it-IT", tz=60, timeout=(10, 45), retries=3, backoff_factor=3.0
    )

    for keyword in probe_keywords:
        try:
            pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            related = pytrends.related_queries()

            rising_df = related.get(keyword, {}).get("rising")
            if rising_df is None or rising_df.empty:
                time.sleep(10)
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
                    extra_json=json.dumps({
                        "parent_keyword": keyword,
                        "breakout": str(value) == "Breakout",
                    }),
                )

            time.sleep(15)  # rispetta rate limit pytrends

        except Exception as e:
            if _is_429(e):
                print(
                    f"[TRENDS-RISING] Google Trends bloccato (429 — IP datacenter). "
                    f"Cooldown {_TRENDS_COOLDOWN_HOURS}h."
                )
                mark_job_run(_TRENDS_BLOCK_KEY)
                break  # interrompe il loop — inutile continuare
            print(f"[TRENDS-RISING] Errore '{keyword}': {e}")
            time.sleep(30)

    print("[TRENDS-RISING] Rising queries completato.")
