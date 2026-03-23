"""
TheVeil Monitor - Main
Orchestratore principale del sistema
"""

import os
import yaml
import schedule
import time
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

load_dotenv()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def job_trend_detector():
    config = load_config()
    run_reddit_detector(config)
    run_twitter_detector(config)
    run_rss_detector(config)
    run_youtube_comments_detector(config)
    run_trends_detector(config)


def job_youtube_scraper():
    config = load_config()
    run_scraper(config)


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

    send_system_message(
        f"✅ Sistema avviato\n"
        f"Trend detector: ogni {interval_hours}h\n"
        f"YouTube scraper: ogni giorno alle {scraper_time}\n"
        f"Moduli attivi: RSS, Google Trends, YouTube Comments, YouTube Scraper, Twitter/X\n"
        f"In attesa credenziali: Reddit"
    )

    print("\n[MAIN] Scheduler attivo. Premi CTRL+C per fermare.\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    import sys

    print("\n" + "="*50)
    print("  TheVeil Monitor")
    print(f"  Avvio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*50 + "\n")

    init_db()

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
        print("[MAIN] Modalità PRODUZIONE: avvio scheduler\n")
        config = load_config()
        start_scheduler(config)
