"""
YTSPERBOT - Reddit via Apify
Alternativa alle credenziali Reddit native: usa trudax~reddit-scraper-lite ($3.40/1k post).

Funzionalità:
  - Velocity detector: calcola crescita menzioni keyword e invia alert se supera soglia
  - Hot post immediato: alert se un post supera N upvote durante il fetch
  - Cross-subreddit signal: alert se la stessa keyword appare in ≥3 subreddit nella stessa run
  - Digest giornaliero: ogni giorno alle 18:00 invia i top 5 post per upvotes

Actor: trudax/reddit-scraper-lite ($3.40/1k)
  Output campi usati: id, title, body, url, upVotes, numberOfComments, createdAt, communityName

Richiede APIFY_API_KEY nel .env.
"""

import os
import time
import math
from datetime import datetime

from modules.apify_scraper import run_actor
from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
    save_reddit_post,
    get_reddit_top_posts,
    log_alert,
)
from modules.telegram_bot import send_message, send_trend_alert

REDDIT_ACTOR = "trudax~reddit-scraper-lite"


def _fetch_subreddit_posts(subreddit: str, limit: int) -> list:
    """Recupera i post più recenti da un subreddit via Apify.
    Restituisce dicts con: id, title, text, url, upvotes, num_comments, created_at, subreddit.
    """
    sub_name = subreddit.strip()
    if sub_name.startswith("r/"):
        sub_name = sub_name[2:]
    url = f"https://www.reddit.com/r/{sub_name}/new/?limit={limit}"
    items = run_actor(
        REDDIT_ACTOR,
        {
            "startUrls": [{"url": url}],
            "maxItems": limit,
        },
        timeout=300,
    )
    posts = []
    for item in items:
        post_id = str(item.get("id") or item.get("postId") or "")
        title = item.get("title") or ""
        text = item.get("text") or item.get("selftext") or item.get("body") or ""
        if post_id:
            posts.append({
                "id": post_id,
                "title": title,
                "text": text,
                "url": item.get("url") or "",
                "upvotes": item.get("upVotes") or 0,
                "num_comments": item.get("numberOfComments") or 0,
                "created_at": item.get("createdAt") or None,
                "subreddit": sub_name,
            })
    return posts


def _count_mentions(posts: list, keyword: str) -> int:
    """Conta occorrenze di keyword in titolo + testo dei post."""
    kw = keyword.lower()
    return sum(
        1 for p in posts if kw in (p.get("title", "") + " " + p.get("text", "")).lower()
    )


def _select_subreddits(subreddits: list, per_run: int) -> list:
    """
    Seleziona un sottoinsieme di subreddit ruotando in base alla settimana.
    Copre tutti i subreddit nel giro di ceil(N/per_run) run.
    """
    n = len(subreddits)
    if per_run <= 0 or per_run >= n:
        return subreddits
    slots = math.ceil(n / per_run)
    offset = (datetime.now().isocalendar()[1] % slots) * per_run
    chunk = subreddits[offset : offset + per_run]
    if len(chunk) < per_run:
        chunk += subreddits[: per_run - len(chunk)]
    return chunk


def _send_hot_post_alert(post: dict) -> None:
    """Invia alert Telegram per un post con molti upvote."""
    upvotes = post.get("upvotes", 0)
    comments = post.get("num_comments", 0)
    title = post.get("title", "")[:120]
    url = post.get("url", "")
    subreddit = post.get("subreddit", "")
    text = (
        f"🔥 <b>HOT POST REDDIT</b>\n\n"
        f"📌 <b>r/{subreddit}</b>\n"
        f"📝 {title}\n\n"
        f"👍 <b>{upvotes:,}</b> upvote  💬 <b>{comments:,}</b> commenti\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        + (f"\n\n🔗 <a href='{url}'>Leggi il post</a>" if url else "")
        + "\n\n<i>Post virale nella nicchia — rilevato da YTSPERBOT</i>"
    )
    send_message(text)


def _send_cross_subreddit_alert(keyword: str, subreddits: set) -> None:
    """Invia alert Telegram per keyword che appare su più subreddit contemporaneamente."""
    subs_list = "  ".join(f"r/{s}" for s in sorted(subreddits))
    text = (
        f"🔀 <b>CROSS-SUBREDDIT SIGNAL</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"📊 <b>{len(subreddits)} subreddit attivi</b>\n"
        f"📌 {subs_list}\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Lo stesso topic è discusso su più subreddit nella stessa run.</i>"
    )
    send_message(text)


