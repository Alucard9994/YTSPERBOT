"""
YTSPERBOT - Telegram Command Handler
Ascolta comandi in arrivo via polling e li esegue
"""

import os
import time
import threading
import requests
from datetime import datetime
from modules.database import add_to_blacklist, remove_from_blacklist, get_blacklist, get_daily_brief_data
from modules.telegram_bot import send_daily_brief


def _token():
    return os.getenv("TELEGRAM_BOT_TOKEN")

def _chat_id():
    return os.getenv("TELEGRAM_CHAT_ID")

def _api(method):
    return f"https://api.telegram.org/bot{_token()}/{method}"


def _send(text: str):
    try:
        requests.post(_api("sendMessage"), json={
            "chat_id": _chat_id(),
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[COMMANDS] Errore invio risposta: {e}", flush=True)


def _get_updates(offset: int) -> list:
    try:
        resp = requests.get(_api("getUpdates"), params={
            "offset": offset,
            "timeout": 30,
            "allowed_updates": ["message"]
        }, timeout=40)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception as e:
        print(f"[COMMANDS] Errore polling: {e}", flush=True)
    return []


# Credenziali richieste per ciascun modulo: lista di (ENV_VAR, nome leggibile)
_MODULE_CREDS = {
    "reddit":           [("REDDIT_CLIENT_ID", "Reddit"), ("REDDIT_CLIENT_SECRET", "Reddit")],
    "twitter":          [("TWITTER_BEARER_TOKEN", "Twitter/X")],
    "comments":         [("YOUTUBE_API_KEY", "YouTube Data API")],
    "scraper":          [("YOUTUBE_API_KEY", "YouTube Data API")],
    "new_video":        [("YOUTUBE_API_KEY", "YouTube Data API")],
    "subscriber_growth":[("YOUTUBE_API_KEY", "YouTube Data API")],
    "news":             [("NEWSAPI_KEY", "NewsAPI")],
    "social":           [("APIFY_API_KEY", "Apify")],
    # moduli senza credenziali obbligatorie
    "rss":         [],
    "trends":      [],
    "pinterest":   [],
    "cross_signal":[],
}

# Mappa comando → chiave modulo
_CMD_MODULE = {
    "/reddit":      "reddit",
    "/twitter":     "twitter",
    "/comments":    "comments",
    "/scraper":     "scraper",
    "/newvideo":    "new_video",
    "/subscribers": "subscriber_growth",
    "/news":        "news",
    "/social":      "social",
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
        f"• {label}: <code>{' / '.join(vars_)}</code>"
        for label, vars_ in seen.items()
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
    "<b>🚫 Blacklist</b>\n"
    "/block &lt;keyword&gt; — silenzia una keyword\n"
    "/unblock &lt;keyword&gt; — rimuovi da blacklist\n"
    "/blocklist — mostra keyword bloccate\n\n"
    "<b>ℹ️ Info</b>\n"
    "/status — stato del bot e schedule\n"
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
            _send(f"⚠️ <b>Completato con errori:</b>\n" + "\n".join(errors))
        else:
            _send("✅ <b>Esecuzione completa terminata.</b>")

    elif cmd == "/rss":
        _run_module("RSS Detector", modules["rss"], config)

    elif cmd == "/reddit":
        err = _check_creds("reddit")
        if err: _send(err); return
        _run_module("Reddit Detector", modules["reddit"], config)

    elif cmd == "/twitter":
        err = _check_creds("twitter")
        if err: _send(err); return
        _run_module("Twitter/X Detector", modules["twitter"], config)

    elif cmd == "/trends":
        _run_module("Google Trends", modules["trends"], config)

    elif cmd == "/comments":
        err = _check_creds("comments")
        if err: _send(err); return
        _run_module("YouTube Comments", modules["comments"], config)

    elif cmd == "/scraper":
        err = _check_creds("scraper")
        if err: _send(err); return
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
        if err: _send(err); return
        _run_module("Competitor Nuovi Video", modules["new_video"], config)

    elif cmd == "/subscribers":
        err = _check_creds("subscriber_growth")
        if err: _send(err); return
        _run_module("Crescita Iscritti", modules["subscriber_growth"], config)

    elif cmd == "/convergence":
        _run_module("Cross Signal Detector", modules["cross_signal"], config)

    elif cmd == "/news":
        err = _check_creds("news")
        if err: _send(err); return
        _run_module("News Detector", modules["news"], config)

    elif cmd == "/social":
        err = _check_creds("social")
        if err: _send(err); return
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
            _send("⚠️ Uso: <code>/cerca keyword</code>\nEsempio: <code>/cerca paranormale</code>")
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
                heat = "🔥🔥🔥" if total > 50 else "🔥🔥" if total > 20 else "🔥" if total > 5 else "❄️"
                _send(
                    f"🔍 <b>Cerca:</b> <code>{keyword}</code>\n\n"
                    f"{heat} <b>Totale 7 giorni:</b> {total} menzioni su {len(data)} fonti\n\n"
                    f"<b>Per fonte:</b>\n{sources_lines}\n\n"
                    f"💡 <i>Usa /graph {keyword} per vedere il grafico.</i>"
                )

    elif cmd == "/graph":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send("⚠️ Uso: <code>/graph keyword</code>\nEsempio: <code>/graph paranormale</code>")
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
                    send_photo(img, caption=f"📊 Trend: <b>{keyword}</b> — ultimi 7 giorni")
            except Exception as e:
                _send(f"❌ <b>Errore generazione grafico:</b>\n<code>{e}</code>")
                print(f"[COMMANDS] Errore /graph: {e}", flush=True)

    elif cmd == "/transcript":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            _send("⚠️ Uso: <code>/transcript video_id</code>\nEsempio: <code>/transcript dQw4w9WgXcQ</code>")
        else:
            video_id = parts[1].strip()
            _send(f"⏳ Recupero trascrizione per <code>{video_id}</code>...")
            print(f"[COMMANDS] /transcript richiesta per {video_id}", flush=True)
            try:
                from modules.youtube_scraper import get_transcript
                transcript = get_transcript(video_id, languages=["it", "en"])
                if not transcript:
                    _send(f"❌ Trascrizione non disponibile per <code>{video_id}</code>.\n\n<i>Il video potrebbe non avere sottotitoli, o sono disabilitati.</i>")
                else:
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    chunks = [transcript[i:i+3500] for i in range(0, len(transcript), 3500)]
                    _send(
                        f"📄 <b>Trascrizione — <a href='{url}'>{video_id}</a></b>\n"
                        f"📏 {len(transcript):,} caratteri · {len(chunks)} parti\n"
                    )
                    for i, chunk in enumerate(chunks, 1):
                        _send(f"<b>Parte {i}/{len(chunks)}:</b>\n\n<i>{chunk}</i>")
                    print(f"[COMMANDS] Trascrizione {video_id} inviata ({len(chunks)} parti)", flush=True)
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

    elif cmd == "/status":
        # Stato credenziali
        cred_checks = [
            ("YOUTUBE_API_KEY",      "YouTube Data API"),
            ("REDDIT_CLIENT_ID",     "Reddit"),
            ("TWITTER_BEARER_TOKEN", "Twitter/X"),
            ("NEWSAPI_KEY",          "NewsAPI"),
            ("APIFY_API_KEY",        "Apify (TikTok + Instagram)"),
            ("PINTEREST_ACCESS_TOKEN", "Pinterest"),
            ("ANTHROPIC_API_KEY",    "Anthropic AI (titoli)"),
        ]
        cred_lines = "\n".join(
            f"{'✅' if os.getenv(var) else '❌'} {label}"
            for var, label in cred_checks
        )
        _send(
            f"⚙️ <b>YTSPERBOT — Status</b>\n\n"
            f"🟢 Bot attivo\n"
            f"🕐 Ora server: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"<b>Credenziali:</b>\n{cred_lines}\n\n"
            f"Usa /help per la lista comandi."
        )

    elif cmd in ("/help", "/listacomandi"):
        _send(f"📋 <b>YTSPERBOT — Comandi</b>\n\n{COMMANDS_HELP}")

    elif cmd.startswith("/"):
        _send(f"❓ Comando non riconosciuto: <code>{cmd}</code>\n\nUsa /help per la lista comandi.")


def start_command_listener(modules: dict, config_fn):
    """
    Avvia il polling in un thread daemon.

    modules: dict con chiavi rss/reddit/twitter/trends/comments/scraper
             e valori funzione(config)
    config_fn: funzione che restituisce il config aggiornato
    """
    if not _token() or not _chat_id():
        print("[COMMANDS] Credenziali mancanti, command listener non avviato.", flush=True)
        return

    def _poll():
        offset = 0
        print("[COMMANDS] Listener attivo — in ascolto comandi Telegram", flush=True)
        while True:
            updates = _get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                if str(msg.get("chat", {}).get("id")) != str(_chat_id()):
                    continue
                text = msg.get("text", "")
                if text:
                    threading.Thread(
                        target=_handle_command,
                        args=(text, modules, config_fn),
                        daemon=True
                    ).start()
            if not updates:
                time.sleep(1)

    threading.Thread(target=_poll, daemon=True).start()
