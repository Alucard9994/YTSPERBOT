"""
YTSPERBOT - Twitter/X via Apify
Usa apidojo~tweet-scraper ($0.40/1k tweet su piano Starter).

Funzionalità:
  - Velocity detector: calcola crescita menzioni keyword e invia alert se supera soglia
  - Quote storm: alert se quoteCount/likeCount > soglia (tweet molto citato/controverso)
  - Engagement ratio: alert se replyCount/likeCount > soglia (dibattito acceso)
  - Digest giornaliero: ogni giorno alle 19:00 invia i top 5 tweet per engagement

Actor: apidojo/tweet-scraper
  URL: https://apify.com/apidojo/tweet-scraper
  Rating: 4.2 ⭐ (155 recensioni) | 45K utenti | issues response: 6.3h
  Pricing: $0.40/1k tweet (Starter $29) | min 50 tweet per query
  Input:  { "searchTerms": [str], "maxItems": int, "sort": "Latest"|"Top" }
  Output: { "id": str, "text": str, "url": str, "twitterUrl": str,
             "retweetCount": int, "replyCount": int, "likeCount": int,
             "quoteCount": int, "createdAt": str, "lang": str,
             "author": { "userName": str, "name": str, "followers": int, ... } }

Richiede APIFY_API_KEY nel .env.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from modules.apify_scraper import run_actor
from modules.database import (
    save_keyword_count,
    get_keyword_counts,
    was_alert_sent_recently,
    mark_alert_sent,
    save_twitter_tweet,
    get_twitter_top_tweets,
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
    Output: lista di dict con id, text, url, likes, retweets, replies, quotes,
            author_username, author_followers, created_at.
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
        text = (
            item.get("text")
            or item.get("full_text")
            or item.get("Embedded_text")
            or (item.get("tweet") or {}).get("text")
            or ""
        )
        if not tweet_id or not text:
            continue
        author = item.get("author") or {}
        result.append({
            "id": tweet_id,
            "text": text,
            "url": item.get("url") or item.get("twitterUrl") or "",
            "likes": item.get("likeCount") or 0,
            "retweets": item.get("retweetCount") or 0,
            "replies": item.get("replyCount") or 0,
            "quotes": item.get("quoteCount") or 0,
            "author_username": author.get("userName") or author.get("username") or "",
            "author_followers": author.get("followers") or 0,
            "created_at": item.get("createdAt") or "",
        })
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


def _send_twitter_viral_tweet_alert(tweet: dict, keyword: str, alert_type: str) -> None:
    """Invia alert per quote storm, tweet controversiale o thread attivo."""
    text_preview = tweet["text"][:120].replace("\n", " ")
    likes = tweet.get("likes", 0)
    quotes = tweet.get("quotes", 0)
    replies = tweet.get("replies", 0)
    retweets = tweet.get("retweets", 0)
    url = tweet.get("url", "")
    author = tweet.get("author_username", "")

    if alert_type == "quote_storm":
        header = "💬 <b>QUOTE STORM TWITTER</b>"
        body = f"Tweet molto citato: {quotes:,} quote vs {likes:,} likes"
    elif alert_type == "thread":
        header = "🧵 <b>THREAD IN CORSO</b>"
        body = f"Conversazione attiva: {replies:,} risposte vs {likes:,} likes"
    else:
        header = "🔥 <b>TWEET CONTROVERSIALE</b>"
        body = f"Alto engagement replies: {replies:,} risposte vs {likes:,} likes"

    text = (
        f"{header}\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        + (f"👤 @{author}\n" if author else "")
        + f"📝 {text_preview}\n\n"
        f"❤️ {likes:,}  💬 {replies:,}  🔁 {retweets:,}  🗣 {quotes:,}\n"
        f"{body}\n"
        + (f'🔗 <a href="{url}">Vedi tweet</a>\n' if url else "")
        + f"\n<i>Rilevato da YTSPERBOT — {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
    )
    send_message(text)


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

    quote_storm_ratio = tw_cfg.get("quote_storm_ratio", 0.3)
    engagement_ratio = tw_cfg.get("engagement_ratio", 0.5)
    thread_ratio = tw_cfg.get("thread_ratio", 0.8)
    min_eng_for_ratios = tw_cfg.get("min_engagement_for_ratios", 20)

    for keyword in keywords:
        tweets = _search_tweets(keyword, max_items)
        current_count = len(tweets)

        # Salva tutti i tweet e controlla viral patterns
        for tweet in tweets:
            save_twitter_tweet(
                tweet_id=tweet["id"],
                keyword=keyword,
                text=tweet["text"],
                url=tweet.get("url", ""),
                likes=tweet.get("likes", 0),
                retweets=tweet.get("retweets", 0),
                replies=tweet.get("replies", 0),
                quotes=tweet.get("quotes", 0),
                author_username=tweet.get("author_username", ""),
                author_followers=tweet.get("author_followers", 0),
                created_at=tweet.get("created_at") or None,
            )

            likes = tweet.get("likes", 0)
            if likes < min_eng_for_ratios:
                continue

            quotes = tweet.get("quotes", 0)
            replies = tweet.get("replies", 0)

            # Quote storm: il tweet viene molto citato
            if quotes > 0 and quotes / likes >= quote_storm_ratio:
                alert_id = f"twitter_quote_storm_{tweet['id']}"
                if not was_alert_sent_recently(alert_id, "twitter_quote_storm", hours=48):
                    print(f"[TWITTER-APIFY] QUOTE STORM: '{tweet['text'][:50]}' ({quotes} quote)")
                    _send_twitter_viral_tweet_alert(tweet, keyword, "quote_storm")
                    mark_alert_sent(alert_id, "twitter_quote_storm")

            # Thread attivo: molte risposte rispetto ai like (soglia alta → conversazione intensa)
            if replies > 0 and replies / likes >= thread_ratio:
                alert_id = f"twitter_thread_{tweet['id']}"
                if not was_alert_sent_recently(alert_id, "twitter_thread", hours=48):
                    print(f"[TWITTER-APIFY] THREAD: '{tweet['text'][:50]}' ({replies} replies vs {likes} likes)")
                    _send_twitter_viral_tweet_alert(tweet, keyword, "thread")
                    mark_alert_sent(alert_id, "twitter_thread")

            # Controversial: risposte moderate (tra engagement_ratio e thread_ratio)
            elif replies > 0 and replies / likes >= engagement_ratio:
                alert_id = f"twitter_controversial_{tweet['id']}"
                if not was_alert_sent_recently(alert_id, "twitter_controversial", hours=48):
                    print(f"[TWITTER-APIFY] CONTROVERSIAL: '{tweet['text'][:50]}' ({replies} replies)")
                    _send_twitter_viral_tweet_alert(tweet, keyword, "controversial")
                    mark_alert_sent(alert_id, "twitter_controversial")

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

        time.sleep(1)

    print("[TWITTER-APIFY] Detector completato.")


def run_twitter_digest(config: dict):
    """Invia il digest giornaliero con i top tweet per engagement."""
    if not os.getenv("APIFY_API_KEY"):
        return

    if was_alert_sent_recently("twitter_daily_digest", "twitter_digest", hours=20):
        print("[TWITTER-DIGEST] Digest già inviato nelle ultime 20h — skip.")
        return

    tweets = get_twitter_top_tweets(hours=24, limit=5)
    if not tweets:
        print("[TWITTER-DIGEST] Nessun tweet nelle ultime 24h.")
        return

    lines = []
    for i, t in enumerate(tweets, 1):
        text_preview = (t.get("text") or "")[:80].replace("\n", " ")
        eng = t.get("engagement", 0)
        likes = t.get("likes", 0)
        retweets = t.get("retweets", 0)
        url = t.get("url", "")
        kw = t.get("keyword", "")
        line = f"{i}. [{kw}] {text_preview}\n   ❤️ {likes:,}  🔁 {retweets:,}  📊 {eng:,}"
        if url:
            line += f'  <a href="{url}">↗</a>'
        lines.append(line)

    text = (
        f"🐦 <b>TWITTER/X DIGEST GIORNALIERO</b>\n"
        f"<i>Top tweet per engagement — {datetime.now().strftime('%d/%m/%Y')}</i>\n\n"
        + "\n\n".join(lines)
        + "\n\n<i>Fonte: monitoraggio keyword nicchia paranormale/occulto</i>"
    )
    send_message(text)
    mark_alert_sent("twitter_daily_digest", "twitter_digest")
    print(f"[TWITTER-DIGEST] Digest inviato — {len(tweets)} tweet.")
