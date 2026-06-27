"""
matching_engine.py — Stage 5 & 6: Score and rank jobs against user profile.
Uses rule-based scoring + TF-IDF cosine similarity.
Scoring weights: role/intent 35%, TF-IDF 25%, skills 15%, experience 10%, location 10%, salary 5%.
"""
import sqlite3
import os
import logging
import re
import numpy as np
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))

# Use the resolved DB path from database.py (handles /tmp copy workaround for OneDrive mounts)
try:
    from database import DB_PATH
except ImportError:
    DB_PATH = os.path.join(_HERE, "careerfit.db")

# TF-IDF objects — built lazily on first search
_tfidf_vectorizer = None
_tfidf_matrix = None
_tfidf_job_ids = None

# Skills to check for gaps
COMMON_SKILLS = [
    "SQL", "Excel", "Python", "Power BI", "Tableau", "Java",
    "JavaScript", "React", "CRM", "SAP", "Jira", "Agile",
    "BI", "Data Analysis", "Information Systems",
]

# Fallback chains
LOCATION_FALLBACKS = {
    "השרון": ["תל אביב", "המרכז", "השפלה", "מרחוק"],
    "תל אביב": ["המרכז", "השרון", "השפלה", "מרחוק"],
    "המרכז": ["תל אביב", "השרון", "השפלה", "מרחוק"],
    "השפלה": ["המרכז", "תל אביב", "מרחוק"],
    "ירושלים": ["המרכז", "מרחוק"],
    "הצפון": ["מרחוק", "המרכז"],
    "הדרום": ["מרחוק", "המרכז"],
    "מרחוק": ["תל אביב", "המרכז", "השרון"],
    "אחר": ["מרחוק", "תל אביב", "המרכז", "השרון", "השפלה"],
}

# ---------------------------------------------------------------------------
# Location classification constants
# ---------------------------------------------------------------------------

# Normalized location_area values that map to Israeli areas (from DB taxonomy)
ISRAEL_AREAS = {
    "השרון", "תל אביב", "המרכז", "השפלה",
    "ירושלים", "הצפון", "הדרום", "גוש דן",
}

# Raw location_clean keywords confirming Israeli location
ISRAEL_LOCATION_KEYWORDS = (
    "tel aviv", "israel", "ramat gan", "herzliya", "haifa", "jerusalem",
    "netanya", "rishon lezion", "rishon-lezion", "holon", "bat yam",
    "rehovot", "beersheba", "ashdod", "ashkelon", "petah tikva",
    "modiin", "nahariya", "eilat", "kfar saba", "raanana",
    "הרצליה", "תל אביב", "ישראל", "חיפה", "ירושלים",
    "רמת גן", "רחובות", "נתניה", "חולון", "בת ים",
    "אשדוד", "באר שבע", "פתח תקווה", "מודיעין", "ראשון לציון",
    "כפר סבא", "רעננה", "הוד השרון", "חדרה", "אשקלון",
    "יקנעם", "קיסריה", "נס ציונה", "לוד", "רמלה",
    "ראש העין", "אור יהודה", "יהוד", "שוהם", "גבעתיים",
    "בני ברק", "רמת השרון",
)

# Raw location keywords confirming remote/global (when is_remote flag absent)
REMOTE_LOCATION_KEYWORDS = (
    "remote", "work from home", "wfh", "anywhere", "worldwide",
    "global", "fully remote", "100% remote", "distributed",
    "telecommute",
)

# US city / state suffixes that identify a US job (checked against location_clean)
US_LOCATION_KEYWORDS = (
    "united states", "usa", "u.s.a.", "u.s.",
    "new york", "los angeles", "chicago", "san francisco", "boston",
    "seattle", "austin", "dallas", "houston", "atlanta", "denver",
    "phoenix", "miami", "minneapolis", "washington dc", "washington, dc",
    "philadelphia", "san diego", "nashville", "portland", "charlotte",
    ", ny", ", ca", ", tx", ", wa", ", il", ", ma", ", fl", ", ga",
    ", nj", ", pa", ", oh", ", mi", ", nc", ", az", ", co",
    ", mn", ", tn", ", or", ", mo", ", va", ", wi", ", ct",
    ", md", ", ky", ", in", ", ia", ", ut", ", ok", ", sc",
    ", ar", ", la", ", al", ", ms", ", ks", ", ne", ", nv",
    ", nh", ", me", ", ri", ", vt", ", nd", ", sd", ", mt",
    ", id", ", wy", ", ak", ", hi", ", dc", ", wv", ", nm",
)

