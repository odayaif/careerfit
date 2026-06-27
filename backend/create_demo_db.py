"""
create_demo_db.py — Build a large representative demo database for Render deployment.

Strategy:
  Phase 1 (curated) — sample top-quality jobs by category, title keywords, and
                       all Israel-possible-remote jobs. (~2,500–3,000 jobs)
  Phase 2 (fill)    — add random jobs from the full DB until reaching FILL_TARGET.
  Size check        — after VACUUM, trim to stay under HARD_LIMIT_MB if needed.

Goal:
  ≥ 20,000 jobs, ≤ 95 MB, identical schema to careerfit.db.

Usage:
    python backend/create_demo_db.py
"""
import sqlite3
import os
import sys
import shutil
import logging
import tempfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DB  = os.path.join(_HERE, "careerfit.db")
DEST_DB = os.path.join(_HERE, "demo_jobs.db")

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

FILL_TARGET   = 25_000   # aim for this many unique jobs total
MIN_TARGET    = 20_000   # must reach at least this many
HARD_LIMIT_MB = 95       # hard maximum file size

# ---------------------------------------------------------------------------
# Phase 1 — curated sampling plan
# ---------------------------------------------------------------------------

CATEGORY_SAMPLES = {
    "דאטה":            300,
    "פיתוח תוכנה":    400,
    "מכירות":          250,
    "ניהול":           250,
    "שיווק":           250,
    "משאבי אנוש":     200,
    "כספים":           200,
    "מוצר":            200,
    "שירות לקוחות":   150,
    "בריאות":          150,
    "ניתוח מערכות":   150,
    "חינוך":           150,
    "תפעול":           120,
    "אחר":             120,
}

TITLE_KEYWORD_SAMPLES = [
    ("QA / Testing",
     ["qa ", "quality assurance", "quality engineer", "test engineer",
      "software tester", "sdet", "automation tester", "qc "],
     150),
    ("Cyber / Security",
     ["cyber", "security engineer", "information security", "infosec",
      "penetration", "soc analyst", "threat", "vulnerability",
      "security analyst", "network security"],
     150),
]

REMOTE_TOTAL_TARGET = 400  # remote jobs to include in curated phase

