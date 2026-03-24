"""
YTSPERBOT - Modulo YouTube Scraper
Cerca canali piccoli/medi con video outperformer (Nx la media del canale)
"""

import os
import time
from datetime import datetime, timedelta, timezone
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

from modules.database import is_channel_video_sent, mark_channel_video_sent
from modules.telegram_bot import send_channel_alert
from modules.yt_api import yt_get


def get_transcript(video_id: str, languages: list = ["it", "en"]) -> str:
    """
    Recupera la trascrizione di un video YouTube senza autenticazione.
    Funziona per la maggior parte dei video pubblici con sottotitoli disponibili.
    """
    time.sleep(2)
    ytt = YouTubeTranscriptApi()

    # Tentativo 1: lingua preferita
    try:
        fetched = ytt.fetch(video_id, languages=languages)
        return " ".join([entry.text for entry in fetched])
    except Exception:
        pass

    # Tentativo 2: qualsiasi lingua disponibile
    try:
        fetched = ytt.fetch(video_id)
        return " ".join([entry.text for entry in fetched])
    except Exception as e:
        print(f"[YT-SCRAPER] Trascrizione non disponibile per {video_id}: {e}")
        return ""


def search_channels(query: str, max_results: int = 10) -> list:
    try:
        data = yt_get("search", {"part": "snippet", "q": query, "type": "channel", "maxResults": max_results})
        return data.get("items", [])
    except Exception as e:
        print(f"[YT-SCRAPER] Errore ricerca canali '{query}': {e}")
        return []


def get_channel_stats(channel_id: str):
    try:
        data = yt_get("channels", {"part": "statistics,snippet,contentDetails", "id": channel_id})
        items = data.get("items", [])
        if not items:
            return None
        stats = items[0]["statistics"]
        snippet = items[0]["snippet"]
        uploads = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
        return {
            "id": channel_id,
            "name": snippet.get("title", ""),
            "subscribers": int(stats.get("subscriberCount", 0)),
            "uploads_playlist": uploads
        }
    except Exception as e:
        print(f"[YT-SCRAPER] Errore stats canale {channel_id}: {e}")
        return None


def get_recent_videos(uploads_playlist: str, lookback_days: int = 30) -> list:
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        videos = []
        next_page_token = None

        while True:
            params = {"part": "snippet", "playlistId": uploads_playlist, "maxResults": 50}
            if next_page_token:
                params["pageToken"] = next_page_token

            data = yt_get("playlistItems", params)

            for item in data.get("items", []):
                published_at_str = item["snippet"]["publishedAt"]
                published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                if published_at < cutoff_date:
                    return videos
                video_id = item["snippet"]["resourceId"]["videoId"]
                videos.append({"id": video_id, "title": item["snippet"]["title"], "published_at": published_at_str})

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        return videos
    except Exception as e:
        print(f"[YT-SCRAPER] Errore recupero video playlist: {e}")
        return []


def _is_short(duration: str) -> bool:
    """Restituisce True se il video dura meno di 3 minuti (probabile Short)."""
    import re
    if not duration:
        return False
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return False
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    if hours > 0:
        return False
    return minutes < 3


def get_video_details(video_ids: list) -> tuple[list, list]:
    """Restituisce due liste: (video_lunghi, shorts)."""
    if not video_ids:
        return [], []
    try:
        data = yt_get("videos", {
            "part": "statistics,snippet,contentDetails",
            "id": ",".join(video_ids[:50])
        })
        long_videos = []
        shorts = []
        for item in data.get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            duration = item.get("contentDetails", {}).get("duration", "")

            video = {
                "id": item["id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "views": int(stats.get("viewCount", 0)),
                "published_at": snippet.get("publishedAt", "")
            }

            if _is_short(duration):
                shorts.append(video)
            else:
                long_videos.append(video)

        return long_videos, shorts
    except Exception as e:
        print(f"[YT-SCRAPER] Errore dettagli video: {e}")
        return [], []


def calculate_multiplier(video_views: int, subscribers: int) -> float:
    if subscribers == 0:
        return 0.0
    return video_views / subscribers


def run_scraper(config: dict):
    print(f"\n[YT-SCRAPER] Avvio scraper - {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    scraper_cfg = config["scraper"]
    max_followers = scraper_cfg["max_followers"]
    min_followers = scraper_cfg["min_followers"]
    multiplier_threshold = scraper_cfg["multiplier_threshold"]
    lookback_days = scraper_cfg["lookback_days"]
    max_channels = scraper_cfg["max_channels_per_run"]

    queries = []
    for lang_queries in config["youtube_search_queries"].values():
        queries.extend(lang_queries)

    channels_analyzed = 0
    channels_seen = set()

    for query in queries:
        if channels_analyzed >= max_channels:
            break

        print(f"[YT-SCRAPER] Query: '{query}'")
        search_results = search_channels(query, max_results=10)

        for result in search_results:
            if channels_analyzed >= max_channels:
                break

            channel_id = result["snippet"]["channelId"]
            if channel_id in channels_seen:
                continue
            channels_seen.add(channel_id)
            channels_analyzed += 1

            channel_stats = get_channel_stats(channel_id)
            if not channel_stats:
                continue

            subs = channel_stats["subscribers"]
            if not (min_followers <= subs <= max_followers):
                print(f"[YT-SCRAPER] Skip {channel_stats['name']} ({subs:,} iscritti)")
                continue

            print(f"[YT-SCRAPER] Analisi canale: {channel_stats['name']} ({subs:,} iscritti)")

            uploads_playlist = channel_stats.get("uploads_playlist", "")
            if not uploads_playlist:
                continue

            recent_videos = get_recent_videos(uploads_playlist, lookback_days)
            if not recent_videos:
                continue

            videos_last_month = len(recent_videos)
            video_ids = [v["id"] for v in recent_videos]
            long_videos, shorts = get_video_details(video_ids)

            for format_label, detailed_videos in [("🎬 Long-form", long_videos), ("⚡ Short", shorts)]:
                if not detailed_videos:
                    continue

                all_views = [v["views"] for v in detailed_videos if v["views"] > 0]
                avg_views = sum(all_views) / len(all_views) if all_views else 0

                for video in detailed_videos:
                    if is_channel_video_sent(channel_id, video["id"]):
                        continue

                    multiplier = calculate_multiplier(video["views"], subs)

                    if multiplier >= multiplier_threshold:
                        print(f"[YT-SCRAPER] OUTPERFORMER trovato ({format_label}): {video['title']} ({multiplier:.1f}x)")
                        transcript = get_transcript(video["id"], languages=["it", "en"])

                        channel_data = {
                            "format": format_label,
                            "channel": {
                                "name": channel_stats["name"],
                                "subscribers": subs,
                                "videos_last_month": videos_last_month,
                                "avg_views": avg_views
                            },
                            "video": {
                                "id": video["id"],
                                "title": video["title"],
                                "description": video["description"],
                                "tags": video.get("tags", []),
                                "views": video["views"],
                                "transcript": transcript
                            },
                            "multiplier": multiplier
                        }

                        send_channel_alert(channel_data)
                        mark_channel_video_sent(channel_id, video["id"])

    print(f"[YT-SCRAPER] Completato. Canali analizzati: {channels_analyzed}")