def run_reddit_apify_detector(config: dict):
    """Esegue il Reddit trend detector via Apify."""
    if not os.getenv("APIFY_API_KEY"):
        print("[REDDIT-APIFY] APIFY_API_KEY non configurata — modulo disabilitato.")
        return

    print(
        f"\n[REDDIT-APIFY] Avvio detector — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    trend_cfg = config.get("trend_detector", {})
    reddit_cfg = config.get("reddit", {})
    keywords = config.get("keywords", [])
    all_subreddits = config.get("subreddits", [])

    per_run = reddit_cfg.get("subreddits_per_run", 5)
    posts_limit = reddit_cfg.get("posts_per_subreddit", 20)
    vel_threshold = trend_cfg.get("velocity_threshold_longform", 300)
    min_mentions = trend_cfg.get("min_mentions_to_track", 3)
    hot_threshold = reddit_cfg.get("hot_post_threshold", 100)
    min_cross_sources = reddit_cfg.get("cross_subreddit_min_sources", 3)

    active = _select_subreddits(all_subreddits, per_run)
    print(f"[REDDIT-APIFY] Subreddit attivi questa run ({len(active)}): {active}")

    all_posts = []
    # keyword → set di subreddit in cui è apparsa questa run
    kw_subreddits: dict = {kw: set() for kw in keywords}

    for sub in active:
        sub_clean = sub[2:] if sub.startswith("r/") else sub
        print(f"[REDDIT-APIFY] Fetch r/{sub_clean} (max {posts_limit})...")
        posts = _fetch_subreddit_posts(sub, posts_limit)
        all_posts.extend(posts)
        print(f"[REDDIT-APIFY] r/{sub_clean}: {len(posts)} post recuperati")

        for post in posts:
            # Salva in DB per digest
            save_reddit_post(
                post_id=post["id"],
                subreddit=sub_clean,
                title=post["title"],
                url=post.get("url", ""),
                upvotes=post.get("upvotes", 0),
                num_comments=post.get("num_comments", 0),
                created_at=post.get("created_at"),
            )
            # Hot post immediato
            if post.get("upvotes", 0) >= hot_threshold:
                alert_id = f"reddit_hot_{post['id']}"
                if not was_alert_sent_recently(alert_id, "reddit_hot_post", hours=48):
                    print(f"[REDDIT-APIFY] HOT POST: '{post['title'][:60]}' ({post['upvotes']} upvotes)")
                    _send_hot_post_alert(post)
                    mark_alert_sent(alert_id, "reddit_hot_post")
                    log_alert("reddit_hot_post", post["title"][:80], "Reddit (via Apify)",
                              velocity_pct=None, extra_json=f'{{"upvotes":{post["upvotes"]},"subreddit":"{sub_clean}","url":"{post.get("url","")}"}}')


        # Traccia subreddit per cross-signal
        for kw in keywords:
            if _count_mentions(posts, kw) > 0:
                kw_subreddits[kw].add(sub_clean)

        time.sleep(1)

    print(f"[REDDIT-APIFY] Totale post: {len(all_posts)}")

    # Cross-subreddit signal
    for kw, subreddits in kw_subreddits.items():
        if len(subreddits) >= min_cross_sources:
            alert_id = f"reddit_cross_{kw[:40].lower().replace(' ', '_')}"
            if not was_alert_sent_recently(alert_id, "reddit_cross_signal", hours=24):
                print(f"[REDDIT-APIFY] CROSS-SIGNAL: '{kw}' su {len(subreddits)} subreddit")
                _send_cross_subreddit_alert(kw, subreddits)
                mark_alert_sent(alert_id, "reddit_cross_signal")
                import json as _json
                log_alert("reddit_cross_signal", kw, "Reddit (via Apify)",
                          sources_list=",".join(sorted(subreddits)),
                          extra_json=_json.dumps({"subreddits": sorted(subreddits)}))

    # Velocity detector (esistente)
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


def run_reddit_digest(config: dict):
    """Invia il digest giornaliero con i top post Reddit per upvotes."""
    if not os.getenv("APIFY_API_KEY"):
        return

    if was_alert_sent_recently("reddit_daily_digest", "reddit_digest", hours=20):
        print("[REDDIT-DIGEST] Digest già inviato nelle ultime 20h — skip.")
        return

    reddit_cfg = config.get("reddit", {})
    min_upvotes = reddit_cfg.get("hot_post_threshold", 10)
    posts = get_reddit_top_posts(hours=24, min_upvotes=min_upvotes, limit=5)

    if not posts:
        print("[REDDIT-DIGEST] Nessun post rilevante nelle ultime 24h.")
        return

    lines = []
    for i, p in enumerate(posts, 1):
        url = p.get("url", "")
        title = (p.get("title") or "")[:80]
        upvotes = p.get("upvotes", 0)
        comments = p.get("num_comments", 0)
        subreddit = p.get("subreddit", "")
        line = f"{i}. <b>r/{subreddit}</b> — {title}\n   👍 {upvotes:,}  💬 {comments:,}"
        if url:
            line += f'  <a href="{url}">↗</a>'
        lines.append(line)

    text = (
        f"📰 <b>REDDIT DIGEST GIORNALIERO</b>\n"
        f"<i>Top post nelle ultime 24h — {datetime.now().strftime('%d/%m/%Y')}</i>\n\n"
        + "\n\n".join(lines)
        + "\n\n<i>Fonte: subreddit nicchia paranormale/occulto</i>"
    )
    send_message(text)
    mark_alert_sent("reddit_daily_digest", "reddit_digest")
    print(f"[REDDIT-DIGEST] Digest inviato — {len(posts)} post.")
