"""
YTSPERBOT - Telegram Command Handler
Ascolta comandi in arrivo via polling e li esegue
"""

import os
import time
import threading
import requests
from datetime import datetime


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


def _handle_command(text: str, job_fn, config_fn):
    text = text.strip().lower()
    chat_id = _chat_id()

    if text == "/run":
        _send("⚡ <b>Esecuzione forzata avviata...</b>\nRiceverai le notifiche a breve.")
        print("[COMMANDS] /run ricevuto — avvio esecuzione forzata", flush=True)
        try:
            config = config_fn()
            job_fn(config)
            _send("✅ <b>Esecuzione completata.</b>")
        except Exception as e:
            _send(f"❌ <b>Errore durante l'esecuzione:</b>\n<code>{e}</code>")
            print(f"[COMMANDS] Errore /run: {e}", flush=True)

    elif text == "/status":
        _send(
            f"⚙️ <b>YTSPERBOT — Status</b>\n\n"
            f"🟢 Bot attivo\n"
            f"🕐 Ora server: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"<b>Comandi disponibili:</b>\n"
            f"/run — esecuzione forzata immediata\n"
            f"/status — questo messaggio"
        )

    elif text.startswith("/"):
        _send(
            f"❓ Comando non riconosciuto: <code>{text}</code>\n\n"
            f"<b>Comandi disponibili:</b>\n"
            f"/run — esecuzione forzata immediata\n"
            f"/status — mostra lo stato del bot"
        )


def start_command_listener(job_fn, config_fn):
    """
    Avvia il polling in un thread daemon.
    job_fn(config) — funzione da chiamare su /run
    config_fn()    — funzione che restituisce il config
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
                # Accetta solo messaggi dal tuo chat_id
                if str(msg.get("chat", {}).get("id")) != str(_chat_id()):
                    continue
                text = msg.get("text", "")
                if text:
                    threading.Thread(
                        target=_handle_command,
                        args=(text, job_fn, config_fn),
                        daemon=True
                    ).start()
            if not updates:
                time.sleep(1)

    thread = threading.Thread(target=_poll, daemon=True)
    thread.start()
