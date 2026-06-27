"""
analytics_engine.py — Stage 8: Trends, summaries, and dashboard data.
"""
import sqlite3
import os
import json
import logging

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "careerfit.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_summary() -> dict:
    """Return high-level summary statistics."""
    if not os.path.exists(DB_PATH):
        return _demo_summary()
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
        if total == 0:
            conn.close()
            return _demo_summary()

        cats = [dict(r) for r in conn.execute(
            "SELECT job_category as name, COUNT(*) as count FROM jobs_clean GROUP BY job_category ORDER BY count DESC LIMIT 10"
        ).fetchall()]

        areas = [dict(r) for r in conn.execute(
            "SELECT location_area as name, COUNT(*) as count FROM jobs_clean GROUP BY location_area ORDER BY count DESC LIMIT 10"
        ).fetchall()]

        exp_levels = [dict(r) for r in conn.execute(
            "SELECT experience_level_clean as name, COUNT(*) as count FROM jobs_clean GROUP BY experience_level_clean ORDER BY count DESC"
        ).fetchall()]

        remote = conn.execute("SELECT COUNT(*) FROM jobs_clean WHERE is_remote=1").fetchone()[0]
        no_sal = conn.execute(
            "SELECT COUNT(*) FROM jobs_clean WHERE salary_min_clean IS NULL AND salary_max_clean IS NULL"
        ).fetchone()[0]
        high_quality = conn.execute(
            "SELECT COUNT(*) FROM jobs_clean WHERE job_quality_score >= 70"
        ).fetchone()[0]

        conn.close()
        return {
            "total_jobs": total,
            "top_categories": cats,
            "top_areas": areas,
            "experience_levels": exp_levels,
            "remote_count": remote,
            "remote_pct": round(remote / total * 100, 1),
            "no_salary_count": no_sal,
            "no_salary_pct": round(no_sal / total * 100, 1),
            "high_quality_count": high_quality,
            "high_quality_pct": round(high_quality / total * 100, 1),
        }
    except Exception as e:
        logger.error("get_summary error: %s", e)
        return _demo_summary()


def get_trends() -> dict:
    """Return trend data for dashboard charts."""
    if not os.path.exists(DB_PATH):
        return _demo_trends()
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
        if total == 0:
            conn.close()
            return _demo_trends()

        # Category distribution
        categories = [dict(r) for r in conn.execute(
            "SELECT job_category as label, COUNT(*) as value FROM jobs_clean GROUP BY job_category ORDER BY value DESC"
        ).fetchall()]

        # Area distribution
        areas = [dict(r) for r in conn.execute(
            "SELECT location_area as label, COUNT(*) as value FROM jobs_clean GROUP BY location_area ORDER BY value DESC"
        ).fetchall()]

        # Experience distribution
        experience = [dict(r) for r in conn.execute(
            "SELECT experience_level_clean as label, COUNT(*) as value FROM jobs_clean GROUP BY experience_level_clean ORDER BY value DESC"
        ).fetchall()]

        # Work type distribution
        work_types = [dict(r) for r in conn.execute(
            "SELECT work_type_clean as label, COUNT(*) as value FROM jobs_clean GROUP BY work_type_clean ORDER BY value DESC LIMIT 8"
        ).fetchall()]

        # Remote distribution
        remote_yes = conn.execute("SELECT COUNT(*) FROM jobs_clean WHERE is_remote=1").fetchone()[0]
        remote_dist = [
            {"label": "מרחוק/היברידי", "value": remote_yes},
            {"label": "משרד", "value": total - remote_yes},
        ]

        # Salary stats by category (top 8 cats with salary data)
        sal_by_cat = [dict(r) for r in conn.execute(
            """SELECT job_category as label,
                      AVG(salary_med_clean) as avg_med,
                      COUNT(*) as cnt
               FROM jobs_clean
               WHERE salary_med_clean IS NOT NULL AND salary_med_clean > 0
               GROUP BY job_category
               ORDER BY cnt DESC LIMIT 8"""
        ).fetchall()]

        # Quality distribution
        quality_bins = []
        for lo, hi, label in [(0, 30, "נמוכה"), (30, 60, "בינונית"), (60, 80, "טובה"), (80, 101, "מצוינת")]:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM jobs_clean WHERE job_quality_score >= ? AND job_quality_score < ?",
                (lo, hi)
            ).fetchone()[0]
            quality_bins.append({"label": label, "value": cnt})

        conn.close()
        return {
            "categories": categories,
            "areas": areas,
            "experience": experience,
            "work_types": work_types,
            "remote_distribution": remote_dist,
            "salary_by_category": sal_by_cat,
            "quality_distribution": quality_bins,
        }
    except Exception as e:
        logger.error("get_trends error: %s", e)
        return _demo_trends()


def get_anomalies_summary() -> dict:
    """Return anomaly statistics."""
    from anomaly_engine import detect_anomalies
    return detect_anomalies()


def _demo_summary() -> dict:
    return {
        "total_jobs": 0,
        "top_categories": [],
        "top_areas": [],
        "experience_levels": [],
        "remote_count": 0,
        "remote_pct": 0,
        "no_salary_count": 0,
        "no_salary_pct": 0,
        "high_quality_count": 0,
        "high_quality_pct": 0,
        "demo_mode": True,
        "message": "השרת פעיל, אך קובץ הדאטה לא נמצא. יש להוסיף את הקובץ לנתיב data/archive.zip ולהריץ עיבוד נתונים.",
    }


def _demo_trends() -> dict:
    return {
        "categories": [],
        "areas": [],
        "experience": [],
        "work_types": [],
        "remote_distribution": [],
        "salary_by_category": [],
        "quality_distribution": [],
        "demo_mode": True,
    }
