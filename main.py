"""
YTSPERBOT - Main
Orchestratore principale del sistema
"""

import os
import yaml
import schedule
import time
import threading
from datetime import datetime
from dotenv import load_dotenv

from modules.database import init_db
from modules.config_manager import init_config_from_yaml, get_config
from modules.telegram_bot import send_system_message
from modules.youtube_scraper import run_scraper
from modules.reddit_detector import run_reddit_detector
from modules.rss_detector import run_rss_detector
from modules.youtube_comments import run_youtube_comments_detector
from modules.trends_detector import (
    run_trends_detector,
    run_trending_rss_monitor,
    run_rising_queries_detector,
)
from modules.twitter_detector import run_twitter_detector
from modules.twitter_apify import run_twitter_apify_detector
from modules.telegram_commands import start_command_listener
from modules.telegram_bot import send_daily_brief
from modules.database import get_daily_brief_data
from modules.competitor_monitor import (
    run_new_video_monitor,
    run_subscriber_growth_monitor,
)
from modules.cross_signal import run_cross_signal_detector
from modules.news_detector import run_news_detector
from modules.apify_scraper import run_apify_scraper
from modules.dispatcher import (
    run_twitter_auto as _dispatch_twitter,
    run_reddit_auto,
    run_pinterest_auto,
)
from modules.bot_logger import init_log_interceptor

load_dotenv()


def start_health_server():
    """Avvia FastAPI + uvicorn in un thread daemon."""
    import uvicorn
    from api.app import create_app

    port = int(os.getenv("PORT", 8080))
    fastapi_app = create_app()
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    print(f"[API] FastAPI avviato sulla porta {port} — docs: /api/docs")


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def job_trend_detector():
    config = get_config()
    job_trend_detector_with_config(config)


def run_twitter_auto(config: dict):
    """Dispatcher: usa Apify o il Bearer Token in base a twitter.use_apify."""
    _dispatch_twitter(
        config, apify_fn=run_twitter_apify_detector, bearer_fn=run_twitter_detector
    )


def job_twitter():
    config = get_config()
    run_twitter_auto(config)


def job_reddit():
    config = get_config()
    run_reddit_auto(config)  # dispatcher: Apify o PRAW nativo


def job_trend_detector_with_config(config: dict):
    # Reddit ha il suo job schedulato separatamente (intervallo diverso in modalità Apify)
    run_rss_detector(config)
    run_youtube_comments_detector(config)
    run_trends_detector(config)
    # Dopo ogni ciclo trend, controlla convergenza multi-piattaforma
    run_cross_signal_detector(config)


def job_youtube_scraper():
    config = get_config()
    run_scraper(config)


def job_daily_brief():
    data = get_daily_brief_data(hours=24)
    send_daily_brief(data)


def job_new_video_monitor():
    config = get_config()
    run_new_video_monitor(config)


def job_subscriber_growth():
    config = get_config()
    run_subscriber_growth_monitor(config)


def job_trending_rss():
    config = get_config()
    run_trending_rss_monitor(config)


def job_pinterest():
    config = get_config()
    run_pinterest_auto(config)  # dispatcher: Apify o API nativa


def job_rising_queries():
    config = get_config()
    run_rising_queries_detector(config)


def job_news():
    config = get_config()
    run_news_detector(config)


def job_apify_scraper():
    config = get_config()
    run_apify_scraper(config)


def job_weekly_report():
    from modules.database import get_daily_brief_data
    from modules.telegram_bot import send_weekly_brief

    data = get_daily_brief_data(hours=168)
    send_weekly_brief(data)


_SERVICE_MAP = {
    "rss": run_rss_detector,
    "reddit": run_reddit_auto,
    "twitter": run_twitter_auto,
    "trends": run_trends_detector,
    "comments": run_youtube_comments_detector,
    "scraper": run_scraper,
    "new_video": run_new_video_monitor,
    "subscriber_growth": run_subscriber_growth_monitor,
    "pinterest": run_pinterest_auto,
    "cross_signal": run_cross_signal_detector,
    "news": run_news_detector,
    "social": run_apify_scraper,
}


