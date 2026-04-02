"""
YTSPERBOT - Apify Social Scraper
Feature: Outperformer detection per TikTok e Instagram

Actor usati:
  TikTok:    clockworks/free-tiktok-scraper   | $2.00/1k risultati | Apify-maintained
             URL: https://apify.com/clockworks/free-tiktok-scraper
             Rating: 4.6 ⭐ (57 rec.) | 42K utenti | 2.4K mensili
             Input:  { "hashtags": [str], "resultsPerPage": int }
                  o  { "profiles": [str], "resultsPerPage": int }
             Output: { "authorMeta": { "name": str, "fans": int, ... },
                        "text": str, "playCount": int, "diggCount": int,
                        "shareCount": int, "createTime": int,
                        "webVideoUrl": str, "id": str }

  Instagram: apify/instagram-scraper          | $1.50/1k risultati | Apify-maintained
             URL: https://apify.com/apify/instagram-scraper
             Rating: 4.7 ⭐ (344 rec.) | 213K utenti | 15K mensili
             Input:  { "directUrls": [str], "resultsType": "posts"|"comments"|"details"|"mentions",
                        "resultsLimit": int }
             Output (posts): { "videoViewCount": int, "likesCount": int,
                                "caption"/"text": str, "url": str,
                                "timestamp": str, "id": str,
                                "ownerFullName": str,
                                "followersCount"/"ownerFollowersCount": int,
                                "owner": { "followersCount": int } }
             Output (details/profiles): stessi campi + followersCount top-level

Logica:
  - Scopre nuovi profili via hashtag (max N per piattaforma al giorno)
  - Filtra per follower (1k–80k) — i profili pinned bypassano il filtro
  - Per ogni profilo analizza i video/post recenti e calcola la media views
  - Segnala i contenuti con views >= soglia × media (outperformer)
  - Profili già in DB vengono ricontrollati ogni 30 giorni (nuovi video)
  - Profili pinned (/watch) vengono analizzati ad ogni run, senza filtro follower

Richiede APIFY_API_KEY nel .env.
"""
from __future__ import annotations

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
    save_outperformer_video,
    list_pinned_profiles,
)
from modules.telegram_bot import send_social_outperformer_alert

APIFY_ENABLED = bool(os.getenv("APIFY_API_KEY"))
APIFY_BASE = "https://api.apify.com/v2"

TIKTOK_ACTOR = "clockworks~free-tiktok-scraper"
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


def discover_tiktok_profiles(
    hashtags: list, max_new: int, cfg: dict, max_results: int = 5
) -> list:
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
        items = run_actor(
            TIKTOK_ACTOR,
            {
                "hashtags": [hashtag],
                "resultsPerPage": max_results,
            },
        )
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
            found.append(
                {
                    "username": username,
                    "display_name": display_name,
                    "followers": followers,
                }
            )
        time.sleep(1)

    return found


def discover_instagram_profiles(
    hashtags: list, max_new: int, max_results: int = 5
) -> list:
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
        items = run_actor(
            INSTAGRAM_ACTOR,
            {
                "directUrls": [f"https://www.instagram.com/explore/tags/{hashtag}/"],
                "resultsType": "posts",
                "resultsLimit": max_results,
            },
        )
        for item in items:
            if len(found) >= max_new:
                break
            username = item.get("ownerUsername", "").strip()
            if not username or username in seen:
                continue
            if apify_profile_exists("instagram", username):
                continue

            # Prova a estrarre followers già dall'item di discovery
            fc, dn = _parse_followers_from_item(item)
            display_name = dn or item.get("ownerFullName") or username

            seen.add(username)
            found.append(
                {"username": username, "display_name": display_name, "followers": fc}
            )
        time.sleep(1)

    return found


# ============================================================
# FASE 2 — Analisi profili: calcolo media e outperformer
# ============================================================


