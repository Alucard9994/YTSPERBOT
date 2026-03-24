"""
TheVeil Monitor - Main
Orchestratore principale del sistema
"""

import os
import yaml
import schedule
import time
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from dotenv import load_dotenv

from modules.database import init_db
from modules.telegram_bot import send_system_message
from modules.youtube_scraper import run_scraper
from modules.reddit_detector import run_reddit_detector
from modules.rss_detector import run_rss_detector
from modules.youtube_comments import run_youtube_comments_detector
from modules.trends_detector import run_trends_detector, run_trending_rss_monitor, run_rising_queries_detector
from modules.twitter_detector import run_twitter_detector
from modules.telegram_commands import start_command_listener
from modules.telegram_bot import send_daily_brief
from modules.database import get_daily_brief_data
from modules.competitor_monitor import run_new_video_monitor, run_subscriber_growth_monitor
from modules.pinterest_detector import run_pinterest_detector
from modules.cross_signal import run_cross_signal_detector
from modules.news_detector import run_news_detector
from modules.apify_scraper import run_apify_scraper

load_dotenv()


class HealthHandler(BaseHTTPRequestHandler):
    def _check_token(self) -> bool:
        """Verifica il token segreto nella query string. Se non configurato, nega sempre."""
        required = os.getenv("DASHBOARD_TOKEN", "")
        if not required:
            return False  # nessun token configurato → accesso negato
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        provided = query.get("token", [""])[0]
        return provided == required

    def _forbidden(self):
        body = b"<h1>403 Forbidden</h1><p>Token mancante o non valido.</p>"
        self.send_response(403)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path  # ignora query string per il routing
        if path == "/dashboard":
            if not self._check_token():
                self._forbidden()
                return
            self._serve_dashboard()
        elif path == "/dashboard/data":
            if not self._check_token():
                self._forbidden()
                return
            self._serve_dashboard_data()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    def _serve_dashboard_data(self):
        """Restituisce le top keyword in formato JSON."""
        try:
            from modules.database import get_daily_brief_data
            data = get_daily_brief_data(hours=168)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def _serve_dashboard(self):
        """Serve la dashboard HTML con le top keyword degli ultimi 7 giorni."""
        try:
            from modules.database import get_daily_brief_data
            data = get_daily_brief_data(hours=168)
        except Exception:
            data = []

        rows_html = ""
        for i, row in enumerate(data, 1):
            heat = "🔥🔥" if row["source_count"] >= 4 else "🔥" if row["source_count"] >= 2 else ""
            rows_html += (
                f"<tr>"
                f"<td>{i}</td>"
                f"<td><strong>{row['keyword']}</strong></td>"
                f"<td>{row['total_mentions']}</td>"
                f"<td>{row['source_count']}</td>"
                f"<td>{heat} {row.get('sources','')[:60]}</td>"
                f"</tr>"
            )

        html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YTSPERBOT Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; margin: 0; padding: 20px; }}
  h1 {{ color: #e94560; margin-bottom: 4px; }}
  p.sub {{ color: #aaa; margin: 0 0 20px; font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; }}
  th {{ background: #e94560; color: white; padding: 10px 14px; text-align: left; font-size: 13px; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #2a2a4a; font-size: 13px; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #1f2f5a; }}
  .badge {{ display: inline-block; background: #e94560; color: white; border-radius: 12px;
            padding: 2px 8px; font-size: 11px; margin-right: 4px; }}
</style>
</head>
<body>
<h1>🤖 YTSPERBOT Dashboard</h1>
<p class="sub">Top keyword ultime 7 giorni — {datetime.now().strftime("%d/%m/%Y %H:%M")} UTC</p>
<table>
  <thead>
    <tr><th>#</th><th>Keyword</th><th>Menzioni</th><th>Fonti</th><th>Piattaforme</th></tr>
  </thead>
  <tbody>
    {rows_html if rows_html else '<tr><td colspan="5" style="text-align:center;color:#aaa">Nessun dato ancora — aspetta il primo ciclo del bot.</td></tr>'}
  </tbody>
</table>
</body>
</html>"""

        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

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
    # Dopo ogni ciclo trend, controlla convergenza multi-piattaforma
    run_cross_signal_detector(config)


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


def job_trending_rss():
    config = load_config()
    run_trending_rss_monitor(config)


def job_pinterest():
    config = load_config()
    run_pinterest_detector(config)


def job_rising_queries():
    config = load_config()
    run_rising_queries_detector(config)


def job_news():
    config = load_config()
    run_news_detector(config)


def job_apify_scraper():
    config = load_config()
    run_apify_scraper(config)


def job_weekly_report():
    from modules.database import get_daily_brief_data
    from modules.telegram_bot import send_weekly_brief
    data = get_daily_brief_data(hours=168)
    send_weekly_brief(data)


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

    apify_time = config.get("apify_scraper", {}).get("run_time", "04:00")
    schedule.every().day.at(apify_time).do(job_apify_scraper)
    print(f"[SCHEDULER] Apify social scraper (TikTok + Instagram): ogni giorno alle {apify_time}")

    brief_time = config.get("daily_brief", {}).get("send_time", "08:00")
    schedule.every().day.at(brief_time).do(job_daily_brief)
    print(f"[SCHEDULER] Brief giornaliero: ogni giorno alle {brief_time}")

    schedule.every(30).minutes.do(job_new_video_monitor)
    print(f"[SCHEDULER] Competitor nuovi video: ogni 30 minuti")

    trending_interval = config.get("trending_rss", {}).get("check_interval_minutes", 60)
    schedule.every(trending_interval).minutes.do(job_trending_rss)
    print(f"[SCHEDULER] Google Trending RSS: ogni {trending_interval} minuti")

    rising_interval = config.get("rising_queries", {}).get("check_interval_hours", 6)
    schedule.every(rising_interval).hours.do(job_rising_queries)
    print(f"[SCHEDULER] Rising queries: ogni {rising_interval} ore")

    pinterest_interval = config.get("pinterest", {}).get("check_interval_hours", 6)
    schedule.every(pinterest_interval).hours.do(job_pinterest)
    print(f"[SCHEDULER] Pinterest detector: ogni {pinterest_interval} ore")

    sub_time = config.get("competitor_monitor", {}).get("subscriber_check_time", "09:00")
    schedule.every().day.at(sub_time).do(job_subscriber_growth)
    print(f"[SCHEDULER] Crescita iscritti competitor: ogni giorno alle {sub_time}")

    news_interval = config.get("news_api", {}).get("check_interval_hours", 6)
    schedule.every(news_interval).hours.do(job_news)
    print(f"[SCHEDULER] News detector: ogni {news_interval} ore")

    weekly_day = config.get("weekly_report", {}).get("send_day", "sunday")
    weekly_time = config.get("weekly_report", {}).get("send_time", "09:00")
    getattr(schedule.every(), weekly_day).at(weekly_time).do(job_weekly_report)
    print(f"[SCHEDULER] Report settimanale: ogni {weekly_day} alle {weekly_time}")

    start_command_listener(
        modules={
            "rss":                run_rss_detector,
            "reddit":             run_reddit_detector,
            "twitter":            run_twitter_detector,
            "trends":             run_trends_detector,
            "comments":           run_youtube_comments_detector,
            "scraper":            run_scraper,
            "new_video":          run_new_video_monitor,
            "subscriber_growth":  run_subscriber_growth_monitor,
            "pinterest":          run_pinterest_detector,
            "cross_signal":       run_cross_signal_detector,
            "news":               run_news_detector,
            "social":             run_apify_scraper,
        },
        config_fn=load_config
    )

    # Verifica credenziali disponibili
    _yt      = bool(os.getenv("YOUTUBE_API_KEY"))
    _reddit  = bool(os.getenv("REDDIT_CLIENT_ID")) and bool(os.getenv("REDDIT_CLIENT_SECRET"))
    _tw      = bool(os.getenv("TWITTER_BEARER_TOKEN"))
    _news    = bool(os.getenv("NEWSAPI_KEY"))
    _apify   = bool(os.getenv("APIFY_API_KEY"))
    _ai      = bool(os.getenv("ANTHROPIC_API_KEY"))

    def _i(ok): return "✅" if ok else "❌"

    send_system_message(
        f"✅ <b>Sistema avviato</b>\n\n"
        f"<b>🔄 Cicli automatici:</b>\n"
        f"{_i(True)} RSS + Google Trends + Trending RSS + Cross-signal: ogni {interval_hours}h / {trending_interval}min\n"
        f"{_i(_yt)} YouTube Comments + Competitor monitor: ogni {interval_hours}h\n"
        f"{_i(_reddit)} Reddit detector: ogni {interval_hours}h\n"
        f"{_i(_tw)} Twitter/X detector: ogni {interval_hours}h\n"
        f"{_i(True)} Rising queries: ogni {rising_interval}h\n"
        f"{_i(True)} Pinterest: ogni {pinterest_interval}h\n"
        f"{_i(_news)} News detector: ogni {news_interval}h\n"
        f"{_i(_yt)} Competitor nuovi video: ogni 30 min\n"
        f"{_i(_yt)} YouTube Scraper (outperformer): ogni giorno alle {scraper_time}\n"
        f"{_i(_apify)} Social scraper TikTok+IG: ogni giorno alle {apify_time}\n"
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
