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

def _build_tfidf_index(limit: int = 100_000):
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_job_ids
    if not os.path.exists(DB_PATH):
        return
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT job_id, combined_text_for_matching FROM jobs_clean WHERE job_quality_score > 20 LIMIT ?",
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
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_job_ids
    if _tfidf_vectorizer is None:
        _build_tfidf_index()
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
    Score a single job against profile.
    Weights: role_intent 35%, tfidf 25%, skills 15%, experience 10%, location 10%, salary 5%.
    + Israel location priority bonus: +20 local, +30 exact area, -15 remote (if not wanted), -40 foreign.
    """
    user_skills = [s.lower() for s in profile.get("skills", [])]
    user_interests = profile.get("career_interests", [])
    profile_signals = profile.get("profile_signals", {})
    exp = profile.get("experience", {})
    user_seniority = exp.get("seniority", "")
    loc = profile.get("location_preference", {})
    user_primary = loc.get("primary", "")
    user_fallbacks = loc.get("fallbacks", [])
    remote_allowed = loc.get("remote_allowed", True)
    ws = profile.get("work_style", {})
    user_env = ws.get("preferred_environment", "")
    wp = profile.get("work_preferences", {})
    work_mode = wp.get("work_mode", "")
    sal = profile.get("salary_expectation", {})
    user_min_sal = sal.get("min")
    user_pref_sal = sal.get("preferred")
    user_flexible = sal.get("flexible", True)
    avoid = profile.get("constraints", {}).get("avoid", [])

    job_text = str(job.get("combined_text_for_matching", "") or "")
    job_title = str(job.get("title_clean", "") or "")
    job_category = str(job.get("job_category", "") or "")
    job_description = str(job.get("description_clean", "") or "")

    # Component scores
    role_score, role_reasons = _score_role_intent(user_interests, job_title, job_category, job_description)
    skill_score, matched_skills = _score_skills(user_skills, job_text)
    exp_score = _score_experience(user_seniority, str(job.get("experience_level_clean", "")))
    loc_score, _ = _score_location(
        user_primary, user_fallbacks, remote_allowed,
        str(job.get("location_area", "")), bool(job.get("is_remote", 0))
    )
    sal_score = _score_salary(
        user_min_sal, user_pref_sal, user_flexible,
        job.get("salary_min_clean"), job.get("salary_max_clean")
    )
    soft_boost, soft_reasons = _score_soft_signals(profile_signals, job_text, job_category)
    seniority_bonus = _score_seniority_title(user_seniority, job_title)

    # ── Country-aware location priority layer ────────────────────────────────
    # Boost jobs matching the user's preferred country; penalise others.
    # country_preference: "Israel" | "United States" | "Global" | ""
    #
    # job_country new values (see classify_job_country):
    #   "Israel"                 — raw location_clean confirms Israel
    #   "Israel_possible_remote" — remote job from known Israeli company
    #   "global_or_foreign"      — remote, definitively non-Israeli company
    #   "unknown_remote"         — remote, company presence unknown
    #   "United States"          — non-remote US job
    #   "Other"                  — non-remote non-US
    job_loc_type  = classify_job_location(job)    # "israel"|"remote"|"foreign"
    job_country   = classify_job_country(job)     # see above
    job_location_area = str(job.get("location_area", "") or "")

    # Compute company Israel presence for debug fields (reuse in priority too)
    _company_name = str(job.get("company_clean", "") or "")
    _co_il_presence = company_has_israel_presence(_company_name)

    # Build classification reason string for debug
    _loc_raw = str(job.get("location_clean", "") or "")
    if job_country == "Israel":
        _loc_reason = "raw_location_contains_israeli_keyword"
    elif job_country == "Israel_possible_remote":
        if "israel" in _loc_raw.lower():
            _loc_reason = "remote_with_israel_in_location_clean"
        else:
            _loc_reason = f"remote_from_known_israeli_company: {_company_name}"
    elif job_country == "global_or_foreign":
        _loc_reason = "remote_known_non_israeli_company"
    elif job_country == "unknown_remote":
        _loc_reason = "remote_company_israel_presence_unknown"
    elif job_country == "United States":
        _loc_reason = "us_keyword_in_location_clean"
    else:
        _loc_reason = f"foreign_unclassified: location_area={job.get('location_area', '')!r}"

    if country_preference == "Israel":
        # Exact Israeli city/area match is best (+30)
        area_exact = (
            job_country == "Israel"
            and bool(user_primary)
            and (
                user_primary == job_location_area
                or user_primary.lower() in job_location_area.lower()
                or job_location_area.lower() in user_primary.lower()
            )
        )
        if area_exact:
            location_priority = 30    # confirmed Israeli, exact area
        elif job_country == "Israel":
            location_priority = 20    # confirmed Israeli job
        elif job_country == "Israel_possible_remote":
            location_priority = 5     # remote from Israeli company — may be workable
        elif job_country == "unknown_remote":
            location_priority = -10   # remote but no Israel signal
        elif job_country == "global_or_foreign":
            location_priority = -20   # remote, known non-Israeli
        else:
            location_priority = -40   # US/Other non-remote: excluded from Israel search

    elif country_preference == "United States":
        if job_country == "United States":
            location_priority = 25    # US job bonus
        elif job_country in ("unknown_remote", "global_or_foreign"):
            location_priority = 5     # remote acceptable for US seekers
        elif job_country == "Israel":
            location_priority = -40   # Israeli jobs not relevant for US search
        elif job_country == "Israel_possible_remote":
            location_priority = -20   # Israeli-company remote, not ideal for US search
        else:
            location_priority = -20   # other foreign

    elif country_preference == "Global":
        # Pure content/skill match — no location bias
        location_priority = 0

    else:
        # country_preference not yet set → mild Israel preference (existing behaviour)
        area_exact = (
            job_loc_type == "israel"
            and bool(user_primary)
            and (
                user_primary == job_location_area
                or user_primary.lower() in job_location_area.lower()
                or job_location_area.lower() in user_primary.lower()
            )
        )
        if area_exact:
            location_priority = 30
        elif job_country == "Israel":
            location_priority = 20
        elif job_country == "Israel_possible_remote":
            location_priority = 5
        elif job_loc_type == "remote" and not remote_only_requested:
            location_priority = -15
        elif job_loc_type == "foreign":
            location_priority = -40
        else:
            location_priority = 0

    # Weighted final score (out of 100)
    # soft_boost adds up to ~5 extra points; seniority_bonus can add or subtract ~5 pts.
    # location_priority adds -40 to +30 directly (not weighted — intentional strong signal).
    final_score = (
        role_score      * 35 +
        tfidf_sim       * 25 +
        skill_score     * 15 +
        exp_score       * 10 +
        loc_score       * 10 +
        sal_score       *  5 +
        soft_boost      *  5 +
        seniority_bonus * 20 +
        location_priority          # Israel priority bonus / remote-foreign penalty
    )

    # Build match reasons
    reasons = list(role_reasons)
    reasons.extend(soft_reasons)
    if matched_skills:
        reasons.append(f"כישורים תואמים: {', '.join(matched_skills[:3])}")
    if exp_score > 0.7:
        reasons.append(f"רמת ניסיון מתאימה: {job.get('experience_level_clean', '')}")
    if loc_score > 0.7:
        reasons.append(f"מיקום תואם: {job.get('location_area', '')}")
    if tfidf_sim > 0.15:
        reasons.append("דמיון טקסטואלי גבוה לפרופיל")
    if job.get("salary_display") == "לא צוין":
        reasons.append("השכר לא צוין")
    if not matched_skills and user_skills:
        reasons.append(f"כישורים חסרים: {', '.join(s.title() for s in user_skills[:2])}")
    if loc_score < 0.3 and user_primary:
        reasons.append(f"מיקום פחות מתאים (משרה ב{job.get('location_area', '')})")
    if not reasons:
        reasons.append("תוצאה כללית לפי פרופיל")

    warnings = _check_constraints(avoid, job)
    missing_skills = _get_missing_skills(user_skills, job_text)
    anomaly_flags = [f for f in str(job.get("anomaly_flags", "")).split("|") if f]

    return {
        "job_id": str(job.get("job_id", "")),
        "title": job_title,
        "company_name": str(job.get("company_clean", "")),
        "location": str(job.get("location_clean", "")),
        "location_area": str(job.get("location_area", "")),
        "job_category": job_category,
        "work_type": str(job.get("work_type_clean", "")),
        "experience_level": str(job.get("experience_level_clean", "")),
        "salary_display": str(job.get("salary_display", "לא צוין")),
        "match_score": round(final_score, 1),
        "similarity_score": round(tfidf_sim * 100, 1),
        "match_reasons": reasons,
        "warnings": warnings,
        "missing_skills": missing_skills,
        "anomaly_flags": anomaly_flags,
        "application_url": job.get("application_url"),
        "job_posting_url": job.get("job_posting_url"),
        # Location classification fields (used by frontend + result assembly)
        "job_location_type": job_loc_type,             # "israel" | "remote" | "foreign"
        "job_country": job_country,                    # see classify_job_country() docstring
        "is_israel_job": (job_country == "Israel"),
        # is_remote_fallback: remote shown as last resort when no Israeli jobs found
        "is_remote_fallback": (
            job_country == "unknown_remote"
            and country_preference in ("Israel", "")
            and not remote_only_requested
        ),
        # ── Debug fields (visible in API response for inspection) ──
        "raw_location": _loc_raw,
        "company_has_israel_presence": _co_il_presence,
        "location_classification_reason": _loc_reason,
    }


# ---------------------------------------------------------------------------
# Search entry points
# ---------------------------------------------------------------------------

def _fetch_candidates(location_area: Optional[str], limit: int = 2000,
                       category_hint: Optional[str] = None,
                       country_preference: str = "") -> List[dict]:
    """Fetch candidate jobs with optional location and category filters.

    For Israel searches: only remote jobs are fetched since the dataset is US-centric
    (location_area fields like הדרום/הצפון/המרכז were wrongly mapped by the pipeline
    to US "South/North/Center" locations — they are NOT Israeli jobs).
    """
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if country_preference == "Israel":
            # Only remote jobs — the only ones that can possibly be Israel-relevant
            # in this US-centric dataset (0 jobs have Israeli city in location_clean)
            rows = conn.execute(
                """SELECT * FROM jobs_clean
                   WHERE is_remote = 1 AND job_quality_score > 20
                   ORDER BY job_quality_score DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        elif location_area and location_area not in ("", "אחר"):
            rows = conn.execute(
                """SELECT * FROM jobs_clean
                   WHERE (location_area = ? OR is_remote = 1)
                     AND job_quality_score > 20
                   ORDER BY job_quality_score DESC LIMIT ?""",
                (location_area, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM jobs_clean
                   WHERE job_quality_score > 20
                   ORDER BY job_quality_score DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetch_by_category(category: str, limit: int = 1000) -> List[dict]:
    """Fetch candidates filtered by job_category."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT * FROM jobs_clean
               WHERE job_category = ?
                 AND job_quality_score > 20
               ORDER BY job_quality_score DESC LIMIT ?""",
            (category, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _filter_by_work_prefs(candidates: list, profile: dict) -> list:
    """Post-fetch filter: remove candidates that definitely don't match work_mode/work_type.
    Returns unfiltered list if too few candidates would remain (< 50)."""
    wp = profile.get("work_preferences", {})
    work_mode = wp.get("work_mode", "")   # hybrid | remote | onsite | ""
    work_type = wp.get("work_type", "")   # full_time | part_time | ""

    if not work_mode and not work_type:
        return candidates

    def _matches(job: dict) -> bool:
        jtype = str(job.get("work_type_clean", "")).lower()
        jremote = int(job.get("is_remote", 0))

        if work_mode == "remote" and not jremote:
            return False
        if work_mode == "hybrid" and not jremote:
            # Many jobs labelled as on-site may actually be hybrid; don't filter too aggressively
            pass  # keep — let score handle it
        if work_mode == "onsite" and jremote:
            return False
        if work_type == "full_time" and "חלקי" in jtype:
            return False
        if work_type == "part_time" and ("מלא" in jtype or "full" in jtype):
            return False
        return True

    filtered = [j for j in candidates if _matches(j)]
    return filtered if len(filtered) >= 50 else candidates


def search_jobs(profile: dict, limit: int = 10,
                location_override: Optional[str] = None) -> Tuple[List[dict], dict]:
    """
    Main search function. Implements smart location expansion (Stage 6).
    Also fetches category-specific candidates when career_interests includes known categories.
    Logs candidate counts and filters for dataset-use verification.
    """
    from nlp_engine import build_profile_text

    if not os.path.exists(DB_PATH):
        logger.warning("Dataset DB not found at %s", DB_PATH)
        return [], {"error": "מסד הנתונים לא נמצא. יש לעבד את הנתונים תחילה.",
                    "dataset_search_ran": False}

    loc = profile.get("location_preference", {})
    primary_location = location_override or loc.get("primary", "")
    sal = profile.get("salary_expectation", {})
    sal_min = sal.get("min") or sal.get("preferred")
    wp = profile.get("work_preferences", {})
    work_mode = wp.get("work_mode", "")
    work_type = wp.get("work_type", "")

    # Country preference drives location filtering logic
    country_preference = profile.get("country_preference", "")  # Israel|United States|Global|""

    # Detect remote-only intent (user explicitly asked for remote work)
    remote_only = (
        work_mode == "remote"
        or country_preference == "Global"   # Global search = treat like remote-allowed
        or any(kw in str(primary_location).lower()
               for kw in ("מרחוק", "remote", "עבודה מרחוק"))
    )

    logger.info("Running dataset matching...")
    logger.info(
        "Profile filters: location=%r, work_mode=%r, work_type=%r, salary_min=%s, open_to_all=%s",
        primary_location, work_mode, work_type,
        f"₪{sal_min:,.0f}" if sal_min else "—",
        profile.get("open_to_all", False),
    )

    profile_text = build_profile_text(profile)

    # Determine target categories from career_interests
    user_interests = profile.get("career_interests", [])
    known_categories = set(CATEGORY_TITLE_KEYWORDS.keys())
    target_categories = [i for i in user_interests if i in known_categories]

    # Fetch location-filtered candidates
    fetch_limit = 3000 if profile.get("open_to_all") else 2000
    candidates = _fetch_candidates(primary_location, limit=fetch_limit,
                                   country_preference=country_preference)

    # If we have category hints, augment candidates with category-specific results
    if target_categories:
        for cat in target_categories[:2]:
            cat_candidates = _fetch_by_category(cat, limit=500)
            existing_ids = {c["job_id"] for c in candidates}
            for c in cat_candidates:
                if c["job_id"] not in existing_ids:
                    candidates.append(c)
                    existing_ids.add(c["job_id"])

    # Apply work_mode/work_type pre-filter
    candidates = _filter_by_work_prefs(candidates, profile)

    logger.info("Candidates scanned: %d", len(candidates))

    candidate_ids = [j["job_id"] for j in candidates]
    tfidf_scores = get_tfidf_scores(profile_text, candidate_ids) if candidate_ids else {}

    scored = [score_job(profile, job, tfidf_scores.get(job["job_id"], 0.0),
                        remote_only_requested=remote_only,
                        country_preference=country_preference)
              for job in candidates]

    # Salary post-filter: down-weight jobs with salary below min (don't hard-exclude
    # since many jobs have no salary data)
    if sal_min:
        for j in scored:
            job_sal = j.get("salary_min") or j.get("salary_max") or 0
            if job_sal and job_sal < sal_min * 0.75:
                j["match_score"] = max(0, j["match_score"] - 15)

    strong = [j for j in scored if j["match_score"] >= 60]

    expanded = False
    used_location = primary_location
    expand_reason = ""

    # Stage 6: Location expansion if < 5 strong matches
    if len(strong) < 5 and primary_location:
        fallbacks = LOCATION_FALLBACKS.get(primary_location,
                    ["מרחוק", "תל אביב", "המרכז", "השרון", "השפלה"])
        for fb in fallbacks:
            fb_candidates = _filter_by_work_prefs(_fetch_candidates(fb), profile)
            fb_ids = [j["job_id"] for j in fb_candidates]
            fb_tfidf = get_tfidf_scores(profile_text, fb_ids) if fb_ids else {}
            fb_scored = [score_job(profile, job, fb_tfidf.get(job["job_id"], 0.0),
                                    country_preference=country_preference)
                         for job in fb_candidates]
            fb_strong = [j for j in fb_scored if j["match_score"] >= 60]
            if len(fb_strong) >= 5:
                scored = fb_scored
                strong = fb_strong
                expanded = True
                used_location = fb
                expand_reason = (
                    f"הורחב ל{fb} — מעט התאמות חזקות נמצאו ב{primary_location}."
                )
                break

    # Sort by match score descending
    scored_sorted = sorted(scored, key=lambda j: j["match_score"], reverse=True)

    # ── Country-aware result assembly ─────────────────────────────────────────
    # Split into granular country buckets (new job_country values)
    israel_bucket          = [j for j in scored_sorted if j.get("job_country") == "Israel"]
    possible_remote_bucket = [j for j in scored_sorted if j.get("job_country") == "Israel_possible_remote"]
    us_bucket              = [j for j in scored_sorted if j.get("job_country") == "United States"]
    unknown_remote_bucket  = [j for j in scored_sorted if j.get("job_country") == "unknown_remote"]
    global_foreign_bucket  = [j for j in scored_sorted if j.get("job_country") == "global_or_foreign"]
    other_bucket           = [j for j in scored_sorted if j.get("job_country") == "Other"]

    def _pick_from(buckets: list, n: int, chosen_ids: set) -> list:
        """Pick up to n jobs from ordered bucket list (deduped by job_id)."""
        picked = []
        for job in buckets:
            if len(picked) >= n:
                break
            jid = job.get("job_id")
            if jid not in chosen_ids:
                picked.append(job)
                chosen_ids.add(jid)
        return picked

    chosen_ids: set = set()

    if country_preference == "Global" or remote_only:
        # No country filtering — return top results by score
        results = scored_sorted[:limit]

    elif country_preference == "United States":
        # US jobs first, then remote (any), then other
        MAX_REMOTE_US = 3
        results = _pick_from(us_bucket, limit, chosen_ids)
        if len(results) < limit:
            all_remote = unknown_remote_bucket + global_foreign_bucket
            results += _pick_from(all_remote, min(MAX_REMOTE_US, limit - len(results)), chosen_ids)
        if len(results) < 3:
            results += _pick_from(other_bucket, limit - len(results), chosen_ids)
        results = results[:limit]

    else:
        # Israel (default) — confirmed Israel first, then Israel_possible_remote
        # NEVER include global_or_foreign or plain US jobs in Israel search results
        MAX_POSSIBLE_REMOTE = 2
        results = _pick_from(israel_bucket, limit, chosen_ids)
        results += _pick_from(possible_remote_bucket,
                               min(MAX_POSSIBLE_REMOTE, limit - len(results)),
                               chosen_ids)
        # Last resort: unknown_remote if still very few results
        if len(results) < 3:
            results += _pick_from(unknown_remote_bucket, limit - len(results), chosen_ids)
        results = results[:limit]

    # Count how many of each type ended up in final results
    loc_mix_debug = {
        "israel_candidates":          len(israel_bucket),
        "possible_remote_candidates": len(possible_remote_bucket),
        "us_candidates":              len(us_bucket),
        "unknown_remote_candidates":  len(unknown_remote_bucket),
        "global_foreign_candidates":  len(global_foreign_bucket),
        "other_candidates":           len(other_bucket),
        "israel_returned":          sum(1 for j in results if j.get("job_country") == "Israel"),
        "possible_remote_returned": sum(1 for j in results if j.get("job_country") == "Israel_possible_remote"),
        "us_returned":              sum(1 for j in results if j.get("job_country") == "United States"),
        "unknown_remote_returned":  sum(1 for j in results if j.get("job_country") == "unknown_remote"),
        "global_foreign_returned":  sum(1 for j in results if j.get("job_country") == "global_or_foreign"),
        "other_returned":           sum(1 for j in results if j.get("job_country") == "Other"),
        "country_preference": country_preference or "unset",
        "remote_only_mode": remote_only,
    }

    logger.info(
        "Country mix [%s] — IL: %d  IL_remote: %d  US: %d  ukn_remote: %d  Other: %d",
        country_preference or "unset",
        loc_mix_debug["israel_returned"],
        loc_mix_debug["possible_remote_returned"],
        loc_mix_debug["us_returned"],
        loc_mix_debug["unknown_remote_returned"],
        loc_mix_debug["other_returned"],
    )
    logger.info("Results returned: %d (top score: %s)",
                len(results), f"{results[0]['match_score']:.1f}" if results else "—")
    if results:
        from collections import Counter
        cats = Counter(j.get("category") or j.get("job_category", "") for j in results)
        top_cats = [c for c, _ in cats.most_common(4) if c]
        logger.info("Top categories: %s", ", ".join(top_cats) if top_cats else "—")

    metadata = {
        "primary_location": primary_location,
        "used_location": used_location,
        "expanded": expanded,
        "reason": expand_reason,
        "total_searched": len(candidates),
        "total_returned": len(results),
        # Debug fields visible in API response
        "dataset_search_ran": True,
        "candidates_scanned": len(candidates),
        "results_count": len(results),
        "location_mix_debug": loc_mix_debug,   # legacy key (kept for compat)
        "location_scope_debug": {
            "country_preference": country_preference or None,
            "country_filter_applied": bool(country_preference),
            "results_country_mix": {
                "Israel":                loc_mix_debug["israel_returned"],
                "Israel_possible_remote": loc_mix_debug["possible_remote_returned"],
                "United States":         loc_mix_debug["us_returned"],
                "unknown_remote":        loc_mix_debug["unknown_remote_returned"],
                "global_or_foreign":     loc_mix_debug["global_foreign_returned"],
                "Other":                 loc_mix_debug["other_returned"],
            },
        },
    }

    return results, metadata


def ensure_tfidf_ready():
    if _tfidf_vectorizer is None:
        _build_tfidf_index()
