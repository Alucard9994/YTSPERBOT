"""
TheVeil Monitor - Modulo X (Twitter) Detector
Monitora tweet recenti per keyword velocity.

Dipendenza: pip install tweepy
Attivare: inserire TWITTER_BEARER_TOKEN nel .env e impostare TWITTER_ENABLED = True
"""

import os
import time
from datetime import datetime

import tweepy

from modules.database import (
    save_keyword_count, get_keyword_counts,
    was_alert_sent_recently, mark_alert_sent,
    is_post_seen, mark_post_seen
)
from modules.telegram_bot import send_message, alert_allowed, calculate_priority_score, score_bar

# ============================================================
# STATO MODULO
# ============================================================
TWITTER_ENABLED = True

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")


def get_twitter_client() -> tweepy.Client:
    if not BEARER_TOKEN or BEARER_TOKEN == "inserisci_qui":
        raise ValueError("TWITTER_BEARER_TOKEN non configurato nel .env")
    return tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=True)


def search_recent_tweets(client: tweepy.Client, keyword: str, max_results: int = 100) -> list:
    """
    Cerca tweet recenti (ultimi 7 giorni) contenenti la keyword.
    Esclude retweet e reply per avere solo contenuto originale.
    """
    query = f'"{keyword}" -is:retweet -is:reply lang:it OR lang:en'
    try:
        response = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=["id", "text", "created_at", "author_id"]
        )
        if not response.data:
            return []
        return [{"id": str(t.id), "text": t.text} for t in response.data]
    except tweepy.errors.TweepyException as e:
        print(f"[TWITTER] Errore ricerca '{keyword}': {e}")
        return []


def send_twitter_alert(keyword: str, velocity: float, count_now: int, count_before: int, sample_tweets: list, min_score: int = 1):
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
        f"<i>Topic in crescita su X/Twitter.</i>"
    )
    return send_message(text)


def run_twitter_detector(config: dict):
    """Esegue il trend detector X/Twitter."""

    if not TWITTER_ENABLED:
        print("[TWITTER] Modulo disabilitato. Impostare TWITTER_ENABLED=True quando le credenziali sono pronte.")
        return

    print(f"\n[TWITTER] Avvio detector - {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    try:
        client = get_twitter_client()
    except ValueError as e:
        print(f"[TWITTER] {e}")
        return

    trend_cfg = config["trend_detector"]
    keywords = config["keywords"]
    min_mentions = trend_cfg.get("min_mentions_to_track", 3)

    for keyword in keywords:
        tweets = search_recent_tweets(client, keyword)
        current_count = len(tweets)

        if current_count < min_mentions:
            continue

        previous_records = get_keyword_counts(keyword, "twitter", 48)
        previous_count = previous_records[0]["count"] if previous_records else 0

        save_keyword_count(keyword, "twitter", current_count)

        if previous_count == 0:
            continue

        velocity = ((current_count - previous_count) / previous_count) * 100

        if velocity >= trend_cfg["velocity_threshold_longform"]:
            if was_alert_sent_recently(keyword, "twitter_trend", hours=12):
                continue

            print(f"[TWITTER] TREND: '{keyword}' velocity +{velocity:.0f}%")
            min_score = config.get("priority_score", {}).get("min_score", 1)
            send_twitter_alert(keyword, velocity, current_count, previous_count, tweets, min_score=min_score)
            mark_alert_sent(keyword, "twitter_trend")

        # Pausa tra keyword per rispettare il rate limit (500k tweet/mese free tier)
        time.sleep(1)

    print("[TWITTER] Detector completato.")
