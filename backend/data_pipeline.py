"""
data_pipeline.py — Stage 2: Clean postings.csv and build SQLite jobs_clean table.
Run standalone: python backend/data_pipeline.py

Handles 3.3M rows via chunked processing.
"""
import zipfile
import os
import sys
import io
import re
import datetime
import logging
import pandas as pd
import numpy as np
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
ZIP_PATH = os.path.join(PROJECT_ROOT, "data", "archive.zip")
DB_PATH = os.path.join(_HERE, "careerfit.db")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")

CHUNK_SIZE = 50_000
MAX_ROWS = None  # None = all rows; set integer to cap for testing


# ---------------------------------------------------------------------------
# Location mapping
# ---------------------------------------------------------------------------

AREA_KEYWORDS = {
    "מרחוק": [
        "remote", "מרחוק", "hybrid remote", "worldwide", "anywhere",
        "work from home", "wfh", "fully remote", "telecommute",
    ],
    "תל אביב": ["tel aviv", "tel-aviv", "תל אביב", "תל-אביב", "jaffa"],
    "השרון": [
        "הרצליה", "herzliya", "רעננה", "ra'anana", "raanana",
        "כפר סבא", "kfar saba", "הוד השרון", "hod hasharon",
        "רמת השרון", "ramat hasharon", "נתניה", "netanya",
        "חדרה", "hadera", "כפר יונה",
    ],
    "המרכז": [
        "רמת גן", "ramat gan", "גבעתיים", "givatayim",
        "פתח תקווה", "petah tikva", "בני ברק", "bnei brak",
        "קריית אונו", "kiryat ono", "אור יהודה", "or yehuda",
        "חולון", "holon", "בת ים", "bat yam",
        "center", "המרכז", "central",
    ],
    "השפלה": [
        "ראשון לציון", "rishon lezion", "rishon", "רחובות", "rehovot",
        "נס ציונה", "nes ziona", "לוד", "lod", "רמלה", "ramla",
        "יבנה", "yavne", "מודיעין", "modiin", "השפלה",
    ],
    "ירושלים": [
        "ירושלים", "jerusalem", "בית שמש", "beit shemesh",
        "מבשרת ציון",
    ],
    "הצפון": [
        "חיפה", "haifa", "יקנעם", "yokneam", "נצרת", "nazareth",
        "כרמיאל", "karmiel", "עפולה", "afula", "טבריה", "tiberias",
        "נהריה", "nahariya", "עכו", "acre", "קריית", "kiriat",
        "north", "צפון", "northern",
    ],
    "הדרום": [
        "באר שבע", "beer sheva", "beersheba", "אשדוד", "ashdod",
        "אשקלון", "ashkelon", "אילת", "eilat", "דימונה", "dimona",
        "קריית גת", "kiryat gat", "south", "דרום", "southern",
        "sderot", "שדרות",
    ],
}


def map_location_to_area(location_text: str) -> str:
    if not location_text or pd.isna(location_text):
        return "אחר"
    loc = str(location_text).lower().strip()
    # Remote first
    for kw in AREA_KEYWORDS["מרחוק"]:
        if kw.lower() in loc:
            return "מרחוק"
    for area, keywords in AREA_KEYWORDS.items():
        if area == "מרחוק":
            continue
        for kw in keywords:
            if kw.lower() in loc:
                return area
    return "אחר"


