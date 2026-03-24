"""
TheVeil Monitor - Modulo YouTube Comments Detector
Tre liste separate:
  Lista 1 - Trend detector: keyword velocity nei commenti di video della nicchia
  Lista 2 - Competitor intelligence: domande/richieste nei commenti dei competitor
"""

import os
import time
from datetime import datetime, timezone, timedelta

from modules.database import (
    save_keyword_count, get_keyword_counts,
    was_alert_sent_recently, mark_alert_sent,
    is_post_seen, mark_post_seen
)
from modules.telegram_bot import send_trend_alert, send_message, alert_allowed, calculate_priority_score, score_bar
from modules.yt_api import yt_get


def resolve_channel_handle(handle: str) -> str | None:
    """Risolve un handle YouTube (@nome) nel channel ID."""
    try:
        data = yt_get("channels", {
            "part": "id,snippet",
            "forHandle": handle
        })
        items = data.get("items", [])
        if items:
            return items[0]["id"]
        return None
    except Exception as e:
        print(f"[YT-COMMENTS] Errore risoluzione handle @{handle}: {e}")
        return None


def get_channel_recent_videos(channel_id: str, max_videos: int = 3) -> list:
    """Recupera gli ultimi N video di un canale."""
    try:
        # Prima ottieni la playlist uploads
        ch_data = yt_get("channels", {
            "part": "contentDetails",
            "id": channel_id
        })
        items = ch_data.get("items", [])
        if not items:
            return []
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Recupera i video
        pl_data = yt_get("playlistItems", {
            "part": "snippet",
            "playlistId": uploads,
            "maxResults": max_videos
        })

        videos = []
        for item in pl_data.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]
            title = item["snippet"]["title"]
            videos.append({"id": video_id, "title": title})

        return videos
    except Exception as e:
        print(f"[YT-COMMENTS] Errore video canale {channel_id}: {e}")
        return []


def get_video_comments(video_id: str, max_comments: int = 100) -> list:
    """Recupera i commenti recenti di un video."""
    try:
        data = yt_get("commentThreads", {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(max_comments, 100),
            "order": "relevance"
        })
        comments = []
        for item in data.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(text)
        return comments
    except Exception as e:
        # I commenti possono essere disabilitati, non è un errore critico
        return []


def count_keyword_in_comments(comments: list, keyword: str) -> int:
    keyword_lower = keyword.lower()
    return sum(1 for c in comments if keyword_lower in c.lower())


SENTIMENT_PATTERNS = {
    "richiesta_video": [
        "fai un video", "potresti fare un video", "fai anche", "prossimo video su",
        "dovresti parlare di", "parla di", "vorrei vedere un video",
        "make a video", "can you do a video", "please do a video on",
        "next video about", "would love to see", "do a video on", "do one on",
        "can you cover", "please cover", "i'd love a video",
    ],
    "domanda_fonte": [
        "qualcuno sa dove", "qualcuno sa come", "sapete dove posso trovare",
        "dove posso trovare", "qualcuno conosce", "avete info su",
        "does anyone know where", "where can i find", "anyone know about",
        "can someone explain", "what is the source", "source?",
    ],
    "richiesta_approfondimento": [
        "potresti approfondire", "vorrei sapere di più su", "hai altre info su",
        "c'è altro su", "puoi dirmi di più",
        "can you go deeper", "more info on", "can you explain more",
        "tell me more about", "i want to know more about",
    ],
    "suggerimento_topic": [
        "dovresti parlare", "hai già parlato di", "hai mai sentito di",
        "you should talk about", "have you heard of", "have you done a video on",
        "you should do", "what about", "how about a video on",
    ],
}


def detect_audience_requests(comments: list) -> list:
    """
    Rileva richieste del pubblico classificandole per categoria.
    Restituisce lista di dict {comment, category}.
    """
    results = []
    for comment in comments:
        comment_lower = comment.lower()
        for category, patterns in SENTIMENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in comment_lower:
                    results.append({
                        "comment": comment[:500],
                        "category": category
                    })
                    break
            else:
                continue
            break
    return results


def send_comments_trend_alert(keyword: str, velocity: float, source_name: str, count_now: int, count_before: int, min_score: int = 1):
    if not alert_allowed(keyword, velocity, min_score):
        return False

    from modules.database import get_keyword_source_count
    source_count = get_keyword_source_count(keyword, hours=24)
    score = calculate_priority_score(velocity, source_count)
    emoji = "💬"
    text = (
        f"{emoji} <b>TREND COMMENTI</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"📡 <b>Fonte:</b> {source_name}\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Menzioni:</b> {count_before} → {count_now}\n"
        f"🎯 <b>Score:</b> {score}/10  {score_bar(score)}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Topic emergente nei commenti YouTube della nicchia.</i>"
    )
    return send_message(text)


CATEGORY_LABELS = {
    "richiesta_video": "🎬 Vogliono un video su",
    "domanda_fonte": "🔍 Cercano fonti / info",
    "richiesta_approfondimento": "📖 Vogliono approfondire",
    "suggerimento_topic": "💡 Suggeriscono topic",
}


