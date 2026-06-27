"""
database.py — SQLite connection and table management for CareerFit

DB priority (resolved at import time):
  1. backend/careerfit.db  — full dataset (~522 MB, not committed to git)
  2. backend/demo_jobs.db  — demo dataset (~2,500 jobs, committed to git)
  3. None                  — empty mode (no job data available)
"""
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))

_FULL_DB = os.path.join(_HERE, "careerfit.db")
_DEMO_DB = os.path.join(_HERE, "demo_jobs.db")


def _resolve_db_path():
    """Return (path, source_label) for the best available DB.

    Tries to actually open each candidate — os.path.exists() can return True
    for cloud-synced (OneDrive/iCloud) files that aren't downloaded to disk.
    """
    def _can_open(p: str) -> bool:
        try:
            conn = sqlite3.connect(p, timeout=5)
            conn.execute("SELECT COUNT(*) FROM jobs_clean")
            conn.close()
            return True
        except Exception:
            return False

    def _try_or_copy(src_path: str) -> str | None:
        """Return usable path (original or /tmp copy), or None if unreadable."""
        if not os.path.exists(src_path):
            return None
        if _can_open(src_path):
            return src_path
        # Try copying to /tmp (bypasses read-only mount / journal issues)
        import shutil, tempfile
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(src_path))
        try:
            shutil.copy2(src_path, tmp)
            if _can_open(tmp):
                logger.info("DB copied to %s (OneDrive mount workaround)", tmp)
                return tmp
        except Exception as e:
            logger.warning("DB copy to /tmp failed: %s", e)
        return None

    full = _try_or_copy(_FULL_DB)
    if full:
        return full, "full"
    demo = _try_or_copy(_DEMO_DB)
    if demo:
        return demo, "demo"
    return _DEMO_DB, "empty"


DB_PATH, DATA_SOURCE = _resolve_db_path()
logger.info("DB selected: %s (%s)", DB_PATH, DATA_SOURCE)


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass  # read-only mount (e.g. OneDrive sandbox) — continue without WAL
    return conn


def db_exists() -> bool:
    """Return True if the database file exists and has the jobs_clean table."""
    if not os.path.exists(DB_PATH):
        return False
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs_clean'"
        )
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False


def create_tables():
    """Create all required tables if they don't already exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs_clean (
                job_id              TEXT PRIMARY KEY,
                title_clean         TEXT,
                company_clean       TEXT,
                location_clean      TEXT,
                location_area       TEXT,
                job_category        TEXT,
                experience_level_clean TEXT,
                work_type_clean     TEXT,
                is_remote           INTEGER DEFAULT 0,
                salary_min_clean    REAL,
                salary_max_clean    REAL,
                salary_med_clean    REAL,
                salary_display      TEXT,
                description_clean   TEXT,
                required_skills_text TEXT,
                combined_text_for_matching TEXT,
                job_quality_score   REAL DEFAULT 0,
                anomaly_flags       TEXT,
                cluster_id          INTEGER,
                job_posting_url     TEXT,
                application_url     TEXT
            );

            CREATE TABLE IF NOT EXISTS cluster_summaries (
                cluster_id          INTEGER PRIMARY KEY,
                top_keywords        TEXT,
                dominant_categories TEXT,
                top_locations       TEXT,
                job_count           INTEGER,
                suggested_direction TEXT
            );

            CREATE TABLE IF NOT EXISTS analytics_cache (
                key     TEXT PRIMARY KEY,
                value   TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_category   ON jobs_clean(job_category);
            CREATE INDEX IF NOT EXISTS idx_jobs_area       ON jobs_clean(location_area);
            CREATE INDEX IF NOT EXISTS idx_jobs_experience ON jobs_clean(experience_level_clean);
            CREATE INDEX IF NOT EXISTS idx_jobs_remote     ON jobs_clean(is_remote);
            CREATE INDEX IF NOT EXISTS idx_jobs_cluster    ON jobs_clean(cluster_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_quality    ON jobs_clean(job_quality_score);
        """)
    logger.info("Database tables created / verified at %s", DB_PATH)


def get_db_stats() -> dict:
    """Return basic statistics about the database."""
    if not db_exists():
        return {"total_jobs": 0, "categories": {}, "remote_count": 0}
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
        cats  = conn.execute(
            "SELECT job_category, COUNT(*) c FROM jobs_clean GROUP BY job_category ORDER BY c DESC LIMIT 20"
        ).fetchall()
        remote = conn.execute("SELECT COUNT(*) FROM jobs_clean WHERE is_remote=1").fetchone()[0]
        conn.close()
        return {
            "total_jobs": total,
            "categories": {c: n for c, n in cats},
            "remote_count": remote,
        }
    except Exception as e:
        logger.error("get_db_stats error: %s", e)
        return {"total_jobs": 0, "categories": {}, "remote_count": 0}
