"""
YTSPERBOT - Config Manager
Gestisce la configurazione centralizzata via SQLite, con override da Telegram.

Logica:
  - All'avvio: config.yaml → DB (INSERT OR IGNORE, preserva override utente)
  - I job leggono sempre dal DB via get_config()
  - /set aggiorna il DB in tempo reale
  - Le liste (keywords, subreddits, ecc.) sono gestite in config_lists DB (seed da YAML al primo avvio)
"""

import os
import re
import yaml

from modules.database import config_load_defaults, config_get_all, config_set, config_get, config_lists_get_all

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")


# ============================================================
# Chiavi valide con metadati per validazione
# ============================================================
# restart=True → il valore viene salvato ma ha effetto solo al prossimo riavvio
# (usato per intervalli dello scheduler configurati al boot)

VALID_KEYS: dict[str, dict] = {
    # --- apify_scraper ---
    "apify_scraper.run_day": {
        "type": "str", "desc": "Giorno esecuzione Apify",
        "choices": ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"],
        "restart": True,
    },
    "apify_scraper.run_time": {
        "type": "str", "desc": "Orario esecuzione Apify (HH:MM)",
        "regex": r"^\d{2}:\d{2}$", "restart": True,
    },
    "apify_scraper.max_results_per_hashtag": {
        "type": "int", "min": 1, "max": 20,
        "desc": "Risultati per hashtag Apify ⚠️ incide sui costi",
    },
    "apify_scraper.new_profiles_per_platform": {
        "type": "int", "min": 1, "max": 20,
        "desc": "Nuovi profili per piattaforma per run",
    },
    "apify_scraper.profile_recheck_days": {
        "type": "int", "min": 1, "max": 90,
        "desc": "Giorni tra rianalisi profili Apify",
    },
    "apify_scraper.min_followers": {
        "type": "int", "min": 0,
        "desc": "Follower minimi profili social",
    },
    "apify_scraper.max_followers": {
        "type": "int", "min": 1000,
        "desc": "Follower massimi profili social",
    },
    "apify_scraper.multiplier_threshold": {
        "type": "float", "min": 1.0, "max": 20.0,
        "desc": "Soglia outperformer vs media views (TikTok/IG)",
    },
    "apify_scraper.multiplier_threshold_followers": {
        "type": "float", "min": 0.0, "max": 20.0,
        "desc": "Soglia outperformer vs follower TikTok",
    },
    "apify_scraper.multiplier_threshold_followers_ig": {
        "type": "float", "min": 0.0, "max": 20.0,
        "desc": "Soglia outperformer vs follower Instagram",
    },
    "apify_scraper.min_views_tiktok": {
        "type": "int", "min": 0,
        "desc": "Views minime assolute TikTok",
    },
    "apify_scraper.min_views_instagram": {
        "type": "int", "min": 0,
        "desc": "Views/engagement minimi Instagram",
    },
    "apify_scraper.lookback_days": {
        "type": "int", "min": 1, "max": 90,
        "desc": "Finestra analisi video Apify (giorni)",
    },
    # --- daily_brief ---
    "daily_brief.send_time": {
        "type": "str", "desc": "Orario brief giornaliero (HH:MM)",
        "regex": r"^\d{2}:\d{2}$", "restart": True,
    },
    # --- weekly_report ---
    "weekly_report.send_day": {
        "type": "str", "desc": "Giorno report settimanale",
        "choices": ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"],
        "restart": True,
    },
    "weekly_report.send_time": {
        "type": "str", "desc": "Orario report settimanale (HH:MM)",
        "regex": r"^\d{2}:\d{2}$", "restart": True,
    },
    # --- cross_signal ---
    "cross_signal.min_sources": {
        "type": "int", "min": 2, "max": 10,
        "desc": "Fonti minime per convergenza multi-piattaforma",
    },
    "cross_signal.lookback_hours": {
        "type": "int", "min": 1, "max": 48,
        "desc": "Finestra temporale convergenza (ore)",
    },
    "cross_signal.cooldown_hours": {
        "type": "int", "min": 1, "max": 72,
        "desc": "Cooldown convergenza stessa keyword (ore)",
    },
    "cross_signal.ai_titles": {
        "type": "bool",
        "desc": "Genera titoli AI su convergenza (richiede ANTHROPIC_API_KEY)",
    },
    # --- news_api ---
    "news_api.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza controllo News API (ore)", "restart": True,
    },
    "news_api.keywords_per_run": {
        "type": "int", "min": 1, "max": 50,
        "desc": "Keyword per run News API",
    },
    "news_api.lookback_hours": {
        "type": "int", "min": 1, "max": 168,
        "desc": "Finestra articoli News API (ore)",
    },
    "news_api.velocity_threshold": {
        "type": "int", "min": 10, "max": 1000,
        "desc": "Soglia velocity News API (%)",
    },
    # --- priority_score ---
    "priority_score.min_score": {
        "type": "int", "min": 1, "max": 10,
        "desc": "Score minimo per ricevere alert (1-10)",
    },
    # --- pinterest ---
    "pinterest.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza Pinterest (ore)", "restart": True,
    },
    "pinterest.velocity_threshold": {
        "type": "int", "min": 5, "max": 500,
        "desc": "Soglia velocity Pinterest (%)",
    },
    # --- competitor_monitor ---
    "competitor_monitor.new_video_max_age_hours": {
        "type": "int", "min": 1, "max": 168,
        "desc": "Età massima video competitor al primo avvio (ore)",
    },
    "competitor_monitor.subscriber_growth_threshold": {
        "type": "float", "min": 0.01, "max": 1.0,
        "desc": "Soglia crescita iscritti — es. 0.10 = 10%",
    },
    "competitor_monitor.subscriber_check_time": {
        "type": "str", "desc": "Orario controllo iscritti (HH:MM)",
        "regex": r"^\d{2}:\d{2}$", "restart": True,
    },
    # --- twitter ---
    "twitter.use_apify": {
        "type": "bool",
        "desc": "Usa Apify per Twitter/X invece del Bearer Token — true = Apify ($0.40/1k tweet) | false = own API",
    },
    "twitter.tweets_per_keyword": {
        "type": "int", "min": 5, "max": 50,
        "desc": "Tweet per keyword (solo con use_apify: true) — ⚠️ aumentare fa salire i costi",
    },
    "twitter.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza Twitter/X (ore) — consigliato 4h con own API, 12h con Apify per restare nel free tier",
        "restart": True,
    },
    # --- trend_detector ---
    "trend_detector.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza trend detector (ore)", "restart": True,
    },
    "trend_detector.velocity_threshold_longform": {
        "type": "int", "min": 10, "max": 2000,
        "desc": "Soglia velocity video lunghi (%)",
    },
    "trend_detector.velocity_threshold_shorts": {
        "type": "int", "min": 10, "max": 2000,
        "desc": "Soglia velocity Shorts (%)",
    },
    "trend_detector.lookback_hours_longform": {
        "type": "int", "min": 1, "max": 168,
        "desc": "Finestra lookback longform (ore)",
    },
    "trend_detector.lookback_hours_shorts": {
        "type": "int", "min": 1, "max": 72,
        "desc": "Finestra lookback Shorts (ore)",
    },
    "trend_detector.min_mentions_to_track": {
        "type": "int", "min": 1, "max": 20,
        "desc": "Menzioni minime per tracciare una keyword",
    },
    # --- scraper ---
    "scraper.max_followers": {
        "type": "int", "min": 1000,
        "desc": "Iscritti massimi canali YouTube",
    },
    "scraper.min_followers": {
        "type": "int", "min": 0,
        "desc": "Iscritti minimi canali YouTube",
    },
    "scraper.multiplier_threshold": {
        "type": "float", "min": 1.0, "max": 20.0,
        "desc": "Soglia outperformer vs media views YouTube",
    },
    "scraper.multiplier_threshold_followers": {
        "type": "float", "min": 0.0, "max": 20.0,
        "desc": "Soglia outperformer vs iscritti YouTube",
    },
    "scraper.min_views_absolute": {
        "type": "int", "min": 0,
        "desc": "Views minime assolute YouTube",
    },
    "scraper.lookback_days": {
        "type": "int", "min": 1, "max": 90,
        "desc": "Finestra scraper YouTube (giorni)",
    },
    "scraper.max_channels_per_run": {
        "type": "int", "min": 10, "max": 1000,
        "desc": "Canali max per run YouTube",
    },
    "scraper.run_time": {
        "type": "str", "desc": "Orario YouTube Scraper (HH:MM)",
        "regex": r"^\d{2}:\d{2}$", "restart": True,
    },
    # --- rising_queries ---
    "rising_queries.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza rising queries (ore)", "restart": True,
    },
    "rising_queries.keywords_per_run": {
        "type": "int", "min": 1, "max": 20,
        "desc": "Keyword per run rising queries",
    },
    "rising_queries.min_growth": {
        "type": "int", "min": 50, "max": 5000,
        "desc": "Crescita minima rising queries (%)",
    },
    # --- google_trends ---
    "google_trends.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza Google Trends (ore)", "restart": True,
    },
    "google_trends.velocity_threshold": {
        "type": "int", "min": 5, "max": 500,
        "desc": "Soglia velocity Google Trends (%)",
    },
    "google_trends.top_n_keywords": {
        "type": "int", "min": 1, "max": 50,
        "desc": "Keyword per run Google Trends",
    },
    # --- youtube_comments ---
    "youtube_comments.check_interval_hours": {
        "type": "int", "min": 1, "max": 24,
        "desc": "Frequenza YouTube Comments (ore)", "restart": True,
    },
    "youtube_comments.max_comments_per_video": {
        "type": "int", "min": 10, "max": 500,
        "desc": "Max commenti per video",
    },
    "youtube_comments.max_videos_per_channel": {
        "type": "int", "min": 1, "max": 10,
        "desc": "Ultimi N video per canale",
    },
    "youtube_comments.min_keyword_mentions": {
        "type": "int", "min": 1, "max": 10,
        "desc": "Menzioni minime per considerare una keyword",
    },
    "youtube_comments.velocity_threshold": {
        "type": "int", "min": 10, "max": 1000,
        "desc": "Soglia velocity Comments (%)",
    },
    "youtube_comments.lookback_hours": {
        "type": "int", "min": 1, "max": 168,
        "desc": "Finestra YouTube Comments (ore)",
    },
}


