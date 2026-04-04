"""
YTSPERBOT - Discovery Advisor
Suggerisce nuovi hashtag, subreddit e keyword scovando co-occorrenze
nei dati già scrappati (apify_outperformer_videos, reddit_posts, twitter_tweets).

Fase 2 (futura): suggerimenti AI via Anthropic API — vedi memory/project_discovery_ai_idea.md
"""
from __future__ import annotations

import re
from collections import Counter
from modules.database import (
    get_connection,
    config_list_get,
    save_discovery_suggestion,
)
from modules.telegram_bot import send_message

# Mapping: tipo suggestion → list_key in config_lists
TYPE_TO_LIST_KEY: dict[str, str] = {
    "tiktok_hashtag": "tiktok_hashtags",
    "instagram_hashtag": "instagram_hashtags",
    "subreddit": "subreddits",
    "keyword": "keywords",
}

# Stopwords da escludere dai candidati keyword
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "this", "that", "are", "was",
    "be", "as", "you", "he", "she", "we", "they", "my", "your", "his",
    "her", "our", "its", "not", "no", "so", "do", "did", "have", "has",
    "will", "would", "can", "could", "may", "might", "shall", "should",
    "been", "being", "had", "here", "there", "when", "where", "what",
    "who", "how", "why", "which", "just", "like", "get", "got", "all",
    "out", "up", "now", "new", "one", "two", "im", "its", "dont", "ive",
    # Italian stopwords
    "il", "la", "le", "lo", "gli", "un", "una", "di", "del", "della",
    "dei", "delle", "da", "dal", "dalla", "dai", "delle", "e", "ed",
    "o", "ma", "se", "che", "con", "per", "tra", "fra", "su", "nel",
    "nella", "nei", "nelle", "al", "alla", "ai", "agli", "alle", "ho",
    "ha", "ci", "si", "ne", "mi", "ti", "ce", "vi", "io", "tu",
}

# Minimo occorrenze per salvare il suggerimento
_MIN_SCORE = 2


def _get_existing_set(list_key: str) -> set[str]:
    """Restituisce gli elementi attuali di una lista (lowercase, senza #)."""
    items = config_list_get(list_key)
    return {
        item["value"].lower().lstrip("#").strip()
        for item in items
        if item.get("value")
    }


def _extract_hashtags_from_captions(platform: str) -> Counter:
    """Estrae hashtag da titoli/caption degli outperformer video."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT title FROM apify_outperformer_videos WHERE platform = ? AND title IS NOT NULL",
        (platform,),
    ).fetchall()
    conn.close()
    counter: Counter = Counter()
    for row in rows:
        tags = re.findall(r"#(\w+)", row["title"].lower())
        for tag in tags:
            if len(tag) >= 3:
                counter[tag] += 1
    return counter


def _extract_subreddits_from_posts() -> Counter:
    """Estrae menzioni r/subreddit dai titoli dei post Reddit."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT title FROM reddit_posts WHERE title IS NOT NULL"
    ).fetchall()
    conn.close()
    counter: Counter = Counter()
    for row in rows:
        subs = re.findall(r"r/([A-Za-z]\w{1,24})", row["title"] or "")
        for s in subs:
            counter[s] += 1
    return counter