# ---------------------------------------------------------------------------
# Job category classification
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "דאטה": [
        "data", "דאטה", "analytics", "analyst", "bi ", "business intelligence",
        "tableau", "power bi", "sql", "etl", "warehouse", "lake",
        "machine learning", "ml engineer", "data science", "data engineer",
        "statistician", "ניתוח נתונים",
    ],
    "ניתוח מערכות": [
        "system analyst", "business analyst", "ba ", "ניתוח מערכות",
        "requirements", "use case", "functional", "systems analyst",
        "מנתח מערכות", "אנליסט",
    ],
    "פיתוח תוכנה": [
        "software", "developer", "engineer", "programmer", "backend", "frontend",
        "fullstack", "full stack", "devops", "qa ", "test", "java", "python dev",
        "react", "node", "angular", "mobile", "ios", "android", "פיתוח",
        "מפתח", "מתכנת",
    ],
    "מוצר": [
        "product manager", "product owner", "pm ", "product", "מנהל מוצר",
        "roadmap", "agile", "scrum master",
    ],
    "שיווק": [
        "marketing", "שיווק", "seo", "sem", "content", "brand", "social media",
        "campaign", "digital marketing", "growth", "copywriter",
    ],
    "מכירות": [
        "sales", "מכירות", "account executive", "account manager", "bdr", "sdr",
        "business development", "revenue", "closing", "quota",
    ],
    "שירות לקוחות": [
        "customer success", "customer service", "support", "שירות לקוחות",
        "helpdesk", "help desk", "technical support", "customer experience",
    ],
    "משאבי אנוש": [
        "hr ", "human resources", "recruiter", "recruiting", "talent",
        "people", "משאבי אנוש", "גיוס", "compensation", "payroll",
    ],
    "כספים": [
        "finance", "financial", "accountant", "accounting", "cfo", "controller",
        "budget", "treasury", "כספים", "חשבונאות", "רואה חשבון",
    ],
    "תפעול": [
        "operations", "ops ", "תפעול", "logistics", "supply chain",
        "procurement", "project coordinator", "office manager",
    ],
    "ניהול": [
        "manager", "director", "vp ", "vice president", "head of",
        "מנהל", "מנכ\"ל", "ceo", "coo", "cto", "chief",
    ],
    "בריאות": [
        "nurse", "doctor", "physician", "medical", "healthcare", "clinical",
        "therapist", "pharmacist", "בריאות", "רפואי",
    ],
    "חינוך": [
        "teacher", "instructor", "professor", "tutor", "education",
        "training", "מורה", "מדריך", "חינוך",
    ],
}


def classify_job_category(title: str, description: str = "", skills: str = "") -> str:
    combined = f"{title} {description[:300]} {skills}".lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw.lower() in combined)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "אחר"


# ---------------------------------------------------------------------------
# Experience normalization
# ---------------------------------------------------------------------------

EXPERIENCE_MAP = [
    (["internship", "intern", "student", "סטודנט", "trainee", "apprentice"], "סטודנט/ית"),
    (["entry level", "entry-level", "junior", "beginner", "ג'וניור", "entry"], "ג'וניור"),
    (["associate"], "ג'וניור/ביניים"),
    (["mid-senior", "mid senior", "senior", "sr.", "experienced", "advanced", "mid level", "mid-level"], "ביניים/בכיר"),
    (["director", "executive", "vp", "vice president", "head of", "chief", "c-level", "president"], "ניהול בכיר"),
]


def normalize_experience_level(text: str) -> str:
    if not text or pd.isna(text):
        return "לא צוין"
    t = str(text).lower().strip()
    for keywords, label in EXPERIENCE_MAP:
        if any(kw in t for kw in keywords):
            return label
    return "לא צוין"


# ---------------------------------------------------------------------------
# Salary normalization
# ---------------------------------------------------------------------------

def normalize_salary_to_annual(value: float, pay_period: str) -> float:
    """Convert salary to annual USD."""
    if pd.isna(value) or value <= 0:
        return np.nan
    period = str(pay_period).upper() if pay_period else ""
    if period == "HOURLY":
        return value * 40 * 52
    if period == "MONTHLY":
        return value * 12
    if period in ("WEEKLY",):
        return value * 52
    return value  # assume yearly


def make_salary_display(sal_min, sal_max, sal_med, pay_period) -> str:
    vals = [v for v in [sal_min, sal_max, sal_med] if not pd.isna(v) and v > 0]
    if not vals:
        return "לא צוין"
    period_map = {"HOURLY": "$/שעה", "MONTHLY": "$/חודש", "YEARLY": "$/שנה", "ANNUAL": "$/שנה"}
    unit = period_map.get(str(pay_period).upper() if pay_period else "", "$/שנה")
    lo = min(vals)
    hi = max(vals)
    if lo == hi:
        return f"{lo:,.0f} {unit}"
    return f"{lo:,.0f}–{hi:,.0f} {unit}"