def analyze_tiktok_profile(username: str, cfg: dict, is_pinned: bool = False) -> tuple:
    """
    Recupera i video recenti di un profilo TikTok.
    is_pinned=True bypassa il filtro follower.
    Restituisce (profile_data, [outperformer_videos]) oppure (None, []).
    """
    results_per_profile = cfg.get("results_per_profile", 10)
    items = run_actor(
        TIKTOK_ACTOR,
        {
            "profiles": [username],
            "resultsPerPage": results_per_profile,
        },
    )
    if not items:
        return None, []

    author = items[0].get("authorMeta", {})
    followers = author.get("fans", 0)
    display_name = author.get("nickName", username)

    if not is_pinned:
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
    threshold_followers = cfg.get("multiplier_threshold_followers", 0)
    min_views = cfg.get("min_views_tiktok", 0)
    outperformers = []

    for item in recent:
        play_count = item.get("playCount", 0)
        if min_views > 0 and play_count < min_views:
            continue

        mult_avg = play_count / avg_views if avg_views > 0 else 0
        mult_fol = play_count / followers if followers > 0 else 0

        is_avg_out = mult_avg >= threshold
        is_fol_out = threshold_followers > 0 and mult_fol >= threshold_followers

        if not (is_avg_out or is_fol_out):
            continue

        video_id = str(item.get("id", ""))
        if not video_id:
            continue

        outperformers.append(
            {
                "id": video_id,
                "title": item.get("text", "")[:120] or "Nessuna didascalia",
                "views": play_count,
                "url": item.get("webVideoUrl", f"https://www.tiktok.com/@{username}"),
                "multiplier": mult_avg,
                "multiplier_followers": mult_fol,
                "is_avg_outperformer": is_avg_out,
                "is_followers_outperformer": is_fol_out,
            }
        )

    profile_data = {
        "username": username,
        "display_name": display_name,
        "followers": followers,
        "avg_views": avg_views,
        "is_pinned": is_pinned,
    }
    return profile_data, outperformers


def _parse_followers_from_item(item: dict) -> tuple[int, str]:
    """
    Prova tutti i pattern noti per estrarre follower count e display name
    da qualsiasi tipo di item restituito dall'Instagram scraper.
    """
    fc = (
        item.get("followersCount")
        or item.get("followers_count")
        or item.get("followers")
        or item.get("followedByCount")
        or item.get("followed_by_count")
        or (item.get("edge_followed_by") or {}).get("count")
        # campi owner annidati (presenti in alcuni formati post)
        or (item.get("owner") or {}).get("followersCount")
        or (item.get("owner") or {}).get("edge_followed_by", {}).get("count")
        or item.get("ownerFollowersCount")
        or 0
    )
    dn = (
        item.get("fullName")
        or item.get("full_name")
        or item.get("name")
        or item.get("ownerFullName")
        or (item.get("owner") or {}).get("fullName")
        or ""
    )
    return (int(fc) if fc else 0), dn


def _get_instagram_profile_info(username: str) -> tuple[int, str]:
    """
    Recupera follower count e display name di un profilo Instagram.
    Usa resultsType='details' (unico tipo che restituisce followersCount).
    Il fallback 'profiles' è stato rimosso: non è un valore valido per l'actor
    (i valori ammessi sono: 'posts', 'comments', 'details', 'mentions').
    """
    items = run_actor(
        INSTAGRAM_ACTOR,
        {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "details",
            "resultsLimit": 1,
        },
    )
    for item in items:
        fc, dn = _parse_followers_from_item(item)
        if fc:
            print(f"[APIFY-IG] @{username} — follower da details: {fc:,}")
            return fc, (dn or username)
        # Debug: logga i campi disponibili per aiutare la diagnostica futura
        follow_keys = [k for k in item.keys() if "follow" in k.lower()]
        all_keys = list(item.keys())[:20]
        print(
            f"[APIFY-IG] details — @{username} nessun follower. "
            f"Follow-fields: {follow_keys} | Keys: {all_keys}"
        )
    return 0, username


