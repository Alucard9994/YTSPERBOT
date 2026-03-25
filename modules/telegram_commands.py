"""
YTSPERBOT - Telegram Command Handler
Ascolta comandi in arrivo via polling e li esegue
"""

import os
import time
import threading
import requests
from datetime import datetime, timedelta
from modules.database import add_to_blacklist, remove_from_blacklist, get_blacklist, get_daily_brief_data, config_get_all
from modules.telegram_bot import send_daily_brief

# Safety lock per /populate: None = disarmato, datetime = scade alle X
_populate_armed_until: datetime | None = None
_populate_lock = threading.Lock()


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


def _send_document(data: bytes, filename: str, caption: str = "") -> bool:
    """Invia un file come documento Telegram."""
    try:
        resp = requests.post(
            _api("sendDocument"),
            data={"chat_id": _chat_id(), "caption": caption, "parse_mode": "HTML"},
            files={"document": (filename, data, "text/plain")},
            timeout=30
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[COMMANDS] Errore invio documento: {e}", flush=True)
        return False


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
    "<b>⚙️ Configurazione</b>\n"
    "/config — mostra tutti i parametri configurabili\n"
    "/set &lt;chiave&gt; &lt;valore&gt; — modifica un parametro\n"
    "/dashboard — link alla dashboard web\n\n"
    "<b>💾 Backup &amp; Restore</b>\n"
    "/backup — scarica un dump SQL del DB\n"
    "/populate — arma il bot per ricevere un file .sql (5 min)\n"
    "/dbstats — statistiche righe e dimensione DB\n\n"
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

    elif cmd == "/dashboard":
        base_url = os.getenv("RENDER_EXTERNAL_URL", "https://ytsperbot.onrender.com").rstrip("/")
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
            _send("⚠️ Config DB vuoto. Riavvia il bot per caricare i valori dal config.yaml.")
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
        print(f"[COMMANDS] /populate: lock attivo fino alle {expires_at.strftime('%H:%M:%S')}", flush=True)

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
                count = conn.execute(f"SELECT COUNT(*) AS n FROM \"{name}\"").fetchone()["n"]
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
            lines.append(f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} UTC")
            lines.append("\n💡 <i>Usa /backup per esportare il DB.</i>")
            _send("\n".join(lines))
        except Exception as e:
            _send(f"❌ <b>Errore lettura DB:</b>\n<code>{e}</code>")

    elif cmd in ("/help", "/listacomandi"):
        _send(f"📋 <b>YTSPERBOT — Comandi</b>\n\n{COMMANDS_HELP}")

    elif cmd.startswith("/"):
        _send(f"❓ Comando non riconosciuto: <code>{cmd}</code>\n\nUsa /help per la lista comandi.")


def _generate_backup_sql() -> tuple[bytes, dict]:
    """
    Genera un dump SQL del DB con INSERT OR IGNORE per tutte le tabelle dati.
    Restituisce (sql_bytes, stats) dove stats è {table: n_rows}.
    """
    from modules.database import get_connection

    # Tabelle interne SQLite da escludere sempre
    _SKIP = {"sqlite_sequence", "sqlite_master", "sqlite_stat1"}

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

        col_info = conn.execute(f"PRAGMA table_info(\"{table}\")").fetchall()
        col_names = [c["name"] for c in col_info]
        rows = conn.execute(f"SELECT * FROM \"{table}\"").fetchall()

        stats[table] = len(rows)
        if not rows:
            lines.append(f"-- {table}: nessun dato")
            continue

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
                    values.append(f"'{escaped}'")
            vals_str = ", ".join(values)
            lines.append(f"INSERT OR IGNORE INTO \"{table}\" ({cols_str}) VALUES ({vals_str});")
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

    # Controlla se il lock è attivo (HTTP call fuori dal lock)
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

    file_id = document.get("file_id", "")
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
    executed = 0
    skipped = 0
    errors = []

    try:
        # Dividi per ";" ma ignora righe di commento e vuote
        raw_statements = sql_content.split(";")
        for raw in raw_statements:
            stmt = raw.strip()
            if not stmt or stmt.startswith("--"):
                continue
            # Ignora solo le direttive di transazione (le gestiamo noi)
            if stmt.upper() in ("BEGIN TRANSACTION", "COMMIT", "BEGIN", "END"):
                continue
            try:
                conn.execute(stmt)
                executed += 1
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
        _send(f"❌ <b>Errore critico durante il restore:</b>\n<code>{e}</code>\n\nNessuna modifica applicata.")
        return
    finally:
        conn.close()

    summary = (
        f"✅ <b>Restore completato!</b>\n\n"
        f"📥 Statement eseguiti: <b>{executed}</b>\n"
        f"⏭ Duplicati saltati: <b>{skipped}</b>\n"
    )
    if errors:
        summary += f"⚠️ Errori inattesi ({len(errors)}):\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            summary += f"\n<i>...e altri {len(errors) - 5}</i>"
    else:
        summary += "🎯 Nessun errore."

    _send(summary)
    print(f"[COMMANDS] /populate: {executed} stmt eseguiti, {skipped} duplicati, {len(errors)} errori", flush=True)


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
                document = msg.get("document")

                if text:
                    threading.Thread(
                        target=_handle_command,
                        args=(text, modules, config_fn),
                        daemon=True
                    ).start()
                elif document and document.get("file_name", "").endswith(".sql"):
                    # File .sql inviato come documento → restore automatico
                    threading.Thread(
                        target=_handle_document,
                        args=(document,),
                        daemon=True
                    ).start()
            if not updates:
                time.sleep(1)

    threading.Thread(target=_poll, daemon=True).start()
