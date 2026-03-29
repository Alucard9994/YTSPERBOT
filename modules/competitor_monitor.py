"""
YTSPERBOT - Competitor Monitor
Feature 8: Alert nuovo video competitor (ogni 30 min, via RSS YouTube — 0 quota API)
Feature 10: Alert crescita iscritti competitor (giornaliero, via YouTube Data API)
"""

import time
import feedparser
from datetime import datetime, timezone

from modules.database import (
    is_channel_video_sent,
    mark_channel_video_sent,
    save_subscriber_count,
    get_subscriber_history,
    get_channel_id_cache,
    set_channel_id_cache,
    was_alert_sent_recently,
    mark_alert_sent,
    save_keyword_count,
    log_competitor_video,
)
from modules.telegram_bot import send_message
from modules.yt_api import yt_get


# ============================================================
# Utility: risoluzione handle → channel_id con cache DB
# ============================================================


def resolve_and_cache(handle: str) -> str | None:
    """Risolve @handle → channel_id. Risultato cachato in DB."""
    cached = get_channel_id_cache(handle)
    if cached:
        return cached
    try:
        data = yt_get("channels", {"part": "id", "forHandle": handle})
        items = data.get("items", [])
        if items:
            channel_id = items[0]["id"]
            set_channel_id_cache(handle, channel_id)
            print(f"[COMPETITOR] Cachato: @{handle} → {channel_id}")
            return channel_id
    except Exception as e:
        print(f"[COMPETITOR] Errore risoluzione @{handle}: {e}")
    return None


def extract_title_keywords(title: str, config_keywords: list) -> list:
    """Controlla quali keyword monitorate compaiono nel titolo di un video competitor."""
    title_lower = title.lower()
    found = []
    for kw in config_keywords:
        if kw.lower() in title_lower:
            found.append(kw)
    return found


def get_all_handles(config: dict) -> list:
    competitor_cfg = config.get("competitor_channels", {})
    handles = []
    for channels in competitor_cfg.values():
        if isinstance(channels, list):
            handles.extend(c.get("handle", "") for c in channels if c.get("handle"))
    return handles


# ============================================================
# Feature 8: Nuovo video competitor via RSS YouTube (no quota)
# ============================================================