# ---------------------------------------------------------------------------
# Job quality score
# ---------------------------------------------------------------------------

def compute_quality_score(row: pd.Series) -> float:
    score = 0
    if row.get("title_clean"):
        score += 15
    if row.get("company_clean") and row.get("company_clean") != "לא ידוע":
        score += 10
    if row.get("location_clean") and row.get("location_clean") != "לא ידוע":
        score += 10
    desc = row.get("description_clean", "")
    if desc and len(str(desc)) > 100:
        score += 20
    if not pd.isna(row.get("salary_min_clean")) or not pd.isna(row.get("salary_max_clean")):
        score += 15
    if row.get("experience_level_clean") and row.get("experience_level_clean") != "לא צוין":
        score += 10
    if row.get("application_url") or row.get("job_posting_url"):
        score += 10
    if row.get("required_skills_text"):
        score += 10
    return float(score)


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(text) -> str:
    if pd.isna(text) or text is None:
        return ""
    t = str(text).strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s֐-׿‏‎.,;:()\-/&@#%+!?]", " ", t)
    return t.strip()


# ---------------------------------------------------------------------------
# Anomaly flags
# ---------------------------------------------------------------------------

def detect_anomalies(row: pd.Series) -> list:
    flags = []
    sal_min = row.get("salary_min_clean")
    sal_max = row.get("salary_max_clean")
    if not pd.isna(sal_min) and sal_min < 10000:
        flags.append("שכר נמוך חריג")
    if not pd.isna(sal_max) and sal_max > 500000:
        flags.append("שכר גבוה חריג")
    desc = row.get("description_clean", "")
    if not desc or len(str(desc)) < 50:
        flags.append("תיאור חסר/קצר")
    if pd.isna(sal_min) and pd.isna(sal_max):
        flags.append("שכר לא צוין")
    if row.get("job_quality_score", 0) < 30:
        flags.append("איכות נמוכה")
    return flags


# ---------------------------------------------------------------------------
# Supporting table loaders
# ---------------------------------------------------------------------------

def load_supporting_tables(z: zipfile.ZipFile) -> dict:
    """Load optional supporting tables from ZIP."""
    tables = {}
    table_map = {
        "job_skills": "jobs/job_skills.csv",
        "salaries": "jobs/salaries.csv",
        "job_industries": "jobs/job_industries.csv",
        "benefits": "jobs/benefits.csv",
        "companies": "companies/companies.csv",
        "company_industries": "companies/company_industries.csv",
        "company_specialities": "companies/company_specialities.csv",
        "employee_counts": "companies/employee_counts.csv",
        "skills_map": "mappings/skills.csv",
        "industries_map": "mappings/industries.csv",
    }
    for key, path in table_map.items():
        try:
            with z.open(path) as f:
                df = pd.read_csv(f, encoding="utf-8", on_bad_lines="skip", low_memory=False)
            tables[key] = df
            logger.info("Loaded %s: %d rows", key, len(df))
        except Exception as e:
            logger.warning("Could not load %s (%s): %s", key, path, e)
            tables[key] = pd.DataFrame()
    return tables


def build_skill_lookup(tables: dict) -> dict:
    """Build job_id -> comma-separated skill names lookup."""
    skills_map = tables.get("skills_map", pd.DataFrame())
    job_skills = tables.get("job_skills", pd.DataFrame())
    if job_skills.empty:
        return {}
    if not skills_map.empty and "skill_abr" in skills_map.columns:
        abr2name = dict(zip(skills_map["skill_abr"], skills_map["skill_name"]))
    else:
        abr2name = {}
    skill_lookup = {}
    for row in job_skills.itertuples(index=False):
        jid = str(int(row.job_id)) if not pd.isna(row.job_id) else None
        if not jid:
            continue
        abr = getattr(row, "skill_abr", "")
        name = abr2name.get(abr, abr)
        if jid not in skill_lookup:
            skill_lookup[jid] = []
        skill_lookup[jid].append(name)
    return {k: ", ".join(v) for k, v in skill_lookup.items()}