# ============================================================
# Metadati liste configurabili
# ============================================================

LIST_META: dict[str, dict] = {
    "keywords":           {"name": "Keywords",          "type": "simple",  "path": ["keywords"]},
    "subreddits":         {"name": "Subreddits",         "type": "simple",  "path": ["subreddits"]},
    "tiktok_hashtags":    {"name": "TikTok hashtag",     "type": "simple",  "path": ["apify_scraper", "tiktok_hashtags"]},
    "instagram_hashtags": {"name": "Instagram hashtag",  "type": "simple",  "path": ["apify_scraper", "instagram_hashtags"]},
    "yt_queries_it":      {"name": "YouTube IT",         "type": "simple",  "path": ["youtube_search_queries", "italian"]},
    "yt_queries_en":      {"name": "YouTube EN",         "type": "simple",  "path": ["youtube_search_queries", "english"]},
    "filter_words":       {"name": "Filter words",       "type": "simple",  "path": ["trending_rss", "extra_filter_words"]},
    "rss_english":        {"name": "RSS English",        "type": "feed",    "path": ["rss_feeds", "english"]},
    "rss_italian":        {"name": "RSS Italian",        "type": "feed",    "path": ["rss_feeds", "italian"]},
    "rss_podcasts":       {"name": "RSS Podcasts",       "type": "feed",    "path": ["rss_feeds", "podcasts"]},
    "rss_tiktok":         {"name": "RSS TikTok",         "type": "feed",    "path": ["rss_feeds", "tiktok"]},
    "rss_instagram":      {"name": "RSS Instagram",      "type": "feed",    "path": ["rss_feeds", "instagram"]},
    "rss_pinterest":      {"name": "RSS Pinterest",      "type": "feed",    "path": ["rss_feeds", "pinterest"]},
    "google_alerts":      {"name": "Google Alerts",      "type": "feed",    "path": ["google_alerts_rss"]},
    "channels_it":        {"name": "Canali IT",          "type": "channel", "path": ["competitor_channels", "italian"]},
    "channels_en":        {"name": "Canali EN",          "type": "channel", "path": ["competitor_channels", "english"]},
}


