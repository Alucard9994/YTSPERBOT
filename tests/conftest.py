"""
Root conftest — imposta YTSPERBOT_DB_PATH prima che qualsiasi modulo
dell'applicazione venga importato. pytest carica questo file per primo.
"""

import os
import tempfile
import pytest

# ── Punta il DB a un file temporaneo dedicato ai test ──────────────────────
# DEVE essere impostato a livello di modulo (prima degli import dei moduli app)
_TEST_DB_DIR = tempfile.mkdtemp(prefix="ytsperbot_test_")
_TEST_DB_PATH = os.path.join(_TEST_DB_DIR, "test.db")
os.environ["YTSPERBOT_DB_PATH"] = _TEST_DB_PATH


# ── Fixture: inizializza il DB una sola volta per sessione ──────────────────
@pytest.fixture(scope="session", autouse=True)
def test_db():
    from modules.database import init_db

    init_db()
    yield _TEST_DB_PATH


# ── Fixture: pulisce le tabelle dati tra un test e l'altro ─────────────────
# Le tabelle di schema (config_params, config_lists) restano intatte.
_DATA_TABLES = [
    "keyword_mentions",
    "alerts_log",
    "youtube_outperformer_log",
    "competitor_video_log",
    "channel_subscribers_history",
    "apify_profiles",
    "sent_alerts",
    "reddit_seen_posts",
]


@pytest.fixture(autouse=True)
def clean_db(test_db):
    """Tronca le tabelle dati prima di ogni test."""
    from modules.database import get_connection

    conn = get_connection()
    for table in _DATA_TABLES:
        try:
            conn.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    yield