def run_service(name: str):
    """Esegue un singolo servizio per nome (usato dall'endpoint /system/run-services)."""
    config = get_config()
    fn = _SERVICE_MAP.get(name)
    if fn is None:
        print(f"[RUN-SERVICE] Servizio sconosciuto: {name}", flush=True)
        return
    print(f"[RUN-SERVICE] Avvio manuale: {name}", flush=True)
    try:
        fn(config)
        print(f"[RUN-SERVICE] Completato: {name}", flush=True)
    except Exception as exc:
        print(f"[RUN-SERVICE] ERRORE in {name}: {exc}", flush=True)


def check_bot_alive():
    """
    Invia un alert Telegram se il bot è silenzioso da troppe ore.
    Viene schedulato ogni ora. Non solleva eccezioni.
    """
    try:
        from datetime import timezone
        from modules.database import get_connection
        from modules.telegram_bot import send_message

        silence_hours = get_config().get("system", {}).get("silence_alert_hours", 6)
        conn = get_connection()
        row = conn.execute("SELECT MAX(logged_at) AS last FROM bot_logs").fetchone()
        conn.close()
        if not (row and row["last"]):
            return
        last_log = datetime.fromisoformat(row["last"].replace("Z", "+00:00"))
        if last_log.tzinfo is None:
            last_log = last_log.replace(tzinfo=timezone.utc)
        hours_silent = (datetime.now(timezone.utc) - last_log).total_seconds() / 3600
        if hours_silent >= silence_hours:
            send_message(
                f"⚠️ <b>Bot silenzioso da {hours_silent:.1f}h</b>\n"
                f"Nessun log registrato — il processo potrebbe essere bloccato.\n"
                f"Ultimo log: <code>{row['last'][:16]}</code>"
            )
    except Exception as e:
        print(f"[MAIN] check_bot_alive errore: {e}", flush=True)


def run_all_manual():
    print("\n" + "=" * 50)
    print("YTSPERBOT - Esecuzione Manuale")
    print("=" * 50)
    config = get_config()
    run_reddit_auto(config)
    run_twitter_auto(config)
    run_pinterest_auto(config)
    run_rss_detector(config)
    run_youtube_comments_detector(config)
    run_trends_detector(config)
    run_scraper(config)
    print("\n[MAIN] Esecuzione manuale completata.")


