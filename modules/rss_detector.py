"""
YTSPERBOT - Modulo RSS Feed Detector
Monitora feed RSS di siti paranormale/horror/occulto
e calcola velocity delle keyword sugli articoli recenti
"""

import os
import time
import feedparser
from datetime import datetime, timezone, timedelta

from modules.database import (
    save_keyword_count, get_keyword_counts,
    was_alert_sent_recently, mark_alert_sent
)
from modules.telegram_bot import send_trend_alert, send_message, alert_allowed, calculate_priority_score, score_bar


def fetch_feed(feed_name: str, feed_url: str, lookback_hours: int = 48) -> list:
    """Recupera articoli recenti da un RSS feed."""
    try:
        feed = feedparser.parse(feed_url)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        articles = []

        for entry in feed.entries:
            # Tenta di leggere la data di pubblicazione
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                import calendar
                published = datetime.fromtimestamp(
                    calendar.timegm(entry.published_parsed), tz=timezone.utc
                )

            # Se non ha data o è troppo vecchio, skip
            if published and published < cutoff:
                continue

            title = entry.get('title', '')
            summary = entry.get('summary', '')
            link = entry.get('link', '')

            articles.append({
                'title': title,
                'summary': summary,
                'link': link,
                'published': published,
                'source': feed_name
            })

        return articles
    except Exception as e:
        print(f"[RSS] Errore fetch '{feed_name}': {e}")
        return []


def count_keyword_in_articles(articles: list, keyword: str) -> list:
    """Restituisce gli articoli che contengono la keyword."""
    keyword_lower = keyword.lower()
    matches = []
    for article in articles:
        text = (article['title'] + ' ' + article['summary']).lower()
        if keyword_lower in text:
            matches.append(article)
    return matches


def send_rss_alert(keyword: str, velocity: float, articles: list, count_now: int, count_before: int, min_score: int = 1):
    """Invia alert RSS su Telegram con preview degli articoli trovati."""
    if not alert_allowed(keyword, velocity, min_score):
        return False

    from modules.database import get_keyword_source_count
    source_count = get_keyword_source_count(keyword, hours=24)
    score = calculate_priority_score(velocity, source_count)
    emoji = "🔺" if velocity >= 500 else "📰"

    articles_preview = ""
    for article in articles[:3]:
        articles_preview += f"\n• <a href='{article['link']}'>{article['title'][:80]}</a> ({article['source']})"

    text = (
        f"{emoji} <b>TREND RSS</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Articoli:</b> {count_before} → {count_now}\n"
        f"🎯 <b>Score:</b> {score}/10  {score_bar(score)}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"\n<b>Articoli recenti:</b>{articles_preview}\n\n"
        f"<i>Topic emergente nel web editoriale.</i>"
    )
    return send_message(text)


def run_rss_detector(config: dict):
    """Esegue il detector RSS completo."""
    print(f"\n[RSS] Avvio RSS detector - {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    trend_cfg = config["trend_detector"]
    keywords = config["keywords"]
    rss_config = config.get("rss_feeds", {})

    # Raccogli tutti i feed
    all_feeds = []
    for lang, feeds in rss_config.items():
        if lang == "google_alerts_rss":
            continue
        if isinstance(feeds, list):
            all_feeds.extend(feeds)

    # Aggiungi Google Alerts RSS se presenti
    google_alerts = config.get("google_alerts_rss", [])
    all_feeds.extend(google_alerts)

    if not all_feeds:
        print("[RSS] Nessun feed configurato.")
        return

    # Recupera tutti gli articoli
    all_articles = []
    for feed in all_feeds:
        name = feed.get("name", "Unknown")
        url = feed.get("url", "")
        if not url:
            continue
        print(f"[RSS] Fetch: {name}")
        articles = fetch_feed(name, url, lookback_hours=48)
        all_articles.extend(articles)
        time.sleep(0.5)  # pausa gentile tra feed

    print(f"[RSS] Articoli totali recuperati: {len(all_articles)}")

    if not all_articles:
        print("[RSS] Nessun articolo trovato.")
        return

    # Analizza keyword
    for keyword in keywords:
        matching_articles = count_keyword_in_articles(all_articles, keyword)
        current_count = len(matching_articles)

        if current_count < trend_cfg.get("min_mentions_to_track", 3):
            continue

        # Calcola velocity rispetto alle ultime 48h
        previous_records = get_keyword_counts(keyword, "rss", 48)
        previous_count = previous_records[0]["count"] if previous_records else 0

        save_keyword_count(keyword, "rss", current_count)

        if previous_count == 0:
            continue

        velocity = ((current_count - previous_count) / previous_count) * 100

        if velocity >= trend_cfg["velocity_threshold_longform"]:
            if was_alert_sent_recently(keyword, "rss_trend", hours=12):
                continue

            print(f"[RSS] TREND: '{keyword}' velocity +{velocity:.0f}%")
            min_score = config.get("priority_score", {}).get("min_score", 1)
            send_rss_alert(keyword, velocity, matching_articles, current_count, previous_count, min_score=min_score)
            mark_alert_sent(keyword, "rss_trend")

    print("[RSS] RSS detector completato.")
