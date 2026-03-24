"""
TheVeil Monitor - Modulo Telegram
Gestisce l'invio di notifiche al bot Telegram personale
"""

import os
import requests
from datetime import datetime


def _token():
    return os.getenv("TELEGRAM_BOT_TOKEN")

def _chat_id():
    return os.getenv("TELEGRAM_CHAT_ID")

def _api_url():
    return f"https://api.telegram.org/bot{_token()}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    token = _token()
    chat_id = _chat_id()

    if not token or not chat_id or token == "inserisci_qui":
        print("[TELEGRAM] Credenziali mancanti, messaggio non inviato.")
        return False

    try:
        response = requests.post(
            f"{_api_url()}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False
            },
            timeout=10
        )
        if response.status_code == 200:
            print(f"[TELEGRAM] Messaggio inviato alle {datetime.now().strftime('%H:%M:%S')}")
            return True
        else:
            print(f"[TELEGRAM] Errore {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[TELEGRAM] Eccezione: {e}")
        return False


def send_trend_alert(keyword: str, velocity: float, source: str, mentions_now: int, mentions_before: int):
    emoji = "🔺" if velocity >= 500 else "📈"
    text = (
        f"{emoji} <b>TREND IN CRESCITA - TheVeil Monitor</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"📡 <b>Fonte:</b> {source}\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Menzioni:</b> {mentions_before} → {mentions_now}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Considera di creare contenuto su questo topic nelle prossime ore.</i>"
    )
    return send_message(text)


def send_channel_alert(channel_data: dict):
    video = channel_data["video"]
    channel = channel_data["channel"]

    multiplier_str = f"{channel_data['multiplier']:.1f}x"
    tags_str = ", ".join(video.get("tags", [])[:8]) if video.get("tags") else "nessun tag"

    text = (
        f"🎯 <b>CANALE OUTPERFORMER {channel_data.get('format', '')} - Monitor</b>\n\n"
        f"📺 <b>Canale:</b> {channel['name']}\n"
        f"👥 <b>Iscritti:</b> {channel['subscribers']:,}\n"
        f"🎬 <b>Video ultimo mese:</b> {channel['videos_last_month']}\n"
        f"📊 <b>Media views canale:</b> {channel['avg_views']:,.0f}\n\n"
        f"🔥 <b>VIDEO OUTPERFORMER ({multiplier_str})</b>\n"
        f"📌 <b>Titolo:</b> {video['title']}\n"
        f"👁 <b>Views:</b> {video['views']:,}\n"
        f"🏷 <b>Tag:</b> {tags_str}\n"
        f"🔗 <b>Link:</b> https://www.youtube.com/watch?v={video['id']}\n\n"
        f"📝 <b>Descrizione:</b>\n<i>{video['description'][:300]}...</i>"
    )

    send_message(text)

    if video.get("transcript"):
        transcript_preview = video["transcript"][:800]
        transcript_msg = (
            f"📄 <b>Trascrizione (preview) - {video['title'][:40]}</b>\n\n"
            f"<i>{transcript_preview}...</i>"
        )
        send_message(transcript_msg)


def send_system_message(text: str):
    full_text = f"⚙️ <b>YTSPERBOT</b>\n{text}"
    return send_message(full_text)