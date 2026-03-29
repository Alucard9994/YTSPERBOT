"""
YTSPERBOT - News Detector
Feature: Monitor notizie di nicchia via NewsAPI.org

Piano free: 100 req/giorno — campiona N keyword per run ogni 6h.
Richiede NEWSAPI_KEY nel .env (registrazione gratuita su newsapi.org).
"""

import os
import time
import requests
from datetime import datetime, timezone, timedelta

from modules.utils import calculate_velocity
from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
    log_alert,
)
from modules.telegram_bot import (
    send_message,
    alert_allowed,
    calculate_priority_score,
    score_bar,
)


NEWSAPI_ENABLED = bool(os.getenv("NEWSAPI_KEY"))
NEWSAPI_BASE = "https://newsapi.org/v2/everything"


def fetch_news_articles(
    keyword: str, language: str = "en", lookback_hours: int = 48
) -> list:
    """Recupera articoli recenti su una keyword da NewsAPI."""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []

    from_date = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    try:
        resp = requests.get(
            NEWSAPI_BASE,
            params={
                "q": keyword,
                "language": language,
                "sortBy": "publishedAt",
                "from": from_date,
                "pageSize": 10,
                "apiKey": api_key,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            articles = []
            for art in data.get("articles", []):
                articles.append(
                    {
                        "title": art.get("title", ""),
                        "source": art.get("source", {}).get("name", ""),
                        "url": art.get("url", ""),
                        "publishedAt": art.get("publishedAt", ""),
                    }
                )
            return articles
        elif resp.status_code == 426:
            print(
                "[NEWS] Piano free non supporta questa richiesta (upgrade richiesto)."
            )
        elif resp.status_code == 401:
            print("[NEWS] NEWSAPI_KEY non valida.")
        else:
            print(f"[NEWS] Errore HTTP {resp.status_code} per '{keyword}'")
    except Exception as e:
        print(f"[NEWS] Errore fetch '{keyword}': {e}")
    return []


def send_news_alert(
    keyword: str,
    velocity: float,
    articles: list,
    count_now: int,
    count_before: int,
    min_score: int = 1,
):
    """Invia alert notizie su Telegram."""
    if not alert_allowed(keyword, velocity, min_score):
        return False

    from modules.database import get_keyword_source_count

    source_count = get_keyword_source_count(keyword, hours=24)
    score = calculate_priority_score(velocity, source_count)
    emoji = "🔺" if velocity >= 500 else "📰"

    preview = ""
    for art in articles[:3]:
        src = f" ({art['source']})" if art["source"] else ""
        preview += f"\n• <a href='{art['url']}'>{art['title'][:80]}</a>{src}"

    text = (
        f"{emoji} <b>TREND NEWS</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Articoli:</b> {count_before} → {count_now}\n"
        f"🎯 <b>Score:</b> {score}/10  {score_bar(score)}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"\n<b>Notizie recenti:</b>{preview}\n\n"
        f"<i>Topic emergente nelle notizie internazionali.</i>"
    )
    return send_message(text)


def run_news_detector(config: dict):
    """Controlla le notizie di nicchia via NewsAPI. Campiona N keyword per run."""
    if not NEWSAPI_ENABLED:
        print("[NEWS] NEWSAPI_KEY non configurata — modulo disabilitato.")
        return

    print(f"\n[NEWS] Avvio news detector — {datetime.now().strftime('%H:%M')}")

    cfg = config.get("news_api", {})
    keywords_per_run = cfg.get("keywords_per_run", 10)
    languages = cfg.get("languages", ["en"])
    lookback_hours = cfg.get("lookback_hours", 48)
    velocity_threshold = cfg.get("velocity_threshold", 200)
    min_score = config.get("priority_score", {}).get("min_score", 1)

    all_keywords = config.get("keywords", [])
    # Campiona le keyword per rispettare la quota giornaliera
    import random

    sampled = random.sample(all_keywords, min(keywords_per_run, len(all_keywords)))

    found = 0
    for keyword in sampled:
        articles = []
        for lang in languages:
            articles.extend(
                fetch_news_articles(
                    keyword, language=lang, lookback_hours=lookback_hours
                )
            )
            time.sleep(0.3)

        current_count = len(articles)
        if current_count == 0:
            continue

        previous_records = get_keyword_counts(keyword, "news", lookback_hours)
        previous_count = previous_records[0]["count"] if previous_records else 0

        save_keyword_count(keyword, "news", current_count)

        velocity = calculate_velocity(current_count, previous_count)
        if velocity is None:
            continue

        if velocity >= velocity_threshold:
            if was_alert_sent_recently(keyword, "news_trend", hours=12):
                continue
            print(f"[NEWS] TREND: '{keyword}' velocity +{velocity:.0f}%")
            send_news_alert(
                keyword,
                velocity,
                articles,
                current_count,
                previous_count,
                min_score=min_score,
            )
            mark_alert_sent(keyword, "news_trend")
            log_alert("news_trend", keyword, "news", velocity_pct=velocity)
            found += 1

        time.sleep(0.5)

    print(f"[NEWS] Completato. Alert inviati: {found}")
