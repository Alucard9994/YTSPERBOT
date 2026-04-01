from fastapi import APIRouter
from modules.database import get_connection as _get_conn

router = APIRouter(prefix="/pinterest", tags=["pinterest"])


@router.get("/trends")
def pinterest_trends(hours: int = 168):
    """
    Pinterest keyword trends con crescita % e tipo (growing/emerging).
    Calcola la variazione dall'inizio alla fine della finestra temporale.
    """
    conn = _get_conn()

    rows = conn.execute(
        """
        SELECT
            keyword,
            MIN(count)          AS val_first,
            MAX(count)          AS val_last,
            COUNT(*)            AS data_points,
            MAX(recorded_at)    AS last_seen
        FROM keyword_mentions
        WHERE source LIKE 'pinterest_%'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY val_last DESC
    """,
        (f"-{hours}",),
    ).fetchall()

    # Identifiers con tipo emerging dalle notifiche
    emerging_ids = conn.execute("""
        SELECT identifier FROM sent_alerts
        WHERE alert_type = 'pinterest_emerging'
        AND sent_at >= datetime('now', '-30 days')
    """).fetchall()
    conn.close()

    # Costruisci set di keyword emerging
    emerging_kws = set()
    for row in emerging_ids:
        ident = row["identifier"] if hasattr(row, "__getitem__") else row[0]
        parts = ident.split("_", 3)  # ['pinterest', 'emerging', 'XX', 'keyword...']
        if len(parts) >= 4:
            emerging_kws.add(parts[3].lower())
        elif len(parts) == 3:
            emerging_kws.add(parts[2].lower())

    items = []
    for r in rows:
        r = dict(r)
        kw = r["keyword"]
        growth_pct = (
            round(((r["val_last"] - r["val_first"]) / r["val_first"]) * 100, 1)
            if r["val_first"] > 0
            else 0.0
        )
        is_emerging = kw.lower()[:40] in emerging_kws or growth_pct >= 50
        items.append({
            "keyword":    kw,
            "saves":      r["val_last"],
            "growth_pct": growth_pct,
            "last_seen":  r["last_seen"],
            "trend_type": "emerging" if is_emerging else "growing",
        })

    items.sort(key=lambda x: x["saves"], reverse=True)
    return items


@router.get("/alerts")
def pinterest_alerts(hours: int = 168):
    """Alert Pinterest (growing + emerging + velocity)."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, alert_type, velocity_pct, extra_json, sent_at
        FROM alerts_log
        WHERE alert_type IN ('pinterest_trend', 'pinterest_emerging', 'pinterest_velocity')
        AND sent_at >= datetime('now', ? || ' hours')
        ORDER BY sent_at DESC
        LIMIT 30
    """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword-counts")
def keyword_counts(hours: int = 168):
    """Menzioni keyword dalla fonte Pinterest."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT keyword, SUM(count) AS total, MAX(recorded_at) AS last_seen
        FROM keyword_mentions
        WHERE source LIKE '%pinterest%'
        AND recorded_at >= datetime('now', ? || ' hours')
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT 20
    """,
        (f"-{hours}",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