# ============================================================
# Helpers interni
# ============================================================

def _type_str(value) -> str:
    if isinstance(value, bool):  return "bool"
    if isinstance(value, int):   return "int"
    if isinstance(value, float): return "float"
    return "str"


def _value_to_str(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _coerce(value_str: str, type_str: str):
    """Converte una stringa nel tipo corretto."""
    if type_str == "int":   return int(value_str)
    if type_str == "float": return float(value_str)
    if type_str == "bool":  return value_str.lower() in ("true", "yes", "1")
    return value_str


def _flatten_scalars(d: dict, prefix: str = "") -> dict:
    """
    Appiattisce un dict annidato in dot-notation.
    Restituisce solo i valori scalari presenti in VALID_KEYS.
    """
    result = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_scalars(v, full_key))
        elif isinstance(v, (int, float, str, bool)) and full_key in VALID_KEYS:
            result[full_key] = v
    return result


def _set_nested(d: dict, keys: list, value):
    """Imposta un valore in un dict annidato percorrendo la lista di chiavi."""
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _get_nested(d: dict, path: list):
    """Naviga un dict annidato con lista di chiavi. Restituisce None se mancante."""
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
        if d is None:
            return None
    return d


# ============================================================
# API pubblica
# ============================================================

def init_config_from_yaml(config: dict):
    """
    Carica i parametri scalari del config.yaml nel DB (INSERT OR IGNORE).
    Da chiamare all'avvio dopo init_db().
    """
    flat = _flatten_scalars(config)
    flat_typed = {
        key: (_value_to_str(value), _type_str(value))
        for key, value in flat.items()
    }
    config_load_defaults(flat_typed)
    print(f"[CONFIG] {len(flat_typed)} parametri caricati nel DB da config.yaml", flush=True)
    _seed_config_lists(config)