def fetch_channel_rss(channel_id: str) -> list:
    """Recupera gli ultimi video di un canale tramite RSS (0 quota API)."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        feed = feedparser.parse(url)
        videos = []
        for entry in feed.entries[:5]:
            video_id = entry.get("yt_videoid") or entry.get("id", "").split(":")[-1]
            if not video_id:
                continue
            published_parsed = entry.get("published_parsed")
            published_dt = (
                datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if published_parsed
                else None
            )
            videos.append(
                {
                    "id": video_id,
                    "title": entry.get("title", "Senza titolo"),
                    "link": entry.get(
                        "link", f"https://www.youtube.com/watch?v={video_id}"
                    ),
                    "channel_name": feed.feed.get("title", ""),
                    "published_dt": published_dt,
                }
            )
        return videos
    except Exception as e:
        print(f"[COMPETITOR] Errore RSS {channel_id}: {e}")
        return []


def send_new_video_alert(video: dict, handle: str):
    text = (
        f"🆕 <b>NUOVO VIDEO COMPETITOR</b>\n\n"
        f"📺 <b>Canale:</b> @{handle}"
        + (f" — {video['channel_name']}" if video["channel_name"] else "")
        + f"\n🎬 <b>Titolo:</b> {video['title']}\n"
        f"🔗 <b>Link:</b> {video['link']}\n"
        f"🆔 <b>Video ID:</b> <code>{video['id']}</code>\n\n"
        f"💡 <i>Scarica la trascrizione con /transcript {video['id']}</i>"
    )
    send_message(text)


def run_new_video_monitor(config: dict):
    """Controlla nuovi video dei competitor via RSS. Eseguito ogni 30 min."""
    print(f"\n[COMPETITOR] Controllo nuovi video — {datetime.now().strftime('%H:%M')}")

    monitor_cfg = config.get("competitor_monitor", {})
    max_age_hours = monitor_cfg.get("new_video_max_age_hours", 48)
    handles = get_all_handles(config)
    new_found = 0

    for handle in handles:
        channel_id = resolve_and_cache(handle)
        if not channel_id:
            continue

        videos = fetch_channel_rss(channel_id)
        for video in videos:
            video_id = video["id"]

            # Salta video già notificati
            if is_channel_video_sent(channel_id, video_id):
                continue

            # Salta video troppo vecchi (evita spam al primo avvio)
            if video["published_dt"]:
                age_hours = (
                    datetime.now(timezone.utc) - video["published_dt"]
                ).total_seconds() / 3600
                if age_hours > max_age_hours:
                    mark_channel_video_sent(channel_id, video_id)
                    continue

            print(f"[COMPETITOR] Nuovo video: @{handle} — {video['title'][:60]}")
            send_new_video_alert(video, handle)
            mark_channel_video_sent(channel_id, video_id)
            matched_kws = extract_title_keywords(
                video["title"], config.get("keywords", [])
            )
            log_competitor_video(
                video_id=video_id,
                title=video["title"],
                channel_name=handle,
                channel_id=channel_id,
                matched_keyword=matched_kws[0] if matched_kws else None,
                published_at=video.get("published_at"),
            )
            new_found += 1

            # Estrai keyword dal titolo e salvale nel DB (fonte: competitor_title)
            config_keywords = config.get("keywords", [])
            matched = extract_title_keywords(video["title"], config_keywords)
            for kw in matched:
                save_keyword_count(kw, "competitor_title", 1)
            if matched:
                print(f"[COMPETITOR] Keyword nel titolo: {matched}")

        time.sleep(0.3)

    print(f"[COMPETITOR] Controllo completato. Nuovi video trovati: {new_found}")


# ============================================================
# Feature 10: Crescita iscritti competitor
# ============================================================


def send_subscriber_growth_alert(
    handle: str, channel_name: str, now: int, before: int, growth: float
):
    diff = now - before
    text = (
        f"📈 <b>CRESCITA ISCRITTI COMPETITOR</b>\n\n"
        f"📺 <b>Canale:</b> @{handle} — {channel_name}\n"
        f"👥 <b>Iscritti ora:</b> {now:,}\n"
        f"📊 <b>Crescita 7 giorni:</b> +{diff:,} (+{growth * 100:.1f}%)\n\n"
        f"🔗 https://www.youtube.com/@{handle}\n\n"
        f"<i>Questo canale sta crescendo rapidamente. Studia i loro ultimi video.</i>"
    )
    send_message(text)


def run_subscriber_growth_monitor(config: dict):
    """Controlla crescita iscritti settimanale dei competitor. Eseguito 1x al giorno."""
    print("\n[COMPETITOR] Controllo crescita iscritti")

    monitor_cfg = config.get("competitor_monitor", {})
    growth_threshold = monitor_cfg.get("subscriber_growth_threshold", 0.10)
    handles = get_all_handles(config)

    saved_count = 0
    alert_count = 0
    first_run_channels = 0

    for handle in handles:
        channel_id = resolve_and_cache(handle)
        if not channel_id:
            continue

        try:
            data = yt_get("channels", {"part": "snippet,statistics", "id": channel_id})
            items = data.get("items", [])
            if not items:
                continue

            stats = items[0]["statistics"]
            snippet = items[0]["snippet"]
            subscribers = int(stats.get("subscriberCount", 0))
            channel_name = snippet.get("title", handle)

            save_subscriber_count(channel_id, channel_name, subscribers)
            saved_count += 1

            history = get_subscriber_history(channel_id, days=8)
            if len(history) < 2:
                first_run_channels += 1
                continue

            oldest = history[-1]["subscribers"]
            if oldest == 0:
                continue

            growth = (subscribers - oldest) / oldest

            if growth >= growth_threshold:
                alert_id = f"sub_growth_{channel_id}"
                if was_alert_sent_recently(alert_id, "subscriber_growth", hours=168):
                    continue
                print(f"[COMPETITOR] Crescita iscritti: @{handle} +{growth * 100:.1f}%")
                send_subscriber_growth_alert(
                    handle, channel_name, subscribers, oldest, growth
                )
                mark_alert_sent(alert_id, "subscriber_growth")
                alert_count += 1

        except Exception as e:
            print(f"[COMPETITOR] Errore iscritti @{handle}: {e}")

        time.sleep(0.5)

    if first_run_channels > 0:
        send_message(
            f"📊 <b>Iscritti competitor — baseline salvata</b>\n\n"
            f"✅ Dati salvati per <b>{saved_count}</b> canali.\n"
            f"⏳ <b>{first_run_channels}</b> canali in attesa di storico (7 giorni).\n\n"
            f"<i>Gli alert di crescita partiranno automaticamente dopo 7 giorni di dati accumulati.</i>"
        )
    elif alert_count == 0:
        print("[COMPETITOR] Nessuna crescita significativa rilevata.")

    print(
        f"[COMPETITOR] Controllo iscritti completato. Salvati: {saved_count}, Alert: {alert_count}"
    )
