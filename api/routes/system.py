import os
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from modules.database import get_connection as _get_conn, DB_PATH

router = APIRouter(prefix="/system", tags=["system"])


def _use_apify(platform: str) -> bool:
    """Legge platform.use_apify dal DB (scritto da init_config_from_yaml al boot)."""
    from modules.database import config_get

    row = config_get(f"{platform}.use_apify")
    return bool(row and row["value"].lower() in ("true", "1", "yes"))


def _platform_active(platform: str) -> bool:
    """
    Restituisce True se la piattaforma è operativa:
    - se use_apify=true → basta APIFY_API_KEY
    - altrimenti → controlla le credenziali native
    """
    apify_ok = bool(os.getenv("APIFY_API_KEY"))

    if _use_apify(platform):
        return apify_ok

    if platform == "twitter":
        return bool(os.getenv("TWITTER_BEARER_TOKEN"))
    if platform == "reddit":
        return bool(os.getenv("REDDIT_CLIENT_ID")) and bool(
            os.getenv("REDDIT_CLIENT_SECRET")
        )
    if platform == "pinterest":
        return bool(os.getenv("PINTEREST_ACCESS_TOKEN"))
    return False


@router.get("/status")
def status():
    """Stato del bot: credenziali, dimensione DB, contatori tabelle."""
    credentials = {
        "youtube": bool(os.getenv("YOUTUBE_API_KEY")),
        "twitter": _platform_active("twitter"),
        "reddit": _platform_active("reddit"),
        "apify": bool(os.getenv("APIFY_API_KEY")),
        "news": bool(os.getenv("NEWSAPI_KEY")),
        "pinterest": _platform_active("pinterest"),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }

    conn = _get_conn()
    tables = {}
    for table in [
        "keyword_mentions",
        "apify_profiles",
        "channel_subscribers_history",
        "alerts_log",
        "youtube_outperformer_log",
        "competitor_video_log",
        "reddit_seen_posts",
        "keyword_blacklist",
        "sent_alerts",
    ]:
        try:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            tables[table] = row["n"]
        except Exception:
            tables[table] = 0

    db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

    # ── Attività bot (ultime 24h) ─────────────────────────
    activity = {}
    try:
        activity["reddit_posts_seen_24h"] = conn.execute(
            "SELECT COUNT(*) AS n FROM reddit_seen_posts WHERE seen_at >= datetime('now','-1 day')"
        ).fetchone()["n"]
    except Exception:
        activity["reddit_posts_seen_24h"] = 0
    try:
        activity["yt_videos_seen_24h"] = conn.execute(
            "SELECT COUNT(*) AS n FROM youtube_seen_channels WHERE sent_at >= datetime('now','-1 day')"
        ).fetchone()["n"]
    except Exception:
        activity["yt_videos_seen_24h"] = 0
    try:
        activity["alerts_dedup_24h"] = conn.execute(
            "SELECT COUNT(*) AS n FROM sent_alerts WHERE sent_at >= datetime('now','-1 day')"
        ).fetchone()["n"]
    except Exception:
        activity["alerts_dedup_24h"] = 0
    try:
        activity["alerts_sent_24h"] = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts_log WHERE sent_at >= datetime('now','-1 day')"
        ).fetchone()["n"]
    except Exception:
        activity["alerts_sent_24h"] = 0

    conn.close()

    return {
        "credentials": credentials,
        "tables": tables,
        "db_size_mb": round(db_size_bytes / 1024 / 1024, 2),
        "activity": activity,
    }


@router.get("/schedule")
def schedule():
    """
    Stato dello scheduler: job configurati con frequenza e stato attivo/inattivo.
    Legge gli intervalli dal DB di configurazione.
    """
    from modules.database import config_get

    def _hours(key, default):
        row = config_get(key)
        if row and row["value"]:
            try:
                return float(row["value"])
            except ValueError:
                pass
        return default

    tw_apify = _use_apify("twitter")
    rd_apify = _use_apify("reddit")
    pint_apify = _use_apify("pinterest")

    tw_label = "Twitter/X via Apify" if tw_apify else "Twitter/X via Bearer Token"
    rd_label = "Reddit via Apify" if rd_apify else "Reddit via PRAW"
    pint_label = "Pinterest via Apify" if pint_apify else "Pinterest via API nativa"

    apify_ok = bool(os.getenv("APIFY_API_KEY"))

    interval = _hours("trend_detector.check_interval_hours", 4)
    tw_interval = _hours("twitter.check_interval_hours", interval)
    rd_interval = _hours("reddit.check_interval_hours", 84)
    pint_interval = _hours("pinterest.check_interval_hours", 360)

    jobs = [
        {
            "name": "Trend Detector (RSS / Comments / Google Trends)",
            "freq": f"{interval:g}h",
            "active": True,
        },
        {
            "name": rd_label,
            "freq": f"{rd_interval:g}h",
            "active": apify_ok
            if rd_apify
            else (
                bool(os.getenv("REDDIT_CLIENT_ID"))
                and bool(os.getenv("REDDIT_CLIENT_SECRET"))
            ),
        },
        {
            "name": tw_label,
            "freq": f"{tw_interval:g}h",
            "active": apify_ok if tw_apify else bool(os.getenv("TWITTER_BEARER_TOKEN")),
        },
        {
            "name": "YouTube Scraper (outperformer)",
            "freq": "1×/giorno",
            "active": bool(os.getenv("YOUTUBE_API_KEY")),
        },
        {
            "name": "Competitor Video Monitor",
            "freq": "30 min",
            "active": bool(os.getenv("YOUTUBE_API_KEY")),
        },
        {
            "name": "Subscriber Growth Tracker",
            "freq": "1×/giorno",
            "active": bool(os.getenv("YOUTUBE_API_KEY")),
        },
        {
            "name": "Google Trending RSS",
            "freq": "60 min",
            "active": True,
        },
        {
            "name": "Rising Queries (Google Trends)",
            "freq": "6h",
            "active": True,
        },
        {
            "name": pint_label,
            "freq": f"{pint_interval:g}h",
            "active": apify_ok
            if pint_apify
            else bool(os.getenv("PINTEREST_ACCESS_TOKEN")),
        },
        {
            "name": "News Detector",
            "freq": "6h",
            "active": bool(os.getenv("NEWSAPI_KEY")),
        },
        {
            "name": "Social Scraper TikTok + Instagram (Apify)",
            "freq": "ogni 14 giorni",
            "active": apify_ok,
        },
    ]
    return jobs