def analyze_instagram_profile(
    username: str, cfg: dict, is_pinned: bool = False
) -> tuple:
    """
    Recupera i post recenti di un profilo Instagram.
    is_pinned=True bypassa il filtro follower.
    Usa due chiamate: una per il profilo (follower count), una per i post.
    Restituisce (profile_data, [outperformer_posts]) oppure (None, []).
    """
    # --- Passo 1: recupera follower count ---
    followers, display_name = _get_instagram_profile_info(username)
    print(f"[APIFY-IG] @{username} — follower dopo profile call: {followers:,}")

    if not is_pinned:
        min_f, max_f = cfg["min_followers"], cfg["max_followers"]
        if followers > 0 and not (min_f <= followers <= max_f):
            print(f"[APIFY-IG] @{username} fuori range follower ({followers:,}) — skip")
            return None, []

    # --- Passo 2: recupera i post recenti ---
    results_per_profile = cfg.get("results_per_profile", 10)
    items = run_actor(
        INSTAGRAM_ACTOR,
        {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": results_per_profile,
        },
    )
    if not items:
        return None, []

    # Fallback: estrai follower count dai post items se la profile call ha fallito
    if followers == 0 and items:
        for post_item in items:
            fc_fallback, dn_fallback = _parse_followers_from_item(post_item)
            if fc_fallback > 0:
                followers = fc_fallback
                if dn_fallback:
                    display_name = dn_fallback
                print(f"[APIFY-IG] @{username} — follower da post item: {followers:,}")
                break
        if followers == 0:
            # Log finale per diagnostica: mostra le chiavi del primo post
            sample_keys = list(items[0].keys())[:25] if items else []
            print(f"[APIFY-IG] @{username} — follower ancora 0. Chiavi post: {sample_keys}")

    def get_video_views(post: dict) -> int:
        """Returns video view count only — photo posts return 0 and are excluded.
        Covers both classic videos (videoViewCount) and Reels (videoPlayCount)."""
        return post.get("videoViewCount") or post.get("videoPlayCount") or 0

    def get_engagement(post: dict) -> int:
        """Full engagement (video views or likes) — used only for avg baseline."""
        return get_video_views(post) or post.get("likesCount") or 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])
    recent_videos = []   # video posts only → outperformer candidates
    video_views_all = [] # video view counts (all dates) → video-only baseline
    all_eng = []         # fallback: all engagement (photo + video, all dates)

    for post in items:
        vv = get_video_views(post)
        eng = get_engagement(post)
        if not eng:
            continue
        all_eng.append(eng)
        if vv > 0:
            video_views_all.append(vv)
        ts = post.get("timestamp", "")
        if ts:
            try:
                pub = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if pub < cutoff:
                    continue  # too old for detection
            except Exception:
                pass
        if vv > 0:
            recent_videos.append(post)  # only real videos as candidates

    if not all_eng:
        return None, []

    # Use video-only baseline when available so that photo likes don't inflate
    # the average and make video outperformer detection impossible.
    if video_views_all:
        avg_views = sum(video_views_all) / len(video_views_all)
    else:
        avg_views = sum(all_eng) / len(all_eng)
    threshold = cfg["multiplier_threshold"]
    threshold_followers = cfg.get("multiplier_threshold_followers_ig", 0)
    min_views = cfg.get("min_views_instagram", 0)
    outperformers = []

    for post in recent_videos:
        views = get_video_views(post)
        if min_views > 0 and views < min_views:
            continue

        mult_avg = views / avg_views if avg_views > 0 else 0
        mult_fol = views / followers if followers > 0 else 0

        is_avg_out = mult_avg >= threshold
        is_fol_out = (
            threshold_followers > 0
            and followers > 0
            and mult_fol >= threshold_followers
        )

        if not (is_avg_out or is_fol_out):
            continue

        video_id = str(post.get("id", ""))
        if not video_id:
            continue

        caption = post.get("caption", "") or post.get("text", "") or ""
        outperformers.append(
            {
                "id": video_id,
                "title": caption[:120] or "Nessuna didascalia",
                "views": views,
                "url": post.get("url", f"https://www.instagram.com/{username}/"),
                "multiplier": mult_avg,
                "multiplier_followers": mult_fol,
                "is_avg_outperformer": is_avg_out,
                "is_followers_outperformer": is_fol_out,
            }
        )

    profile_data = {
        "username": username,
        "display_name": display_name,
        "followers": followers,
        "avg_views": avg_views,
        "is_pinned": is_pinned,
    }
    return profile_data, outperformers


# ============================================================
# Entry point principale
# ============================================================