def send_competitor_requests_alert(channel_name: str, video_title: str, video_id: str, requests: list):
    if not requests:
        return

    # Raggruppa per categoria
    from collections import defaultdict
    by_category = defaultdict(list)
    for r in requests:
        by_category[r["category"]].append(r["comment"])

    sections = []
    for cat, comments in by_category.items():
        label = CATEGORY_LABELS.get(cat, cat)
        preview = "\n".join(f"  • {c[:400]}" for c in comments[:3])
        sections.append(f"<b>{label} ({len(comments)}):</b>\n<i>{preview}</i>")

    text = (
        f"🧠 <b>SENTIMENT COMMENTI COMPETITOR</b>\n\n"
        f"📺 <b>Canale:</b> {channel_name}\n"
        f"🎬 <b>Video:</b> {video_title[:60]}\n"
        f"🔗 https://www.youtube.com/watch?v={video_id}\n"
        f"🆔 <code>{video_id}</code>\n\n"
        f"{'—' * 20}\n"
        + "\n\n".join(sections) +
        f"\n\n<i>💡 Usa /transcript {video_id} per analizzare il contenuto.</i>"
    )
    return send_message(text)


# ============================================================
# LISTA 1: Trend detector nei commenti della nicchia
# ============================================================

def run_comments_trend_detector(config: dict):
    """Monitora commenti di video recenti nella nicchia per keyword velocity."""
    print(f"\n[YT-COMMENTS] Lista 1: Trend detector commenti nicchia")

    trend_cfg = config["trend_detector"]
    comments_cfg = config.get("youtube_comments", {})
    keywords = config["keywords"]
    queries = []
    for lang_queries in config["youtube_search_queries"].values():
        queries.extend(lang_queries[:3])  # prime 3 query per lingua, basta per il sampling

    max_comments = comments_cfg.get("max_comments_per_video", 100)
    velocity_threshold = comments_cfg.get("velocity_threshold", 200)

    all_comments = []

    # Cerca video recenti della nicchia (ultimi 7 giorni)
    for query in queries[:6]:  # limitiamo le query per risparmiare quota
        try:
            data = yt_get("search", {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 5,
                "order": "date",
                "publishedAfter": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            for item in data.get("items", []):
                video_id = item["id"]["videoId"]
                comments = get_video_comments(video_id, max_comments)
                all_comments.extend(comments)
                time.sleep(0.5)
        except Exception as e:
            print(f"[YT-COMMENTS] Errore query '{query}': {e}")
            continue

    print(f"[YT-COMMENTS] Commenti totali recuperati (nicchia): {len(all_comments)}")

    for keyword in keywords:
        current_count = count_keyword_in_comments(all_comments, keyword)
        if current_count < trend_cfg.get("min_mentions_to_track", 3):
            continue

        previous_records = get_keyword_counts(keyword, "yt_comments_trend", 48)
        previous_count = previous_records[0]["count"] if previous_records else 0
        save_keyword_count(keyword, "yt_comments_trend", current_count)

        if previous_count == 0:
            continue

        velocity = ((current_count - previous_count) / previous_count) * 100

        if velocity >= velocity_threshold:
            if was_alert_sent_recently(keyword, "yt_comments_trend", hours=12):
                continue
            print(f"[YT-COMMENTS] TREND: '{keyword}' velocity +{velocity:.0f}%")
            min_score = config.get("priority_score", {}).get("min_score", 1)
            send_comments_trend_alert(keyword, velocity, "YouTube Comments (nicchia)", current_count, previous_count, min_score=min_score)
            mark_alert_sent(keyword, "yt_comments_trend")

    print("[YT-COMMENTS] Lista 1 completata.")


# ============================================================
# LISTA 2: Competitor intelligence
# ============================================================

def run_competitor_comments(config: dict):
    """Monitora commenti dei canali competitor cercando richieste del pubblico."""
    print(f"\n[YT-COMMENTS] Lista 2: Competitor intelligence")

    comments_cfg = config.get("youtube_comments", {})
    competitor_cfg = config.get("competitor_channels", {})
    max_comments = comments_cfg.get("max_comments_per_video", 100)
    max_videos = comments_cfg.get("max_videos_per_channel", 3)

    all_channels = []
    for lang, channels in competitor_cfg.items():
        if isinstance(channels, list):
            all_channels.extend(channels)

    for channel in all_channels:
        handle = channel.get("handle", "")
        if not handle:
            continue

        print(f"[YT-COMMENTS] Analisi competitor: @{handle}")

        channel_id = resolve_channel_handle(handle)
        if not channel_id:
            continue

        recent_videos = get_channel_recent_videos(channel_id, max_videos)

        for video in recent_videos:
            video_id = video["id"]
            video_title = video["title"]

            if is_post_seen(f"comp_{video_id}", "yt_comments"):
                continue

            comments = get_video_comments(video_id, max_comments)
            if not comments:
                mark_post_seen(f"comp_{video_id}", "yt_comments")
                continue

            requests_found = detect_audience_requests(comments)

            if len(requests_found) >= 2:
                print(f"[YT-COMMENTS] Richieste trovate in '{video_title}': {len(requests_found)}")
                send_competitor_requests_alert(handle, video_title, video_id, requests_found)

            mark_post_seen(f"comp_{video_id}", "yt_comments")
            time.sleep(1)

        time.sleep(1)

    print("[YT-COMMENTS] Lista 2 completata.")


def run_youtube_comments_detector(config: dict):
    """Esegue entrambe le liste."""
    run_comments_trend_detector(config)
    run_competitor_comments(config)