@router.post("/run-all")
def run_all():
    """Avvia manualmente tutti i job del bot in background."""
    import threading
    import importlib.util
    import pathlib

    # Locate main.py — it sits one level above the api/ package
    main_path = pathlib.Path(__file__).resolve().parents[2] / "main.py"

    def _run():
        try:
            print("[RUN-ALL] Avvio manuale da dashboard...", flush=True)
            spec = importlib.util.spec_from_file_location("__main_manual__", main_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run_all_manual()
            print("[RUN-ALL] Completato.", flush=True)
        except Exception as exc:
            print(f"[RUN-ALL] Errore: {exc}", flush=True)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"triggered": True}


class RunServicesRequest(BaseModel):
    services: List[str]


@router.post("/run-services")
def run_services(req: RunServicesRequest):
    """Avvia in background i servizi specificati per nome."""
    import threading
    import sys
    import pathlib
    import importlib.util

    if not req.services:
        return {"triggered": False, "error": "Nessun servizio selezionato"}

    main_path = pathlib.Path(__file__).resolve().parents[2] / "main.py"

    def _run():
        try:
            # Prova a riusare il modulo main già caricato nell'ambiente corrente
            main_mod = sys.modules.get("__main__")
            if main_mod and hasattr(main_mod, "run_service"):
                for svc in req.services:
                    main_mod.run_service(svc)
            else:
                spec = importlib.util.spec_from_file_location("__main_svc__", main_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for svc in req.services:
                    mod.run_service(svc)
        except Exception as exc:
            print(f"[RUN-SERVICES] Errore: {exc}", flush=True)

    threading.Thread(target=_run, daemon=True).start()
    return {"triggered": True, "services": req.services}


@router.get("/logs")
def get_logs(
    minutes: int = Query(60, ge=1, le=10080),
    level: str = Query("ALL"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Restituisce i log di sistema con filtro per livello e finestra temporale."""
    from modules.database import get_bot_logs

    logs = get_bot_logs(minutes=minutes, level=level, limit=limit)
    return logs


@router.get("/backup")
def backup():
    """Scarica un dump SQL del DB (stesso formato di /backup su Telegram)."""
    from modules.telegram_commands import _generate_backup_sql

    try:
        sql_bytes, _ = _generate_backup_sql()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"ytsperbot_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.sql"
    return Response(
        content=sql_bytes,
        media_type="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/restore")
async def restore(file: UploadFile = File(...)):
    """Ripristina il DB da un file .sql (stesso formato prodotto da /backup)."""
    if not file.filename.endswith(".sql"):
        raise HTTPException(
            status_code=400, detail="Il file deve avere estensione .sql"
        )

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20 MB limite
        raise HTTPException(status_code=400, detail="File troppo grande (max 20 MB)")

    try:
        sql_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="Il file non è un testo UTF-8 valido"
        )

    conn = _get_conn()
    inserted = skipped = 0
    errors = []

    try:
        for raw in sql_content.split(";"):
            stmt = raw.strip()
            if not stmt:
                continue
            # Strip leading comment lines: the backup format places
            # "-- tablename: N righe" on the line before the first INSERT of
            # each table, so after split(";") they end up in the same chunk.
            non_comment_lines = [
                ln for ln in stmt.split("\n") if not ln.strip().startswith("--")
            ]
            stmt = "\n".join(non_comment_lines).strip()
            if not stmt:
                continue
            if stmt.upper() in ("BEGIN TRANSACTION", "COMMIT", "BEGIN", "END"):
                continue
            try:
                cur = conn.execute(stmt)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                msg = str(e)
                if "UNIQUE constraint" in msg or "already exists" in msg:
                    skipped += 1
                else:
                    errors.append(msg[:200])
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore critico restore: {e}")
    finally:
        conn.close()

    return {"inserted": inserted, "skipped": skipped, "errors": errors}


@router.post("/restart")
def restart():
    """Riavvia il servizio Render via API (stessa logica di /restart su Telegram)."""
    import requests as _req

    render_key = os.getenv("RENDER_API_KEY", "")
    render_service = os.getenv("RENDER_SERVICE_ID", "")

    if not render_key or not render_service:
        raise HTTPException(
            status_code=503,
            detail="Variabili RENDER_API_KEY e/o RENDER_SERVICE_ID non configurate."
        )

    try:
        resp = _req.post(
            f"https://api.render.com/v1/services/{render_service}/restart",
            headers={"Authorization": f"Bearer {render_key}", "Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code not in (200, 202):
            raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"restarted": True}


@router.get("/db-stats")
def db_stats():
    """Statistiche sintetiche del database."""
    conn = _get_conn()
    result = {}
    for table in [
        "keyword_mentions",
        "apify_profiles",
        "channel_subscribers_history",
        "alerts_log",
        "youtube_outperformer_log",
        "competitor_video_log",
    ]:
        try:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            result[table] = row["n"]
        except Exception:
            result[table] = 0
    conn.close()
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    result["db_size_mb"] = round(db_size / 1024 / 1024, 2)
    return result