def build_salary_lookup(tables: dict) -> dict:
    """Build job_id -> (min, max, med, period) from salaries table."""
    sal = tables.get("salaries", pd.DataFrame())
    if sal.empty:
        return {}
    lookup = {}
    for row in sal.itertuples(index=False):
        jid = str(int(row.job_id)) if not pd.isna(row.job_id) else None
        if not jid:
            continue
        lookup[jid] = {
            "sal_min": getattr(row, "min_salary", np.nan),
            "sal_max": getattr(row, "max_salary", np.nan),
            "sal_med": getattr(row, "med_salary", np.nan),
            "pay_period": getattr(row, "pay_period", "YEARLY"),
        }
    return lookup


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline():
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not os.path.exists(ZIP_PATH):
        logger.error("archive.zip לא נמצא בנתיב: %s", ZIP_PATH)
        logger.error("המערכת תפעל במצב דמו.")
        return False

    logger.info("פותח ZIP: %s", ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        logger.info("טוען טבלאות עזר...")
        tables = load_supporting_tables(z)
        skill_lookup = build_skill_lookup(tables)
        salary_lookup = build_salary_lookup(tables)
        logger.info("skill_lookup: %d entries, salary_lookup: %d entries",
                    len(skill_lookup), len(salary_lookup))

        # --- Set up SQLite ---
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("DROP TABLE IF EXISTS jobs_clean")
        conn.execute("""
            CREATE TABLE jobs_clean (
                job_id TEXT PRIMARY KEY,
                title_clean TEXT,
                company_clean TEXT,
                location_clean TEXT,
                location_area TEXT,
                job_category TEXT,
                experience_level_clean TEXT,
                work_type_clean TEXT,
                is_remote INTEGER DEFAULT 0,
                salary_min_clean REAL,
                salary_max_clean REAL,
                salary_med_clean REAL,
                salary_display TEXT,
                description_clean TEXT,
                required_skills_text TEXT,
                combined_text_for_matching TEXT,
                job_quality_score REAL DEFAULT 0,
                anomaly_flags TEXT,
                cluster_id INTEGER,
                job_posting_url TEXT,
                application_url TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_area ON jobs_clean(location_area);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cat ON jobs_clean(job_category);
        """)
        conn.commit()

        # --- Process postings in chunks ---
        logger.info("מעבד postings.csv בחתיכות של %d שורות...", CHUNK_SIZE)
        with z.open("postings.csv") as f:
            reader = pd.read_csv(
                f,
                chunksize=CHUNK_SIZE,
                encoding="utf-8",
                on_bad_lines="skip",
                low_memory=False,
                nrows=MAX_ROWS,
            )

            total_processed = 0
            total_inserted = 0
            seen_ids = set()

            for chunk_num, chunk in enumerate(reader):
                rows_out = []
                for _, row in chunk.iterrows():
                    # --- De-duplicate ---
                    jid_raw = row.get("job_id", None)
                    if pd.isna(jid_raw):
                        continue
                    jid = str(int(jid_raw))
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)

                    title = clean_text(row.get("title", ""))
                    if not title:
                        continue  # must have title

                    company = clean_text(row.get("company_name", "")) or "לא ידוע"
                    location = clean_text(row.get("location", "")) or "לא ידוע"
                    description = clean_text(row.get("description", ""))
                    skills_desc = clean_text(row.get("skills_desc", ""))

                    # Enrich skills from job_skills table
                    skills_from_table = skill_lookup.get(jid, "")
                    combined_skills = " ".join(filter(None, [skills_desc, skills_from_table]))

                    # Salary — prefer salaries table, fallback to postings columns
                    sal_info = salary_lookup.get(jid, {})
                    sal_min = sal_info.get("sal_min", row.get("min_salary", np.nan))
                    sal_max = sal_info.get("sal_max", row.get("max_salary", np.nan))
                    sal_med = sal_info.get("sal_med", row.get("med_salary", np.nan))
                    pay_period = sal_info.get("pay_period", row.get("pay_period", "YEARLY"))

                    sal_min_a = normalize_salary_to_annual(sal_min, pay_period)
                    sal_max_a = normalize_salary_to_annual(sal_max, pay_period)
                    sal_med_a = normalize_salary_to_annual(sal_med, pay_period)

                    experience_raw = row.get("formatted_experience_level", "")
                    work_type_raw = row.get("formatted_work_type", row.get("work_type", ""))
                    remote_raw = row.get("remote_allowed", 0)

                    is_remote = 1 if str(remote_raw).lower() in ("1", "1.0", "true", "yes") else 0

                    location_area = map_location_to_area(location)
                    if is_remote:
                        location_area = "מרחוק"

                    experience_level = normalize_experience_level(experience_raw)
                    category = classify_job_category(title, description, combined_skills)

                    combined_text = " ".join(filter(None, [
                        title, company, location, description[:1000], combined_skills
                    ]))

                    sal_display = make_salary_display(sal_min, sal_max, sal_med, pay_period)

                    partial = {
                        "job_id": jid,
                        "title_clean": title,
                        "company_clean": company,
                        "location_clean": location,
                        "location_area": location_area,
                        "job_category": category,
                        "experience_level_clean": experience_level,
                        "work_type_clean": clean_text(work_type_raw) or "לא צוין",
                        "is_remote": is_remote,
                        "salary_min_clean": None if pd.isna(sal_min_a) else float(sal_min_a),
                        "salary_max_clean": None if pd.isna(sal_max_a) else float(sal_max_a),
                        "salary_med_clean": None if pd.isna(sal_med_a) else float(sal_med_a),
                        "salary_display": sal_display,
                        "description_clean": description[:2000],
                        "required_skills_text": combined_skills[:500],
                        "combined_text_for_matching": combined_text[:3000],
                        "job_posting_url": str(row.get("job_posting_url", "")) if not pd.isna(row.get("job_posting_url", "")) else None,
                        "application_url": str(row.get("application_url", "")) if not pd.isna(row.get("application_url", "")) else None,
                    }

                    # Quality score and anomalies
                    partial_series = pd.Series(partial)
                    partial["job_quality_score"] = compute_quality_score(partial_series)
                    flags = detect_anomalies(partial_series)
                    partial["anomaly_flags"] = "|".join(flags) if flags else ""
                    partial["cluster_id"] = None

                    rows_out.append(partial)

                if rows_out:
                    conn.executemany("""
                        INSERT OR IGNORE INTO jobs_clean VALUES (
                            :job_id, :title_clean, :company_clean, :location_clean,
                            :location_area, :job_category, :experience_level_clean,
                            :work_type_clean, :is_remote, :salary_min_clean,
                            :salary_max_clean, :salary_med_clean, :salary_display,
                            :description_clean, :required_skills_text,
                            :combined_text_for_matching, :job_quality_score,
                            :anomaly_flags, :cluster_id, :job_posting_url, :application_url
                        )
                    """, rows_out)
                    conn.commit()
                    total_inserted += len(rows_out)

                total_processed += len(chunk)
                logger.info("chunk %d: עובד %d, הוכנס %d, סה\"כ %d",
                            chunk_num + 1, len(chunk), len(rows_out), total_inserted)

        conn.close()
        logger.info("✅ Pipeline הושלם. סה\"כ שורות: %d", total_inserted)

    # --- Generate reports ---
    _write_cleaning_report(total_processed, total_inserted)
    _write_data_summary()
    return True


