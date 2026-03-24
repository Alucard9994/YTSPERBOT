"""
YTSPERBOT - Apify Social Scraper
Feature: Outperformer detection per TikTok e Instagram

Logica identica allo YouTube Scraper:
  - Scopre nuovi profili via hashtag (max N per piattaforma al giorno)
  - Filtra: 1k–80k follower
  - Per ogni profilo analizza i video recenti e calcola la media views
  - Segnala i video con views >= soglia × media (outperformer)
  - Profili già in DB vengono ricontrollati ogni 30 giorni (nuovi video)

Richiede APIFY_API_KEY nel .env.
"""

import os
import time
import requests
from datetime import datetime, timezone, timedelta

from modules.database import (
    upsert_apify_profile,
    apify_profile_exists,
    count_apify_profiles_added_today,
    get_apify_profiles_to_analyze,
    update_apify_profile_analyzed,
    is_apify_video_sent,
    mark_apify_video_sent,
)
from modules.telegram_bot import send_social_outperformer_alert

APIFY_ENABLED = bool(os.getenv("APIFY_API_KEY"))
APIFY_BASE = "https://api.apify.com/v2"

TIKTOK_ACTOR  = "clockworks~free-tiktok-scraper"
INSTAGRAM_ACTOR = "apify~instagram-scraper"


# ============================================================
# Helper: chiamata Apify sincrona
# ============================================================

def run_actor(actor_id: str, input_data: dict, timeout: int = 120) -> list:
    """Esegue un actor Apify in modo sincrono e restituisce gli items."""
    api_key = os.getenv("APIFY_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = requests.post(
            f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items",
            params={"token": api_key, "timeout": timeout},
            json=input_data,
            timeout=timeout + 30,
        )
        if resp.status_code in (200, 201):
            return resp.json() if isinstance(resp.json(), list) else []
        print(f"[APIFY] Errore HTTP {resp.status_code} — {actor_id}: {resp.text[:200]}")
    except Exception as e:
        print(f"[APIFY] Eccezione {actor_id}: {e}")
    return []


# ============================================================
# FASE 1 — Discovery nuovi profili via hashtag
# ============================================================

def discover_tiktok_profiles(hashtags: list, max_new: int, cfg: dict, max_results: int = 5) -> list:
    """
    Cerca profili TikTok su hashtag di nicchia.
    Filtra subito per follower count (disponibile nei risultati hashtag).
    Restituisce lista di profili nuovi da salvare in DB.
    """
    min_f = cfg["min_followers"]
    max_f = cfg["max_followers"]
    found = []
    seen = set()

    for hashtag in hashtags:
        if len(found) >= max_new:
            break
        print(f"[APIFY-TT] Discovery hashtag #{hashtag}")
        items = run_actor(TIKTOK_ACTOR, {
            "hashtags": [hashtag],
            "resultsPerPage": max_results,
        })
        for item in items:
            if len(found) >= max_new:
                break
            author = item.get("authorMeta", {})
            username = author.get("name", "").strip()
            followers = author.get("fans", 0)
            display_name = author.get("nickName", username)

            if not username or username in seen:
                continue
            if not (min_f <= followers <= max_f):
                continue
            if apify_profile_exists("tiktok", username):
                continue

            seen.add(username)
            found.append({
                "username": username,
                "display_name": display_name,
                "followers": followers,
            })
        time.sleep(1)

    return found


def discover_instagram_profiles(hashtags: list, max_new: int, max_results: int = 5) -> list:
    """
    Cerca profili Instagram su hashtag di nicchia.
    Raccoglie solo username (il follower count viene verificato in fase 2).
    """
    found = []
    seen = set()

    for hashtag in hashtags:
        if len(found) >= max_new:
            break
        print(f"[APIFY-IG] Discovery hashtag #{hashtag}")
        items = run_actor(INSTAGRAM_ACTOR, {
            "directUrls": [f"https://www.instagram.com/explore/tags/{hashtag}/"],
            "resultsType": "posts",
            "resultsLimit": max_results,
        })
        for item in items:
            if len(found) >= max_new:
                break
            username = item.get("ownerUsername", "").strip()
            if not username or username in seen:
                continue
            if apify_profile_exists("instagram", username):
                continue

            seen.add(username)
            found.append({"username": username, "display_name": username, "followers": 0})
        time.sleep(1)

    return found