def _seed_config_lists(yaml_config: dict):
    """Seed iniziale delle liste dal config.yaml (INSERT OR IGNORE, non sovrascrive modifiche utente)."""
    from modules.database import config_list_seed
    for list_key, meta in LIST_META.items():
        items = _get_nested(yaml_config, meta["path"])
        if not items:
            continue
        if meta["type"] == "channel":
            # competitor_channels: lista di {"handle": "..."}
            normalized = [item["handle"] if isinstance(item, dict) else str(item) for item in items]
            config_list_seed(list_key, normalized)
        else:
            config_list_seed(list_key, items)


def get_config() -> dict:
    """
    Restituisce il config completo:
    - Base: config.yaml
    - Override scalari: dal DB bot_config (via /set)
    - Override liste: dal DB config_lists (via /add, /rm)
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Override scalari
    rows = config_get_all()
    for row in rows:
        keys = row["key"].split(".")
        _set_nested(config, keys, _coerce(row["value"], row["type"]))

    # Override liste
    all_lists = config_lists_get_all()
    for list_key, meta in LIST_META.items():
        raw_items = all_lists.get(list_key)
        if not raw_items:
            continue
        if meta["type"] == "feed":
            converted = [{"name": i["label"] or "", "url": i["value"]} for i in raw_items]
        elif meta["type"] == "channel":
            converted = [{"handle": i["value"]} for i in raw_items]
        else:
            converted = [i["value"] for i in raw_items]
        _set_nested(config, meta["path"], converted)

    return config


def validate_and_set(key: str, raw_value: str) -> tuple[bool, str]:
    """
    Valida e salva un parametro di configurazione.
    Restituisce (ok: bool, messaggio: str) pronto per Telegram.
    """
    if key not in VALID_KEYS:
        # Suggerisci chiavi della stessa sezione se esiste
        section = key.split(".")[0] if "." in key else None
        known_sections = {k.split(".")[0] for k in VALID_KEYS}
        if section and section in known_sections:
            section_keys = sorted(k for k in VALID_KEYS if k.startswith(section + "."))
            return False, (
                f"❌ Chiave <code>{key}</code> non trovata.\n\n"
                f"Chiavi disponibili per <b>{section}</b>:\n"
                + "\n".join(f"• <code>{k}</code>" for k in section_keys)
            )
        return False, (
            f"❌ Chiave <code>{key}</code> non riconosciuta.\n\n"
            f"Usa /config per vedere tutte le chiavi disponibili."
        )

    meta = VALID_KEYS[key]
    type_str = meta["type"]

    # Conversione tipo
    try:
        if type_str == "int":
            value = int(raw_value)
        elif type_str == "float":
            value = float(raw_value)
        elif type_str == "bool":
            if raw_value.lower() not in ("true", "false", "yes", "no", "1", "0"):
                return False, (
                    f"❌ <code>{key}</code> è un booleano.\n"
                    f"Valori accettati: <code>true</code> / <code>false</code>"
                )
            value = raw_value.lower() in ("true", "yes", "1")
        else:
            value = raw_value
    except ValueError:
        return False, (
            f"❌ <code>{key}</code> richiede un valore di tipo <b>{type_str}</b>.\n"
            f"Hai fornito: <code>{raw_value}</code>"
        )

    # Validazione range
    if "min" in meta and isinstance(value, (int, float)) and value < meta["min"]:
        return False, (
            f"❌ <code>{key}</code>: valore minimo consentito è <b>{meta['min']}</b>.\n"
            f"Hai fornito: <code>{value}</code>"
        )
    if "max" in meta and isinstance(value, (int, float)) and value > meta["max"]:
        return False, (
            f"❌ <code>{key}</code>: valore massimo consentito è <b>{meta['max']}</b>.\n"
            f"Hai fornito: <code>{value}</code>"
        )

    # Validazione choices
    if "choices" in meta and str(value).lower() not in meta["choices"]:
        return False, (
            f"❌ <code>{key}</code>: valore non valido.\n"
            f"Valori accettati: {', '.join(f'<code>{c}</code>' for c in meta['choices'])}"
        )

    # Validazione regex
    if "regex" in meta and not re.match(meta["regex"], str(value)):
        return False, (
            f"❌ <code>{key}</code>: formato non valido.\n"
            f"Formato atteso: <code>HH:MM</code> — esempio: <code>08:30</code>"
        )

    # Salva nel DB
    config_set(key, _value_to_str(value), type_str)

    restart_note = (
        "\n\n⚠️ <i>Questo parametro è letto allo scheduler startup — "
        "verrà applicato al prossimo riavvio del bot.</i>"
    ) if meta.get("restart") else ""

    return True, (
        f"✅ <code>{key}</code> aggiornato a <b>{value}</b>{restart_note}"
    )


def get_key_info(key: str) -> str:
    """Restituisce una stringa con i dettagli di una chiave (per /set chiave senza valore)."""
    if key not in VALID_KEYS:
        return f"❌ Chiave <code>{key}</code> non riconosciuta.\nUsa /config per vedere le chiavi valide."

    meta = VALID_KEYS[key]
    type_str = meta["type"]
    row = config_get(key)
    current_val = row["value"] if row else "N/D"
    source_label = "🟠 override utente" if row and row["source"] == "user" else "🔵 default yaml"

    type_info = type_str
    if "choices" in meta:
        type_info += f"\nValori: {', '.join(f'<code>{c}</code>' for c in meta['choices'])}"
    else:
        bounds = []
        if "min" in meta: bounds.append(f"min {meta['min']}")
        if "max" in meta: bounds.append(f"max {meta['max']}")
        if bounds:
            type_info += f" ({', '.join(bounds)})"

    restart = "\n⚠️ Richiede riavvio per applicarsi allo scheduler." if meta.get("restart") else ""

    return (
        f"ℹ️ <b>{key}</b>\n\n"
        f"📝 {meta['desc']}\n"
        f"🔢 Tipo: <code>{type_info}</code>\n"
        f"💾 Valore attuale: <b>{current_val}</b> ({source_label}){restart}\n\n"
        f"Usa: <code>/set {key} nuovo_valore</code>"
    )