def _extract_hashtags_from_tweets() -> Counter:
    """Estrae hashtag dai tweet come candidati keyword."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT text FROM twitter_tweets WHERE text IS NOT NULL"
    ).fetchall()
    conn.close()
    counter: Counter = Counter()
    for row in rows:
        tags = re.findall(r"#(\w+)", row["text"].lower())
        for tag in tags:
            if len(tag) >= 4 and tag not in _STOPWORDS:
                counter[tag] += 1
    return counter


def _build_and_save_suggestions() -> dict[str, list[dict]]:
    """
    Costruisce i suggerimenti da tutte le fonti e li persiste nel DB.
    Restituisce i nuovi suggerimenti trovati raggruppati per tipo.
    """
    new_suggestions: dict[str, list[dict]] = {
        "tiktok_hashtag": [],
        "instagram_hashtag": [],
        "subreddit": [],
        "keyword": [],
    }

    # TikTok hashtag — da caption outperformer
    existing_tiktok = _get_existing_set("tiktok_hashtags")
    tiktok_counts = _extract_hashtags_from_captions("tiktok")
    for tag, score in tiktok_counts.most_common():
        if score < _MIN_SCORE:
            break
        if tag not in existing_tiktok:
            save_discovery_suggestion("tiktok_hashtag", tag, "tiktok_caption", score)
            new_suggestions["tiktok_hashtag"].append({"value": tag, "score": score})

    # Instagram hashtag — da caption outperformer
    existing_ig = _get_existing_set("instagram_hashtags")
    ig_counts = _extract_hashtags_from_captions("instagram")
    for tag, score in ig_counts.most_common():
        if score < _MIN_SCORE:
            break
        if tag not in existing_ig:
            save_discovery_suggestion("instagram_hashtag", tag, "instagram_caption", score)
            new_suggestions["instagram_hashtag"].append({"value": tag, "score": score})

    # Subreddit — da menzioni r/xxx in reddit_posts
    existing_subs = _get_existing_set("subreddits")
    sub_counts = _extract_subreddits_from_posts()
    for sub, score in sub_counts.most_common():
        if score < _MIN_SCORE:
            break
        if sub.lower() not in existing_subs:
            save_discovery_suggestion("subreddit", sub, "reddit_post", score)
            new_suggestions["subreddit"].append({"value": sub, "score": score})

    # Keyword — da hashtag nei tweet
    existing_kw = _get_existing_set("keywords")
    kw_counts = _extract_hashtags_from_tweets()
    for kw, score in kw_counts.most_common():
        if score < _MIN_SCORE:
            break
        if kw not in existing_kw:
            save_discovery_suggestion("keyword", kw, "twitter_tweet", score)
            new_suggestions["keyword"].append({"value": kw, "score": score})

    return new_suggestions


def _send_telegram_discovery_digest(new_suggestions: dict[str, list[dict]]):
    """Invia il digest Telegram con i nuovi suggerimenti trovati."""
    total = sum(len(v) for v in new_suggestions.values())
    if total == 0:
        print("[DISCOVERY] Nessun nuovo suggerimento trovato.", flush=True)
        return

    lines = ["🔍 <b>DISCOVERY SETTIMANALE</b>\n"]
    lines.append(f"Trovati <b>{total}</b> nuovi candidati da approvare:\n")

    type_meta = [
        ("tiktok_hashtag",    "🎵 TikTok hashtag",    True),
        ("instagram_hashtag", "📸 Instagram hashtag",  True),
        ("subreddit",         "👽 Subreddit",          False),
        ("keyword",           "🔑 Keyword",            True),
    ]

    for stype, label, is_hashtag in type_meta:
        items = new_suggestions.get(stype, [])
        if not items:
            continue
        top = items[:8]
        lines.append(f"<b>{label} ({len(items)}):</b>")
        for item in top:
            prefix = "#" if is_hashtag else "r/" if stype == "subreddit" else ""
            lines.append(f"  • {prefix}{item['value']} ({item['score']}x)")
        if len(items) > 8:
            lines.append(f"  … e altri {len(items) - 8}")
        lines.append("")

    lines.append("💡 <i>Approva o rifiuta nella dashboard → sezione Discovery</i>")
    send_message("\n".join(lines))


def run_discovery_advisor(config: dict):
    """
    Entry point: estrae suggerimenti per co-occurrence dai dati scrappati,
    li salva nel DB e invia il digest Telegram.
    """
    cfg = config.get("discovery_advisor", {})
    if not cfg.get("enabled", True):
        print("[DISCOVERY] Discovery advisor disabilitato (config).", flush=True)
        return

    print("[DISCOVERY] Avvio discovery advisor (co-occurrence)…", flush=True)
    new_suggestions = _build_and_save_suggestions()
    total = sum(len(v) for v in new_suggestions.values())
    print(f"[DISCOVERY] Salvati {total} nuovi suggerimenti.", flush=True)
    _send_telegram_discovery_digest(new_suggestions)