def _write_cleaning_report(total_raw: int, total_clean: int):
    report = f"""# דו\"ח ניקוי נתונים — CareerFit

**תאריך:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

## סקירה כללית

| פרמטר | ערך |
|-------|-----|
| שורות גולמיות (postings.csv) | {total_raw:,} |
| שורות לאחר ניקוי | {total_clean:,} |
| שורות שנפסלו | {total_raw - total_clean:,} |
| שיעור שמירה | {total_clean/max(total_raw,1)*100:.1f}% |

## פעולות ניקוי שבוצעו

1. **הסרת כפילויות** — לפי job_id.
2. **פסילת שורות ללא כותרת** — כל משרה חייבת כותרת.
3. **נרמול טקסט** — הסרת רווחים כפולים, תווים מיוחדים.
4. **נרמול שכר** — המרה לשנתי (שעתי × 2080, חודשי × 12).
5. **נרמול רמת ניסיון** — מיפוי ל-5 קטגוריות עבריות.
6. **מיפוי מיקום לאזור** — 8 אזורי ישראל + מרחוק + אחר.
7. **סיווג קטגוריית משרה** — 14 קטגוריות לפי מילות מפתח.
8. **העשרה מטבלאות עזר** — כישורים, שכר, תעשיות.
9. **ציון איכות** — 0–100 לפי שלמות השדות.
10. **סימון אנומליות** — שכר חריג, תיאור חסר, איכות נמוכה.

## עמודות חדשות שנוצרו

| עמודה | תיאור |
|-------|--------|
| title_clean | כותרת מנוקה |
| company_clean | שם חברה מנוקה |
| location_clean | מיקום מנוקה |
| location_area | אזור מיפוי (השרון, תל אביב...) |
| job_category | קטגוריה (דאטה, פיתוח תוכנה...) |
| experience_level_clean | רמת ניסיון עברית |
| work_type_clean | סוג עבודה |
| is_remote | האם מרחוק (0/1) |
| salary_min/max/med_clean | שכר שנתי מנורמל |
| salary_display | תצוגת שכר קריאה |
| description_clean | תיאור מנוקה (עד 2000 תווים) |
| required_skills_text | כישורים מורכב |
| combined_text_for_matching | טקסט משולב לדמיון |
| job_quality_score | ציון איכות 0–100 |
| anomaly_flags | דגלי אנומליה מופרדים ב-pipe |
| cluster_id | מזהה אשכול (אחרי clustering) |
"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(os.path.join(REPORTS_DIR, "cleaning_report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("cleaning_report.md נכתב")


def _write_data_summary():
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0]
        cats = conn.execute(
            "SELECT job_category, COUNT(*) c FROM jobs_clean GROUP BY job_category ORDER BY c DESC"
        ).fetchall()
        areas = conn.execute(
            "SELECT location_area, COUNT(*) c FROM jobs_clean GROUP BY location_area ORDER BY c DESC"
        ).fetchall()
        exp = conn.execute(
            "SELECT experience_level_clean, COUNT(*) c FROM jobs_clean GROUP BY experience_level_clean ORDER BY c DESC"
        ).fetchall()
        remote = conn.execute("SELECT COUNT(*) FROM jobs_clean WHERE is_remote=1").fetchone()[0]
        no_sal = conn.execute(
            "SELECT COUNT(*) FROM jobs_clean WHERE salary_min_clean IS NULL AND salary_max_clean IS NULL"
        ).fetchone()[0]

        lines = [f"# סיכום נתונים — CareerFit\n",
                 f"**סך משרות:** {total:,}\n",
                 "## קטגוריות משרות\n| קטגוריה | כמות |",
                 "|---------|------|"]
        for cat, cnt in cats:
            lines.append(f"| {cat} | {cnt:,} |")
        lines.append("\n## אזורים גאוגרפיים\n| אזור | כמות |")
        lines.append("|------|------|")
        for area, cnt in areas:
            lines.append(f"| {area} | {cnt:,} |")
        lines.append("\n## רמות ניסיון\n| רמה | כמות |")
        lines.append("|-----|------|")
        for exp_lv, cnt in exp:
            lines.append(f"| {exp_lv} | {cnt:,} |")
        lines.append(f"\n## עבודה מרחוק\n- משרות מרחוק: {remote:,} ({remote/max(total,1)*100:.1f}%)")
        lines.append(f"- משרות ללא שכר: {no_sal:,} ({no_sal/max(total,1)*100:.1f}%)")

        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(os.path.join(REPORTS_DIR, "data_summary.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info("data_summary.md נכתב")
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_pipeline()
    if success:
        print("✅ data_pipeline הושלם בהצלחה.")
    else:
        print("⚠️  data_pipeline לא הושלם — archive.zip חסר.")
