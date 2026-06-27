"""
clustering_engine.py — Stage 7: KMeans clustering on combined_text_for_matching.
Run standalone: python backend/clustering_engine.py
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

N_CLUSTERS = 10
SAMPLE_SIZE = 50_000  # cap for TF-IDF matrix in memory


def run_clustering():
    if not os.path.exists(DB_PATH):
        logger.warning("DB not found — skipping clustering")
        return

    logger.info("טוען נתונים לאשכולות...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT job_id, combined_text_for_matching, job_category, location_area
           FROM jobs_clean
           WHERE combined_text_for_matching IS NOT NULL
             AND length(combined_text_for_matching) > 50
             AND job_quality_score > 20
           ORDER BY job_quality_score DESC
           LIMIT ?""",
        (SAMPLE_SIZE,)
    ).fetchall()

    if len(rows) < 100:
        logger.warning("Not enough rows for clustering (%d)", len(rows))
        conn.close()
        return

    job_ids = [r["job_id"] for r in rows]
    texts = [str(r["combined_text_for_matching"]) for r in rows]
    categories = [str(r["job_category"]) for r in rows]
    areas = [str(r["location_area"]) for r in rows]

    logger.info("בונה TF-IDF על %d משרות...", len(texts))
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.decomposition import TruncatedSVD
    import numpy as np

    vec = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.9,
        sublinear_tf=True,
    )
    X = vec.fit_transform(texts)
    feature_names = vec.get_feature_names_out()

    # Reduce dimensions for clustering
    logger.info("מקטין מימד עם SVD...")
    svd = TruncatedSVD(n_components=50, random_state=42)
    X_reduced = svd.fit_transform(X)

    logger.info("מריץ KMeans עם %d אשכולות...", N_CLUSTERS)
    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10, max_iter=300)
    labels = km.fit_predict(X_reduced)

    # Assign labels to database
    logger.info("מעדכן cluster_id במסד הנתונים...")
    updates = [(int(labels[i]), job_ids[i]) for i in range(len(job_ids))]
    conn.executemany("UPDATE jobs_clean SET cluster_id = ? WHERE job_id = ?", updates)
    conn.commit()

    # Generate cluster summaries
    logger.info("מחשב סיכומי אשכולות...")
    from collections import Counter

    cluster_summaries = []
    for c in range(N_CLUSTERS):
        idx = [i for i, l in enumerate(labels) if l == c]
        if not idx:
            continue

        # Top keywords from cluster centroid
        centroid = km.cluster_centers_[c]
        # Map back via SVD inverse
        original_centroid = svd.inverse_transform(centroid.reshape(1, -1))[0]
        top_k_idx = original_centroid.argsort()[-10:][::-1]
        top_keywords = [feature_names[i] for i in top_k_idx]

        # Dominant categories
        cluster_cats = [categories[i] for i in idx]
        cat_counter = Counter(cluster_cats)
        dominant_cats = [cat for cat, _ in cat_counter.most_common(3)]

        # Top locations
        cluster_areas = [areas[i] for i in idx]
        area_counter = Counter(cluster_areas)
        top_areas = [a for a, _ in area_counter.most_common(3)]

        # Suggested career direction
        if dominant_cats:
            direction_map = {
                "דאטה": "אנשי דאטה ואנליטיקס",
                "פיתוח תוכנה": "מפתחי תוכנה",
                "ניתוח מערכות": "מנתחי מערכות ו-BA",
                "מוצר": "מנהלי מוצר",
                "שיווק": "אנשי שיווק דיגיטלי",
                "מכירות": "אנשי מכירות",
                "שירות לקוחות": "שירות לקוחות",
                "משאבי אנוש": "משאבי אנוש וגיוס",
                "כספים": "פיננסים וחשבונאות",
                "ניהול": "תפקידי ניהול",
                "תפעול": "תפעול ולוגיסטיקה",
                "בריאות": "תחום הבריאות",
                "חינוך": "חינוך והדרכה",
                "אחר": "תחומים מגוונים",
            }
            suggested = direction_map.get(dominant_cats[0], dominant_cats[0])
        else:
            suggested = "תחומים מגוונים"

        summary = {
            "cluster_id": c,
            "top_keywords": ", ".join(top_keywords[:7]),
            "dominant_categories": ", ".join(dominant_cats),
            "top_locations": ", ".join(top_areas),
            "job_count": len(idx),
            "suggested_direction": suggested,
        }
        cluster_summaries.append(summary)

        # Save to DB
        conn.execute("""
            INSERT OR REPLACE INTO cluster_summaries
            (cluster_id, top_keywords, dominant_categories, top_locations, job_count, suggested_direction)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (c, summary["top_keywords"], summary["dominant_categories"],
              summary["top_locations"], len(idx), suggested))

    conn.commit()
    conn.close()

    logger.info("✅ Clustering הושלם: %d אשכולות", len(cluster_summaries))
    _write_clustering_report(cluster_summaries, len(texts))


def _write_clustering_report(summaries: list, total: int):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    lines = [
        f"# דו\"ח Clustering — CareerFit",
        f"\n**תאריך:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**סך משרות שאושכלו:** {total:,}",
        f"**מספר אשכולות:** {N_CLUSTERS}",
        "",
        "## למה השתמשנו ב-Clustering?",
        "",
        "Clustering מאפשר לנו לקבץ משרות דומות יחד מבלי שנדרוש תיוג ידני.",
        "הסוכן יכול להשתמש באשכולות להצגת כיוונים קריירה ולהמלצות גיוון.",
        "",
        "## כיצד בוצע הוקטוריזציה?",
        "",
        "1. **TF-IDF** על שדה `combined_text_for_matching` (כותרת + חברה + תיאור + כישורים).",
        "2. **TruncatedSVD** (50 רכיבים) לצמצום מימד לפני KMeans.",
        "3. **KMeans** עם 10 אשכולות, 10 אתחולים, 300 איטרציות מקסימום.",
        "",
        "## אשכולות שנמצאו",
        "",
        "| אשכול | כמות משרות | קטגוריות דומיננטיות | כיוון קריירה מוצע | מיקומים מובילים |",
        "|-------|------------|---------------------|-------------------|-----------------|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['cluster_id']} | {s['job_count']:,} | {s['dominant_categories']} | "
            f"{s['suggested_direction']} | {s['top_locations']} |"
        )

    lines.append("")
    lines.append("## מילות מפתח לפי אשכול")
    lines.append("")
    for s in summaries:
        lines.append(f"### אשכול {s['cluster_id']}: {s['suggested_direction']}")
        lines.append(f"**מילות מפתח:** {s['top_keywords']}")
        lines.append("")

    lines.append("## ערך עסקי לסוכן")
    lines.append("")
    lines.append("- **גיוון המלצות:** הסוכן יכול להציג אשכולות כיוון קריירה.")
    lines.append("- **הבנת שוק העבודה:** כל אשכול מייצג קלאסטר של משרות עם אופי דומה.")
    lines.append("- **חיפוש יעיל:** סינון לפי אשכול מסייע לצמצם מרחב החיפוש.")

    with open(os.path.join(REPORTS_DIR, "clustering_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("clustering_report.md נכתב")


def get_cluster_summaries() -> list:
    """Return cluster summaries from DB."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM cluster_summaries ORDER BY job_count DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_clustering()
    print("✅ Clustering הושלם.")
