"""
TheVeil Monitor - Modulo Telegram
Gestisce l'invio di notifiche al bot Telegram personale
"""

import os
import requests
from datetime import datetime
from modules.database import is_blacklisted, get_keyword_source_count


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


def alert_allowed(keyword: str, velocity: float, min_score: int = 1) -> bool:
    """Controlla blacklist e score minimo. Restituisce False se l'alert va bloccato."""
    if is_blacklisted(keyword):
        print(f"[TELEGRAM] Alert bloccato (blacklist): {keyword}", flush=True)
        return False
    source_count = get_keyword_source_count(keyword, hours=24)
    score = calculate_priority_score(velocity, source_count)
    if score < min_score:
        print(f"[TELEGRAM] Alert filtrato (score {score} < min {min_score}): {keyword}", flush=True)
        return False
    return True


def calculate_priority_score(velocity: float, source_count: int) -> int:
    """Score 1-10: velocità (0-5) + numero fonti (0-5)."""
    velocity_score = min(velocity / 100, 5.0)
    source_score = min(source_count * 1.5, 5.0)
    return max(1, round(velocity_score + source_score))


def score_bar(score: int) -> str:
    filled = round(score / 2)
    return "🟥" * filled + "⬜" * (5 - filled)


def send_trend_alert(keyword: str, velocity: float, source: str, mentions_now: int, mentions_before: int, source_count: int = 1, min_score: int = 1):
    if not alert_allowed(keyword, velocity, min_score):
        return False

    source_count = max(source_count, get_keyword_source_count(keyword, hours=24))
    score = calculate_priority_score(velocity, source_count)
    emoji = "🔺" if velocity >= 500 else "📈"
    text = (
        f"{emoji} <b>TREND IN CRESCITA</b>\n\n"
        f"🔍 <b>Keyword:</b> <code>{keyword}</code>\n"
        f"📡 <b>Fonte:</b> {source}\n"
        f"⚡ <b>Velocity:</b> +{velocity:.0f}%\n"
        f"📊 <b>Menzioni:</b> {mentions_before} → {mentions_now}\n"
        f"🎯 <b>Score:</b> {score}/10  {score_bar(score)}\n"
        f"🕐 <b>Rilevato:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"<i>Considera di creare contenuto su questo topic nelle prossime ore.</i>"
    )
    return send_message(text)


def send_daily_brief(data: list):
    if not data:
        return send_message("📋 <b>Brief giornaliero</b>\n\nNessun dato nelle ultime 24 ore.")

    lines = []
    for i, row in enumerate(data, 1):
        sources_n = row["source_count"]
        score = calculate_priority_score(0, sources_n)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(
            f"{medal} <code>{row['keyword']}</code> — "
            f"{row['total_mentions']} menzioni · {sources_n} {'fonti' if sources_n > 1 else 'fonte'}"
        )

    text = (
        f"📋 <b>Brief giornaliero — {datetime.now().strftime('%d/%m/%Y')}</b>\n\n"
        f"<b>Top keyword ultime 24h:</b>\n\n"
        + "\n".join(lines)
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