def start_scheduler(config: dict):
    interval_hours = config["trend_detector"]["check_interval_hours"]
    scraper_time = config["scraper"]["run_time"]
    tw_cfg = config.get("twitter", {})
    tw_interval = tw_cfg.get("check_interval_hours", interval_hours)
    tw_use_apify = tw_cfg.get("use_apify", False)

    reddit_cfg = config.get("reddit", {})
    reddit_use_apify = reddit_cfg.get("use_apify", False)
    reddit_interval = (
        reddit_cfg.get("check_interval_hours", interval_hours)
        if reddit_use_apify
        else interval_hours
    )

    schedule.every(interval_hours).hours.do(job_trend_detector)
    print(
        f"[SCHEDULER] Trend detector (RSS + Comments + Google Trends): ogni {interval_hours} ore"
    )

    schedule.every(reddit_interval).hours.do(job_reddit)
    reddit_mode = "Apify" if reddit_use_apify else "PRAW"
    print(f"[SCHEDULER] Reddit ({reddit_mode}): ogni {reddit_interval} ore")

    schedule.every(tw_interval).hours.do(job_twitter)
    tw_mode = "Apify" if tw_use_apify else "Bearer Token"
    print(f"[SCHEDULER] Twitter/X ({tw_mode}): ogni {tw_interval} ore")

    schedule.every().day.at(scraper_time).do(job_youtube_scraper)
    print(f"[SCHEDULER] YouTube scraper: ogni giorno alle {scraper_time}")

    apify_time = config.get("apify_scraper", {}).get("run_time", "04:00")
    apify_interval = config.get("apify_scraper", {}).get("run_interval_days", 14)
    schedule.every(apify_interval).days.at(apify_time).do(job_apify_scraper)
    print(
        f"[SCHEDULER] Apify social scraper (TikTok + Instagram): ogni {apify_interval} giorni alle {apify_time}"
    )

    brief_time = config.get("daily_brief", {}).get("send_time", "08:00")
    schedule.every().day.at(brief_time).do(job_daily_brief)
    print(f"[SCHEDULER] Brief giornaliero: ogni giorno alle {brief_time}")

    schedule.every(30).minutes.do(job_new_video_monitor)
    print("[SCHEDULER] Competitor nuovi video: ogni 30 minuti")

    trending_interval = config.get("trending_rss", {}).get("check_interval_minutes", 60)
    schedule.every(trending_interval).minutes.do(job_trending_rss)
    print(f"[SCHEDULER] Google Trending RSS: ogni {trending_interval} minuti")

    rising_interval = config.get("rising_queries", {}).get("check_interval_hours", 6)
    schedule.every(rising_interval).hours.do(job_rising_queries)
    print(f"[SCHEDULER] Rising queries: ogni {rising_interval} ore")

    pinterest_interval = config.get("pinterest", {}).get("check_interval_hours", 6)
    schedule.every(pinterest_interval).hours.do(job_pinterest)
    print(f"[SCHEDULER] Pinterest detector: ogni {pinterest_interval} ore")

    sub_time = config.get("competitor_monitor", {}).get(
        "subscriber_check_time", "09:00"
    )
    schedule.every().day.at(sub_time).do(job_subscriber_growth)
    print(f"[SCHEDULER] Crescita iscritti competitor: ogni giorno alle {sub_time}")

    news_interval = config.get("news_api", {}).get("check_interval_hours", 6)
    schedule.every(news_interval).hours.do(job_news)
    print(f"[SCHEDULER] News detector: ogni {news_interval} ore")

    weekly_day = config.get("weekly_report", {}).get("send_day", "sunday")
    weekly_time = config.get("weekly_report", {}).get("send_time", "09:00")
    getattr(schedule.every(), weekly_day).at(weekly_time).do(job_weekly_report)
    print(f"[SCHEDULER] Report settimanale: ogni {weekly_day} alle {weekly_time}")

    schedule.every().hour.do(check_bot_alive)
    print("[SCHEDULER] Bot silence check: ogni ora")

    start_command_listener(
        modules={
            "rss": run_rss_detector,
            "reddit": run_reddit_auto,
            "twitter": run_twitter_auto,
            "trends": run_trends_detector,
            "comments": run_youtube_comments_detector,
            "scraper": run_scraper,
            "new_video": run_new_video_monitor,
            "subscriber_growth": run_subscriber_growth_monitor,
            "pinterest": run_pinterest_auto,
            "cross_signal": run_cross_signal_detector,
            "news": run_news_detector,
            "social": run_apify_scraper,
        },
        config_fn=get_config,
    )

    # Verifica credenziali disponibili
    _yt = bool(os.getenv("YOUTUBE_API_KEY"))
    _reddit = bool(os.getenv("REDDIT_CLIENT_ID")) and bool(
        os.getenv("REDDIT_CLIENT_SECRET")
    )
    _tw = bool(os.getenv("TWITTER_BEARER_TOKEN"))
    _news = bool(os.getenv("NEWSAPI_KEY"))
    _apify = bool(os.getenv("APIFY_API_KEY"))
    _ai = bool(os.getenv("ANTHROPIC_API_KEY"))
    _pint = bool(os.getenv("PINTEREST_ACCESS_TOKEN"))

    def _i(ok):
        return "✅" if ok else "❌"

    # Etichette modalità per ogni piattaforma
    if tw_use_apify:
        _tw_label = (
            f"{_i(_apify)} Twitter/X via Apify (altimis/scweet): ogni {tw_interval}h"
        )
    else:
        _tw_label = f"{_i(_tw)} Twitter/X via Bearer Token: ogni {tw_interval}h"

    if reddit_use_apify:
        _reddit_label = f"{_i(_apify)} Reddit via Apify: ogni {reddit_interval}h"
    else:
        _reddit_label = f"{_i(_reddit)} Reddit via PRAW: ogni {reddit_interval}h"

    pint_use_apify = config.get("pinterest", {}).get("use_apify", False)
    if pint_use_apify:
        _pint_label = f"{_i(_apify)} Pinterest via Apify: ogni {pinterest_interval}h"
    else:
        _pint_label = (
            f"{_i(_pint)} Pinterest via API nativa: ogni {pinterest_interval}h"
        )

    send_system_message(
        f"✅ <b>Sistema avviato</b>\n\n"
        f"<b>🔄 Cicli automatici:</b>\n"
        f"{_i(True)} RSS + Google Trends + Trending RSS + Cross-signal: ogni {interval_hours}h / {trending_interval}min\n"
        f"{_i(_yt)} YouTube Comments + Competitor monitor: ogni {interval_hours}h\n"
        f"{_reddit_label}\n"
        f"{_tw_label}\n"
        f"{_i(True)} Rising queries: ogni {rising_interval}h\n"
        f"{_pint_label}\n"
        f"{_i(_news)} News detector: ogni {news_interval}h\n"
        f"{_i(_yt)} Competitor nuovi video: ogni 30 min\n"
        f"{_i(_yt)} YouTube Scraper (outperformer): ogni giorno alle {scraper_time}\n"
        f"{_i(_apify)} Social scraper TikTok+IG: ogni {apify_interval} giorni alle {apify_time}\n"
        f"{_i(_yt)} Crescita iscritti competitor: ogni giorno alle {sub_time}\n"
        f"{_i(True)} Brief giornaliero: ogni giorno alle {brief_time}\n"
        f"{_i(True)} Report settimanale: ogni {weekly_day} alle {weekly_time}\n"
        f"{_i(_ai)} AI titoli su convergenza (Anthropic)\n\n"
        f"<i>❌ = credenziali mancanti — usa /status per dettagli</i>"
    )

    print("\n[MAIN] Scheduler attivo. Premi CTRL+C per fermare.\n")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[MAIN] Errore scheduler (non fatale): {e}", flush=True)
        time.sleep(60)


