"""
YTSPERBOT - Reddit via Apify
Alternativa alle credenziali Reddit native: usa fatihtahta~reddit-scraper-search-fast ($1.50/1k post).

Logica identica a reddit_detector.py:
  - Recupera post recenti da subreddit monitorati (rotazione per contenere i costi)
  - Calcola velocity menzioni per keyword
  - Invia alert Telegram se supera la soglia

Configurazione consigliata per restare nel free tier Apify ($5/mese):
  reddit.subreddits_per_run: 5        # subreddit per run (ruota su tutti quelli configurati)
  reddit.posts_per_subreddit: 20      # post per subreddit
  reddit.check_interval_hours: 84     # 2x/settimana (ogni ~84h)
  → 5 × 20 × 2 run/sett × 4 sett = 800 post/mese = $1.20/mese ✅

Richiede APIFY_API_KEY nel .env.
"""

import os
import time
import math
from datetime import datetime

from modules.apify_scraper import run_actor
from modules.database import (
    save_keyword_count, get_keyword_counts,
    was_alert_sent_recently, mark_alert_sent,
)
from modules.telegram_bot import send_trend_alert

REDDIT_ACTOR = "fatihtahta~reddit-scraper-search-fast"


def _fetch_subreddit_posts(subreddit: str, limit: int) -> list:
    """Recupera i post più recenti da un subreddit via Apify."""
    url = f"https://www.reddit.com/r/{subreddit}/new/?limit={limit}"
    items = run_actor(REDDIT_ACTOR, {
        "startUrls": [{"url": url}],
        "maxItems": limit,
    })
    posts = []
    for item in items:
        post_id = str(item.get("id") or item.get("postId") or "")
        title   = item.get("title") or ""
        text    = item.get("text") or item.get("selftext") or item.get("body") or ""
        if post_id:
            posts.append({"id": post_id, "title": title, "text": text})
    return posts


def _count_mentions(posts: list, keyword: str) -> int:
    """Conta occorrenze di keyword in titolo + testo dei post."""
    kw = keyword.lower()
    return sum(
        1 for p in posts
        if kw in (p.get("title", "") + " " + p.get("text", "")).lower()
    )


def _select_subreddits(subreddits: list, per_run: int) -> list:
    """
    Seleziona un sottoinsieme di subreddit ruotando in base alla settimana.
    Copre tutti i subreddit nel giro di ceil(N/per_run) run.
    """
    n = len(subreddits)
    if per_run <= 0 or per_run >= n:
        return subreddits
    slots  = math.ceil(n / per_run)
    offset = (datetime.now().isocalendar()[1] % slots) * per_run
    chunk  = subreddits[offset: offset + per_run]
    # Completa se il chunk è a cavallo della fine della lista
    if len(chunk) < per_run:
        chunk += subreddits[: per_run - len(chunk)]
    return chunk


def run_reddit_apify_detector(config: dict):
    """Esegue il Reddit trend detector via Apify."""
    if not os.getenv("APIFY_API_KEY"):
        print("[REDDIT-APIFY] APIFY_API_KEY non configurata — modulo disabilitato.")
        return

    print(f"\n[REDDIT-APIFY] Avvio detector — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    trend_cfg      = config.get("trend_detector", {})
    reddit_cfg     = config.get("reddit", {})
    keywords       = config.get("keywords", [])
    all_subreddits = config.get("subreddits", [])

    per_run      = reddit_cfg.get("subreddits_per_run", 5)
    posts_limit  = reddit_cfg.get("posts_per_subreddit", 20)
    vel_threshold = trend_cfg.get("velocity_threshold_longform", 300)
    min_mentions  = trend_cfg.get("min_mentions_to_track", 3)

    active = _select_subreddits(all_subreddits, per_run)
    print(f"[REDDIT-APIFY] Subreddit attivi questa run ({len(active)}): {active}")

    all_posts = []
    for sub in active:
        print(f"[REDDIT-APIFY] Fetch r/{sub} (max {posts_limit})...")
        posts = _fetch_subreddit_posts(sub, posts_limit)
        all_posts.extend(posts)
        print(f"[REDDIT-APIFY] r/{sub}: {len(posts)} post recuperati")
        time.sleep(1)

    print(f"[REDDIT-APIFY] Totale post: {len(all_posts)}")

    for keyword in keywords:
        current_count = _count_mentions(all_posts, keyword)
        if current_count < min_mentions:
            continue

        previous = get_keyword_counts(keyword, "reddit_apify", 48)
        prev_count = previous[0]["count"] if previous else 0
        save_keyword_count(keyword, "reddit_apify", current_count)

        if prev_count == 0:
            continue

        velocity = ((current_count - prev_count) / prev_count) * 100
        if velocity >= vel_threshold:
            if was_alert_sent_recently(keyword, "reddit_apify_trend", hours=12):
                continue
            print(f"[REDDIT-APIFY] TREND: '{keyword}' +{velocity:.0f}%")
            send_trend_alert(
                keyword=keyword,
                velocity=velocity,
                source="Reddit (via Apify)",
                mentions_now=current_count,
                mentions_before=max(1, prev_count),
            )
            mark_alert_sent(keyword, "reddit_apify_trend")

    print("[REDDIT-APIFY] Detector completato.")