def _analyze_and_alert(
    platform: str, username: str, is_pinned: bool, analyze_fn, cfg: dict
) -> int:
    """
    Analizza un singolo profilo e invia alert per gli outperformer trovati.
    Restituisce il numero di alert inviati.
    """
    print(f"[APIFY] Analisi @{username} ({platform}{'  📌' if is_pinned else ''})")
    profile_data, outperformers = analyze_fn(username, cfg, is_pinned)

    if profile_data is None:
        update_apify_profile_analyzed(platform, username, 0)
        return 0

    update_apify_profile_analyzed(
        platform, username,
        profile_data["avg_views"],
        profile_data.get("followers"),
    )

    alerts = 0
    for video in outperformers:
        already_sent = is_apify_video_sent(platform, video["id"])

        # Salva sempre per la UI (INSERT OR IGNORE — non duplica)
        save_outperformer_video(
            platform,
            video["id"],
            username,
            video["title"],
            video["views"],
            video.get("url", ""),
            video["multiplier"],
        )

        # Alert Telegram solo se non già inviato
        if not already_sent:
            print(
                f"[APIFY] OUTPERFORMER @{username}: {video['title'][:50]} ({video['multiplier']:.1f}x)"
            )
            send_social_outperformer_alert(platform, profile_data, video, cfg)
            mark_apify_video_sent(platform, video["id"])
            alerts += 1

    return alerts


def run_apify_scraper(config: dict):
    if not APIFY_ENABLED:
        print("[APIFY] APIFY_API_KEY non configurata — modulo disabilitato.")
        return

    print(
        f"\n[APIFY] Avvio social scraper — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    cfg = config.get("apify_scraper", {})
    new_per_platform = cfg.get("new_profiles_per_platform", 5)
    recheck_days = cfg.get("profile_recheck_days", 30)
    max_results = cfg.get("max_results_per_hashtag", 5)
    tiktok_hashtags = cfg.get("tiktok_hashtags", [])
    ig_hashtags = cfg.get("instagram_hashtags", [])

    total_alerts = 0

    for platform, hashtags, discover_fn, analyze_fn in [
        ("tiktok", tiktok_hashtags, discover_tiktok_profiles, analyze_tiktok_profile),
        (
            "instagram",
            ig_hashtags,
            discover_instagram_profiles,
            analyze_instagram_profile,
        ),
    ]:
        print(f"\n[APIFY] — {platform.upper()} —")

        # ---- Profili pinned: analizzati sempre, senza filtro follower ----
        pinned = list_pinned_profiles(platform)
        if pinned:
            print(f"[APIFY] Profili watchlist: {len(pinned)}")
            for p in pinned:
                total_alerts += _analyze_and_alert(
                    platform, p["username"], True, analyze_fn, cfg
                )
                time.sleep(2)

        # ---- Fase 1: discovery nuovi profili via hashtag ----
        already_today = count_apify_profiles_added_today(platform)
        remaining_slots = max(0, new_per_platform - already_today)

        if remaining_slots > 0:
            if platform == "tiktok":
                new_profiles = discover_fn(hashtags, remaining_slots, cfg, max_results)
            else:
                new_profiles = discover_fn(hashtags, remaining_slots, max_results)

            for p in new_profiles:
                upsert_apify_profile(
                    platform, p["username"], p["display_name"], p["followers"]
                )
                print(
                    f"[APIFY] Nuovo profilo: @{p['username']} ({p['followers']:,} follower)"
                )
        else:
            print(
                f"[APIFY] Limite giornaliero già raggiunto ({new_per_platform} profili)."
            )

        # ---- Fase 2: analisi profili scoperti (nuovi + cache scaduta) ----
        to_analyze = get_apify_profiles_to_analyze(
            platform, recheck_days, limit=new_per_platform + 10
        )
        print(f"[APIFY] Profili da analizzare: {len(to_analyze)}")

        for profile_row in to_analyze:
            total_alerts += _analyze_and_alert(
                platform, profile_row["username"], False, analyze_fn, cfg
            )
            time.sleep(2)

    print(f"\n[APIFY] Completato. Alert inviati: {total_alerts}")
