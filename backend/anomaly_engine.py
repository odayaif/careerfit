"""
anomaly_engine.py — Stage 8: Detect anomalies in job postings dataset.
Run standalone: python backend/anomaly_engine.py
"""
import sqlite3
import os
import logging
import json
import datetime

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
DB_PATH = os.path.join(_HERE, "careerfit.db")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")


def detect_anomalies() -> dict:
    """Run all anomaly checks and return summary dict."""
    if not os.path.exists(DB_PATH):
        return {"error": "מסד הנתונים לא נמצא"}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
    if total == 0:
        conn.close()
        return {"error": "אין נתונים"}

    results = {"total_jobs": total, "anomalies": {}}

    # 1. No salary
    no_sal = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE salary_min_clean IS NULL AND salary_max_clean IS NULL"
    ).fetchone()[0]
    results["anomalies"]["ללא שכר"] = {"count": no_sal, "pct": round(no_sal / total * 100, 1)}

    # 2. Very high salary (annual > $500k)
    high_sal = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE salary_max_clean > 500000"
    ).fetchone()[0]
    results["anomalies"]["שכר גבוה חריג"] = {"count": high_sal, "pct": round(high_sal / total * 100, 1)}

    # 3. Very low salary (annual < $10k)
    low_sal = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE salary_min_clean < 10000 AND salary_min_clean IS NOT NULL"
    ).fetchone()[0]
    results["anomalies"]["שכר נמוך חריג"] = {"count": low_sal, "pct": round(low_sal / total * 100, 1)}

    # 4. Missing or very short description
    no_desc = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE description_clean IS NULL OR length(description_clean) < 50"
    ).fetchone()[0]
    results["anomalies"]["תיאור חסר/קצר"] = {"count": no_desc, "pct": round(no_desc / total * 100, 1)}

    # 5. Low quality score
    low_quality = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE job_quality_score < 30"
    ).fetchone()[0]
    results["anomalies"]["איכות נמוכה"] = {"count": low_quality, "pct": round(low_quality / total * 100, 1)}

    # 6. Unknown company
    no_company = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE company_clean = 'לא ידוע' OR company_clean IS NULL"
    ).fetchone()[0]
    results["anomalies"]["חברה לא ידועה"] = {"count": no_company, "pct": round(no_company / total * 100, 1)}

    # 7. Unknown location
    no_location = conn.execute(
        "SELECT COUNT(*) FROM jobs_clean WHERE location_area = 'אחר' OR location_clean = 'לא ידוע'"
    ).fetchone()[0]
    results["anomalies"]["מיקום לא מזוהה"] = {"count": no_location, "pct": round(no_location / total * 100, 1)}

    # 8. Rare categories (< 0.5% of total)
    cats = conn.execute(
        "SELECT job_category, COUNT(*) c FROM jobs_clean GROUP BY job_category ORDER BY c ASC"
    ).fetchall()
    rare = [(r["job_category"], r["c"]) for r in cats if r["c"] < total * 0.005]
    results["anomalies"]["קטגוריות נדירות"] = {
        "count": len(rare),
        "categories": [f"{cat} ({cnt:,})" for cat, cnt in rare[:5]],
    }

    # 9. Jobs with many anomaly flags
    multi_flags = conn.execute(
        """SELECT COUNT(*) FROM jobs_clean
           WHERE length(anomaly_flags) - length(replace(anomaly_flags, '|', '')) >= 2"""
    ).fetchone()[0]
    results["anomalies"]["ריבוי דגלי בעיה"] = {"count": multi_flags, "pct": round(multi_flags / total * 100, 1)}

    conn.close()
    _write_anomaly_report(results)
    return results


def _write_anomaly_report(data: dict):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    total = data.get("total_jobs", 0)
    anomalies = data.get("anomalies", {})

    lines = [
        f"# דו\"ח אנומליות — CareerFit",
        f"\n**תאריך:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**סך משרות:** {total:,}",
        "",
        "## ממצאי האנומליות",
        "",
        "| סוג בעיה | כמות | אחוז |",
        "|----------|------|------|",
    ]

    for name, val in anomalies.items():
        cnt = val.get("count", 0)
        pct = val.get("pct", "")
        if isinstance(pct, float):
            lines.append(f"| {name} | {cnt:,} | {pct}% |")
        else:
            lines.append(f"| {name} | {cnt} | — |")

    lines += [
        "",
        "## ניתוח ממצאים",
        "",
        "### שכר חסר",
        f"רוב המשרות ({anomalies.get('ללא שכר', {}).get('pct', '?')}%) לא כוללות מידע שכר.",
        "הסיבות הנפוצות: מדיניות חברה, שכר תלוי-ניסיון, גמישות במשא ומתן.",
        "",
        "### שכר חריג",
        "משרות עם שכר חריג גבוה עשויות להיות שכר שנתי של ניהול בכיר, או שגיאת הזנה.",
        "משרות עם שכר חריג נמוך עשויות להיות שכר שעתי שלא הומר נכון.",
        "",
        "### תיאורים חסרים",
        "משרות ללא תיאור מספק מקבלות ציון איכות נמוך ומסוננות בחיפוש.",
        "",
        "## השפעה על הסוכן",
        "",
        "- משרות עם `job_quality_score < 30` לא מוחזרות בחיפוש הרגיל.",
        "- אנומליות שכר מוצגות כאזהרה בכרטיס המשרה.",
        "- שדה `anomaly_flags` מאפשר לסנן בקלות.",
    ]

    with open(os.path.join(REPORTS_DIR, "anomaly_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("anomaly_report.md נכתב")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = detect_anomalies()
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("✅ anomaly_engine הושלם.")
