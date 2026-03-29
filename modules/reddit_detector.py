"""
YTSPERBOT - Modulo Reddit Trend Detector (API nativa via PRAW)
Richiede REDDIT_CLIENT_ID e REDDIT_CLIENT_SECRET nel .env.
Se non disponibili, usare l'alternativa Apify (reddit_apify.py) impostando
  reddit.use_apify: true  nel config.yaml.
"""

import os
import praw
from datetime import datetime

from modules.database import (
    save_keyword_count, get_keyword_counts,
    is_post_seen, mark_post_seen,
    was_alert_sent_recently, mark_alert_sent
)
from modules.telegram_bot import send_trend_alert

REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT", "theveil-monitor/1.0")

# Attivo solo se le credenziali sono presenti e non sono i placeholder
REDDIT_ENABLED = (
    bool(REDDIT_CLIENT_ID)
    and bool(REDDIT_CLIENT_SECRET)
    and REDDIT_CLIENT_ID != "inserisci_qui"
)


def get_reddit_client():
    if not REDDIT_CLIENT_ID or REDDIT_CLIENT_ID == "inserisci_qui":
        raise ValueError("Credenziali Reddit non configurate nel file .env")
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )


def count_keyword_mentions(posts: list, keyword: str) -> int:
    """Conta quante volte una keyword appare nei post (titolo + testo)."""
    count = 0
    keyword_lower = keyword.lower()
    for post in posts:
        text = (post.get("title", "") + " " + post.get("text", "")).lower()
        if keyword_lower in text:
            count += 1
    return count


def fetch_subreddit_posts(reddit, subreddit_name: str, limit: int = 100) -> list:
    """Recupera i post recenti da un subreddit."""
    try:
        subreddit = reddit.subreddit(subreddit_name)
        posts = []
        for post in subreddit.new(limit=limit):
            posts.append({
                "id": post.id,
                "title": post.title,
                "text": post.selftext or ""
            })
        return posts
    except Exception as e:
        print(f"[REDDIT] Errore fetch r/{subreddit_name}: {e}")
        return []


def calculate_velocity(keyword: str, source: str, current_count: int, lookback_hours: int) -> float:
    """
    Calcola la velocity rispetto al run precedente.
    Restituisce il % di crescita (es. 500.0 = +500%)
    """
    previous_records = get_keyword_counts(keyword, source, lookback_hours)
    if not previous_records:
        return 0.0

    # Prende il valore più vecchio disponibile come riferimento
    previous_count = previous_records[0]["count"]
    if previous_count == 0:
        return 0.0

    velocity = ((current_count - previous_count) / previous_count) * 100
    return velocity


def run_reddit_detector(config: dict):
    """Esegue il trend detector Reddit."""

    if not REDDIT_ENABLED:
        print("[REDDIT] Modulo disabilitato. Attivare REDDIT_ENABLED quando le credenziali sono pronte.")
        return

    print(f"\n[REDDIT] Avvio trend detector - {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    try:
        reddit = get_reddit_client()
    except ValueError as e:
        print(f"[REDDIT] {e}")
        return

    trend_cfg = config["trend_detector"]
    keywords = config["keywords"]
    subreddits = config["subreddits"]

    # Recupera post da tutti i subreddit
    all_posts = []
    for subreddit_name in subreddits:
        posts = fetch_subreddit_posts(reddit, subreddit_name)
        all_posts.extend(posts)
        print(f"[REDDIT] r/{subreddit_name}: {len(posts)} post recuperati")

    # Analizza ogni keyword
    for keyword in keywords:
        current_count = count_keyword_mentions(all_posts, keyword)

        if current_count < trend_cfg.get("min_mentions_to_track", 3):
            continue

        # Calcola velocity per longform e shorts
        velocity_48h = calculate_velocity(keyword, "reddit", current_count, 48)
        velocity_24h = calculate_velocity(keyword, "reddit", current_count, 24)

        # Salva il conteggio attuale
        save_keyword_count(keyword, "reddit", current_count)

        # Controlla soglie
        threshold_longform = trend_cfg["velocity_threshold_longform"]
        threshold_shorts = trend_cfg["velocity_threshold_shorts"]

        if velocity_48h >= threshold_longform or velocity_24h >= threshold_shorts:
            # Evita alert duplicati nelle ultime 12 ore
            if was_alert_sent_recently(keyword, "trend", hours=12):
                continue

            velocity = max(velocity_48h, velocity_24h)
            mentions_before = max(1, current_count - int(current_count * velocity / 100))

            print(f"[REDDIT] TREND: '{keyword}' velocity +{velocity:.0f}%")
            send_trend_alert(
                keyword=keyword,
                velocity=velocity,
                source="Reddit",
                mentions_now=current_count,
                mentions_before=mentions_before
            )
            mark_alert_sent(keyword, "trend")

    print("[REDDIT] Trend detector completato.")
