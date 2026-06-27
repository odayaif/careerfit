"""
database.py — SQLite connection and table management for CareerFit
"""
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

# Resolve DB path relative to this file's location
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "careerfit.db")


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def db_exists() -> bool:
    """Return True if the database file exists and has the jobs_clean table."""
    if not os.path.exists(DB_PATH):
        return False
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs_clean'"
            )
            return cur.fetchone() is not None
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
        return {"status": "missing", "total_jobs": 0}
    try:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
            cats = conn.execute(
                "SELECT job_category, COUNT(*) as cnt FROM jobs_clean GROUP BY job_category ORDER BY cnt DESC LIMIT 5"
            ).fetchall()
            return {
                "status": "ok",
                "total_jobs": total,
                "top_categories": [dict(r) for r in cats],
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "total_jobs": 0}
