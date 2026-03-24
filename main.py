"""
TheVeil Monitor - Main
Orchestratore principale del sistema
"""

import os
import yaml
import schedule
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from dotenv import load_dotenv

from modules.database import init_db
from modules.telegram_bot import send_system_message
from modules.youtube_scraper import run_scraper
from modules.reddit_detector import run_reddit_detector
from modules.rss_detector import run_rss_detector
from modules.youtube_comments import run_youtube_comments_detector
from modules.trends_detector import run_trends_detector
from modules.twitter_detector import run_twitter_detector
from modules.telegram_commands import start_command_listener
from modules.telegram_bot import send_daily_brief
from modules.database import get_daily_brief_data
from modules.competitor_monitor import run_new_video_monitor, run_subscriber_growth_monitor

load_dotenv()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # silenzia i log HTTP


def start_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[HEALTH] Server avviato sulla porta {port}")


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def job_trend_detector():
    config = load_config()
    job_trend_detector_with_config(config)


def job_trend_detector_with_config(config: dict):
    run_reddit_detector(config)
    run_twitter_detector(config)
    run_rss_detector(config)
    run_youtube_comments_detector(config)
    run_trends_detector(config)


def job_youtube_scraper():
    config = load_config()
    run_scraper(config)


def job_daily_brief():
    data = get_daily_brief_data(hours=24)
    send_daily_brief(data)


def job_new_video_monitor():
    config = load_config()
    run_new_video_monitor(config)


def job_subscriber_growth():
    config = load_config()
    run_subscriber_growth_monitor(config)


def run_all_manual():
    print("\n" + "="*50)
    print("TheVeil Monitor - Esecuzione Manuale")
    print("="*50)
    config = load_config()
    run_reddit_detector(config)
    run_twitter_detector(config)
    run_rss_detector(config)
    run_youtube_comments_detector(config)
    run_trends_detector(config)
    run_scraper(config)
    print("\n[MAIN] Esecuzione manuale completata.")


def start_scheduler(config: dict):
    interval_hours = config["trend_detector"]["check_interval_hours"]
    scraper_time = config["scraper"]["run_time"]

    schedule.every(interval_hours).hours.do(job_trend_detector)
    print(f"[SCHEDULER] Trend detector (Reddit + RSS + Comments): ogni {interval_hours} ore")

    schedule.every().day.at(scraper_time).do(job_youtube_scraper)
    print(f"[SCHEDULER] YouTube scraper: ogni giorno alle {scraper_time}")

    brief_time = config.get("daily_brief", {}).get("send_time", "08:00")
    schedule.every().day.at(brief_time).do(job_daily_brief)
    print(f"[SCHEDULER] Brief giornaliero: ogni giorno alle {brief_time}")

    schedule.every(30).minutes.do(job_new_video_monitor)
    print(f"[SCHEDULER] Competitor nuovi video: ogni 30 minuti")

    sub_time = config.get("competitor_monitor", {}).get("subscriber_check_time", "09:00")
    schedule.every().day.at(sub_time).do(job_subscriber_growth)
    print(f"[SCHEDULER] Crescita iscritti competitor: ogni giorno alle {sub_time}")

    start_command_listener(
        modules={
            "rss":      run_rss_detector,
            "reddit":   run_reddit_detector,
            "twitter":  run_twitter_detector,
            "trends":   run_trends_detector,
            "comments": run_youtube_comments_detector,
            "scraper":  run_scraper,
        },
        config_fn=load_config
    )

    send_system_message(
        f"✅ Sistema avviato\n"
        f"Trend detector: ogni {interval_hours}h\n"
        f"YouTube scraper: ogni giorno alle {scraper_time}\n"
        f"Competitor monitor: ogni 30 min\n"
        f"Moduli attivi: RSS, Google Trends, YouTube Comments, YouTube Scraper, Twitter/X, Competitor Monitor\n"
        f"In attesa credenziali: Reddit"
    )

    print("\n[MAIN] Scheduler attivo. Premi CTRL+C per fermare.\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    import sys

    print("\n" + "="*50, flush=True)
    print("  YTSPERBOT", flush=True)
    print(f"  Avvio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", flush=True)
    print("="*50 + "\n", flush=True)

    try:
        init_db()
        print("[OK] Database inizializzato", flush=True)
    except Exception as e:
        print(f"[ERRORE] Database: {e}", flush=True)
        sys.exit(1)

    start_health_server()

    if "--test" in sys.argv:
        print("[MAIN] Modalità TEST: esecuzione immediata di tutti i moduli\n")
        run_all_manual()

    elif "--scraper" in sys.argv:
        print("[MAIN] Modalità TEST: solo YouTube Scraper\n")
        config = load_config()
        run_scraper(config)

    elif "--reddit" in sys.argv:
        print("[MAIN] Modalità TEST: solo Reddit Detector\n")
        config = load_config()
        run_reddit_detector(config)

    elif "--rss" in sys.argv:
        print("[MAIN] Modalità TEST: solo RSS Detector\n")
        config = load_config()
        run_rss_detector(config)

    elif "--comments" in sys.argv:
        print("[MAIN] Modalità TEST: solo YouTube Comments\n")
        config = load_config()
        run_youtube_comments_detector(config)

    elif "--trends" in sys.argv:
        print("[MAIN] Modalità TEST: solo Google Trends\n")
        config = load_config()
        run_trends_detector(config)

    elif "--twitter" in sys.argv:
        print("[MAIN] Modalità TEST: solo Twitter/X\n")
        config = load_config()
        run_twitter_detector(config)

    else:
        print("[MAIN] Modalità PRODUZIONE: avvio scheduler\n", flush=True)
        try:
            config = load_config()
            start_scheduler(config)
        except Exception as e:
            print(f"[ERRORE CRITICO] {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.exit(1)