# ---------------------------------------------------------------------------
# Company Israel presence — for classifying remote/global jobs
# ---------------------------------------------------------------------------

# Known Israeli tech companies (match against lowercase company_clean substrings).
# Used to tag remote jobs as "Israel_possible_remote".
# Note: no company CSV is available from archive.zip (per security constraint).
KNOWN_ISRAEL_COMPANIES: frozenset = frozenset({
    "check point", "cyberark", "wix", "monday.com", "amdocs",
    "nice systems", "nice ltd", "radcom", "allot",
    "cellebrite", "ironsource", "appsflyer", "skai", "kaltura",
    "riskified", "fiverr", "outbrain", "taboola",
    "varonis", "sentinelone", "mobileye", "solaredge technologies",
    "tower semiconductor", "elbit systems", "teva pharmaceutical",
    "audiocodes", "comverse", "eci telecom", "nayax",
    "similarweb", "playtika", "au10tix", "telco systems",
    "shoukhon", "gett", "artza",
})

# Companies that are definitively NOT Israeli — checked FIRST to prevent false
# positives from short-name substring matching (e.g., "wixon" contains "wix",
# "monday talent" contains "monday", "#twiceasnice" would match bare "nice").
KNOWN_NON_ISRAEL_COMPANIES: frozenset = frozenset({
    # Major US corporations
    "walmart", "amazon.com", "google llc", "microsoft corporation",
    "apple inc", "meta platforms", "tesla, inc", "general motors",
    "ford motor", "boeing", "lockheed martin", "raytheon",
    "cvs health", "walgreens", "home depot",
    # Names containing "Israel" that are NOT Israeli companies
    "beth israel lahey health", "beth israel deaconess",
    "israel firstfruits",
    # False-positive traps for short-name matching:
    "wixon",           # WI food manufacturer ≠ Wix (Israeli web builder)
    "monday talent",   # US PR staffing agency ≠ monday.com (Israeli)
    "twiceasnice",     # US recruiting firm ("#twiceasnice") ≠ NICE Systems
    "nice cannabis", "nice north america", "softnice", "asknicely",
    "omnicell",        # US pharma automation, not Israeli
})


def company_has_israel_presence(company_name: str) -> Optional[bool]:
    """
    Heuristic: does this company have a known presence in Israel?

    Returns:
        True   — company is a known Israeli tech firm
        False  — company is definitively NOT Israeli (US-only or confirmed non-Israeli)
        None   — unknown (no data available)

    IMPORTANT: KNOWN_NON_ISRAEL_COMPANIES is checked FIRST to prevent false
    positives from short-name substring matching (e.g., "Wixon" ⊃ "wix").

    Note: Based on hardcoded list only. No company CSV extracted from archive.zip
          (per security constraint — archive.zip must not be committed to GitHub).
    """
    if not company_name:
        return None
    co_lower = company_name.lower().strip()

    # Check non-Israel FIRST (prevents short-name false positives)
    for name in KNOWN_NON_ISRAEL_COMPANIES:
        if name in co_lower:
            return False

    # Check known Israeli companies
    for name in KNOWN_ISRAEL_COMPANIES:
        if name in co_lower:
            return True

    return None  # Unknown


# Category → related Hebrew/English keywords for title matching
CATEGORY_TITLE_KEYWORDS = {
    "דאטה":           ["data", "analyst", "analytics", "bi ", "business intelligence", "data science", "דאטה", "נתונים"],
    "ניתוח מערכות":   ["system analyst", "business analyst", "מנתח", "ניתוח מערכות"],
    "פיתוח תוכנה":    ["developer", "engineer", "software", "programmer", "מפתח", "פיתוח"],
    "מוצר":           ["product manager", "product owner", "מנהל מוצר", "product"],
    "שיווק":          ["marketing", "שיווק", "digital", "content", "brand"],
    "מכירות":         ["sales", "account", "business development", "מכירות"],
    "שירות לקוחות":   ["customer service", "support", "שירות לקוחות", "success"],
    "משאבי אנוש":     ["hr ", "human resources", "recruiter", "talent", "משאבי אנוש", "גיוס"],
    "כספים":          ["finance", "accounting", "controller", "cfo", "כספים", "חשבונאות"],
    "חינוך":          ["teacher", "tutor", "education", "teaching", "instructor", "מורה", "הוראה", "מחנך", "educator"],
    "ניהול":          ["manager", "director", "head of", "vp", "מנהל", "ניהול"],
    "בריאות":         ["nurse", "medical", "health", "therapist", "doctor", "בריאות", "רפואה"],
    "תפעול":          ["operations", "logistics", "supply chain", "project manager", "תפעול"],
}