if __name__ == "__main__":
    import sys

    print("\n" + "=" * 50, flush=True)
    print("  YTSPERBOT", flush=True)
    print(f"  Avvio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", flush=True)
    print("=" * 50 + "\n", flush=True)

    try:
        init_db()
        print("[OK] Database inizializzato", flush=True)
    except Exception as e:
        print(f"[ERRORE] Database: {e}", flush=True)
        sys.exit(1)

    init_log_interceptor()

    try:
        _yaml_config = load_config()
        init_config_from_yaml(_yaml_config)
        print("[OK] Config parametri caricati nel DB", flush=True)
    except Exception as e:
        print(f"[ERRORE] Config init: {e}", flush=True)
        sys.exit(1)

    start_health_server()

    if "--test" in sys.argv:
        print("[MAIN] Modalità TEST: esecuzione immediata di tutti i moduli\n")
        run_all_manual()

    elif "--scraper" in sys.argv:
        print("[MAIN] Modalità TEST: solo YouTube Scraper\n")
        run_scraper(get_config())

    elif "--reddit" in sys.argv:
        print("[MAIN] Modalità TEST: solo Reddit Detector\n")
        run_reddit_detector(get_config())

    elif "--rss" in sys.argv:
        print("[MAIN] Modalità TEST: solo RSS Detector\n")
        run_rss_detector(get_config())

    elif "--comments" in sys.argv:
        print("[MAIN] Modalità TEST: solo YouTube Comments\n")
        run_youtube_comments_detector(get_config())

    elif "--trends" in sys.argv:
        print("[MAIN] Modalità TEST: solo Google Trends\n")
        run_trends_detector(get_config())

    elif "--twitter" in sys.argv:
        print("[MAIN] Modalità TEST: solo Twitter/X\n")
        run_twitter_auto(get_config())

    else:
        print("[MAIN] Modalità PRODUZIONE: avvio scheduler\n", flush=True)
        try:
            config = get_config()
            start_scheduler(config)
        except Exception as e:
            print(f"[ERRORE CRITICO] {e}", flush=True)
            import traceback

            traceback.print_exc()
            sys.exit(1)
