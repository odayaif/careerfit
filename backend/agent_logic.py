"""
agent_logic.py — Conversational AI agent logic.
Smart onboarding, education→career inference, domain skill detection,
auto-search trigger, off-topic guard, soft-signal confirmation.
"""
import re
import logging
from typing import Optional
from models import empty_profile, profile_completeness
from nlp_engine import (
    extract_profile_updates, merge_profile_updates,
    detect_language, detect_career_direction_change,
    is_open_to_all,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

INTENT_PATTERNS_ORDERED = [
    ("reset_profile", [
        r"אפס|reset|התחל מחדש|start over|start fresh|מחק פרופיל|clear profile",
    ]),
    ("search_jobs", [
        r"חפש לי|חיפוש|מצא לי|find jobs?|search jobs?|show me jobs",
        r"הצג משרות|הראה לי משרות|איזה משרות|what jobs|recommend|המלץ",
        r"תמצא לי עבודה|רוצה עבודה|תציע לי משרות|match me|find me work",
        r"אפשר לראות משרות|מה מתאים לי",
    ]),
    ("expand_location", [
        r"הרחב|expand search|enlarge|מקומות נוספים|more locations?|wider search",
    ]),
    ("skill_gap_analysis", [
        r"כישורים חסרים|missing skills?|skill gap|מה לפתח|מה ללמוד|improve",
        r"מה כדאי ללמוד|what to learn|courses?|קורסים",
    ]),
    ("career_advice", [
        r"ייעוץ קריירה|career advice|עצה לקריירה|כיוון קריירה|future career",
        r"מה מתאים לי|what career fits|מה כדאי לי|what should i",
        r"אני לא יודע[תי]?(?:\s+מה|$)",
    ]),
    ("salary_advice", [
        r"שכר|salary|כסף|earn|מרוויח|הכנסה|income|negotiate",
    ]),
    ("show_trends", [
        r"מגמות|trends?|שוק עבודה|job market|סטטיסטיקות|statistics",
    ]),
    ("show_clusters", [
        r"אשכולות|clusters?|קבוצות משרות|job groups?",
    ]),
    ("show_anomalies", [
        r"חריגות|anomalies?|בעיות|unusual",
    ]),
    ("explain_recommendation", [
        r"למה|why|explain|הסבר|מדוע",
    ]),
    ("update_profile", [
        r"אני|i am|my|שלי|יש לי|i have|i know|אני יודע|אני מחפש|looking for|prefer|מעדיף",
        r"הניסיון שלי|my experience|כישור|skill|השכלה|education|לא רוצה|don.?t want",
        r"ניסיון|experience|background|רקע",
    ]),
]


def detect_intent(message: str, profile: dict) -> str:
    msg_lower = message.lower()
    for intent, patterns in INTENT_PATTERNS_ORDERED:
        for pat in patterns:
            if re.search(pat, msg_lower, re.IGNORECASE):
                return intent
    if profile_completeness(profile) < 20:
        return "onboarding"
    return "update_profile"


# ---------------------------------------------------------------------------
# Off-topic guard
# ---------------------------------------------------------------------------

OFFTOPIC_PATTERNS = [
    r"(?:איזה|מי|which)\s+(?:שחקן|זמר|ספורטאי|סופר|מחבר|actor|singer|musician|author)\b",
    r"\b(?:מתכון|recipe|how to cook|איך מכינים)\b",
    r"(?:תוצאות משחק|sport.*score|מי ניצח|who won|כדורגל.*תוצאה)",
    r"\b(?:מזג אוויר|weather forecast|what.?s the weather)\b",
    r"(?:\bפוליטיק|party politics|party leader|president of|ראש ממשלה|בחירות)\b",
    r"(?:עצה רפואית|medical advice|what medicine|what drug)\b",
]


def _is_offtopic(message: str) -> bool:
    tl = message.lower()
    return any(re.search(pat, tl, re.IGNORECASE) for pat in OFFTOPIC_PATTERNS)


# ---------------------------------------------------------------------------
# Yes / No detection
# ---------------------------------------------------------------------------

def _is_affirmative(message: str) -> bool:
    tl = message.strip().lower()
    return bool(re.search(
        r"^(?:כן|yeah|yes|sure|בטח|מסכים[ה]?|אכן|בוודאי|ok|okay|נכון|בהחלט|כמובן)\b",
        tl, re.IGNORECASE
    ))


def _is_negative(message: str) -> bool:
    tl = message.strip().lower()
    return bool(re.search(
        r"^(?:לא|no|nope|לא ממש|לא בדיוק|זה רק|רק תחביב|לא קשור|לא רלוונטי)\b",
        tl, re.IGNORECASE
    ))


# Replies the user can give when asked the refinement question that mean "nothing to add, search now"
def _is_refinement_decline(message: str) -> bool:
    """True when the user has nothing to add and wants the search to proceed."""
    tl = message.strip().lower()
    return bool(re.search(
        r"^(?:לא|אין|בסדר|ok|okay|no|nope|nothing|לא כרגע|לא עכשיו|תחפש|go|search|yes|כן)\b",
        tl, re.IGNORECASE
    ))


# The refinement question shown when profile is "complete enough" but we offer one last chance
REFINEMENT_Q_HE = "יש עוד משהו שתרצה/י להוסיף על עצמך כדי לדייק את ההתאמה?"
REFINEMENT_Q_EN = "Anything else you'd like to add to refine the job match?"

# Country selection — first location question (before asking Israeli area)
COUNTRY_Q_HE = "באיזו מדינה לחפש? ישראל, ארה״ב או לא משנה?"
COUNTRY_Q_EN = "Which country should I search in? Israel, United States, or anywhere?"

# Israeli area — only asked after user chooses Israel
ISRAEL_AREA_Q_HE = "באיזו עיר או אזור בישראל לחפש?"
ISRAEL_AREA_Q_EN = "Which city or area in Israel should I search?"


# ---------------------------------------------------------------------------
# Onboarding questions — short, career-focused
# ---------------------------------------------------------------------------

ONBOARDING_QUESTIONS_HE = [
    ("education",           "מה למדת?"),
    ("experience",          "כמה ניסיון יש לך?"),
    ("skills",              "אילו כישורים יש לך?"),
    ("career_interests",    "איזה תפקיד מעניין אותך?"),
    ("country_preference",  COUNTRY_Q_HE),
    ("location_preference", ISRAEL_AREA_Q_HE),
    ("salary_expectation",  "מה ציפיות השכר?"),
    ("work_style",          "היברידי, מרחוק או מהמשרד?"),
    ("constraints",         "ממה להימנע?"),
]

ONBOARDING_QUESTIONS_EN = [
    ("education",           "What did you study?"),
    ("experience",          "How many years of experience do you have?"),
    ("skills",              "What skills do you have?"),
    ("career_interests",    "What role interests you?"),
    ("country_preference",  COUNTRY_Q_EN),
    ("location_preference", ISRAEL_AREA_Q_EN),
    ("salary_expectation",  "What are your salary expectations?"),
    ("work_style",          "Hybrid, remote, or office?"),
    ("constraints",         "Anything to avoid?"),
]

# Career domains that substitute for explicit skills listing
_DOMAIN_CAREER_INTERESTS = {
    "פיתוח תוכנה", "תכנות", "עיצוב", "UX/UI", "דאטה", "BI",
    "שיווק", "תוכן", "ניהול", "כספים", "חינוך", "תפעול",
    "הנדסת תוכנה", "מדעי נתונים", "ניתוח מערכות",
    "ניהול משרד", "אדמיניסטרציה", "משאבי אנוש", "גיוס",
    "מכירות", "ניהול לקוחות", "שירות לקוחות",
    "הדרכה", "Customer Success",
    "בריאות", "סיעוד", "פסיכולוגיה", "עבודה סוציאלית",
    "משפטים", "ייעוץ משפטי", "לוגיסטיקה", "שרשרת אספקה",
    "ניהול פרויקטים", "מוצר", "ניהול מוצר", "הנדסה",
    "חשבונאות", "QA", "בדיקות תוכנה",
    # Cyber / InfoSec
    "אבטחת מידע", "סייבר", "Cyber Security", "SOC", "GRC",
    "Information Security",
}

PROFILE_FIELD_CHECK = {
    "education":           lambda p: bool(p.get("education", {}).get("degree") or p.get("education", {}).get("field")),
    "experience":          lambda p: (p.get("experience", {}).get("years") is not None or bool(p.get("experience", {}).get("seniority"))),
    # Skills: satisfied if explicit skills exist OR if career_interests already captures a domain
    "skills":              lambda p: bool(p.get("skills")) or bool(
        set(p.get("career_interests", [])) & _DOMAIN_CAREER_INTERESTS
    ),
    "career_interests":    lambda p: bool(p.get("career_interests")),
    # country_preference: satisfied as soon as any value is set
    "country_preference":  lambda p: bool(p.get("country_preference")),
    # location_preference: satisfied if country=US/Global (no area needed), OR Israel area set
    "location_preference": lambda p: _location_known(p),
    "salary_expectation":  lambda p: (
        p.get("salary_expectation", {}).get("preferred") is not None or
        p.get("salary_expectation", {}).get("min") is not None
    ),
    "work_style":          lambda p: bool(p.get("work_style", {}).get("preferred_environment")),
    "constraints":         lambda p: bool(p.get("constraints", {}).get("avoid")),
}


def _location_known(profile: dict) -> bool:
    """
    Return True when we have enough location info to run a search.
    - Global / United States: country_preference alone is sufficient.
    - Israel: needs country_preference=Israel AND a location_area.primary.
    - Legacy (no country_preference): check location_area.primary directly.
    """
    country = profile.get("country_preference", "")
    if country in ("United States", "Global"):
        return True
    if country == "Israel":
        return bool(profile.get("location_preference", {}).get("primary"))
    # No country set yet — check for direct area (legacy / implicit Israel)
    return bool(profile.get("location_preference", {}).get("primary"))


def _get_question_slot(question: str) -> str:
    """Infer the semantic slot from the question text for pending-answer tracking."""
    q = question.lower()
    if any(w in q for w in ["ניסיון", "experience", "ותק", "שנות", "license", "רישיון",
                              "certificate", "תעודה", "portfolio", "תיק"]):
        return "experience"
    # Country question (must be checked before generic location so it isn't swallowed)
    if any(w in q for w in ["מדינה", "country", "ישראל, ארה", "israel, united",
                              "ארה״ב", "united states", "לא משנה"]):
        return "country"
    # Israeli area (only asked after country=Israel is known)
    if any(w in q for w in ["אזור", "area", "location", "where", "עיר", "city", "region",
                              "בישראל"]):
        return "location"
    if any(w in q for w in ["למדת", "תואר", "degree", "studied", "education", "השכלה"]):
        return "education"
    return "general"


def _record_question(profile: dict, question: str):
    conv = profile.setdefault("conversation", {})
    # asked_questions: sequential, allows duplicates — used for no-repeat guard (last 3)
    asked = conv.setdefault("asked_questions", [])
    asked.append(question)
    if len(asked) > 10:
        asked[:] = asked[-10:]
    # question_history: deduped — used by pick() and legacy code
    history = conv.setdefault("question_history", [])
    if question not in history:
        history.append(question)
    if len(history) > 10:
        history[:] = history[-10:]
    conv["last_bot_question"] = question
    conv["last_question"] = question  # legacy alias
    # pending_question metadata for yes/no answer interpretation
    slot   = _get_question_slot(question)
    domain = _detect_domain(profile) or ""
    conv["pending_question"] = {"slot": slot, "domain": domain, "question": question}
    # Track whether refinement was ever asked (can only be asked once per conversation)
    if question in (REFINEMENT_Q_HE, REFINEMENT_Q_EN):
        conv["refinement_asked"] = True


# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------

def _detect_domain(profile: dict) -> Optional[str]:
    """Detect primary career domain from career_interests + skills + previous_roles.
    Returns None when open_to_all=True so domain-specific questions are suppressed."""
    if profile.get("open_to_all"):
        return None  # user signalled openness → don't lock into any domain
    interests_lower = set(i.lower() for i in profile.get("career_interests", []))
    skills_lower    = set(s.lower() for s in profile.get("skills", []))
    prev_roles      = " ".join(profile.get("experience", {}).get("previous_roles", [])).lower()

    # QA / Testing (check before data — SQL+QA should resolve to qa)
    qa_interest_kw = {"qa", "בדיקות תוכנה", "software testing", "quality assurance"}
    qa_skill_kw    = {"qa", "selenium", "cypress", "appium", "postman"}
    if interests_lower & qa_interest_kw or skills_lower & qa_skill_kw:
        return "qa"

    data_interest_kw = {"דאטה", "bi", "ניתוח מערכות", "ניתוח נתונים", "מדעי נתונים"}
    data_skill_kw    = {"sql", "mysql", "postgresql", "excel", "power bi", "tableau",
                        "looker", "qlik", "bi", "etl"}
    if interests_lower & data_interest_kw or skills_lower & data_skill_kw:
        return "data"

    edu_interest_kw = {"חינוך", "הוראה"}
    if (edu_interest_kw & interests_lower
            or any("מורה" in i or "teacher" in i for i in profile.get("career_interests", []))):
        return "education"

    # Cyber / Information Security (before software — cyber is more specific)
    cyber_interest_kw = {"אבטחת מידע", "סייבר", "cyber security", "information security",
                         "soc", "grc", "infosec"}
    cyber_skill_kw    = {"cyber security", "siem"}
    if interests_lower & cyber_interest_kw or skills_lower & cyber_skill_kw:
        return "cyber"

    sw_interest_kw = {"פיתוח תוכנה", "תכנות", "הנדסת תוכנה"}
    sw_skill_kw    = {"programming", "java", "javascript", "typescript", "python", "react",
                      "angular", "vue", "node.js", "c#", "php", "ruby", "swift", "kotlin"}
    if interests_lower & sw_interest_kw or skills_lower & sw_skill_kw:
        return "software"

    # Business / Office / Admin
    business_kw = {"ניהול משרד", "אדמיניסטרציה", "ניהול עסקים", "ניהול עסקי",
                   "business administration", "office manager"}
    if interests_lower & business_kw:
        return "business"
    # Also detect from previous_roles
    if any(kw in prev_roles for kw in ("משרד", "מנהל", "אדמיני", "office", "admin", "business")):
        if interests_lower & {"ניהול", "תפעול", "אדמיניסטרציה", "ניהול משרד"}:
            return "business"

    # People-facing broad (when all interests are people-related, no specific domain yet)
    # Must come BEFORE hr so "אנשים" answer stays in "people" domain for sub-direction Q
    people_broad_kw = {"משאבי אנוש", "שירות לקוחות", "הדרכה", "customer success"}
    if interests_lower and (interests_lower <= people_broad_kw):
        return "people"

    # HR / Recruiting (specific — user named a role, not just "אנשים")
    hr_kw = {"משאבי אנוש", "גיוס"}
    if hr_kw & interests_lower:
        return "hr"

    # Sales
    sales_kw = {"מכירות", "ניהול לקוחות"}
    if sales_kw & interests_lower:
        return "sales"

    # Customer Service
    if "שירות לקוחות" in interests_lower:
        return "service"

    # Finance / Accounting
    if interests_lower & {"כספים", "חשבונאות", "פיננסים"}:
        return "finance"

    # Marketing
    if interests_lower & {"שיווק", "תוכן", "יחסי ציבור"}:
        return "marketing"

    # Design / UX
    if interests_lower & {"עיצוב", "ux/ui"}:
        return "design"

    # Healthcare / Medical / Social
    healthcare_kw = {"בריאות", "סיעוד", "רפואה"}
    social_kw     = {"עבודה סוציאלית", "פסיכולוגיה"}
    if healthcare_kw & interests_lower:
        return "healthcare"
    if social_kw & interests_lower:
        return "social"

    # Law / Legal
    if interests_lower & {"משפטים", "ייעוץ משפטי"}:
        return "law"

    # Logistics
    if interests_lower & {"לוגיסטיקה", "שרשרת אספקה"}:
        return "logistics"

    # Operations / Project management
    if interests_lower & {"תפעול", "ניהול פרויקטים"}:
        return "operations"

    # Product management
    if interests_lower & {"מוצר", "ניהול מוצר"}:
        return "product"

    # Engineering (non-software)
    if "הנדסה" in interests_lower:
        return "engineering"

    # General management (fallback when only "ניהול" present)
    if "ניהול" in interests_lower:
        return "management"

    return None


# ---------------------------------------------------------------------------
# Context-aware next question
# ---------------------------------------------------------------------------

OPEN_TO_ALL_Q_HE = "מה יותר מעניין אותך — אנשים, נתונים, ניהול, יצירה או טכנולוגיה?"
OPEN_TO_ALL_Q_EN = "What draws you more — people, data, management, creativity, or tech?"
DIRECTION_MISSING_Q_HE = "איזה תחום או תפקיד מעניין אותך?"
DIRECTION_MISSING_Q_EN = "What field or role interests you?"


def _has_strong_constraint(profile: dict) -> bool:
    """True when profile has at least one concrete constraint we can filter on."""
    wp = profile.get("work_preferences", {})
    sal = profile.get("salary_expectation", {})
    return bool(
        wp.get("work_type") or wp.get("work_mode") or
        sal.get("preferred") or sal.get("min") or
        profile.get("location_preference", {}).get("primary")
    )


def next_context_aware_question(profile: dict, lang: str) -> Optional[str]:
    """
    Returns the next useful question based on detected career domain.
    Returns None when all domain questions are satisfied (→ trigger search).
    Falls back to generic onboarding when no domain is detected.

    IMPORTANT: pick() checks last 2 asked questions (not just the last one).
    Domain flows use explicit fall-through: if a question is blocked by pick(),
    the next condition is checked rather than returning None immediately.
    """
    domain = _detect_domain(profile)
    is_he = lang != "English"

    exp       = profile.get("experience", {})
    # has_exp: any numeric years (0 = no exp), explicit seniority, OR answered flag
    # (experience_answered=True is set when user says yes/no to an experience question)
    has_exp   = (
        exp.get("years") is not None
        or bool(exp.get("seniority"))
        or bool(exp.get("experience_answered"))
    )
    # has_loc: True when we have enough location info to run a search
    # (country=US/Global → no area needed; country=Israel → need area too)
    has_loc   = _location_known(profile)
    skills    = profile.get("skills", [])
    # Specific skill = any skill except the generic "Programming" / "Design" / "Cyber Security" token
    specific_skills = [s for s in skills if s not in ("Programming", "Design", "Cyber Security")]
    has_specific_skill = bool(specific_skills)

    history  = profile.get("conversation", {}).get("question_history", [])
    recent   = history[-2:]  # last 2 asked questions

    def pick(q: str) -> Optional[str]:
        """Return q only if it was NOT among the last 2 asked questions."""
        return q if q not in recent else None

    def _loc_q() -> Optional[str]:
        """Return the next appropriate location question (country → Israeli area → None)."""
        country = profile.get("country_preference", "")
        if not country:
            return pick(COUNTRY_Q_HE if is_he else COUNTRY_Q_EN)
        if country == "Israel" and not profile.get("location_preference", {}).get("primary"):
            return pick(ISRAEL_AREA_Q_HE if is_he else ISRAEL_AREA_Q_EN)
        return None  # US / Global — no more location questions

    # ── open_to_all: no domain locked in ─────────────────────────────────────
    # When user said "הכל" / "לא משנה לי" and domain is None:
    # if they also gave constraints → return None to trigger broad search.
    # Otherwise → ask the broad direction question.
    if profile.get("open_to_all") and domain is None:
        if _has_strong_constraint(profile):
            return None  # constraints present → let process_message run broad search
        q = pick(OPEN_TO_ALL_Q_HE if is_he else OPEN_TO_ALL_Q_EN)
        if q:
            return q
        # Broad Q was just asked and user responded with something unrecognised →
        # fall through to DIRECTION_MISSING_Q instead of repeating
        return pick(DIRECTION_MISSING_Q_HE if is_he else DIRECTION_MISSING_Q_EN)

    # Helper: standard 2-step (experience → location → None)
    # loc_q_he/en are ignored — _loc_q() drives location questions now.
    def _exp_then_loc(exp_q_he, exp_q_en, loc_q_he=None, loc_q_en=None):
        if not has_exp:
            q = pick(exp_q_he if is_he else exp_q_en)
            if q:
                return q
        if not has_loc:
            q = _loc_q()
            if q:
                return q
        return None

    if domain == "data":
        return _exp_then_loc(
            "כמה ניסיון יש לך בדאטה/BI?", "How much data/BI experience do you have?"
        )

    elif domain == "education":
        # teaching: country/location first (schools are location-bound), then certificate
        if not has_loc:
            q = _loc_q()
            if q:
                return q
        if not has_exp:
            q = pick("יש לך תעודת הוראה או ניסיון בהוראה?" if is_he else
                     "Do you have a teaching certificate or teaching experience?")
            if q:
                return q
        return None

    elif domain == "cyber":
        # cyber flow: experience → specialization (SOC/GRC/pentest/network) → location
        interests_combined = " ".join(profile.get("career_interests", []) + profile.get("skills", [])).lower()
        has_cyber_spec = any(kw in interests_combined for kw in
                             ["soc", "grc", "pentest", "network security", "cloud security",
                              "penetration", "application security"])
        if not has_exp:
            q = pick("יש לך ניסיון באבטחת מידע, רשתות או IT?" if is_he else
                     "Do you have experience in cyber security, networking, or IT?")
            if q:
                return q
        if not has_cyber_spec:
            q = pick("מעניין אותך יותר SOC, רשתות, GRC או בדיקות חדירות?" if is_he else
                     "Are you more interested in SOC, networking, GRC, or penetration testing?")
            if q:
                return q
        if not has_loc:
            q = _loc_q()
            if q:
                return q
        return None

    elif domain == "software":
        # software flow: specific language → experience → location
        if not has_specific_skill:
            q = pick("יש שפה או תחום שמעניין אותך — Python, Java, Frontend?" if is_he else
                     "Any preferred language — Python, Java, Frontend?")
            if q:
                return q
        if not has_exp:
            q = pick("כמה ניסיון יש לך בפיתוח?" if is_he else "How much development experience do you have?")
            if q:
                return q
        if not has_loc:
            q = _loc_q()
            if q:
                return q
        return None

    elif domain == "people":
        # People-facing broad: ask sub-direction first, then experience, then location
        sub_q_he = "מעדיפ/ה עבודה מול לקוחות, הדרכה, משאבי אנוש או טיפול?"
        sub_q_en = "Do you prefer customer-facing, training, HR, or care roles?"
        q = pick(sub_q_he if is_he else sub_q_en)
        if q:
            return q
        return _exp_then_loc(
            "יש לך ניסיון בתחום?", "Do you have experience in this field?"
        )

    elif domain == "design":
        return _exp_then_loc(
            "יש לך תיק עבודות או ניסיון בעיצוב?", "Do you have a portfolio or design experience?"
        )

    elif domain == "business":
        return _exp_then_loc(
            "יש לך ניסיון בתחום?", "Do you have experience in this field?"
        )

    elif domain == "hr":
        return _exp_then_loc(
            "יש לך ניסיון בגיוס או משאבי אנוש?", "Do you have HR or recruiting experience?"
        )

    elif domain == "sales":
        return _exp_then_loc(
            "כמה ניסיון יש לך במכירות?", "How much sales experience do you have?"
        )

    elif domain == "service":
        return _exp_then_loc(
            "יש לך ניסיון בשירות לקוחות?", "Do you have customer service experience?"
        )

    elif domain == "marketing":
        return _exp_then_loc(
            "יש לך ניסיון בשיווק דיגיטלי או תוכן?", "Do you have digital marketing or content experience?"
        )

    elif domain == "finance":
        return _exp_then_loc(
            "כמה ניסיון יש לך בתחום הכספים?", "How much finance experience do you have?"
        )

    elif domain == "healthcare":
        return _exp_then_loc(
            "יש לך רישיון או ניסיון בתחום הרפואי?", "Do you have a license or medical experience?"
        )

    elif domain == "social":
        return _exp_then_loc(
            "יש לך ניסיון בעבודה סוציאלית או ייעוץ?", "Do you have social work or counseling experience?"
        )

    elif domain == "law":
        return _exp_then_loc(
            "יש לך רישיון עורך דין או ניסיון משפטי?", "Are you a licensed attorney or do you have legal experience?"
        )

    elif domain == "logistics":
        return _exp_then_loc(
            "יש לך ניסיון בלוגיסטיקה, רכש או שרשרת אספקה?", "Do you have logistics or supply chain experience?"
        )

    elif domain == "operations":
        return _exp_then_loc(
            "יש לך ניסיון בתפעול או ניהול פרויקטים?", "Do you have operations or project management experience?"
        )

    elif domain == "product":
        return _exp_then_loc(
            "יש לך ניסיון בניהול מוצר?", "Do you have product management experience?"
        )

    elif domain == "engineering":
        return _exp_then_loc(
            "יש לך ניסיון בתחום ההנדסה?", "Do you have engineering experience?"
        )

    elif domain == "management":
        return _exp_then_loc(
            "יש לך ניסיון בניהול?", "Do you have management experience?"
        )

    elif domain == "qa":
        return _exp_then_loc(
            "כמה ניסיון יש לך בבדיקות תוכנה?", "How much QA/testing experience do you have?"
        )

    # No domain detected → fall back to generic onboarding order
    return next_onboarding_question(profile, lang)


def next_onboarding_question(profile: dict, lang: str) -> Optional[str]:
    questions = ONBOARDING_QUESTIONS_EN if lang == "English" else ONBOARDING_QUESTIONS_HE
    history = profile.get("conversation", {}).get("question_history", [])
    last_q = history[-1] if history else ""

    for field, question in questions:
        check = PROFILE_FIELD_CHECK.get(field, lambda p: False)
        if not check(profile):
            if question == last_q:
                continue  # skip just-asked question
            return question
    return None


# ---------------------------------------------------------------------------
# Short reply helpers
# ---------------------------------------------------------------------------

def _join(lst, n=5):
    return ", ".join(lst[:n])


def _build_update_ack(updates: dict, lang: str, direction_changed: bool = False) -> str:
    """One-line ack only for direction change or constraint filter."""
    if direction_changed and updates.get("career_interests"):
        dirs = _join(updates["career_interests"], 2)
        return ("אעבור לכיוון " + dirs + ".") if lang != "English" else ("Switching to " + dirs + ".")
    con = updates.get("constraints", {})
    if con.get("avoid"):
        items = _join(con["avoid"], 2)
        return ("אסנן " + items + ".") if lang != "English" else ("Filtering out " + items + ".")
    return ""


DIRECTION_Q_HE = "זה כיוון שמעניין אותך?"
DIRECTION_Q_EN = "Is this a direction that interests you?"

UNCERTAINTY_HE = "מה מושך אותך יותר — אנשים, נתונים, יצירה או ניהול?"
UNCERTAINTY_EN = "What draws you more — people, data, creativity, or management?"

HOBBY_ONLY_HE = "הבנתי. איזה תחום עבודה כן מעניין אותך?"
HOBBY_ONLY_EN = "Got it. What work field interests you?"

CONFIRMED_HE = "אפשר לכוון למשרות {dirs}. יש לך ניסיון בתחום?"
CONFIRMED_EN = "I can target {dirs} roles. Do you have experience in this area?"


def _build_soft_reply(soft: dict, lang: str) -> str:
    if soft.get("reply_hint") == "uncertainty":
        return UNCERTAINTY_HE if lang != "English" else UNCERTAINTY_EN
    dirs = soft.get("possible_career_directions", [])
    if dirs:
        dirs_text = ", ".join(dirs[:3])
        if lang == "English":
            return "This could lead to " + dirs_text + " roles. " + DIRECTION_Q_EN
        return "זה יכול לכוון ל" + dirs_text + ". " + DIRECTION_Q_HE
    return ""


def _student_job_reply(profile: dict, jobs: list, search_metadata: dict, lang: str) -> str:
    """Short job reply tailored for students/juniors."""
    interests = profile.get("career_interests", [])
    main = interests[0] if interests else ""
    if jobs:
        expanded = search_metadata.get("expanded", False)
        if expanded:
            return ("מצאתי מעט התאמות באזור שבחרת, אז הרחבתי לאזורים קרובים." if lang != "English"
                    else "Few matches nearby, so I expanded to adjacent areas.")
        if main and lang != "English":
            return "מצאתי משרות " + main + " מתאימות לסטודנטים וג'וניורים."
        return "Found matching jobs for students and juniors, ranked by fit."
    return ("לא מצאתי התאמה מדויקת. אפשר להרחיב אזור או לרכך תנאי אחד." if lang != "English"
            else "No exact matches. Try expanding location or relaxing one condition.")


def _top_categories_from_jobs(jobs: list, top_n: int = 4) -> list:
    """Extract the most common job categories from a list of scored jobs.
    Uses the real category data returned by the matching engine — no invention."""
    from collections import Counter
    cats = Counter()
    for j in jobs:
        cat = j.get("category") or j.get("job_category") or ""
        if cat and cat not in ("לא ידוע", "unknown", ""):
            cats[cat] += 1
    return [c for c, _ in cats.most_common(top_n)]


# ---------------------------------------------------------------------------
# Main reply generator
# ---------------------------------------------------------------------------

def generate_reply(intent: str, message: str, profile: dict, updates: dict,
                   jobs: list, search_metadata: dict, lang: str,
                   direction_changed: bool = False, soft: dict = None,
                   edu_reply_hint: str = "", domain_answered: bool = False,
                   auto_searched: bool = False,
                   domain_reply_hint: str = "",
                   pending_domain_q: Optional[str] = None,
                   decided_action: dict = None) -> str:
    soft = soft or {}
    ack = _build_update_ack(updates, lang, direction_changed)

    is_student = profile.get("experience", {}).get("seniority") in ("סטודנט/ית", "student")
    has_interests = bool(profile.get("career_interests"))
    has_location = bool(profile.get("location_preference", {}).get("primary"))

    # ── 0. Off-topic guard ────────────────────────────────────────────────────
    if _is_offtopic(message):
        return ("אני מתמקד בחיפוש עבודה וקריירה." if lang != "English"
                else "I focus on job search and career guidance.")

    # ── 1. Reset ──────────────────────────────────────────────────────────────
    if intent == "reset_profile":
        return ("הפרופיל אופס. מה למדת?" if lang != "English"
                else "Profile reset. What did you study?")

    # ── 2. Career direction change ────────────────────────────────────────────
    if direction_changed and updates.get("career_interests"):
        new_dir = _join(updates["career_interests"], 2)
        if jobs:
            cnt = str(len(jobs))
            return ("אעבור לכיוון " + new_dir + ". מצאתי " + cnt + " משרות." if lang != "English"
                    else "Switching to " + new_dir + ". Found " + cnt + " jobs.")
        if not has_location:
            _cp = profile.get("country_preference", "")
            _loc_follow = (
                (COUNTRY_Q_HE if lang != "English" else COUNTRY_Q_EN)
                if not _cp
                else (ISRAEL_AREA_Q_HE if (lang != "English" and _cp == "Israel")
                      else (ISRAEL_AREA_Q_EN if _cp == "Israel" else ""))
            )
            if _loc_follow:
                return ("אעבור לכיוון " + new_dir + ". " + _loc_follow if lang != "English"
                        else "Switching to " + new_dir + ". " + _loc_follow)
        return ("אעבור לכיוון " + new_dir + ". לא נמצאו משרות מדויקות — מציג קרובות." if lang != "English"
                else "Switching to " + new_dir + ". No exact matches — showing closest.")

    # ── 3. Job search / auto-search results ──────────────────────────────────
    open_to_all = bool(profile.get("open_to_all"))
    if jobs or (intent == "search_jobs" and not direction_changed) or auto_searched:
        if jobs:
            if is_student and has_interests:
                return _student_job_reply(profile, jobs, search_metadata, lang)
            expanded = search_metadata.get("expanded", False)
            if expanded:
                return ("מצאתי מעט התאמות באזור שבחרת, אז הרחבתי לאזורים קרובים." if lang != "English"
                        else "Few matches nearby, so I expanded to adjacent areas.")
            # Broad/open-to-all search: group results by top categories
            if open_to_all and not has_interests:
                cats = _top_categories_from_jobs(jobs)
                if cats and lang != "English":
                    return ("מצאתי משרות בכמה כיוונים. הכי רלוונטיים לפרופיל שלך: "
                            + ", ".join(cats[:4]) + ". איזה כיוון תרצ/י לראות קודם?")
                elif cats:
                    return ("Found jobs across several fields: " + ", ".join(cats[:4])
                            + ". Which direction would you like to see first?")
            return ("מצאתי משרות מתאימות. דירגתי אותן לפי התאמה לפרופיל שלך." if lang != "English"
                    else "Found matching jobs, ranked by profile fit.")
        # No jobs found
        if open_to_all:
            # Ask direction instead of expand-area when open_to_all has no results
            return (DIRECTION_MISSING_Q_HE if lang != "English" else DIRECTION_MISSING_Q_EN)
        return ("לא מצאתי התאמה מדויקת. אפשר להרחיב אזור או לרכך תנאי אחד." if lang != "English"
                else "No exact matches. Try expanding location or relaxing one condition.")

    # ── 4. Expand location ────────────────────────────────────────────────────
    if intent == "expand_location":
        if not jobs:
            return ("לא נמצאו משרות גם לאחר הרחבה." if lang != "English"
                    else "No jobs found even after expanding.")
        used_loc = search_metadata.get("used_location", "")
        return ("הרחבתי ל" + used_loc + ". נמצאו " + str(len(jobs)) + " משרות." if lang != "English"
                else "Expanded to " + used_loc + ". Found " + str(len(jobs)) + " jobs.")

    # ── 5. Soft signal with suggested career directions ───────────────────────
    if soft and soft.get("possible_career_directions") and not updates.get("career_interests"):
        return _build_soft_reply(soft, lang)

    # ── 6. Education-based smart reply ───────────────────────────────────────
    # edu_reply_hint already contains the full first question from EDUCATION_CAREER_MAP.
    # Show it when: no domain_answered in same turn, no location yet.
    if edu_reply_hint and not domain_answered and not has_location:
        return edu_reply_hint

    # ── 7-9. Unified Q-selection via decide_next_action ──────────────────────
    # Single decision point: handles domain inference, open_to_all, onboarding,
    # refinement (at most ONCE per conversation), and hard no-repeat guard (last 3 Qs).
    if domain_answered or domain_reply_hint or updates.get("open_to_all") \
            or intent in ("onboarding", "update_profile"):
        act = decided_action or decide_next_action(
            profile, updates, domain_answered, domain_reply_hint, soft, edu_reply_hint, lang
        )
        if act["action"] in ("ask_question", "ask_refinement"):
            if act["action"] == "ask_refinement":
                profile.get("conversation", {})["refinement_asked"] = True
            _record_question(profile, act["reply"])
            return (ack + " " + act["reply"]).strip() if ack else act["reply"]
        if ack:
            return ack
        # run_search → auto_search already handled in process_message
        return ("מחפש משרות מתאימות..." if lang != "English" else "Searching for matching jobs...")

    # ── 9. Skill gap ──────────────────────────────────────────────────────────
    if intent == "skill_gap_analysis":
        user_skills = set(s.lower() for s in profile.get("skills", []))
        common = ["SQL", "Excel", "Python", "Power BI", "Tableau", "Jira", "Git"]
        missing = [s for s in common if s.lower() not in user_skills]
        if lang != "English":
            return "כישורים שכדאי לחזק: " + _join(missing, 5) + "." if missing else "הכישורים שלך נראים טובים!"
        return "Consider adding: " + _join(missing, 5) + "." if missing else "Skill set looks solid!"

    # ── 10. Career advice ─────────────────────────────────────────────────────
    if intent == "career_advice":
        interests = profile.get("career_interests", [])
        skills = profile.get("skills", [])
        if not interests and not skills:
            return UNCERTAINTY_HE if lang != "English" else UNCERTAINTY_EN
        if lang != "English":
            if interests:
                return "כיווני קריירה מתאימים: " + _join(interests, 3) + ". רוצה לחפש משרות?"
            return "ספר/י יותר על הרקע שלך ואוכל להמליץ על כיוון."
        return "Based on your profile: " + _join(interests or ["general"], 3) + ". Want me to search?"

    # ── 11. Salary advice ─────────────────────────────────────────────────────
    if intent == "salary_advice":
        sal = profile.get("salary_expectation", {})
        base = ("שכר תלוי בתפקיד, רמת ניסיון ומיקום." if lang != "English"
                else "Salary depends on role, seniority, location.")
        if sal.get("preferred"):
            base += (" יעד שלך: \u20aa{:,.0f}.".format(sal["preferred"]) if lang != "English"
                     else " Your target: \u20aa{:,.0f}.".format(sal["preferred"]))
        return base

    if intent == "show_trends":
        return "מגמות — ראה/י לוח האנליטיקס." if lang != "English" else "Check the Analytics Dashboard."
    if intent == "show_clusters":
        return "אשכולות — בלוח האשכולות." if lang != "English" else "Job clusters are in the Cluster Panel."
    if intent == "show_anomalies":
        return "חריגות — בלוח האנליטיקס." if lang != "English" else "Anomaly data is in the Analytics Dashboard."

    if intent == "explain_recommendation":
        if jobs:
            reasons = jobs[0].get("match_reasons", [])
            text = " | ".join(reasons) if reasons else "התאמה כללית לפרופיל"
            return ("למה זו מתאימה:\n" + text if lang != "English" else "Why it matches:\n" + text)
        return "חפש/י משרות קודם." if lang != "English" else "Search for jobs first."

    # ── Fallback ──────────────────────────────────────────────────────────────
    # All paths above have returned. Use decide_next_action — NEVER hard-code refinement here.
    act = decided_action or decide_next_action(
        profile, updates, domain_answered, domain_reply_hint, soft, edu_reply_hint, lang
    )
    if ack:
        act_r = act.get("reply", "") if act["action"] in ("ask_question", "ask_refinement") else ""
        if act_r and profile_completeness(profile) < 80:
            if act["action"] == "ask_refinement":
                profile.get("conversation", {})["refinement_asked"] = True
            _record_question(profile, act_r)
            return ack + " " + act_r
        return ack
    if soft and soft.get("reply_hint"):
        return _build_soft_reply(soft, lang)
    if act["action"] in ("ask_question", "ask_refinement"):
        if act["action"] == "ask_refinement":
            profile.get("conversation", {})["refinement_asked"] = True
        _record_question(profile, act["reply"])
        return act["reply"]
    return ("מחפש משרות מתאימות..." if lang != "English" else "Searching for matching jobs...")


# ---------------------------------------------------------------------------
# No-repeat safety guard (module-level helper)
# ---------------------------------------------------------------------------

def _guard_no_repeat(reply: str, profile: dict, lang: str) -> str:
    """
    Final safety guard: if the reply is identical to one of the last 2 bot questions
    already in question_history, pick a different question instead.
    This is the last line of defence before any reply is returned.
    """
    history = profile.get("conversation", {}).get("question_history", [])
    if reply not in history[-2:]:
        return reply  # no repeat — safe to send
    # Reply repeats a recent question. Choose a safer alternative.
    # Try to find the next unanswered question; if none, ask for direction.
    alt = next_context_aware_question(profile, lang)
    if alt and alt not in history[-2:]:
        _record_question(profile, alt)
        return alt
    dir_q = DIRECTION_MISSING_Q_HE if lang != "English" else DIRECTION_MISSING_Q_EN
    if dir_q not in history[-2:]:
        _record_question(profile, dir_q)
        return dir_q
    # All sensible questions are blocked → prompt generic move-forward
    return ("איזה תפקיד תרצה/י לראות קודם?" if lang != "English"
            else "Which role type would you like to see first?")


# ---------------------------------------------------------------------------
# Central flow controller — single decision point for all Q/action choices
# ---------------------------------------------------------------------------

def decide_next_action(profile: dict, updates: dict,
                       domain_answered: bool, domain_reply_hint: str,
                       soft: dict, edu_reply_hint: str,
                       lang: str) -> dict:
    """
    Single decision point: what should the agent do next?

    Returns:
        action:       "ask_question" | "ask_refinement" | "run_search" | "no_action"
        reply:        bot text (empty string for run_search / no_action)
        pending_slot: slot name or None
        reason:       debug string
    """
    is_he  = lang != "English"
    soft   = soft or {}
    conv   = profile.get("conversation", {})
    # asked_questions: sequential, used for no-repeat hard guard (last 3)
    asked  = conv.get("asked_questions", conv.get("question_history", []))
    recent = set(asked[-3:])

    refinement_asked    = conv.get("refinement_asked", False)
    refinement_declined = conv.get("refinement_declined", False)

    has_interests = bool(profile.get("career_interests"))
    has_location  = _location_known(profile)   # True for US/Global, or Israel+area
    open_to_all   = bool(profile.get("open_to_all"))

    def _fresh(q: str) -> Optional[str]:
        """Return q only when it is NOT in the last 3 asked questions."""
        return q if q not in recent else None

    def _loc_q_action() -> Optional[dict]:
        """Return a decide_next_action dict for the next location question, or None."""
        country = profile.get("country_preference", "")
        if not country:
            q = _fresh(COUNTRY_Q_HE if is_he else COUNTRY_Q_EN)
            if q:
                return {"action": "ask_question", "reply": q,
                        "pending_slot": "country", "reason": "no_country_fallback"}
        elif country == "Israel":
            if not profile.get("location_preference", {}).get("primary"):
                q = _fresh(ISRAEL_AREA_Q_HE if is_he else ISRAEL_AREA_Q_EN)
                if q:
                    return {"action": "ask_question", "reply": q,
                            "pending_slot": "location", "reason": "israel_no_area_fallback"}
        return None  # US / Global — location resolved

    # ── 1. Domain inference / skill match → ask next domain-specific Q ───────
    if domain_answered or domain_reply_hint:
        next_q = next_context_aware_question(profile, lang)
        if next_q:
            nq = _fresh(next_q)
            if nq:
                prefix = (domain_reply_hint + " ") if domain_reply_hint else ""
                return {"action": "ask_question", "reply": prefix + nq,
                        "pending_slot": _get_question_slot(nq), "reason": "domain_answered_next_q"}
        # All domain Qs done → fall through to refinement/search

    # ── 2. Education hint ─────────────────────────────────────────────────────
    if edu_reply_hint and not has_location:
        q = _fresh(edu_reply_hint)
        if q:
            return {"action": "ask_question", "reply": q,
                    "pending_slot": "education_follow", "reason": "edu_hint"}

    # ── 3. Normal context-aware next Q ───────────────────────────────────────
    next_q = next_context_aware_question(profile, lang)
    if next_q:
        nq = _fresh(next_q)
        if nq:
            return {"action": "ask_question", "reply": nq,
                    "pending_slot": _get_question_slot(nq), "reason": "context_q"}

    # ── 4. Soft direction signal (not yet committed) ──────────────────────────
    if soft and soft.get("possible_career_directions") and not updates.get("career_interests"):
        soft_r = _build_soft_reply(soft, lang)
        if soft_r and _fresh(soft_r):
            return {"action": "ask_question", "reply": soft_r,
                    "pending_slot": "domain", "reason": "soft_signal"}

    # ── 5. All context Qs done → refinement ONCE, then search ─────────────────
    enough = (
        (has_interests and has_location)
        or (open_to_all and _has_strong_constraint(profile))
    )
    if enough:
        if not refinement_asked and not refinement_declined:
            ref_q = REFINEMENT_Q_HE if is_he else REFINEMENT_Q_EN
            return {"action": "ask_refinement", "reply": ref_q,
                    "pending_slot": "refinement", "reason": "offer_refinement"}
        # Refinement already asked or declined → run dataset search
        return {"action": "run_search", "reply": "", "pending_slot": None,
                "reason": "run_search_after_refinement"}

    # ── 6. Not enough info; all Qs blocked → ask most critical missing slot ───
    if not has_interests and not open_to_all:
        q = _fresh(DIRECTION_MISSING_Q_HE if is_he else DIRECTION_MISSING_Q_EN)
        if q:
            return {"action": "ask_question", "reply": q,
                    "pending_slot": "domain", "reason": "no_domain_fallback"}
    if not has_location:
        loc_act = _loc_q_action()
        if loc_act:
            return loc_act

    # ── 7. Everything blocked: if we have any profile → search; else ask ──────
    if has_interests or open_to_all:
        return {"action": "run_search", "reply": "", "pending_slot": None,
                "reason": "total_fallback_search"}
    return {
        "action": "ask_question",
        "reply": "מה תרצה/י שאחפש עבורך?" if is_he else "What would you like me to search for?",
        "pending_slot": "domain",
        "reason": "total_fallback_ask",
    }


# ---------------------------------------------------------------------------
# Pending question answer interpreter
# ---------------------------------------------------------------------------

def _interpret_pending_answer(message: str, pending_q: dict, profile: dict) -> dict:
    """
    If the user's message directly answers the last bot question (yes/no or
    yes+extra info), return profile updates to apply BEFORE normal NLP extraction.

    Returns {} if the message is not a direct answer to the pending question,
    or if pending_q is empty.

    Key: we only handle the "experience" slot here.
    Location slot: answered implicitly via extract_location in normal NLP.
    """
    if not pending_q:
        return {}

    slot   = pending_q.get("slot", "")
    domain = pending_q.get("domain", "general")

    if slot != "experience":
        return {}

    is_neg    = _is_negative(message)
    is_affirm = _is_affirmative(message)

    if is_neg:
        # "לא" / "no" → user has no experience → entry-level
        return {
            "experience": {
                "years": 0,
                "experience_answered": True,
                "seniority": "junior",
            },
            "_slot_answered": f"experience_{domain}",
        }

    if is_affirm:
        # "כן" / "yes" (possibly + extra info) → has some experience
        return {
            "experience": {"experience_answered": True},
            "_slot_answered": f"experience_{domain}",
        }

    return {}


# ---------------------------------------------------------------------------
# Broad-direction-Q answer interpreter
# ---------------------------------------------------------------------------
# When bot asks OPEN_TO_ALL_Q ("מה יותר מעניין אותך — אנשים, נתונים, ניהול, יצירה או טכנולוגיה?")
# and user replies with one of the category words, map it to specific career interests.

_BROAD_Q_ANSWER_MAP = [
    {
        "patterns": [
            r"^אנשים$", r"^people$",
            r"^עם\s+אנשים$", r"^working\s+with\s+people$", r"^helping\s+people$",
        ],
        "career_interests": ["משאבי אנוש", "שירות לקוחות", "הדרכה", "Customer Success"],
        "reply_hint": "מתאים למשאבי אנוש, שירות לקוחות, הדרכה או Customer Success.",
    },
    {
        "patterns": [r"^נתונים$", r"^data$", r"^מספרים$", r"^analytics$"],
        "career_interests": ["דאטה", "BI", "ניתוח נתונים"],
        "reply_hint": "",
    },
    {
        "patterns": [r"^ניהול$", r"^management$", r"^manage$"],
        "career_interests": ["ניהול", "ניהול פרויקטים", "תפעול"],
        "reply_hint": "",
    },
    {
        "patterns": [r"^יצירה$", r"^creativity$", r"^creative$", r"^עיצוב$", r"^design$"],
        "career_interests": ["עיצוב", "UX/UI", "שיווק יצירתי", "תוכן"],
        "reply_hint": "",
    },
    {
        "patterns": [r"^טכנולוגיה$", r"^technology$", r"^tech$", r"^תכנות$"],
        "career_interests": ["פיתוח תוכנה", "דאטה", "מוצר"],
        "reply_hint": "",
    },
    {
        "patterns": [r"^אבטחה$", r"^סייבר$", r"^cyber$", r"^security$"],
        "career_interests": ["אבטחת מידע", "סייבר", "Cyber Security"],
        "reply_hint": "מתאים לתפקידי אבטחת מידע וסייבר.",
    },
]


def _interpret_broad_q_answer(message: str, lang: str) -> dict:
    """
    If message is a short answer to the broad direction Q (OPEN_TO_ALL_Q),
    return profile updates: career_interests, clear open_to_all, domain hint.
    Returns {} if message doesn't match any broad-Q answer.
    """
    tl = message.strip().lower()
    for entry in _BROAD_Q_ANSWER_MAP:
        if any(re.search(p, tl, re.IGNORECASE) for p in entry["patterns"]):
            upd: dict = {
                "career_interests": entry["career_interests"],
                "open_to_all": False,   # direction is now resolved
                "_domain_answered": True,
            }
            if entry.get("reply_hint"):
                upd["_domain_reply_hint"] = entry["reply_hint"]
            return upd
    return {}


# ---------------------------------------------------------------------------
# Pending confirmation handler
# ---------------------------------------------------------------------------

def _handle_pending_confirmation(message: str, profile: dict, lang: str) -> Optional[dict]:
    pending = profile.get("conversation", {}).get("pending_career_directions", [])
    if not pending:
        return None

    if _is_affirmative(message):
        interests = profile.setdefault("career_interests", [])
        for d in pending:
            if d not in interests:
                interests.append(d)
        profile["conversation"]["pending_career_directions"] = []
        profile["conversation"]["pending_context"] = ""
        dirs_text = _join(pending, 3)
        reply = (CONFIRMED_EN.format(dirs=dirs_text) if lang == "English"
                 else CONFIRMED_HE.format(dirs=dirs_text))
        return {
            "reply": reply, "profile": profile, "jobs": [], "search_metadata": {},
            "profile_updated": True, "changed_fields": ["career_interests"],
            "should_clear_jobs": False, "intent": "confirm_direction",
            "profile_completeness": profile_completeness(profile), "insights": {},
        }

    if _is_negative(message):
        profile["conversation"]["pending_career_directions"] = []
        profile["conversation"]["pending_context"] = ""
        reply = HOBBY_ONLY_EN if lang == "English" else HOBBY_ONLY_HE
        return {
            "reply": reply, "profile": profile, "jobs": [], "search_metadata": {},
            "profile_updated": False, "changed_fields": [],
            "should_clear_jobs": False, "intent": "reject_direction",
            "profile_completeness": profile_completeness(profile), "insights": {},
        }

    return None


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

def process_message(message: str, profile: Optional[dict] = None) -> dict:
    if profile is None:
        profile = empty_profile()

    lang = detect_language(message)
    profile.setdefault("conversation", {})["language"] = lang

    # 1a. Check for pending confirmation (yes/no after soft direction suggestion)
    pending_result = _handle_pending_confirmation(message, profile, lang)
    if pending_result is not None:
        return pending_result

    # 1b. Refinement-decline: user replied "לא" / "אין" to the refinement question →
    #     treat as "search now" if profile has career_interests + location.
    last_q = profile.get("conversation", {}).get("last_question", "")
    _is_refinement_q = last_q in (REFINEMENT_Q_HE, REFINEMENT_Q_EN)
    if _is_refinement_q and _is_refinement_decline(message):
        has_interests_now = bool(profile.get("career_interests"))
        has_location_now  = _location_known(profile)
        if has_interests_now and has_location_now:
            # Trigger search with current profile
            jobs_ref, meta_ref = [], {}
            try:
                from matching_engine import search_jobs
                jobs_ref, meta_ref = search_jobs(profile, limit=10)
            except Exception as e:
                logger.error("Refinement search error: %s", e)
            is_student_ref = profile.get("experience", {}).get("seniority") in ("סטודנט/ית", "student")
            if jobs_ref:
                reply_ref = (_student_job_reply(profile, jobs_ref, meta_ref, lang)
                             if is_student_ref else
                             ("מצאתי משרות מתאימות. דירגתי אותן לפי התאמה לפרופיל שלך."
                              if lang != "English" else "Found matching jobs, ranked by profile fit."))
            else:
                reply_ref = ("לא מצאתי התאמה מדויקת. אפשר להרחיב אזור או לרכך תנאי אחד."
                             if lang != "English" else "No exact matches. Try expanding location or relaxing one condition.")
            completeness_ref = profile_completeness(profile)
            return {
                "reply": reply_ref, "profile": profile, "jobs": jobs_ref,
                "intent": "search_jobs", "search_metadata": meta_ref, "insights": {},
                "profile_completeness": completeness_ref,
                "profile_updated": False, "changed_fields": [],
                "should_clear_jobs": False,
            }
        else:
            # Not enough data — mark declined, NEVER fall back to refinement Q.
            # Ask the next concrete missing slot instead.
            profile.setdefault("conversation", {})["refinement_declined"] = True
            profile.get("conversation", {}).pop("pending_question", None)
            _qs3 = set(profile.get("conversation", {})
                       .get("asked_questions",
                            profile.get("conversation", {})
                            .get("question_history", []))[-3:])
            next_q = next_context_aware_question(profile, lang)
            if next_q and next_q not in _qs3:
                reply_ref = next_q
            elif not _location_known(profile):
                # Country-first: ask country before Israeli area
                _cp = profile.get("country_preference", "")
                if not _cp:
                    reply_ref = (COUNTRY_Q_HE if lang != "English" else COUNTRY_Q_EN)
                elif _cp == "Israel":
                    reply_ref = (ISRAEL_AREA_Q_HE if lang != "English" else ISRAEL_AREA_Q_EN)
                else:
                    reply_ref = (COUNTRY_Q_HE if lang != "English" else COUNTRY_Q_EN)
            elif not profile.get("career_interests"):
                reply_ref = (DIRECTION_MISSING_Q_HE if lang != "English"
                             else DIRECTION_MISSING_Q_EN)
            else:
                reply_ref = ("איזה תפקיד תרצה/י לראות?" if lang != "English"
                             else "What kind of role would you like to see?")
            _record_question(profile, reply_ref)
            return {
                "reply": reply_ref, "profile": profile, "jobs": [],
                "intent": "update_profile", "search_metadata": {}, "insights": {},
                "profile_completeness": profile_completeness(profile),
                "profile_updated": False, "changed_fields": [],
                "should_clear_jobs": False,
            }

    # 1c. Interpret yes/no replies relative to the last bot question.
    #     This runs BEFORE normal NLP so that "לא" to an experience question
    #     sets experience_answered=True and years=0, preventing the same question
    #     from repeating.  Mixed answers ("כן אני יודעת גם SQL QA") are also
    #     handled: the yes/no part fills the pending slot, and the extra content
    #     is extracted normally in step 2.
    pending_q = profile.get("conversation", {}).get("pending_question", {})
    if pending_q:
        pa_updates = _interpret_pending_answer(message, pending_q, profile)
        if pa_updates:
            slot_key = pa_updates.pop("_slot_answered", None)
            # Merge experience flags immediately (before normal NLP)
            profile = merge_profile_updates(profile, pa_updates)
            if slot_key:
                profile.setdefault("conversation", {}).setdefault(
                    "answered_slots", []).append(slot_key)
            # Clear the pending question — it has now been answered
            profile.get("conversation", {}).pop("pending_question", None)

    # 1d. Interpret single-word / short answer to the broad open-to-all direction Q.
    #     Must run BEFORE normal NLP so that "אנשים" after OPEN_TO_ALL_Q maps to
    #     specific career_interests rather than being lost.
    if profile.get("open_to_all") and last_q in (OPEN_TO_ALL_Q_HE, OPEN_TO_ALL_Q_EN):
        broad_upd = _interpret_broad_q_answer(message, lang)
        if broad_upd:
            profile = merge_profile_updates(profile, broad_upd)
            # domain_reply_hint was embedded in broad_upd under _domain_reply_hint;
            # merge_profile_updates stores it in conversation for generate_reply to consume.

    # 2. Normal processing
    intent = detect_intent(message, profile)
    updates = extract_profile_updates(message, profile)

    direction_changed = False
    soft = {}
    edu_reply_hint = ""
    domain_answered = False
    domain_reply_hint = ""

    if intent == "reset_profile":
        profile = empty_profile()
        # Fully clear all conversation state — nothing from the old chat leaks
        profile["conversation"].update({
            "language": lang,
            "last_bot_question": "",
            "last_question": "",
            "asked_questions": [],
            "question_history": [],
            "refinement_asked": False,
            "refinement_declined": False,
            "pending_question": {},
            "answered_slots": [],
            "turn_count": 0,
        })
        updates = {}
    else:
        profile = merge_profile_updates(profile, updates)
        direction_changed = profile.get("conversation", {}).pop("career_direction_changed", False)
        soft = profile.get("conversation", {}).pop("_last_soft", {})
        edu_reply_hint = profile.get("conversation", {}).pop("_edu_reply_hint", "")
        domain_answered = profile.get("conversation", {}).pop("_domain_answered", False)
        domain_reply_hint = profile.get("conversation", {}).pop("_domain_reply_hint", "")

    profile["conversation"]["last_intent"] = intent

    # Store pending soft career directions for confirmation flow
    if soft and soft.get("possible_career_directions") and not updates.get("career_interests"):
        profile["conversation"]["pending_career_directions"] = soft["possible_career_directions"]
        profile["conversation"]["pending_context"] = soft.get("reply_he", "")

    has_interests = bool(profile.get("career_interests"))
    has_location  = _location_known(profile)
    # newly_has_loc: True when this turn provided enough location info to start searching
    newly_has_loc = (
        # US or Global country just set
        updates.get("country_preference") in ("United States", "Global")
        # OR Israel + area already in profile (area was set earlier; country set this turn)
        or (updates.get("country_preference") == "Israel"
            and bool(profile.get("location_preference", {}).get("primary")))
        # OR Israeli area just provided (country already Israel or implied)
        or bool(updates.get("location_preference", {}).get("primary"))
    )
    newly_has_dir = bool(updates.get("career_interests") or domain_answered or domain_reply_hint)
    open_to_all   = bool(profile.get("open_to_all"))
    has_strong_constraint = _has_strong_constraint(profile)

    # Central flow controller — single decision point for Q selection and search.
    # Called once here; passed to generate_reply so it is NOT called again inside.
    _da = decide_next_action(
        profile, updates, domain_answered, domain_reply_hint, soft, edu_reply_hint, lang
    )

    # pending_domain_q kept for backward compat (generate_reply legacy paths)
    pending_domain_q = next_context_aware_question(profile, lang)

    # Auto-search when:
    #   a) decide_next_action recommends run_search, OR
    #   b) user just provided BOTH direction + location in same turn
    auto_search = (
        intent not in ("reset_profile", "expand_location")
        and (
            _da["action"] == "run_search"
            or (has_interests and has_location and newly_has_loc and newly_has_dir)
        )
    )

    jobs = []
    search_metadata = {}
    should_clear_jobs = direction_changed

    run_search = (intent in ("search_jobs", "expand_location")) or direction_changed or auto_search
    if run_search:
        try:
            from matching_engine import search_jobs
            loc_override = None
            if intent == "expand_location":
                loc = profile.get("location_preference", {})
                primary = loc.get("primary", "")
                from matching_engine import LOCATION_FALLBACKS
                fallbacks = LOCATION_FALLBACKS.get(primary, ["מרחוק", "תל אביב"])
                loc_override = fallbacks[0] if fallbacks else None
            jobs, search_metadata = search_jobs(profile, limit=10, location_override=loc_override)
        except Exception as e:
            logger.error("Job search error: %s", e)
            search_metadata = {"error": str(e)}

    reply = generate_reply(
        intent, message, profile, updates,
        jobs, search_metadata, lang,
        direction_changed=direction_changed,
        soft=soft,
        edu_reply_hint=edu_reply_hint,
        domain_answered=domain_answered,
        auto_searched=auto_search,
        domain_reply_hint=domain_reply_hint,
        pending_domain_q=pending_domain_q,
        decided_action=_da,
    )

    completeness = profile_completeness(profile)
    changed_fields = [k for k in updates if k not in (
        "conversation", "_soft", "_edu_reply_hint", "_domain_answered", "_domain_reply_hint")]

    return {
        "reply": reply,
        "profile": profile,
        "jobs": jobs,
        "intent": intent,
        "search_metadata": search_metadata,
        "insights": {},
        "profile_completeness": completeness,
        "profile_updated": bool(changed_fields),
        "changed_fields": changed_fields,
        "should_clear_jobs": should_clear_jobs,
        "dataset_search_ran": search_metadata.get("dataset_search_ran", False),
        "candidates_scanned": search_metadata.get("candidates_scanned", 0),
        "results_count": search_metadata.get("results_count", 0),
    }