# ============================================================
# FASE 2 — Analisi profili: calcolo media e outperformer
# ============================================================

def analyze_tiktok_profile(username: str, cfg: dict) -> tuple:
    """
    Recupera i video recenti di un profilo TikTok.
    Restituisce (profile_data, [outperformer_videos]) oppure (None, []).
    """
    items = run_actor(TIKTOK_ACTOR, {
        "profiles": [username],
        "resultsPerPage": 30,
    })
    if not items:
        return None, []

    author = items[0].get("authorMeta", {})
    followers = author.get("fans", 0)
    display_name = author.get("nickName", username)

    min_f, max_f = cfg["min_followers"], cfg["max_followers"]
    if followers > 0 and not (min_f <= followers <= max_f):
        return None, []

    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])
    views_list = []
    recent = []

    for item in items:
        create_time = item.get("createTime", 0)
        play_count = item.get("playCount", 0)
        if not play_count:
            continue
        if create_time:
            pub = datetime.fromtimestamp(create_time, tz=timezone.utc)
            if pub < cutoff:
                continue
            recent.append(item)
        views_list.append(play_count)

    if not views_list:
        return None, []

    avg_views = sum(views_list) / len(views_list)
    threshold = cfg["multiplier_threshold"]
    outperformers = []

    for item in recent:
        play_count = item.get("playCount", 0)
        multiplier = play_count / avg_views if avg_views > 0 else 0
        if multiplier < threshold:
            continue

        video_id = str(item.get("id", ""))
        if not video_id or is_apify_video_sent("tiktok", video_id):
            continue

        outperformers.append({
            "id": video_id,
            "title": item.get("text", "")[:120] or "Nessuna didascalia",
            "views": play_count,
            "url": item.get("webVideoUrl", f"https://www.tiktok.com/@{username}"),
            "multiplier": multiplier,
        })

    profile_data = {
        "username": username,
        "display_name": display_name,
        "followers": followers,
        "avg_views": avg_views,
    }
    return profile_data, outperformers


def analyze_instagram_profile(username: str, cfg: dict) -> tuple:
    """
    Recupera i post recenti di un profilo Instagram.
    Restituisce (profile_data, [outperformer_posts]) oppure (None, []).
    """
    items = run_actor(INSTAGRAM_ACTOR, {
        "directUrls": [f"https://www.instagram.com/{username}/"],
        "resultsType": "posts",
        "resultsLimit": 30,
    })
    if not items:
        return None, []

    # Cerca il follower count: può essere nel primo item (profilo) o nei metadati dei post
    followers = 0
    display_name = username
    posts = []

    for item in items:
        if item.get("type") == "user":
            followers = item.get("followersCount", 0)
            display_name = item.get("fullName", username) or username
        else:
            # Prova a estrarre follower count dai metadati owner del post
            if followers == 0:
                owner_info = item.get("ownerInfo", {}) or {}
                followers = owner_info.get("followersCount", 0)
            posts.append(item)

    min_f, max_f = cfg["min_followers"], cfg["max_followers"]
    if followers > 0 and not (min_f <= followers <= max_f):
        return None, []

    def get_engagement(post: dict) -> int:
        return post.get("videoViewCount") or post.get("likesCount") or 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])
    recent = []
    all_eng = []

    for post in posts:
        eng = get_engagement(post)
        if not eng:
            continue
        ts = post.get("timestamp", "")
        if ts:
            try:
                pub = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if pub < cutoff:
                    continue
            except Exception:
                pass
        recent.append(post)
        all_eng.append(eng)

    if not all_eng:
        return None, []

    avg_views = sum(all_eng) / len(all_eng)
    threshold = cfg["multiplier_threshold"]
    outperformers = []

    for post in recent:
        eng = get_engagement(post)
        multiplier = eng / avg_views if avg_views > 0 else 0
        if multiplier < threshold:
            continue

        video_id = str(post.get("id", ""))
        if not video_id or is_apify_video_sent("instagram", video_id):
            continue

        caption = post.get("caption", "") or post.get("text", "") or ""
        outperformers.append({
            "id": video_id,
            "title": caption[:120] or "Nessuna didascalia",
            "views": eng,
            "url": post.get("url", f"https://www.instagram.com/{username}/"),
            "multiplier": multiplier,
        })

    profile_data = {
        "username": username,
        "display_name": display_name,
        "followers": followers,
        "avg_views": avg_views,
    }
    return profile_data, outperformers


