"""
YTSPERBOT - Twitter/X via Apify
Usa apidojo~tweet-scraper ($0.40/1k tweet su piano Starter).

Actor: apidojo/tweet-scraper
  URL: https://apify.com/apidojo/tweet-scraper
  Rating: 4.2 ⭐ (155 recensioni) | 45K utenti | issues response: 6.3h
  Pricing: $0.40/1k tweet (Starter $29) | min 50 tweet per query
  Input:  { "searchTerms": [str], "maxItems": int, "sort": "Latest"|"Top" }
  Output: { "id": str, "text": str, "url": str, "twitterUrl": str,
             "retweetCount": int, "replyCount": int, "likeCount": int,
             "quoteCount": int, "createdAt": str, "lang": str,
             "author": { "userName": str, "name": str, "followers": int, ... } }

Logica identica a twitter_detector.py:
  - Cerca tweet recenti per ogni keyword monitorata
  - Calcola velocity rispetto al check precedente
  - Invia alert Telegram se supera la soglia

Configurazione consigliata per restare nel free tier Apify ($5/mese):
  twitter.tweets_per_keyword: 20
  twitter.check_interval_hours: 24
  → 5 kw × 20 tweet × 30 run/mese = 3.000 tweet × $0.0004 = $1.20/mese ✅

Costo in modalità Starter ($29/mese):
  twitter.tweets_per_keyword: 50
  twitter.check_interval_hours: 8   (3×/giorno)
  → 5 kw × 50 tweet × 90 run/mese = 22.500 tweet × $0.0004 = $9.00/mese

Richiede APIFY_API_KEY nel .env.
"""

import os
import time
from datetime import datetime

from modules.apify_scraper import run_actor
from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
)
from modules.telegram_bot import (
    send_message,
    alert_allowed,
    calculate_priority_score,
    score_bar,
)

TWITTER_ACTOR = "apidojo~tweet-scraper"


def _search_tweets(keyword: str, max_items: int) -> list:
    """
    Cerca tweet recenti per la keyword usando Apify (apidojo/tweet-scraper).
    Input: searchTerms (array), maxItems, sort.
    Nota: min 50 tweet per query imposto dall'attore.
    Output top-level: id (str), text (str), url, author, likeCount, retweetCount, ...
    """
    items = run_actor(
        TWITTER_ACTOR,
        {
            "searchTerms": [keyword],
            "maxItems": max(max_items, 50),
            "sort": "Latest",
        },
    )
    result = []
    for item in items:
        tweet_id = str(
            item.get("id")
            or item.get("tweetId")
            or item.get("tweet_id")
            or ""
        )
        # Testo disponibile a top-level o nel sotto-oggetto tweet
        text = (
            item.get("text")
            or item.get("full_text")
            or item.get("Embedded_text")
            or (item.get("tweet") or {}).get("text")
            or ""
        )
        if tweet_id and text:
            result.append({"id": tweet_id, "text": text})
    return result


def _send_twitter_apify_alert(
    keyword: str,
    velocity: float,
    count_now: int,
    count_before: int,
    sample_tweets: list,
    min_score: int = 1,
) -> bool:
    if not alert_allowed(keyword, velocity, min_score):
        return False

    from modules.database import get_keyword_source_count

    source_count = get_keyword_source_count(keyword, hours=24)
    score = calculate_priority_score(velocity, source_count)
    emoji = "🔺" if velocity >= 500 else "🐦"

    tweets_preview = ""
    for tweet in sample_tweets[:3]:
        preview = tweet["text"][:100].replace("\n", " ")
        tweets_preview += f"\n• {preview}…"

    text = (
        f"{emoji} <b>TREND X/TWITTER</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Tweet:</b> {count_before} → {count_now}\n"
        f"🎯 <b>Score:</b> {score}/10  {score_bar(score)}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"\n<b>Esempi:</b>{tweets_preview}\n\n"
        f"<i>Topic in crescita su X/Twitter. (via Apify)</i>"
    )
    return send_message(text)


def run_twitter_apify_detector(config: dict):
    """Esegue il trend detector Twitter/X via Apify."""
    apify_key = os.getenv("APIFY_API_KEY", "")
    if not apify_key:
        print("[TWITTER-APIFY] APIFY_API_KEY non configurata — modulo disabilitato.")
        return

    print(
        f"\n[TWITTER-APIFY] Avvio detector — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    tw_cfg = config.get("twitter", {})
    trend_cfg = config.get("trend_detector", {})
    keywords = config.get("keywords", [])

    max_items = tw_cfg.get("tweets_per_keyword", 15)
    min_mentions = trend_cfg.get("min_mentions_to_track", 3)
    velocity_threshold = trend_cfg.get("velocity_threshold_longform", 300)
    min_score = config.get("priority_score", {}).get("min_score", 1)

    for keyword in keywords:
        tweets = _search_tweets(keyword, max_items)
        current_count = len(tweets)

        if current_count < min_mentions:
            time.sleep(0.5)
            continue

        previous_records = get_keyword_counts(keyword, "twitter", 48)
        previous_count = previous_records[0]["count"] if previous_records else 0

        save_keyword_count(keyword, "twitter", current_count)

        if previous_count == 0:
            time.sleep(0.5)
            continue

        velocity = ((current_count - previous_count) / previous_count) * 100

        if velocity >= velocity_threshold:
            if was_alert_sent_recently(keyword, "twitter_trend", hours=12):
                time.sleep(0.5)
                continue

            print(f"[TWITTER-APIFY] TREND: '{keyword}' velocity +{velocity:.0f}%")
            _send_twitter_apify_alert(
                keyword, velocity, current_count, previous_count, tweets, min_score
            )
            mark_alert_sent(keyword, "twitter_trend")

        # Pausa tra keyword per rispettare il rate limit Apify
        time.sleep(1)

    print("[TWITTER-APIFY] Detector completato.")
