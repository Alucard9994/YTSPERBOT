"""
YTSPERBOT - Telegram Command Handler
Ascolta comandi in arrivo via polling e li esegue
"""
from __future__ import annotations

import os
import time
import threading
import requests
from datetime import datetime, timedelta
from modules.database import (
    add_to_blacklist,
    remove_from_blacklist,
    get_blacklist,
    config_get_all,
    config_list_add,
    config_list_remove,
    config_list_get,
)
from modules.config_manager import LIST_META
from modules.telegram_bot import send_daily_brief

# Safety lock per /populate: None = disarmato, datetime = scade alle X
_populate_armed_until: datetime | None = None
_populate_lock = threading.Lock()

# Dedup file_id per /populate: evita doppia elaborazione dello stesso documento
_processed_file_ids: set = set()
_processed_file_ids_lock = threading.Lock()

# Session state per /add, /rm, /showlist (inline keyboard flow)
_sessions: dict[str, dict] = {}


def _token():
    return os.getenv("TELEGRAM_BOT_TOKEN")


def _chat_id():
    return os.getenv("TELEGRAM_CHAT_ID")


def _api(method):
    return f"https://api.telegram.org/bot{_token()}/{method}"


def _send(text: str):
    try:
        requests.post(
            _api("sendMessage"),
            json={"chat_id": _chat_id(), "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[COMMANDS] Errore invio risposta: {e}", flush=True)


def _send_document(data: bytes, filename: str, caption: str = "") -> bool:
    """Invia un file come documento Telegram."""
    try:
        resp = requests.post(
            _api("sendDocument"),
            data={"chat_id": _chat_id(), "caption": caption, "parse_mode": "HTML"},
            files={"document": (filename, data, "text/plain")},
            timeout=30,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[COMMANDS] Errore invio documento: {e}", flush=True)
        return False


def _get_updates(offset: int) -> list:
    try:
        resp = requests.get(
            _api("getUpdates"),
            params={
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message", "callback_query"],
            },
            timeout=40,
        )
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception as e:
        print(f"[COMMANDS] Errore polling: {e}", flush=True)
    return []


# ============================================================
# Liste configurabili — inline keyboard helpers
# ============================================================


def _send_keyboard(text: str, keyboard: list) -> int | None:
    """Invia messaggio con inline keyboard. Restituisce message_id."""
    try:
        resp = requests.post(
            _api("sendMessage"),
            json={
                "chat_id": _chat_id(),
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["result"]["message_id"]
    except Exception as e:
        print(f"[COMMANDS] Errore _send_keyboard: {e}", flush=True)
    return None


def _edit_keyboard(message_id: int, text: str, keyboard: list | None = None):
    """Modifica testo e keyboard di un messaggio esistente."""
    try:
        payload: dict = {
            "chat_id": _chat_id(),
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": keyboard if keyboard is not None else []
            },
        }
        requests.post(_api("editMessageText"), json=payload, timeout=10)
    except Exception as e:
        print(f"[COMMANDS] Errore _edit_keyboard: {e}", flush=True)


def _answer_callback(callback_id: str, text: str = ""):
    """Risponde al callback query (rimuove loading spinner)."""
    try:
        requests.post(
            _api("answerCallbackQuery"),
            json={
                "callback_query_id": callback_id,
                "text": text,
            },
            timeout=5,
        )
    except Exception:
        pass


def _list_main_keyboard(action: str) -> list:
    rows = [
        [
            ("🔑 Keywords", f"lst:{action}:keywords"),
            ("📰 Subreddits", f"lst:{action}:subreddits"),
        ],
        [
            ("🎵 TikTok hashtag", f"lst:{action}:tiktok_hashtags"),
            ("📸 IG hashtag", f"lst:{action}:instagram_hashtags"),
        ],
        [
            ("▶ YouTube IT", f"lst:{action}:yt_queries_it"),
            ("▶ YouTube EN", f"lst:{action}:yt_queries_en"),
        ],
        [("🔍 Filter words", f"lst:{action}:filter_words")],
        [
            ("📡 Feed RSS ▶", f"lst:{action}:rss_group"),
            ("📺 Canali YouTube ▶", f"lst:{action}:ch_group"),
        ],
    ]
    return [[{"text": t, "callback_data": d} for t, d in row] for row in rows]


def _list_rss_keyboard(action: str) -> list:
    rows = [
        [
            ("🌍 English", f"lst:{action}:rss_english"),
            ("🇮🇹 Italian", f"lst:{action}:rss_italian"),
        ],
        [
            ("🎙 Podcasts", f"lst:{action}:rss_podcasts"),
            ("🔔 Google Alerts", f"lst:{action}:google_alerts"),
        ],
        [
            ("📱 TikTok", f"lst:{action}:rss_tiktok"),
            ("📸 Instagram", f"lst:{action}:rss_instagram"),
            ("📌 Pinterest", f"lst:{action}:rss_pinterest"),
        ],
        [("◀ Indietro", f"lst:back:{action}")],
    ]
    return [[{"text": t, "callback_data": d} for t, d in row] for row in rows]


def _list_ch_keyboard(action: str) -> list:
    rows = [
        [
            ("🇮🇹 Canali IT", f"lst:{action}:channels_it"),
            ("🌍 Canali EN", f"lst:{action}:channels_en"),
        ],
        [("◀ Indietro", f"lst:back:{action}")],
    ]
    return [[{"text": t, "callback_data": d} for t, d in row] for row in rows]


def _list_items_keyboard(items: list, list_type: str) -> list:
    """Keyboard con gli item attuali per /rm (tap per rimuovere)."""
    buttons = []
    display_items = items[:30]
    for i, item in enumerate(display_items):
        if list_type == "feed":
            label = (item.get("label") or item.get("value", ""))[:50]
        else:
            label = str(item.get("value", ""))[:50]
        buttons.append([{"text": label, "callback_data": f"lst:rm_i:{i}"}])
    if len(items) > 30:
        buttons.append(
            [
                {
                    "text": f"⚠️ +{len(items) - 30} non mostrati",
                    "callback_data": "lst:noop:x",
                }
            ]
        )
    buttons.append([{"text": "✖ Annulla", "callback_data": "lst:cancel:x"}])
    return buttons


def _start_list_action(action: str):
    """Avvia /add, /rm, /showlist mostrando la keyboard principale."""
    labels = {"add": "➕ Aggiungi a", "rm": "🗑 Rimuovi da", "show": "📋 Mostra lista"}
    text = f"<b>{labels.get(action, action)}...</b>\n\n<i>Seleziona la lista:</i>"
    msg_id = _send_keyboard(text, _list_main_keyboard(action))
    if msg_id:
        _sessions[str(_chat_id())] = {
            "action": action,
            "msg_id": msg_id,
            "state": "choose_list",
        }


def _show_list_content(list_key: str, msg_id: int):
    """Mostra il contenuto di una lista (modifica messaggio)."""
    meta = LIST_META.get(list_key, {})
    items = config_list_get(list_key)
    name = meta.get("name", list_key)
    list_type = meta.get("type", "simple")

    if not items:
        _edit_keyboard(msg_id, f"📭 <b>{name}</b> è vuota.", [])
        return

    lines = [f"📋 <b>{name}</b> — {len(items)} voci:\n"]
    for item in items:
        if list_type == "feed":
            lbl = item.get("label") or ""
            url = item.get("value") or ""
            lines.append(f"• <b>{lbl}</b>\n  <code>{url}</code>")
        else:
            lines.append(f"• {item.get('value', '')}")

    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3800] + "\n<i>... (lista troncata)</i>"
    _edit_keyboard(msg_id, text, [])


def _handle_callback(callback: dict):
    """Gestisce i callback_query (tap su bottoni inline keyboard)."""
    callback_id = callback["id"]
    data = callback.get("data", "")
    msg = callback.get("message", {})
    msg_id = msg.get("message_id")

    _answer_callback(callback_id)

    if not data.startswith("lst:"):
        return

    parts = data.split(":", 2)
    if len(parts) < 3:
        return
    _, verb, key = parts

    chat_key = str(_chat_id())
    session = _sessions.get(chat_key, {})
    action = session.get("action", "add")

    # Annulla
    if verb == "cancel":
        _edit_keyboard(msg_id, "❌ Operazione annullata.", [])
        _sessions.pop(chat_key, None)
        return

    # Noop
    if verb == "noop":
        return

    # Back → torna alla keyboard principale
    if verb == "back":
        # key è l'action qui
        back_action = key
        labels = {
            "add": "➕ Aggiungi a",
            "rm": "🗑 Rimuovi da",
            "show": "📋 Mostra lista",
        }
        text = f"<b>{labels.get(back_action, back_action)}...</b>\n\n<i>Seleziona la lista:</i>"
        _edit_keyboard(msg_id, text, _list_main_keyboard(back_action))
        _sessions[chat_key] = {
            "action": back_action,
            "msg_id": msg_id,
            "state": "choose_list",
        }
        return

    # rm_i → rimuove elemento per indice
    if verb == "rm_i":
        idx = int(key)
        items = session.get("items", [])
        list_key = session.get("list_key", "")
        meta = LIST_META.get(list_key, {})
        if idx >= len(items):
            _edit_keyboard(msg_id, "❌ Elemento non trovato.", [])
            _sessions.pop(chat_key, None)
            return
        item = items[idx]
        value = item.get("value", "")
        label = item.get("label") or value
        config_list_remove(list_key, value)
        _edit_keyboard(
            msg_id,
            f"✅ <b>{label}</b> rimosso da <b>{meta.get('name', list_key)}</b>.",
            [],
        )
        _sessions.pop(chat_key, None)
        print(f"[COMMANDS] /rm list: rimosso '{label}' da {list_key}", flush=True)
        return

    # Navigazione gruppi
    if key == "rss_group":
        _edit_keyboard(
            msg_id,
            "📡 <b>Feed RSS</b> — seleziona categoria:",
            _list_rss_keyboard(action),
        )
        return

    if key == "ch_group":
        _edit_keyboard(
            msg_id, "📺 <b>Canali YouTube</b> — seleziona:", _list_ch_keyboard(action)
        )
        return

    # Lista specifica selezionata
    meta = LIST_META.get(key)
    if not meta:
        return

    if action == "show":
        _show_list_content(list_key=key, msg_id=msg_id)
        _sessions.pop(chat_key, None)
        return

    if action == "rm":
        items = config_list_get(key)
        if not items:
            _edit_keyboard(msg_id, f"📭 <b>{meta['name']}</b> è vuota.", [])
            _sessions.pop(chat_key, None)
            return
        _sessions[chat_key] = {
            "action": "rm",
            "list_key": key,
            "msg_id": msg_id,
            "state": "rm_choose_item",
            "items": items,
        }
        kb = _list_items_keyboard(items, meta["type"])
        _edit_keyboard(
            msg_id,
            f"🗑 <b>{meta['name']}</b> — {len(items)} voci\nSeleziona quella da rimuovere:",
            kb,
        )
        return

    if action == "add":
        if meta["type"] == "feed":
            _sessions[chat_key] = {
                "action": "add",
                "list_key": key,
                "msg_id": msg_id,
                "state": "await_url",
                "extra": {},
            }
            _edit_keyboard(
                msg_id,
                f"➕ <b>{meta['name']}</b>\n\n✏️ Invia l'<b>URL</b> del feed:",
                [],
            )
        else:
            hint = (
                "handle del canale (es. <code>MrBallen</code>)"
                if meta["type"] == "channel"
                else "valore da aggiungere"
            )
            _sessions[chat_key] = {
                "action": "add",
                "list_key": key,
                "msg_id": msg_id,
                "state": "await_value",
                "extra": {},
            }
            _edit_keyboard(
                msg_id, f"➕ <b>{meta['name']}</b>\n\n✏️ Invia il {hint}:", []
            )
        return


def _handle_session_input(text: str, session: dict, chat_key: str) -> bool:
    """
    Gestisce input testuale durante una sessione /add attiva.
    Returns True se l'input è stato consumato dalla sessione.
    """
    state = session.get("state")
    list_key = session.get("list_key", "")
    msg_id = session.get("msg_id")
    meta = LIST_META.get(list_key, {})

    if state == "await_value":
        value = text.strip()
        if not value:
            return True
        config_list_add(list_key, value)
        _edit_keyboard(
            msg_id,
            f"✅ <b>{value}</b> aggiunto a <b>{meta.get('name', list_key)}</b>.",
            [],
        )
        _sessions.pop(chat_key, None)
        print(f"[COMMANDS] /add list: aggiunto '{value}' a {list_key}", flush=True)
        return True

    if state == "await_url":
        url = text.strip()
        if not url.startswith("http"):
            _send(
                "⚠️ L'URL deve iniziare con <code>http://</code> o <code>https://</code>. Riprova:"
            )
            return True
        session["extra"]["url"] = url
        session["state"] = "await_label"
        _edit_keyboard(
            msg_id,
            f"➕ <b>{meta.get('name', list_key)}</b>\n\nURL: <code>{url[:80]}</code>\n\n✏️ Ora invia il <b>nome</b> del feed:",
            [],
        )
        return True

    if state == "await_label":
        label = text.strip()
        url = session["extra"].get("url", "")
        config_list_add(list_key, url, label=label)
        _edit_keyboard(
            msg_id,
            f"✅ Feed <b>{label}</b> aggiunto a <b>{meta.get('name', list_key)}</b>.",
            [],
        )
        _sessions.pop(chat_key, None)
        print(
            f"[COMMANDS] /add list: aggiunto feed '{label}' ({url}) a {list_key}",
            flush=True,
        )
        return True

    return False


# Credenziali richieste per ciascun modulo: lista di (ENV_VAR, nome leggibile)
_MODULE_CREDS = {
    "reddit": [("REDDIT_CLIENT_ID", "Reddit"), ("REDDIT_CLIENT_SECRET", "Reddit")],
    "twitter": [("TWITTER_BEARER_TOKEN", "Twitter/X")],
    "comments": [("YOUTUBE_API_KEY", "YouTube Data API")],
    "scraper": [("YOUTUBE_API_KEY", "YouTube Data API")],
    "new_video": [("YOUTUBE_API_KEY", "YouTube Data API")],
    "subscriber_growth": [("YOUTUBE_API_KEY", "YouTube Data API")],
    "news": [("NEWSAPI_KEY", "NewsAPI")],
    "social": [("APIFY_API_KEY", "Apify")],
    # moduli senza credenziali obbligatorie
    "rss": [],
    "trends": [],
    "pinterest": [],
    "cross_signal": [],
}

# Mappa comando → chiave modulo
_CMD_MODULE = {
    "/reddit": "reddit",
    "/twitter": "twitter",
    "/comments": "comments",
    "/scraper": "scraper",
    "/newvideo": "new_video",
    "/subscribers": "subscriber_growth",
    "/news": "news",
    "/social": "social",
}


def _check_creds(module_key: str) -> str | None:
    """Restituisce un messaggio di errore se mancano credenziali, altrimenti None."""
    required = _MODULE_CREDS.get(module_key, [])
    missing = [(var, label) for var, label in required if not os.getenv(var)]
    if not missing:
        return None
    seen = {}
    for var, label in missing:
        seen.setdefault(label, []).append(var)
    lines = "\n".join(
        f"• {label}: <code>{' / '.join(vars_)}</code>" for label, vars_ in seen.items()
    )
    return (
        f"❌ <b>Modulo disattivato — credenziali mancanti:</b>\n{lines}\n\n"
        f"<i>Aggiungile su Render → Environment e riavvia il bot.</i>"
    )


COMMANDS_HELP = (
    "<b>▶ Esecuzione moduli</b>\n"
    "/run — esegui tutti i moduli attivi\n"
    "/rss — RSS detector\n"
    "/reddit — Reddit detector\n"
    "/twitter — Twitter/X detector\n"
    "/trends — Google Trends\n"
    "/comments — YouTube Comments\n"
    "/scraper — YouTube Scraper (outperformer)\n"
    "/pinterest — Pinterest trending\n"
    "/trending — Google Trending RSS (IT + US)\n"
    "/rising — keyword emergenti correlate\n"
    "/newvideo — nuovi video competitor\n"
    "/subscribers — crescita iscritti competitor\n"
    "/convergence — convergenza multi-piattaforma\n"
    "/news — notizie di nicchia\n"
    "/social — TikTok + Instagram outperformer\n"
    "/weekly — report settimanale top keyword\n\n"
    "<b>🔍 Ricerca e analisi</b>\n"
    "/transcript &lt;video_id&gt; — trascrizione video\n"
    "/cerca &lt;keyword&gt; — cerca keyword in tutte le fonti\n"
    "/graph &lt;keyword&gt; — grafico trend 7 giorni\n"
    "/brief — riepilogo ultime 24h\n\n"
    "<b>👁 Watchlist profili social</b>\n"
    "/watch &lt;tiktok|instagram&gt; @username — monitora sempre questo profilo\n"
    "/unwatch &lt;tiktok|instagram&gt; @username — rimuovi dalla watchlist\n"
    "/watchlist — mostra tutti i profili in watchlist\n\n"
    "<b>📋 Liste configurabili</b>\n"
    "/add — aggiungi voce a keywords, subreddits, hashtag, feed RSS, canali\n"
    "/rm — rimuovi voce da una lista\n"
    "/showlist — mostra il contenuto di una lista\n\n"
    "<b>⚙️ Configurazione</b>\n"
    "/config — mostra tutti i parametri configurabili\n"
    "/set &lt;chiave&gt; &lt;valore&gt; — modifica un parametro\n"
    "/dashboard — link alla dashboard web\n\n"
    "<b>💾 Backup &amp; Restore</b>\n"
    "/backup — scarica un dump SQL del DB\n"
    "/populate — arma il bot per ricevere un file .sql (5 min)\n"
    "/dbstats — statistiche righe e dimensione DB\n"
    "/cleandb [giorni] — pulisce i dati vecchi (opz: retention personalizzata)\n\n"
    "<b>🚫 Blacklist</b>\n"
    "/block &lt;keyword&gt; — silenzia una keyword\n"
    "/unblock &lt;keyword&gt; — rimuovi da blacklist\n"
    "/blocklist — mostra keyword bloccate\n\n"
    "<b>🔧 Sistema</b>\n"
    "/restart — riavvia il servizio su Render (DB intatto, ~30s offline)\n\n"
    "<b>ℹ️ Info</b>\n"
    "/status — stato del bot e schedule\n"
    "/logs [minuti] — ultimi log (default 60 min, max 7 giorni)\n"
    "/help — lista comandi"
)


def _run_module(label: str, fn, config):
    _send(f"⚡ <b>{label} avviato...</b>")
    print(f"[COMMANDS] {label} avviato", flush=True)
    try:
        fn(config)
        _send(f"✅ <b>{label} completato.</b>")
    except Exception as e:
        _send(f"❌ <b>Errore in {label}:</b>\n<code>{e}</code>")
        print(f"[COMMANDS] Errore {label}: {e}", flush=True)


def _handle_command(text: str, modules: dict, config_fn):
    chat_key = str(_chat_id())

    # Se c'è una sessione attiva e il testo non è un comando → input per la sessione
    if chat_key in _sessions and not text.strip().startswith("/"):
        session = _sessions[chat_key]
        if _handle_session_input(text, session, chat_key):
            return

    if not text.strip():
        return
    cmd = text.strip().lower().split()[0]  # ignora eventuali argomenti
    config = config_fn()

    if cmd == "/run":
        # Salta moduli pesanti e quelli senza credenziali
        heavy = {"scraper", "subscriber_growth"}
        skipped_creds = []
        to_run = []
        for label, fn in modules.items():
            if label in heavy:
                continue
            err = _check_creds(label)
            if err:
                skipped_creds.append(label)
            else:
                to_run.append((label, fn))

        msg = f"⚡ <b>Esecuzione avviata ({len(to_run)} moduli)...</b>"
        if skipped_creds:
            msg += f"\n⏭ Saltati per credenziali mancanti: {', '.join(skipped_creds)}"
        _send(msg)
        print("[COMMANDS] /run — avvio moduli attivi", flush=True)
        errors = []
        for label, fn in to_run:
            try:
                print(f"[COMMANDS] /run → {label}", flush=True)
                fn(config)
            except Exception as e:
                errors.append(f"• {label}: {e}")
                print(f"[COMMANDS] Errore {label}: {e}", flush=True)
        if errors:
            _send("⚠️ <b>Completato con errori:</b>\n" + "\n".join(errors))
        else:
            _send("✅ <b>Esecuzione completa terminata.</b>")

    elif cmd == "/rss":
        _run_module("RSS Detector", modules["rss"], config)

    elif cmd == "/reddit":
        err = _check_creds("reddit")
        if err:
            _send(err)
            return
        _run_module("Reddit Detector", modules["reddit"], config)

    elif cmd == "/twitter":
        use_apify = config.get("twitter", {}).get("use_apify", False)
        if use_apify:
            err = _check_creds("social")  # richiede APIFY_API_KEY
            if err:
                _send(
                    err.replace("Modulo disattivato", "Twitter/X via Apify disattivato")
                )
                return
        else:
            err = _check_creds("twitter")  # richiede TWITTER_BEARER_TOKEN
            if err:
                _send(err)
                return
        _run_module("Twitter/X Detector", modules["twitter"], config)

    elif cmd == "/trends":
        _run_module("Google Trends", modules["trends"], config)

    elif cmd == "/comments":
        err = _check_creds("comments")
        if err:
            _send(err)
            return
        _run_module("YouTube Comments", modules["comments"], config)

    elif cmd == "/scraper":
        err = _check_creds("scraper")
        if err:
            _send(err)
            return
        _run_module("YouTube Scraper", modules["scraper"], config)

    elif cmd == "/pinterest":
        _run_module("Pinterest Detector", modules["pinterest"], config)

    elif cmd == "/trending":
        _send("🔥 <b>Controllo trending Google...</b>")
        try:
            from modules.trends_detector import run_trending_rss_monitor

            run_trending_rss_monitor(config)
            _send("✅ <b>Trending RSS completato.</b>")
        except Exception as e:
            _send(f"❌ <b>Errore:</b> <code>{e}</code>")

    elif cmd == "/rising":
        _send("🚀 <b>Ricerca rising queries...</b> (può richiedere 1-2 minuti)")
        try:
            from modules.trends_detector import run_rising_queries_detector

            run_rising_queries_detector(config)
            _send("✅ <b>Rising queries completato.</b>")
        except Exception as e:
            _send(f"❌ <b>Errore:</b> <code>{e}</code>")

    elif cmd == "/newvideo":
        err = _check_creds("new_video")
        if err:
            _send(err)
            return
        _run_module("Competitor Nuovi Video", modules["new_video"], config)

    elif cmd == "/subscribers":
        err = _check_creds("subscriber_growth")
        if err:
            _send(err)
            return
        _run_module("Crescita Iscritti", modules["subscriber_growth"], config)

    elif cmd == "/convergence":
        _run_module("Cross Signal Detector", modules["cross_signal"], config)

    elif cmd == "/news":
        err = _check_creds("news")
        if err:
            _send(err)
            return
        _run_module("News Detector", modules["news"], config)

    elif cmd == "/social":
        err = _check_creds("social")
        if err:
            _send(err)
            return
        _run_module("Social Scraper (TikTok + Instagram)", modules["social"], config)

    elif cmd == "/weekly":
        _send("📊 <b>Generazione report settimanale...</b>")
        try:
            from modules.database import get_daily_brief_data
            from modules.telegram_bot import send_weekly_brief

            data = get_daily_brief_data(hours=168)
            send_weekly_brief(data)
        except Exception as e:
            _send(f"❌ <b>Errore:</b> <code>{e}</code>")

    elif cmd == "/cerca":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send(
                "⚠️ Uso: <code>/cerca keyword</code>\nEsempio: <code>/cerca paranormale</code>"
            )
        else:
            keyword = parts[1].strip()
            from modules.database import get_keyword_all_mentions

            data = get_keyword_all_mentions(keyword, hours=168)
            if not data:
                _send(
                    f"🔍 <b>Cerca:</b> <code>{keyword}</code>\n\n"
                    f"❌ Nessun dato nelle ultime 7 giorni.\n\n"
                    f"<i>Il bot deve aver eseguito almeno un ciclo. Prova /run prima.</i>"
                )
            else:
                total = sum(r["total"] for r in data)
                sources_lines = "\n".join(
                    f"  • <b>{r['source']}</b>: {r['total']} menzioni (ultimo: {r['last_seen'][:16]})"
                    for r in data
                )
                heat = (
                    "🔥🔥🔥"
                    if total > 50
                    else "🔥🔥"
                    if total > 20
                    else "🔥"
                    if total > 5
                    else "❄️"
                )
                _send(
                    f"🔍 <b>Cerca:</b> <code>{keyword}</code>\n\n"
                    f"{heat} <b>Totale 7 giorni:</b> {total} menzioni su {len(data)} fonti\n\n"
                    f"<b>Per fonte:</b>\n{sources_lines}\n\n"
                    f"💡 <i>Usa /graph {keyword} per vedere il grafico.</i>"
                )

    elif cmd == "/graph":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send(
                "⚠️ Uso: <code>/graph keyword</code>\nEsempio: <code>/graph paranormale</code>"
            )
        else:
            keyword = parts[1].strip()
            _send(f"📊 Generazione grafico per <code>{keyword}</code>...")
            try:
                from modules.telegram_bot import generate_trend_graph, send_photo

                img = generate_trend_graph(keyword)
                if not img:
                    _send(
                        f"❌ Nessun dato trovato per <code>{keyword}</code>.\n\n"
                        f"<i>Il bot deve aver eseguito almeno un ciclo. Prova /run prima.</i>"
                    )
                else:
                    send_photo(
                        img, caption=f"📊 Trend: <b>{keyword}</b> — ultimi 7 giorni"
                    )
            except Exception as e:
                _send(f"❌ <b>Errore generazione grafico:</b>\n<code>{e}</code>")
                print(f"[COMMANDS] Errore /graph: {e}", flush=True)

    elif cmd == "/transcript":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send(
                "⚠️ Uso: <code>/transcript video_id</code>\nEsempio: <code>/transcript dQw4w9WgXcQ</code>"
            )
        else:
            video_id = parts[1].strip()
            _send(f"⏳ Recupero trascrizione per <code>{video_id}</code>...")
            print(f"[COMMANDS] /transcript richiesta per {video_id}", flush=True)
            try:
                from modules.youtube_scraper import get_transcript

                transcript = get_transcript(video_id, languages=["it", "en"])
                if not transcript:
                    _send(
                        f"❌ Trascrizione non disponibile per <code>{video_id}</code>.\n\n<i>Il video potrebbe non avere sottotitoli, o sono disabilitati.</i>"
                    )
                else:
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    chunks = [
                        transcript[i : i + 3500]
                        for i in range(0, len(transcript), 3500)
                    ]
                    _send(
                        f"📄 <b>Trascrizione — <a href='{url}'>{video_id}</a></b>\n"
                        f"📏 {len(transcript):,} caratteri · {len(chunks)} parti\n"
                    )
                    for i, chunk in enumerate(chunks, 1):
                        _send(f"<b>Parte {i}/{len(chunks)}:</b>\n\n<i>{chunk}</i>")
                    print(
                        f"[COMMANDS] Trascrizione {video_id} inviata ({len(chunks)} parti)",
                        flush=True,
                    )
            except Exception as e:
                _send(f"❌ <b>Errore:</b> <code>{e}</code>")
                print(f"[COMMANDS] Errore /transcript {video_id}: {e}", flush=True)

    elif cmd == "/brief":
        data = get_daily_brief_data(hours=24)
        send_daily_brief(data)

    elif cmd == "/block":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send("⚠️ Uso: <code>/block keyword</code>")
        else:
            kw = parts[1].strip()
            add_to_blacklist(kw)
            _send(f"🚫 <code>{kw}</code> aggiunta alla blacklist.")
            print(f"[COMMANDS] Blacklist: aggiunta '{kw}'", flush=True)

    elif cmd == "/unblock":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send("⚠️ Uso: <code>/unblock keyword</code>")
        else:
            kw = parts[1].strip()
            remove_from_blacklist(kw)
            _send(f"✅ <code>{kw}</code> rimossa dalla blacklist.")
            print(f"[COMMANDS] Blacklist: rimossa '{kw}'", flush=True)

    elif cmd == "/blocklist":
        bl = get_blacklist()
        if not bl:
            _send("✅ Nessuna keyword in blacklist.")
        else:
            items = "\n".join(f"• <code>{k}</code>" for k in bl)
            _send(f"🚫 <b>Keyword bloccate ({len(bl)}):</b>\n\n{items}")

    elif cmd == "/logs":
        # Ultimi log dal DB (priorità a ERROR/WARNING)
        from modules.database import get_bot_logs

        parts = text.strip().split()
        minutes = 60
        if len(parts) >= 2:
            try:
                minutes = int(parts[1])
            except ValueError:
                pass
        minutes = max(1, min(minutes, 10080))  # 1 min – 7 giorni

        logs = get_bot_logs(minutes=minutes, level="ALL", limit=20)
        if not logs:
            _send(f"✅ Nessun log nelle ultime {minutes} minuti.")
        else:
            important = [lg for lg in logs if lg["level"] in ("ERROR", "WARNING")]
            to_show = (important or logs)[:7]
            level_emoji = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "ℹ️"}
            lines = []
            for lg in to_show:
                emoji = level_emoji.get(lg["level"], "•")
                ts = lg["logged_at"][:16]
                msg = lg["message"][:200]
                lines.append(f"{emoji} <code>{ts}</code>\n<i>{msg}</i>")
            header = (
                f"🔴 {sum(1 for lg in logs if lg['level'] == 'ERROR')} errori  "
                f"🟡 {sum(1 for lg in logs if lg['level'] == 'WARNING')} warning  "
                f"ℹ️ {sum(1 for lg in logs if lg['level'] == 'INFO')} info\n\n"
            )
            _send(
                f"📋 <b>Log ultimi {minutes} min</b> ({len(logs)} righe):\n\n"
                + header
                + "\n\n".join(lines)
            )

    elif cmd == "/status":
        # Stato credenziali — considera use_apify per reddit/twitter/pinterest
        _apify_ok = bool(os.getenv("APIFY_API_KEY"))
        _reddit_use_apify = config.get("reddit", {}).get("use_apify", False)
        _twitter_use_apify = config.get("twitter", {}).get("use_apify", False)
        _pinterest_use_apify = config.get("pinterest", {}).get("use_apify", False)

        def _cred_line(label, env_var, use_apify=False):
            if use_apify:
                ok = _apify_ok
                mode = " (via Apify)"
            else:
                ok = bool(os.getenv(env_var))
                mode = ""
            return f"{'✅' if ok else '❌'} {label}{mode}"

        cred_lines = "\n".join([
            _cred_line("YouTube Data API", "YOUTUBE_API_KEY"),
            _cred_line("Reddit", "REDDIT_CLIENT_ID", use_apify=_reddit_use_apify),
            _cred_line("Twitter/X", "TWITTER_BEARER_TOKEN", use_apify=_twitter_use_apify),
            _cred_line("NewsAPI", "NEWSAPI_KEY"),
            _cred_line("Apify (TikTok + Instagram)", "APIFY_API_KEY"),
            _cred_line("Pinterest", "PINTEREST_ACCESS_TOKEN", use_apify=_pinterest_use_apify),
            _cred_line("Anthropic AI (titoli)", "ANTHROPIC_API_KEY"),
        ])
        _send(
            f"⚙️ <b>YTSPERBOT — Status</b>\n\n"
            f"🟢 Bot attivo\n"
            f"🕐 Ora server: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"<b>Credenziali:</b>\n{cred_lines}\n\n"
            f"Usa /help per la lista comandi."
        )

    elif cmd == "/dashboard":
        base_url = os.getenv(
            "RENDER_EXTERNAL_URL", "https://ytsperbot.onrender.com"
        ).rstrip("/")
        token = os.getenv("DASHBOARD_TOKEN", "")
        if not token:
            _send(
                "❌ <b>DASHBOARD_TOKEN</b> non configurato.\n\n"
                "Aggiungilo su Render → Environment come variabile d'ambiente."
            )
            return
        url = f"{base_url}/dashboard?token={token}"
        _send(
            f"📊 <b>Dashboard YTSPERBOT</b>\n\n"
            f"🔗 <a href='{url}'>Apri Dashboard</a>\n\n"
            f"<code>{url}</code>\n\n"
            f"<i>Il link include il token — non condividere.</i>"
        )

    elif cmd == "/config":
        rows = config_get_all()
        if not rows:
            _send(
                "⚠️ Config DB vuoto. Riavvia il bot per caricare i valori dal config.yaml."
            )
            return
        # Raggruppa per sezione
        sections: dict[str, list] = {}
        for row in rows:
            section = row["key"].split(".")[0]
            sections.setdefault(section, []).append(row)

        lines = [
            "⚙️ <b>Configurazione YTSPERBOT</b>",
            "<i>🔵 default yaml  ·  🟠 override /set</i>\n",
        ]
        for section in sorted(sections):
            lines.append(f"<b>― {section} ―</b>")
            for row in sections[section]:
                short_key = row["key"].split(".", 1)[1]
                icon = "🟠" if row["source"] == "user" else "🔵"
                lines.append(f"{icon} <code>{short_key}</code>: <b>{row['value']}</b>")
            lines.append("")

        lines.append(
            "💡 <i>/set &lt;chiave&gt; — info su una chiave\n"
            "/set &lt;chiave&gt; &lt;valore&gt; — modifica</i>\n"
            "Esempio: <code>/set scraper.multiplier_threshold 2.5</code>"
        )

        # Telegram max 4096 char — se supera, manda in due parti
        full = "\n".join(lines)
        if len(full) <= 4000:
            _send(full)
        else:
            mid = len(lines) // 2
            _send("\n".join(lines[:mid]))
            _send("\n".join(lines[mid:]))

    elif cmd == "/set":
        from modules.config_manager import validate_and_set, get_key_info

        parts = text.strip().split(maxsplit=2)
        if len(parts) < 2:
            _send(
                "⚠️ <b>Uso:</b>\n"
                "• <code>/set chiave valore</code> — modifica un parametro\n"
                "• <code>/set chiave</code> — info su una chiave\n\n"
                "Esempio: <code>/set scraper.multiplier_threshold 2.5</code>\n"
                "Usa /config per vedere tutte le chiavi."
            )
            return
        key = parts[1].strip()
        if len(parts) < 3:
            # Nessun valore: mostra info chiave
            _send(get_key_info(key))
            return
        raw_value = parts[2].strip()
        ok, msg = validate_and_set(key, raw_value)
        _send(msg)
        if ok:
            print(f"[COMMANDS] /set {key} = {raw_value}", flush=True)

    elif cmd == "/backup":
        _send("💾 <b>Generazione backup in corso...</b>")
        try:
            sql_bytes, stats = _generate_backup_sql()
            filename = f"ytsperbot_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.sql"
            total_rows = sum(stats.values())
            caption = (
                f"💾 <b>YTSPERBOT Backup</b> — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                f"📊 {total_rows} righe totali\n\n"
                + "\n".join(f"• {t}: {n}" for t, n in sorted(stats.items()) if n > 0)
                + "\n\n<i>Per ripristinare: /populate → poi invia questo file.</i>"
            )
            ok = _send_document(sql_bytes, filename, caption)
            if not ok:
                _send("❌ Errore invio file backup.")
            else:
                print(f"[COMMANDS] /backup: {total_rows} righe esportate", flush=True)
        except Exception as e:
            _send(f"❌ <b>Errore generazione backup:</b>\n<code>{e}</code>")
            print(f"[COMMANDS] Errore /backup: {e}", flush=True)

    elif cmd == "/populate":
        global _populate_armed_until
        _ARM_MINUTES = 5
        expires_at = datetime.now() + timedelta(minutes=_ARM_MINUTES)
        with _populate_lock:
            _populate_armed_until = expires_at
        _send(
            f"🔓 <b>Bot armato per il restore.</b>\n\n"
            f"Hai <b>{_ARM_MINUTES} minuti</b> per inviare il file <code>.sql</code> "
            f"esportato con /backup come documento in questa chat.\n\n"
            f"⏰ Scade alle <b>{expires_at.strftime('%H:%M:%S')}</b> UTC\n\n"
            f"<i>Se non invii nulla entro {_ARM_MINUTES} minuti il lock scade automaticamente.</i>"
        )
        print(
            f"[COMMANDS] /populate: lock attivo fino alle {expires_at.strftime('%H:%M:%S')}",
            flush=True,
        )

    elif cmd == "/dbstats":
        from modules.database import get_connection, DB_PATH

        try:
            conn = get_connection()
            _SKIP = {"sqlite_sequence", "sqlite_master", "sqlite_stat1"}
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()

            lines = ["🗄 <b>Statistiche Database</b>\n"]
            total_rows = 0
            for t in tables:
                name = t["name"]
                if name in _SKIP:
                    continue
                count = conn.execute(f'SELECT COUNT(*) AS n FROM "{name}"').fetchone()[
                    "n"
                ]
                total_rows += count
                bar = "▓" * min(count // 10, 20) if count > 0 else "░"
                lines.append(f"<code>{name:<35}</code> {count:>6} righe  {bar}")
            conn.close()

            # Dimensione file DB
            try:
                size_bytes = os.path.getsize(DB_PATH)
                if size_bytes >= 1024 * 1024:
                    size_str = f"{size_bytes / 1024 / 1024:.1f} MB"
                else:
                    size_str = f"{size_bytes / 1024:.1f} KB"
            except Exception:
                size_str = "N/D"

            lines.append(f"\n📦 <b>Totale:</b> {total_rows} righe")
            lines.append(f"💽 <b>Dimensione file:</b> {size_str}")
            lines.append(
                f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} UTC"
            )
            lines.append("\n💡 <i>Usa /backup per esportare il DB.</i>")
            _send("\n".join(lines))
        except Exception as e:
            _send(f"❌ <b>Errore lettura DB:</b>\n<code>{e}</code>")

    elif cmd == "/cleandb":
        from modules.database import cleanup_db

        # Argomento opzionale: /cleandb 30  → forza retention a 30 giorni per tutte le tabelle
        parts = text.strip().split()
        custom_days = None
        if len(parts) >= 2:
            try:
                custom_days = int(parts[1])
            except ValueError:
                _send("❌ Usa: <code>/cleandb [giorni]</code>\nEsempio: <code>/cleandb 30</code>")
                return

        _send("🧹 <b>Pulizia DB in corso…</b>")
        try:
            retention = None
            if custom_days is not None:
                # Applica la retention personalizzata a tutte le tabelle pulibili
                tables = [
                    "keyword_mentions", "alerts_log", "bot_logs",
                    "youtube_outperformer_log", "competitor_video_log",
                    "youtube_comment_intel", "channel_subscribers_history",
                    "apify_outperformer_videos",
                ]
                retention = {t: custom_days for t in tables}

            results = cleanup_db(retention_days=retention)

            lines = ["🧹 <b>Pulizia DB completata</b>\n"]
            total = 0
            for table, deleted in results.items():
                if isinstance(deleted, int):
                    emoji = "🗑" if deleted > 0 else "✅"
                    lines.append(f"{emoji} <code>{table}</code>: <b>{deleted}</b> righe eliminate")
                    total += deleted
                else:
                    lines.append(f"⚠️ <code>{table}</code>: {deleted}")

            days_label = f"{custom_days} giorni (manuale)" if custom_days else "default config"
            lines.append(f"\n📊 <b>Totale:</b> {total} righe eliminate")
            lines.append(f"⚙️ <b>Retention applicata:</b> {days_label}")
            lines.append("💡 <i>Tabelle config e deduplication non toccate.</i>")
            _send("\n".join(lines))
        except Exception as e:
            _send(f"❌ <b>Errore pulizia DB:</b>\n<code>{e}</code>")

    elif cmd == "/watch":
        parts = text.strip().split(maxsplit=2)
        if len(parts) < 3:
            _send(
                "⚠️ <b>Uso:</b>\n"
                "<code>/watch tiktok @username</code>\n"
                "<code>/watch instagram @username</code>\n\n"
                "I profili watchlist vengono analizzati ad ogni run /social,\n"
                "senza limite di follower."
            )
            return
        platform = parts[1].strip().lower()
        if platform not in ("tiktok", "instagram"):
            _send(
                "⚠️ Piattaforma non valida. Usa: <code>tiktok</code> oppure <code>instagram</code>"
            )
            return
        username = parts[2].strip().lstrip("@")
        from modules.database import upsert_pinned_profile

        upsert_pinned_profile(platform, username)
        _send(
            f"👁 <b>@{username}</b> aggiunto alla watchlist <b>{platform}</b>.\n\n"
            f"Verrà analizzato ad ogni run /social, senza filtro follower.\n"
            f"Usa /watchlist per vedere tutti i profili monitorati."
        )
        print(f"[COMMANDS] Watchlist: aggiunto {platform}/@{username}", flush=True)

    elif cmd == "/unwatch":
        parts = text.strip().split(maxsplit=2)
        if len(parts) < 3:
            _send(
                "⚠️ <b>Uso:</b>\n"
                "<code>/unwatch tiktok @username</code>\n"
                "<code>/unwatch instagram @username</code>"
            )
            return
        platform = parts[1].strip().lower()
        if platform not in ("tiktok", "instagram"):
            _send(
                "⚠️ Piattaforma non valida. Usa: <code>tiktok</code> oppure <code>instagram</code>"
            )
            return
        username = parts[2].strip().lstrip("@")
        from modules.database import remove_pinned_profile

        remove_pinned_profile(platform, username)
        _send(f"✅ <b>@{username}</b> rimosso dalla watchlist <b>{platform}</b>.")
        print(f"[COMMANDS] Watchlist: rimosso {platform}/@{username}", flush=True)

    elif cmd == "/watchlist":
        from modules.database import list_pinned_profiles

        profiles = list_pinned_profiles()
        if not profiles:
            _send(
                "👁 <b>Watchlist vuota.</b>\n\n"
                "Aggiungi profili con:\n"
                "<code>/watch tiktok @username</code>\n"
                "<code>/watch instagram @username</code>"
            )
            return
        by_platform: dict[str, list] = {}
        for p in profiles:
            by_platform.setdefault(p["platform"], []).append(p)
        lines = [f"👁 <b>Watchlist — {len(profiles)} profili monitorati</b>\n"]
        for platform in sorted(by_platform):
            lines.append(f"<b>― {platform.upper()} ―</b>")
            for p in by_platform[platform]:
                last = p["last_analyzed"][:10] if p.get("last_analyzed") else "mai"
                fol = f"{p['followers']:,}" if p.get("followers") else "?"
                lines.append(
                    f"• @{p['username']} · {fol} follower · analizzato: {last}"
                )
            lines.append("")
        lines.append("<i>Rimuovi con /unwatch &lt;piattaforma&gt; @username</i>")
        _send("\n".join(lines))

    elif cmd == "/restart":
        render_key = os.getenv("RENDER_API_KEY", "")
        render_service = os.getenv("RENDER_SERVICE_ID", "")
        if not render_key or not render_service:
            _send(
                "❌ <b>Variabili d'ambiente mancanti per il restart.</b>\n\n"
                "Aggiungi su Render → Environment:\n"
                "• <code>RENDER_API_KEY</code> — da Account Settings → API Keys\n"
                "• <code>RENDER_SERVICE_ID</code> — es. <code>srv-xxxxxxxxxxxx</code>\n\n"
                "<i>Il Service ID è nell'URL della dashboard: dashboard.render.com/web/<b>srv-xxx</b></i>"
            )
            return
        _send(
            "🔄 <b>Riavvio del servizio in corso...</b>\n\n"
            "⏳ Il bot sarà offline per ~30 secondi.\n\n"
            "⚠️ <b>Su Render (disco effimero) il DB viene ricreato al riavvio:</b>\n"
            "• I dati operativi (keyword, alert, ecc.) vengono <b>azzerati</b>\n"
            "• I parametri impostati con <code>/set</code> tornano ai valori yaml\n\n"
            "💡 Per preservare tutto: <code>/backup</code> prima del riavvio, poi <code>/populate</code> dopo.\n\n"
            "<i>Il bot invierà il messaggio di avvio quando tornerà online.</i>"
        )
        try:
            resp = requests.post(
                f"https://api.render.com/v1/services/{render_service}/restart",
                headers={
                    "Authorization": f"Bearer {render_key}",
                    "Accept": "application/json",
                },
                timeout=15,
            )
            if resp.status_code not in (200, 202):
                _send(
                    f"❌ <b>Errore Render API:</b> {resp.status_code}\n<code>{resp.text[:300]}</code>"
                )
        except Exception as e:
            _send(f"❌ <b>Errore chiamata Render API:</b>\n<code>{e}</code>")
        print("[COMMANDS] /restart: richiesta inviata a Render API", flush=True)

    elif cmd == "/add":
        _start_list_action("add")

    elif cmd == "/rm":
        _start_list_action("rm")

    elif cmd in ("/showlist", "/lists"):
        _start_list_action("show")

    elif cmd in ("/help", "/listacomandi"):
        _send(f"📋 <b>YTSPERBOT — Comandi</b>\n\n{COMMANDS_HELP}")

    elif cmd.startswith("/"):
        _send(
            f"❓ Comando non riconosciuto: <code>{cmd}</code>\n\nUsa /help per la lista comandi."
        )


def _generate_backup_sql() -> tuple[bytes, dict]:
    """
    Genera un dump SQL del DB per tutte le tabelle dati.
    - bot_config e config_lists usano INSERT OR REPLACE (override utente sopravvivono al deploy)
    - tutte le altre tabelle usano INSERT OR IGNORE (dati operativi, skip duplicati)
    Restituisce (sql_bytes, stats) dove stats è {table: n_rows}.
    """
    from modules.database import get_connection

    # Tabelle interne SQLite da escludere sempre
    _SKIP = {"sqlite_sequence", "sqlite_master", "sqlite_stat1"}

    # Queste tabelle vengono ri-seedate ad ogni avvio dal YAML:
    # usiamo OR REPLACE così i valori utente sovrascrivono il seed di default.
    _REPLACE_TABLES = {"bot_config", "config_lists"}

    conn = get_connection()
    lines = [
        "-- YTSPERBOT Database Backup",
        f"-- Generato: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} UTC",
        "-- Usa /populate inviando questo file al bot per ripristinare.",
        "-- Esegui SOLO su un DB già inizializzato (bot avviato almeno una volta).",
        "",
        "BEGIN TRANSACTION;",
        "",
    ]
    stats = {}

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    for table_row in tables:
        table = table_row["name"]
        if table in _SKIP:
            continue

        col_info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        col_names = [c["name"] for c in col_info]
        rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()

        stats[table] = len(rows)
        if not rows:
            lines.append(f"-- {table}: nessun dato")
            continue

        verb = "OR REPLACE" if table in _REPLACE_TABLES else "OR IGNORE"
        lines.append(f"-- {table}: {len(rows)} righe")
        cols_str = ", ".join(f'"{c}"' for c in col_names)

        for row in rows:
            values = []
            for v in row:
                if v is None:
                    values.append("NULL")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                else:
                    escaped = str(v).replace("'", "''")
                    # Replace newlines to prevent SQL comment injection:
                    # a value like "text\n-- foo" would generate a line
                    # starting with "--" which SQLite (and the restore parser)
                    # treats as a comment, breaking the INSERT statement.
                    escaped = escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
                    values.append(f"'{escaped}'")
            vals_str = ", ".join(values)
            lines.append(
                f'INSERT {verb} INTO "{table}" ({cols_str}) VALUES ({vals_str});'
            )
        lines.append("")

    lines += ["COMMIT;", ""]
    conn.close()
    return "\n".join(lines).encode("utf-8"), stats


def _handle_document(document: dict):
    """Gestisce un file .sql inviato come documento — esegue il restore del DB."""
    global _populate_armed_until

    file_name = document.get("file_name", "")
    if not file_name.endswith(".sql"):
        return  # ignora silenziosamente file non .sql

    file_id = document.get("file_id", "")

    # Controlla se il lock è attivo PRIMA del dedup: se non armato, il file_id non
    # viene bloccato, così l'utente può reinviare lo stesso file dopo /populate.
    with _populate_lock:
        armed = _populate_armed_until
        is_armed = armed is not None and datetime.now() <= armed
        _populate_armed_until = None  # disarma sempre (sia per restore che per scaduto)

    if not is_armed:
        _send(
            "🔒 <b>Restore bloccato.</b>\n\n"
            "Il bot non è in modalità restore. Usa prima /populate per armarlo.\n\n"
            "<i>Il lock dura 5 minuti dall'invio del comando.</i>"
        )
        return

    # Dedup: solo dopo aver verificato che il bot è armato, per non bloccare
    # file_id di documenti rifiutati che potrebbero essere reinviati legittimamente.
    with _processed_file_ids_lock:
        if file_id in _processed_file_ids:
            return
        _processed_file_ids.add(file_id)
    file_size = document.get("file_size", 0)

    if file_size > 10 * 1024 * 1024:  # 10 MB limite cautelativo
        _send("❌ File troppo grande (max 10 MB).")
        return

    _send("⏳ <b>Download file in corso...</b>")

    # Step 1: ottieni il path del file su Telegram
    try:
        resp = requests.get(_api("getFile"), params={"file_id": file_id}, timeout=10)
        file_path = resp.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{_token()}/{file_path}"
    except Exception as e:
        _send(f"❌ Errore recupero file da Telegram: <code>{e}</code>")
        return

    # Step 2: scarica il contenuto
    try:
        resp2 = requests.get(file_url, timeout=30)
        sql_content = resp2.content.decode("utf-8")
    except Exception as e:
        _send(f"❌ Errore download file: <code>{e}</code>")
        return

    # Step 3: esegui gli statement
    from modules.database import get_connection

    conn = get_connection()
    inserted = 0  # righe realmente inserite/sostituite (rowcount > 0)
    skipped = 0  # INSERT OR IGNORE silenziosamente ignorati (rowcount = 0)
    errors = []

    try:
        # Dividi per ";" e filtra commenti e righe vuote.
        # NOTA: il formato backup mette "-- tablename: N righe" sulla riga
        # PRIMA del primo INSERT di ogni tabella, quindi dopo split(";") il
        # primo INSERT di ogni tabella finisce nello stesso chunk del commento.
        # Dobbiamo rimuovere le righe di commento dal chunk prima di eseguirlo.
        raw_statements = sql_content.split(";")
        for raw in raw_statements:
            stmt = raw.strip()
            if not stmt:
                continue
            non_comment_lines = [
                ln for ln in stmt.split("\n") if not ln.strip().startswith("--")
            ]
            stmt = "\n".join(non_comment_lines).strip()
            if not stmt:
                continue
            # Ignora le direttive di transazione (le gestiamo noi)
            if stmt.upper() in ("BEGIN TRANSACTION", "COMMIT", "BEGIN", "END"):
                continue
            try:
                cur = conn.execute(stmt)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                err_msg = str(e)
                # UNIQUE constraint = duplicato atteso, non è un errore reale
                if "UNIQUE constraint" in err_msg or "already exists" in err_msg:
                    skipped += 1
                else:
                    errors.append(f"<code>{err_msg[:120]}</code>")
        conn.commit()
    except Exception as e:
        conn.rollback()
        _send(
            f"❌ <b>Errore critico durante il restore:</b>\n<code>{e}</code>\n\nNessuna modifica applicata."
        )
        return
    finally:
        conn.close()

    summary = (
        f"✅ <b>Restore completato!</b>\n\n"
        f"📥 Righe inserite/aggiornate: <b>{inserted}</b>\n"
        f"⏭ Già presenti (saltate): <b>{skipped}</b>\n"
    )
    if errors:
        summary += f"⚠️ Errori inattesi ({len(errors)}):\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            summary += f"\n<i>...e altri {len(errors) - 5}</i>"
    else:
        summary += "🎯 Nessun errore."

    _send(summary)
    print(
        f"[COMMANDS] /populate: {inserted} righe inserite, {skipped} saltate, {len(errors)} errori",
        flush=True,
    )


def start_command_listener(modules: dict, config_fn):
    """
    Avvia il polling in un thread daemon.

    modules: dict con chiavi rss/reddit/twitter/trends/comments/scraper
             e valori funzione(config)
    config_fn: funzione che restituisce il config aggiornato
    """
    if not _token() or not _chat_id():
        print(
            "[COMMANDS] Credenziali mancanti, command listener non avviato.", flush=True
        )
        return

    def _poll():
        # Salta gli aggiornamenti pendenti al boot: evita che file .sql stale consumino
        # lo stato armato di /populate prima che l'utente invii il file reale.
        offset = 0
        try:
            stale = _get_updates(offset)
            if stale:
                offset = stale[-1]["update_id"] + 1
                print(
                    f"[COMMANDS] Saltati {len(stale)} aggiornamenti pendenti al boot (offset → {offset})",
                    flush=True,
                )
        except Exception as e:
            print(f"[COMMANDS] Errore skip aggiornamenti pendenti: {e}", flush=True)

        print("[COMMANDS] Listener attivo — in ascolto comandi Telegram", flush=True)
        while True:
            updates = _get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1

                # Callback query (bottoni inline keyboard)
                callback = update.get("callback_query")
                if callback:
                    cb_chat_id = str(
                        callback.get("message", {}).get("chat", {}).get("id", "")
                    )
                    if cb_chat_id == str(_chat_id()):
                        threading.Thread(
                            target=_handle_callback, args=(callback,), daemon=True
                        ).start()
                    continue

                # Messaggi testuali e documenti
                msg = update.get("message", {})
                if str(msg.get("chat", {}).get("id")) != str(_chat_id()):
                    continue

                text = msg.get("text", "")
                document = msg.get("document")

                if text:
                    threading.Thread(
                        target=_handle_command,
                        args=(text, modules, config_fn),
                        daemon=True,
                    ).start()
                elif document and document.get("file_name", "").endswith(".sql"):
                    # File .sql inviato come documento → restore automatico
                    threading.Thread(
                        target=_handle_document, args=(document,), daemon=True
                    ).start()
            if not updates:
                time.sleep(1)

    threading.Thread(target=_poll, daemon=True).start()