# ============================================================
# Entry point principale
# ============================================================

def run_apify_scraper(config: dict):
    if not APIFY_ENABLED:
        print("[APIFY] APIFY_API_KEY non configurata — modulo disabilitato.")
        return

    print(f"\n[APIFY] Avvio social scraper — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    cfg = config.get("apify_scraper", {})
    new_per_platform = cfg.get("new_profiles_per_platform", 5)
    recheck_days     = cfg.get("profile_recheck_days", 30)
    max_results      = cfg.get("max_results_per_hashtag", 5)
    tiktok_hashtags  = cfg.get("tiktok_hashtags", [])
    ig_hashtags      = cfg.get("instagram_hashtags", [])

    total_alerts = 0

    for platform, hashtags, discover_fn, analyze_fn in [
        ("tiktok",    tiktok_hashtags, discover_tiktok_profiles,    analyze_tiktok_profile),
        ("instagram", ig_hashtags,     discover_instagram_profiles,  analyze_instagram_profile),
    ]:
        print(f"\n[APIFY] — {platform.upper()} —")

        # ---- Fase 1: discovery nuovi profili ----
        already_today = count_apify_profiles_added_today(platform)
        remaining_slots = max(0, new_per_platform - already_today)

        if remaining_slots > 0:
            if platform == "tiktok":
                new_profiles = discover_fn(hashtags, remaining_slots, cfg, max_results)
            else:
                new_profiles = discover_fn(hashtags, remaining_slots, max_results)

            for p in new_profiles:
                upsert_apify_profile(platform, p["username"], p["display_name"], p["followers"])
                print(f"[APIFY] Nuovo profilo salvato: @{p['username']} ({p['followers']:,} follower)")
        else:
            print(f"[APIFY] Limite giornaliero già raggiunto ({new_per_platform} profili).")

        # ---- Fase 2: analisi profili (nuovi + profili con cache scaduta) ----
        to_analyze = get_apify_profiles_to_analyze(platform, recheck_days, limit=new_per_platform + 10)
        print(f"[APIFY] Profili da analizzare: {len(to_analyze)}")

        for profile_row in to_analyze:
            username = profile_row["username"]
            print(f"[APIFY] Analisi @{username} ({platform})")

            if platform == "tiktok":
                profile_data, outperformers = analyze_fn(username, cfg)
            else:
                profile_data, outperformers = analyze_fn(username, cfg)

            if profile_data is None:
                update_apify_profile_analyzed(platform, username, 0)
                time.sleep(1)
                continue

            update_apify_profile_analyzed(platform, username, profile_data["avg_views"])

            for video in outperformers:
                print(f"[APIFY] OUTPERFORMER @{username}: {video['title'][:50]} ({video['multiplier']:.1f}x)")
                send_social_outperformer_alert(platform, profile_data, video, cfg)
                mark_apify_video_sent(platform, video["id"])
                total_alerts += 1

            time.sleep(2)

    print(f"\n[APIFY] Completato. Alert inviati: {total_alerts}")