# ---------------------------------------------------------------------------
# TF-IDF index
# ---------------------------------------------------------------------------

def _build_tfidf_index(limit: int = 15_000):
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_job_ids
    if not os.path.exists(DB_PATH):
        return
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        conn = sqlite3.connect(DB_PATH)
        # Random sample across quality tiers for representative vocabulary
        rows = conn.execute(
            "SELECT job_id, combined_text_for_matching FROM jobs_clean "
            "ORDER BY RANDOM() LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        if not rows:
            return
        ids = [r[0] for r in rows]
        texts = [str(r[1] or "") for r in rows]
        vec = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )
        mat = vec.fit_transform(texts)
        _tfidf_vectorizer = vec
        _tfidf_matrix = mat
        _tfidf_job_ids = ids
        logger.info("TF-IDF index built: %d jobs, %d features", len(ids), mat.shape[1])
    except Exception as e:
        logger.error("TF-IDF index build failed: %s", e)


def get_tfidf_scores(profile_text: str, candidate_ids: List[str]) -> Dict[str, float]:
    """Return TF-IDF cosine similarity scores. Returns {} if index not ready (non-blocking)."""
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_job_ids
    # Never build synchronously inside a request — background thread handles it
    if _tfidf_vectorizer is None or not profile_text.strip():
        return {}
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        q_vec = _tfidf_vectorizer.transform([profile_text])
        candidate_set = set(candidate_ids)
        scores = {}
        for i, jid in enumerate(_tfidf_job_ids):
            if jid in candidate_set:
                sim = float(cosine_similarity(q_vec, _tfidf_matrix[i])[0][0])
                scores[jid] = sim
        return scores
    except Exception as e:
        logger.error("TF-IDF scoring error: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Role-intent scoring (most important component)
# ---------------------------------------------------------------------------

def _score_role_intent(user_interests: List[str], job_title: str,
                        job_category: str, job_description: str) -> Tuple[float, List[str]]:
    """
    Score how well a job matches the user's target role/career interest.
    Checks job title first (strongest signal), then category, then description.
    Returns (score 0-1, match_reasons list).
    """
    if not user_interests:
        return 0.3, []

    title_lower = (job_title or "").lower()
    cat_lower = (job_category or "").lower()
    desc_lower = (job_description or "")[:500].lower()
    reasons = []

    best_score = 0.0

    for interest in user_interests:
        interest_lower = interest.lower()

        # 1. Direct title match
        if interest_lower in title_lower:
            best_score = max(best_score, 1.0)
            reasons.append(f"כותרת תואמת: {job_title}")
            continue

        # 2. Category keyword match from CATEGORY_TITLE_KEYWORDS
        cat_kws = CATEGORY_TITLE_KEYWORDS.get(interest, [])

        # Check title against category keywords
        title_hit = any(kw.lower() in title_lower for kw in cat_kws)
        if title_hit:
            best_score = max(best_score, 0.9)
            reasons.append(f"תפקיד תואם: {job_title}")
            continue

        # 3. Job category match
        if interest_lower in cat_lower or cat_lower in interest_lower:
            best_score = max(best_score, 0.8)
            reasons.append(f"קטגוריה תואמת: {job_category}")
            continue

        # 4. Category kw in category field
        cat_kw_hit = any(kw.lower() in cat_lower for kw in cat_kws)
        if cat_kw_hit:
            best_score = max(best_score, 0.7)
            reasons.append(f"קטגוריה קרובה: {job_category}")
            continue

        # 5. Description match
        desc_hit = any(kw.lower() in desc_lower for kw in cat_kws) if cat_kws else (interest_lower in desc_lower)
        if desc_hit:
            best_score = max(best_score, 0.4)
            reasons.append(f"תיאור תואם לתחום {interest}")

    return min(best_score, 1.0), reasons


# ---------------------------------------------------------------------------
# Other score components
# ---------------------------------------------------------------------------

def _score_skills(user_skills: List[str], job_text: str) -> Tuple[float, List[str]]:
    if not user_skills:
        return 0.0, []
    job_lower = job_text.lower()
    matched = [s for s in user_skills if s.lower() in job_lower]
    score = len(matched) / max(len(user_skills), 1)
    return min(score, 1.0), matched


def _score_experience(user_seniority: str, job_level: str) -> float:
    SENIORITY_ORDER = ["סטודנט/ית", "ג'וניור", "ג'וניור/ביניים", "ביניים/בכיר", "ניהול בכיר", "לא צוין"]
    if not user_seniority or job_level == "לא צוין":
        return 0.5
    try:
        u_idx = SENIORITY_ORDER.index(user_seniority)
        j_idx = SENIORITY_ORDER.index(job_level)
        diff = abs(u_idx - j_idx)
        return 1.0 if diff == 0 else (0.7 if diff == 1 else (0.3 if diff == 2 else 0.0))
    except ValueError:
        return 0.5


def _score_location(user_primary: str, user_fallbacks: List[str],
                     remote_allowed: bool, job_area: str, is_remote: bool) -> Tuple[float, Optional[str]]:
    if is_remote and remote_allowed:
        return 1.0, None
    if not user_primary:
        return 0.5, None
    if job_area == user_primary:
        return 1.0, None
    if job_area in user_fallbacks:
        return 0.6, None
    if remote_allowed and job_area == "מרחוק":
        return 0.8, None
    return 0.0, None


def _score_salary(user_min: Optional[float], user_preferred: Optional[float],
                   user_flexible: bool, job_min: Optional[float], job_max: Optional[float]) -> float:
    if user_flexible or (user_min is None and user_preferred is None):
        return 0.7
    if job_min is None and job_max is None:
        return 0.5
    job_salary = job_min or job_max or 0
    user_target = user_preferred or user_min or 0
    if job_salary >= user_target:
        return 1.0
    if job_salary >= user_target * 0.85:
        return 0.7
    if job_salary >= user_target * 0.7:
        return 0.4
    return 0.0


def _score_work_env(user_env: str, is_remote: int, work_type: str) -> float:
    if not user_env:
        return 0.5
    env = user_env.lower()
    if "מרחוק" in env or "remote" in env:
        return 1.0 if is_remote else 0.0
    if "היברידי" in env or "hybrid" in env:
        return 0.8 if is_remote else 0.4
    if "משרד" in env or "office" in env:
        return 1.0 if not is_remote else 0.3
    return 0.5


def classify_job_location(job: dict) -> str:
    """
    Classify a job as 'israel', 'remote', or 'foreign'.

    CRITICAL: Do NOT use location_area for Israeli classification.
    The data pipeline wrongly mapped US "South/North/Center" locations to
    Hebrew area names (הדרום=South US, הצפון=North US, המרכז=Central US).
    Only raw location_clean text is reliable.

    Priority:
        1. Raw location_clean contains an Israeli city/keyword  → 'israel'
        2. is_remote DB flag = 1                                → 'remote'
        3. location_area = 'מרחוק' (only reliable area value)  → 'remote'
        4. Raw location_clean contains a remote keyword         → 'remote'
        5. Everything else                                       → 'foreign'

    Returns:
        'israel'  — raw location_clean confirms Israeli job
        'remote'  — job is flagged/labelled as remote
        'foreign' — job is outside Israel and not remote
    """
    is_remote_flag = bool(job.get("is_remote", 0))
    location_area  = str(job.get("location_area", "") or "")
    location_raw   = str(job.get("location_clean", "") or "").lower()

    # 1. Raw Israeli keyword (highest confidence — ground truth)
    for kw in ISRAEL_LOCATION_KEYWORDS:
        if kw in location_raw:
            return "israel"

    # 2. DB remote flag — most reliable for remote detection
    if is_remote_flag:
        return "remote"

    # 3. location_area = 'מרחוק' is the one reliable area value from the pipeline
    if location_area == "מרחוק":
        return "remote"

    # 4. Raw remote keywords
    for kw in REMOTE_LOCATION_KEYWORDS:
        if kw in location_raw:
            return "remote"

    # 5. Everything else is foreign.
    # NOTE: We intentionally do NOT check location_area in ISRAEL_AREAS here.
    # Those area labels (הדרום, הצפון, המרכז, השפלה) were erroneously assigned
    # by the data pipeline to US "South/North/Center/etc." locations and do NOT
    # indicate Israeli jobs.
    return "foreign"


def classify_job_country(job: dict) -> str:
    """
    Classify a job into a detailed country bucket for filtering and display.

    Classification priority (raw location_clean first):
        1. Raw location_clean contains Israeli keyword          → 'Israel'
        2. Remote + 'israel' in location_clean or known IL co  → 'Israel_possible_remote'
        3. Remote + definitively non-Israeli company           → 'global_or_foreign'
        4. Remote + company presence unknown                   → 'unknown_remote'
        5. Foreign + US keyword in location_clean              → 'United States'
        6. Foreign + other / unclassifiable                    → 'Other'

    Returns:
        'Israel'                 — confirmed Israeli location in raw data
        'Israel_possible_remote' — remote job from a known Israeli company
        'global_or_foreign'      — remote job, company definitively NOT Israeli
        'unknown_remote'         — remote job, company Israel presence unknown
        'United States'          — non-remote US job
        'Other'                  — non-remote non-US / unclassified
    """
    loc_type     = classify_job_location(job)
    location_raw = str(job.get("location_clean", "") or "").lower()
    company_name = str(job.get("company_clean", "") or "")

    # 1. Raw location confirms Israel
    if loc_type == "israel":
        return "Israel"

    # 2-4. Remote — check company Israel presence
    if loc_type == "remote":
        # Explicit "israel" in location_clean (e.g., "Remote - Israel")
        if "israel" in location_raw:
            return "Israel_possible_remote"
        presence = company_has_israel_presence(company_name)
        if presence is True:
            return "Israel_possible_remote"
        if presence is False:
            return "global_or_foreign"
        return "unknown_remote"

    # 5. Non-remote foreign — check US keywords
    for kw in US_LOCATION_KEYWORDS:
        if kw in location_raw:
            return "United States"

    return "Other"


def _score_soft_signals(profile_signals: dict, job_text: str, job_category: str) -> Tuple[float, List[str]]:
    """
    Boost score based on soft signals (interests, hobbies, personality).
    Returns (boost 0-1, reason_strings). Max effective boost is ~0.5 (light influence only).
    """
    if not profile_signals:
        return 0.0, []

    job_lower = (job_text + " " + job_category).lower()
    reasons = []
    score = 0.0

    # Signals → keywords to look for in jobs
    SOFT_BOOST_MAP = {
        "יצירתיות":          ["design", "creative", "ux", "ui", "marketing", "content", "visual", "עיצוב", "שיווק"],
        "עבודה ויזואלית":     ["design", "ux", "ui", "visual", "creative", "עיצוב"],
        "עבודה עם מספרים":    ["data", "analyst", "finance", "bi", "BI", "accounting", "נתונים", "כספים"],
        "ניתוח":              ["analyst", "analysis", "data", "BI", "intelligence"],
        "עבודה עם אנשים":     ["hr", "human resources", "education", "training", "customer", "משאבי אנוש", "חינוך"],
        "עזרה לאחרים":        ["hr", "education", "training", "support", "teacher", "מורה", "חינוך"],
        "הוראה":              ["teacher", "instructor", "training", "education", "מורה", "הדרכה", "חינוך"],
        "הדרכה":              ["trainer", "instructor", "education", "training", "הדרכה"],
        "ארגון":              ["operations", "project manager", "coordinator", "admin", "תפעול"],
        "תהליכים":            ["operations", "process", "project", "תפעול", "ניהול"],
        "טכנולוגיה":          ["tech", "software", "developer", "engineer", "data", "פיתוח"],
        "חדשנות":             ["innovation", "startup", "product", "tech", "מוצר"],
    }

    interests = profile_signals.get("interests", [])
    hobbies = profile_signals.get("hobbies", [])

    for signal in interests:
        kws = SOFT_BOOST_MAP.get(signal, [signal.lower()])
        if any(kw.lower() in job_lower for kw in kws):
            score = min(score + 0.25, 0.5)
            reasons.append("ההתאמה התחזקה כי ציינת עניין ב" + signal)

    # Hobbies give smaller boost only if confirmed for job search (career_interests non-empty)
    for hobby in hobbies:
        hobby_l = hobby.lower()
        if hobby_l in job_lower:
            score = min(score + 0.1, 0.5)
            reasons.append("ההתאמה התחזקה כי ציינת תחביב: " + hobby)

    return min(score, 1.0), reasons



# ---------------------------------------------------------------------------
# Seniority-based title boost/penalty
# ---------------------------------------------------------------------------

JUNIOR_TITLE_KEYWORDS = [
    "junior", "entry level", "entry-level", "student", "intern", "internship",
    "graduate", "grad ", "ג'וניור", "סטודנט", "התמחות", "מתחיל", "ללא ניסיון",
    "no experience", "associate",
]
SENIOR_TITLE_KEYWORDS = [
    "senior", "sr.", "lead ", "principal", "architect", "director",
    "head of", " vp ", "chief", "בכיר", "מנהל ", "ראש צוות",
]


def _score_seniority_title(profile_seniority: str, job_title: str) -> float:
    """Boost junior/student titles when profile is student/junior. Penalise senior titles."""
    if not profile_seniority:
        return 0.0
    is_junior = profile_seniority in ("סטודנט/ית", "ג'וניור", "student", "junior")
    if not is_junior:
        return 0.0
    title_lower = (job_title or "").lower()
    boost   = sum(1 for kw in JUNIOR_TITLE_KEYWORDS if kw in title_lower) * 0.12
    penalty = sum(1 for kw in SENIOR_TITLE_KEYWORDS if kw in title_lower) * 0.18
    return max(-0.3, min(boost, 0.25) - penalty)


def _get_missing_skills(user_skills: List[str], job_text: str) -> List[str]:
    job_lower = job_text.lower()
    missing = []
    for skill in COMMON_SKILLS:
        if skill.lower() in job_lower and skill.lower() not in " ".join(user_skills).lower():
            missing.append(skill)
    return missing[:5]


def _check_constraints(constraints_avoid: List[str], job: dict) -> List[str]:
    warnings = []
    category = str(job.get("job_category", "")).lower()
    title = str(job.get("title_clean", "")).lower()
    combined = category + " " + title
    for avoid in constraints_avoid:
        avoid_l = avoid.lower()
        if "מכירות" in avoid_l and ("מכירות" in combined or "sales" in combined):
            warnings.append("משרה זו כוללת מכירות — סימנת שאינך מעוניינ/ת")
        if "משמרות" in avoid_l and ("shifts" in combined or "משמרות" in combined):
            warnings.append("משרה זו עשויה לכלול משמרות")
    return warnings


# ---------------------------------------------------------------------------
# Main scoring function — new weights
# ---------------------------------------------------------------------------

def score_job(profile: dict, job: dict, tfidf_sim: float = 0.0,
              remote_only_requested: bool = False,
              country_preference: str = "") -> dict:
    """
    Score a single job against the user profile.
    Weights: role/intent 35%, TF-IDF 25%, skills 15%, experience 10%,
             location 10%, salary 5%.
    Returns a dict with 'score', 'match_reasons', 'skill_gaps', 'warnings',
    'job_country', and all raw job fields.
    """
    # ---------- Extract profile fields ----------
    interests  = profile.get("career_interests", [])
    skills     = profile.get("skills", [])
    exp        = profile.get("experience", {})
    seniority  = exp.get("seniority", "")
    loc_pref   = profile.get("location_preference", {})
    user_area  = loc_pref.get("primary", "")
    fallbacks  = loc_pref.get("fallbacks", [])
    remote_ok  = loc_pref.get("remote_allowed", False) or remote_only_requested
    sal        = profile.get("salary_expectation", {})
    sal_min    = sal.get("min")
    sal_pref   = sal.get("preferred")
    sal_flex   = sal.get("flexible", True)
    work_style = profile.get("work_style", {})
    work_env   = work_style.get("preferred_environment", "")
    signals    = profile.get("profile_signals", {})
    avoids     = profile.get("constraints", {}).get("avoid", [])

    # ---------- Job fields ----------
    title    = str(job.get("title_clean", "") or "")
    cat      = str(job.get("job_category", "") or "")
    desc     = str(job.get("description_clean", "") or "")
    skills_t = str(job.get("required_skills_text", "") or "")
    combined = str(job.get("combined_text_for_matching", "") or "")
    job_text = combined or (title + " " + cat + " " + desc + " " + skills_t)
    job_area = str(job.get("location_area", "") or "")
    is_rem   = bool(job.get("is_remote", 0))
    job_lvl  = str(job.get("experience_level_clean", "לא צוין") or "לא צוין")
    job_sal_min = job.get("salary_min_clean")
    job_sal_max = job.get("salary_max_clean")
    job_work_type = str(job.get("work_type_clean", "") or "")

    # ---------- Component scores ----------
    role_score, role_reasons = _score_role_intent(interests, title, cat, desc)
    skill_score, matched_skills = _score_skills(skills, job_text)
    exp_score = _score_experience(seniority, job_lvl)
    loc_score, _ = _score_location(user_area, fallbacks, remote_ok, job_area, is_rem)
    sal_score = _score_salary(sal_min, sal_pref, sal_flex, job_sal_min, job_sal_max)
    env_score = _score_work_env(work_env, is_rem, job_work_type)
    soft_score, soft_reasons = _score_soft_signals(signals, job_text, cat)
    sen_boost = _score_seniority_title(seniority, title)

    # Apply country-level filter/boost
    job_country = classify_job_country(job)
    country_mult = 1.0
    if country_preference:
        if country_preference == "Israel":
            if job_country in ("Israel", "Israel_possible_remote"):
                country_mult = 1.2
            elif job_country in ("global_or_foreign", "United States", "Other"):
                country_mult = 0.1
        elif country_preference == "United States":
            if job_country == "United States":
                country_mult = 1.2
            elif job_country in ("Israel",):
                country_mult = 0.1
        elif country_preference == "Global":
            # No filter — all countries valid
            pass

    # ---------- Weighted total ----------
    base_score = (
        role_score  * 0.35 +
        tfidf_sim   * 0.25 +
        skill_score * 0.15 +
        exp_score   * 0.10 +
        loc_score   * 0.10 +
        sal_score   * 0.05
    )
    total = min((base_score + soft_score * 0.05 + sen_boost) * country_mult, 1.0)

    # ---------- Compile reasons ----------
    reasons = role_reasons[:]
    if matched_skills:
        reasons.append("כישורים תואמים: " + ", ".join(matched_skills[:3]))
    reasons.extend(soft_reasons[:2])

    # ---------- Gaps & warnings ----------
    skill_gaps = _get_missing_skills(skills, job_text)
    warnings   = _check_constraints(avoids, job)

    result = dict(job)
    result.update({
        "score":         round(total, 4),
        "match_reasons": reasons,
        "skill_gaps":    skill_gaps,
        "warnings":      warnings,
        "job_country":   job_country,
        "_debug": {
            "role":    round(role_score, 3),
            "tfidf":   round(tfidf_sim, 3),
            "skill":   round(skill_score, 3),
            "exp":     round(exp_score, 3),
            "loc":     round(loc_score, 3),
            "sal":     round(sal_score, 3),
            "country_mult": round(country_mult, 2),
        },
    })
    return result


# ---------------------------------------------------------------------------
# Build profile text for TF-IDF query
# ---------------------------------------------------------------------------

def build_profile_text(profile: dict) -> str:
    """Convert profile to a text string for TF-IDF similarity matching."""
    parts = []
    for ci in profile.get("career_interests", []):
        parts.append(ci)
    for sk in profile.get("skills", []):
        parts.append(sk)
    edu = profile.get("education", {})
    if edu.get("field"):
        parts.append(edu["field"])
    if edu.get("degree"):
        parts.append(edu["degree"])
    exp = profile.get("experience", {})
    if exp.get("seniority"):
        parts.append(exp["seniority"])
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_jobs(profile: dict, limit: int = 10,
                location_override: Optional[str] = None) -> Tuple[List[dict], dict]:
    """
    Search and rank jobs from the database against the user profile.

    Returns (jobs_list, metadata_dict).
    jobs_list: top `limit` scored jobs sorted by score DESC.
    metadata_dict: debug info (candidates_scanned, results_count, etc.)
    """
    # Resolve DB path — prefer demo_jobs.db when careerfit.db is absent
    db_path = DB_PATH
    if not os.path.exists(db_path):
        demo = os.path.join(_HERE, "demo_jobs.db")
        if os.path.exists(demo):
            db_path = demo
        else:
            logger.warning("No database found at %s or demo_jobs.db", db_path)
            return [], {"error": "no_database"}

    country_pref = profile.get("country_preference", "")
    interests    = profile.get("career_interests", [])
    open_to_all  = profile.get("open_to_all", False)
    loc_pref     = profile.get("location_preference", {})
    user_area    = location_override or loc_pref.get("primary", "")
    remote_ok    = loc_pref.get("remote_allowed", False)
    exp          = profile.get("experience", {})
    seniority    = exp.get("seniority", "")
    work_pref    = profile.get("work_preferences", {})
    work_mode    = work_pref.get("work_mode", "")

    # ---------- Build SQL WHERE clause ----------
    conditions: list = []
    params: list = []

    # Country filter
    if country_pref == "Israel":
        # Israeli jobs only (raw location_clean-based) — use approximate filter
        # Exact classification happens per-job; SQL pre-filter catches most cases
        il_kws = ["israel", "tel aviv", "haifa", "jerusalem", "netanya",
                  "herzliya", "ramat gan", "petah tikva", "rishon", "rehovot",
                  "ב׳ ישראל", "ישראל"]
        il_conds = " OR ".join(
            "LOWER(location_clean) LIKE ?" for _ in il_kws
        )
        # Also include remote from known Israeli companies (can't easily filter in SQL)
        conditions.append(f"(is_remote = 1 OR ({il_conds}))")
        params.extend(f"%{kw}%" for kw in il_kws)
    elif country_pref == "United States":
        us_kws = [", ny", ", ca", ", tx", ", wa", ", il", ", ma", ", fl",
                  "new york", "los angeles", "chicago", "san francisco",
                  "seattle", "austin", "boston", "united states", "usa"]
        us_conds = " OR ".join("LOWER(location_clean) LIKE ?" for _ in us_kws)
        conditions.append(f"({us_conds})")
        params.extend(f"%{kw}%" for kw in us_kws)
    elif country_pref == "Global":
        pass  # no country filter

    # Work mode filter
    if work_mode == "remote":
        conditions.append("is_remote = 1")
    elif work_mode == "onsite":
        conditions.append("is_remote = 0")

    # Career interest pre-filter (broad — exact scoring happens later)
    if interests and not open_to_all:
        interest_kws = []
        for ci in interests[:3]:
            kw = ci.lower().replace("'", "''")
            interest_kws.append(kw)
        if interest_kws:
            # Match against category or combined text
            ci_conds = " OR ".join(
                "LOWER(job_category) LIKE ? OR LOWER(combined_text_for_matching) LIKE ?"
                for _ in interest_kws
            )
            conditions.append(f"({ci_conds})")
            for kw in interest_kws:
                params.extend([f"%{kw}%", f"%{kw}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    candidate_limit = max(limit * 40, 2000)
    sql = (
        f"SELECT * FROM jobs_clean {where} "
        f"ORDER BY job_quality_score DESC "
        f"LIMIT {candidate_limit}"
    )

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
    except Exception as e:
        logger.error("DB query error: %s | SQL: %s | params: %s", e, sql, params)
        return [], {"error": str(e)}

    if not rows:
        # Fallback: try without interest filter
        try:
            fallback_sql = (
                f"SELECT * FROM jobs_clean "
                f"ORDER BY job_quality_score DESC LIMIT {candidate_limit}"
            )
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(fallback_sql).fetchall()
            conn.close()
        except Exception as e2:
            logger.error("Fallback DB query error: %s", e2)
            return [], {"error": str(e2)}

    if not rows:
        return [], {"candidates_scanned": 0, "results_count": 0}

    jobs_raw = [dict(r) for r in rows]
    candidate_ids = [j.get("job_id", "") for j in jobs_raw]

    # ---------- TF-IDF scores ----------
    profile_text = build_profile_text(profile)
    tfidf_scores = {}
    if profile_text.strip():
        try:
            tfidf_scores = get_tfidf_scores(profile_text, candidate_ids)
        except Exception as e:
            logger.warning("TF-IDF scoring skipped: %s", e)

    # ---------- Score all candidates ----------
    remote_only = (work_mode == "remote")
    scored = []
    for job in jobs_raw:
        jid = job.get("job_id", "")
        tsim = tfidf_scores.get(jid, 0.0)
        try:
            result = score_job(
                profile, job,
                tfidf_sim=tsim,
                remote_only_requested=remote_only,
                country_preference=country_pref,
            )
            scored.append(result)
        except Exception as e:
            logger.debug("score_job error for %s: %s", jid, e)

    # Sort by score descending
    scored.sort(key=lambda j: j.get("score", 0), reverse=True)
    top = scored[:limit]

    # Build metadata
    meta = {
        "candidates_scanned": len(jobs_raw),
        "results_count":      len(top),
        "dataset_search_ran": True,
        "country_filter":     country_pref or "none",
        "location_filter":    user_area or "none",
        "work_mode_filter":   work_mode or "none",
        "top_score":          top[0].get("score", 0) if top else 0,
    }
    return top, meta


def ensure_tfidf_ready():
    """Pre-build the TF-IDF index if not already built. Called at startup."""
    global _tfidf_vectorizer
    if _tfidf_vectorizer is None:
        _build_tfidf_index()