ISRAEL_COMPANY_KEYWORDS = [
    "cyberark", "sentinelone", "monday.com", "nice systems", "nice ltd",
    "au10tix", "telco systems", "shoukhon", "check point", "wix",
    "varonis", "solaredge technologies", "elbit systems", "amdocs", "cellebrite",
    "fiverr", "gett", "riskified", "appsflyer", "mobileye",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kw_like(kws):
    return " OR ".join(
        f"LOWER(title_clean) LIKE '%{k.lower()}%'" for k in kws
    )


def _open_src(path):
    """Open source DB, copying to temp if direct open fails (e.g. OneDrive mount)."""
    try:
        c = sqlite3.connect(path)
        c.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()  # smoke test
        c.row_factory = sqlite3.Row
        logger.info("Opened source DB directly: %s", path)
        return c, None
    except Exception:
        tmp = tempfile.mktemp(suffix=".db")
        logger.info("Direct open failed — copying to temp: %s", tmp)
        shutil.copy2(path, tmp)
        c = sqlite3.connect(tmp)
        c.row_factory = sqlite3.Row
        return c, tmp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def create_demo_db():
    if not os.path.exists(SRC_DB):
        logger.error("Source DB not found: %s", SRC_DB)
        logger.error("Run the data pipeline first: python backend/data_pipeline.py")
        sys.exit(1)

    if os.path.exists(DEST_DB):
        os.remove(DEST_DB)
        logger.info("Removed existing demo_jobs.db")

    src, _tmp = _open_src(SRC_DB)

    # ── Copy schema ──────────────────────────────────────────────────────────
    dest = sqlite3.connect(DEST_DB)
    logger.info("Copying schema...")
    for row in src.execute(
        "SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL"
    ).fetchall():
        try:
            dest.execute(row[0])
        except Exception:
            pass
    dest.commit()

    # ── Phase 1: curated samples ─────────────────────────────────────────────
    seen_ids = set()
    all_jobs = []

    def add_rows(rows, label):
        added = 0
        for r in rows:
            jid = r["job_id"] if hasattr(r, "__getitem__") else r[0]
            if isinstance(r, sqlite3.Row):
                job = dict(r)
            else:
                job = r
            if jid not in seen_ids:
                seen_ids.add(jid)
                all_jobs.append(job)
                added += 1
        logger.info("  %-36s +%d  (total %d)", label, added, len(all_jobs))

    logger.info("=== Phase 1: curated sampling ===")

    for cat, limit in CATEGORY_SAMPLES.items():
        rows = src.execute(
            "SELECT * FROM jobs_clean WHERE job_category = ? "
            "ORDER BY job_quality_score DESC LIMIT ?", (cat, limit)
        ).fetchall()
        add_rows(rows, f"category={cat}")

    for label, kws, limit in TITLE_KEYWORD_SAMPLES:
        cond = _kw_like(kws)
        rows = src.execute(
            f"SELECT * FROM jobs_clean WHERE ({cond}) "
            f"ORDER BY job_quality_score DESC LIMIT ?", (limit,)
        ).fetchall()
        add_rows(rows, label)

    # Israel-possible-remote — ALL of them
    il_cond = " OR ".join(f"LOWER(company_clean) LIKE '%{k}%'" for k in ISRAEL_COMPANY_KEYWORDS)
    rows = src.execute(
        f"SELECT * FROM jobs_clean WHERE is_remote=1 AND ({il_cond}) "
        f"ORDER BY job_quality_score DESC"
    ).fetchall()
    add_rows(rows, "Israel-company remote (ALL)")

    # Top remote jobs (fill up to REMOTE_TOTAL_TARGET)
    current_remote = sum(1 for j in all_jobs if j.get("is_remote"))
    need_remote = max(0, REMOTE_TOTAL_TARGET - current_remote)
    if need_remote > 0:
        rows = src.execute(
            "SELECT * FROM jobs_clean WHERE is_remote=1 "
            "ORDER BY job_quality_score DESC LIMIT ?", (need_remote + 100,)
        ).fetchall()
        add_rows(rows, f"remote top-quality fill")

    curated_count = len(all_jobs)
    logger.info("Phase 1 complete: %d curated jobs", curated_count)

    # ── Phase 2: random fill ─────────────────────────────────────────────────
    still_needed = FILL_TARGET - curated_count
    logger.info("=== Phase 2: random fill (need ~%d more to reach %d) ===",
                still_needed, FILL_TARGET)

    if still_needed > 0:
        # Build exclusion set as SQL list (batched to avoid hitting SQLite limits)
        excluded = list(seen_ids)
        total_src = src.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
        available = total_src - len(excluded)
        fetch_count = min(still_needed + 2000, available)  # overfetch for dedup safety

        # SQLite handles large NOT IN poorly; use a temp exclusion table instead
        src.execute("CREATE TEMP TABLE IF NOT EXISTS _seen (job_id TEXT PRIMARY KEY)")
        BATCH = 5000
        for i in range(0, len(excluded), BATCH):
            batch = excluded[i:i+BATCH]
            src.executemany("INSERT OR IGNORE INTO _seen VALUES (?)", [(x,) for x in batch])

        rows = src.execute(
            "SELECT * FROM jobs_clean "
            "WHERE job_id NOT IN (SELECT job_id FROM _seen) "
            "ORDER BY RANDOM() "
            f"LIMIT {fetch_count}"
        ).fetchall()
        src.execute("DROP TABLE IF EXISTS _seen")

        add_rows(rows, f"random fill (random sample)")

    src.close()
    if _tmp and os.path.exists(_tmp):
        os.remove(_tmp)

    total_collected = len(all_jobs)
    logger.info("Total unique jobs collected: %d", total_collected)

    # ── Write to demo DB ─────────────────────────────────────────────────────
    cols = [
        "job_id", "title_clean", "company_clean", "location_clean", "location_area",
        "job_category", "experience_level_clean", "work_type_clean", "is_remote",
        "salary_min_clean", "salary_max_clean", "salary_med_clean", "salary_display",
        "description_clean", "required_skills_text", "combined_text_for_matching",
        "job_quality_score", "anomaly_flags", "cluster_id", "job_posting_url",
        "application_url",
    ]
    ph = ", ".join("?" * len(cols))
    cl = ", ".join(cols)

    logger.info("Writing %d jobs to demo_jobs.db...", total_collected)
    dest.executemany(
        f"INSERT OR IGNORE INTO jobs_clean ({cl}) VALUES ({ph})",
        [[j.get(c) for c in cols] for j in all_jobs]
    )
    dest.commit()

    # VACUUM to compact the file
    logger.info("Running VACUUM...")
    dest.execute("VACUUM")
    dest.commit()

    # ── Size check & trim if needed ──────────────────────────────────────────
    size_mb = os.path.getsize(DEST_DB) / 1_048_576
    logger.info("After VACUUM: %.1f MB, %d jobs",
                size_mb, dest.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0])

    if size_mb > HARD_LIMIT_MB:
        # Calculate how many jobs fit within the hard limit
        current_count = dest.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
        keep_ratio = (HARD_LIMIT_MB * 0.95) / size_mb   # target 95% of limit for buffer
        keep_count = int(current_count * keep_ratio)
        logger.warning(
            "File is %.1f MB — over limit! Trimming to %d jobs (%.0f%%)...",
            size_mb, keep_count, keep_ratio * 100
        )
        dest.execute(
            f"""DELETE FROM jobs_clean WHERE job_id NOT IN (
                    SELECT job_id FROM jobs_clean
                    ORDER BY job_quality_score DESC
                    LIMIT {keep_count}
                )"""
        )
        dest.commit()
        dest.execute("VACUUM")
        dest.commit()
        size_mb = os.path.getsize(DEST_DB) / 1_048_576
        logger.info("After trim + VACUUM: %.1f MB", size_mb)

    # ── Final stats ──────────────────────────────────────────────────────────
    final_count = dest.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
    cats = dest.execute(
        "SELECT job_category, COUNT(*) c FROM jobs_clean "
        "GROUP BY job_category ORDER BY c DESC"
    ).fetchall()
    remote_n = dest.execute("SELECT COUNT(*) FROM jobs_clean WHERE is_remote=1").fetchone()[0]
    il_possible = dest.execute(
        f"SELECT COUNT(*) FROM jobs_clean WHERE is_remote=1 AND ({il_cond})"
    ).fetchone()[0]
    size_mb = os.path.getsize(DEST_DB) / 1_048_576

    dest.close()

    target_reached = final_count >= MIN_TARGET

    print()
    print("=" * 55)
    print(f"  demo_jobs.db complete")
    print("=" * 55)
    print(f"  Jobs:              {final_count:,}")
    print(f"  File size:         {size_mb:.1f} MB")
    print(f"  Remote jobs:       {remote_n:,}")
    print(f"  Israel-possible:   {il_possible:,}")
    print(f"  Under 95 MB limit: {'✅ YES' if size_mb < HARD_LIMIT_MB else '❌ NO'}")
    print(f"  ≥{MIN_TARGET:,} job target: {'✅ REACHED' if target_reached else '❌ NOT REACHED'}")
    print()
    print("  Category distribution:")
    for cat, cnt in cats:
        print(f"    {cat or '(null)':<28} {cnt:>6,}")
    print()
    print(f"  Path: {DEST_DB}")

    if not target_reached:
        logger.warning("Target of %d jobs NOT reached (got %d). "
                       "Source DB may have fewer jobs than expected.", MIN_TARGET, final_count)
    if size_mb >= HARD_LIMIT_MB:
        logger.error("File is %.1f MB — OVER the %.0f MB hard limit!", size_mb, HARD_LIMIT_MB)
        sys.exit(1)

    return final_count, size_mb


if __name__ == "__main__":
    create_demo_db()
