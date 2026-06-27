"""
agent_logic.py
Conversational AI agent logic.

Profiling gate: Agent asks at least 4 profiling questions (education, skills,
experience, direction, country) before running any job search.
Relaxed search fallback: if strict search returns 0, retry without location filter.
"""
import re
import logging
from typing import Optional
from models import empty_profile, profile_completeness
from nlp_engine import (
    extract_profile_updates, merge_profile_updates,
    detect_language, is_open_to_all,
)

logger = logging.getLogger(__name__)

INTENT_PATTERNS_ORDERED = [
    ("reset_profile", [
        r"אפס|reset|התחל מחדש|start over|start fresh|מחק פרופיל|clear profile",
    ]),
    ("search_jobs", [
        r"חפש לי|חיפוש|מצא לי|find jobs?|search jobs?|show me jobs",
        r"הצג משרות|הראה לי משרות|איזה משרות|what jobs|recommend|המלץ",
        r"תמצא לי עבודה|רוצה עבודה|תציע לי משרות|match me|find me work",
        r"אפשר לראות משרות|מה מתאים לי",
        r"לחפש עבודה|לחפש משרה|אפשר לחפש",
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


def _is_refinement_decline(message: str) -> bool:
    tl = message.strip().lower()
    return bool(re.search(
        r"^(?:לא|אין|בסדר|ok|okay|no|nope|nothing|לא כרגע|לא עכשיו|תחפש|go|search|yes|כן)\b",
        tl, re.IGNORECASE
    ))


REFINEMENT_Q_HE = "יש עוד משהו שתרצה/י להוסיף על עצמך כדי לדייק את ההתאמה?"
REFINEMENT_Q_EN = "Anything else you'd like to add to refine the job match?"

COUNTRY_Q_HE = "באיזו מדינה לחפש? ישראל, ארה״ב או לא משנה?"
COUNTRY_Q_EN = "Which country should I search in? Israel, United States, or anywhere?"

ISRAEL_AREA_Q_HE = "באיזו עיר או אזור בישראל לחפש?"
ISRAEL_AREA_Q_EN = "Which city or area in Israel should I search?"

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
    "אבטחת מידע", "סייבר", "Cyber Security", "SOC", "GRC",
    "Information Security",
}

PROFILE_FIELD_CHECK = {
    "education":           lambda p: bool(p.get("education", {}).get("degree") or p.get("education", {}).get("field")),
    "experience":          lambda p: (p.get("experience", {}).get("years") is not None or bool(p.get("experience", {}).get("seniority"))),
    "skills":              lambda p: bool(p.get("skills")) or bool(set(p.get("career_interests", [])) & _DOMAIN_CAREER_INTERESTS),
    "career_interests":    lambda p: bool(p.get("career_interests")),
    "country_preference":  lambda p: bool(p.get("country_preference")),
    "location_preference": lambda p: _location_known(p),
    "salary_expectation":  lambda p: (p.get("salary_expectation", {}).get("preferred") is not None or p.get("salary_expectation", {}).get("min") is not None),
    "work_style":          lambda p: bool(p.get("work_style", {}).get("preferred_environment")),
    "constraints":         lambda p: bool(p.get("constraints", {}).get("avoid")),
}


def _location_known(profile: dict) -> bool:
    country = profile.get("country_preference", "")
    if country in ("United States", "Global"):
        return True
    if country == "Israel":
        return bool(profile.get("location_preference", {}).get("primary"))
    return bool(profile.get("location_preference", {}).get("primary"))


# ---------------------------------------------------------------------------
# Profiling slot tracking and readiness gate
# ---------------------------------------------------------------------------

def _count_answered_slots(profile: dict) -> int:
    count = 0
    edu = profile.get("education", {})
    if edu.get("degree") or edu.get("field"):
        count += 1
    exp = profile.get("experience", {})
    if (exp.get("years") is not None
            or bool(exp.get("seniority"))
            or bool(exp.get("experience_answered"))):
        count += 1
    if profile.get("skills"):
        count += 1
    if profile.get("career_interests"):
        count += 1
    if profile.get("country_preference"):
        count += 1
    wp = profile.get("work_preferences", {})
    if wp.get("work_mode") or wp.get("work_type"):
        count += 1
    return count


def has_enough_profile(profile: dict) -> bool:
    slots = _count_answered_slots(profile)
    if slots >= 4:
        return True
    q_count = profile.get("conversation", {}).get("profiling_questions_asked", 0)
    return q_count >= 4 and slots >= 2


def get_next_missing_profile_question(profile: dict, lang: str) -> Optional[str]:
    """Return the next unanswered profiling question, or None if all covered.

    Uses slot-name tracking (not question text) so language changes don't
    cause the same slot to be asked twice.
    A slot is 'skipped' once it has been asked MAX_SLOT_ASKS times unanswered.
    """
    MAX_SLOT_ASKS = 2
    is_he = lang != "English"
    conv = profile.get("conversation", {})
    slot_asks: dict = conv.get("slot_asks", {})   # {slot_name: ask_count}

    def _asked_too_many(slot: str) -> bool:
        return slot_asks.get(slot, 0) >= MAX_SLOT_ASKS

    def ask(slot: str, q_he: str, q_en: str):
        if _asked_too_many(slot):
            return None
        return q_he if is_he else q_en

    edu = profile.get("education", {})
    if not (edu.get("degree") or edu.get("field")):
        q = ask("education",
                "מה למדת או באיזה תחום יש לך רקע?",
                "What did you study or what's your professional background?")
        if q:
            return q
    if not profile.get("skills"):
        q = ask("skills",
                "אילו כלים או כישורים יש לך? למשל SQL, Python, Excel, QA...",
                "What tools or skills do you have? e.g. SQL, Python, Excel, QA...")
        if q:
            return q
    exp = profile.get("experience", {})
    if (exp.get("years") is None
            and not exp.get("seniority")
            and not exp.get("experience_answered")):
        q = ask("experience",
                "יש לך ניסיון קודם בעבודה או בפרויקטים?",
                "Do you have prior work experience or projects?")
        if q:
            return q
    if not profile.get("career_interests"):
        q = ask("direction",
                "איזה כיוון מעניין אותך — דאטה/BI, פיתוח, QA, סייבר או משהו אחר?",
                "What direction interests you — Data/BI, Development, QA, Cyber, or something else?")
        if q:
            return q
    if not profile.get("country_preference"):
        q = ask("country",
                'באיזו מדינה או אזור לחפש? ארה׳ב, ישראל, מרחוק או לא משנה?',
                "Which country or region? US, Israel, Remote, or doesn't matter?")
        if q:
            return q
    q_count = conv.get("profiling_questions_asked", 0)
    wp = profile.get("work_preferences", {})
    if q_count >= 4 and not wp.get("work_mode") and not wp.get("work_type"):
        q = ask("work_mode",
                "האם אתה/את מחפש/ת משרה מלאה/חלקית, מרחוק, היברידי או מהמשרד?",
                "Full-time/part-time? Remote, hybrid, or on-site?")
        if q:
            return q
    return None


# ---------------------------------------------------------------------------
# Question slot inference and recording
# ---------------------------------------------------------------------------

def _get_question_slot(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ["ניסיון", "experience", "ותק", "שנות", "license", "רישיון",
                              "certificate", "תעודה", "portfolio", "תיק"]):
        return "experience"
    if any(w in q for w in ["מדינה", "country", "ישראל, ארה", "israel, united",
                              "ארה״ב", "united states", "לא משנה"]):
        return "country"
    if any(w in q for w in ["אזור", "area", "location", "where", "עיר", "city", "region",
                              "בישראל"]):
        return "location"
    if any(w in q for w in ["למדת", "תואר", "degree", "studied", "education", "השכלה"]):
        return "education"
    return "general"


# Map question substrings → slot name (language-agnostic)
_QUESTION_SLOT_MAP = [
    (["למדת", "studied", "background", "רקע", "השכלה", "degree"],         "education"),
    (["כישורים", "כלים", "skills", "tools", "python", "excel", "sql"],    "skills"),
    (["ניסיון", "experience", "projects", "פרויקט", "ותק"],               "experience"),
    (["כיוון", "direction", "data", "דאטה", "פיתוח", "development"],      "direction"),
    (["מדינה", "country", "ישראל", "ארה", "israel", "united states"],     "country"),
    (["מרחוק", "remote", "היברידי", "hybrid", "מהמשרד", "on-site",
      "full-time", "part-time", "מלאה", "חלקית"],                          "work_mode"),
]

def _question_to_slot(question: str) -> str:
    q = question.lower()
    for keywords, slot in _QUESTION_SLOT_MAP:
        if any(kw in q for kw in keywords):
            return slot
    return "general"


def _record_question(profile: dict, question: str):
    conv = profile.setdefault("conversation", {})
    asked = conv.setdefault("asked_questions", [])
    asked.append(question)
    if len(asked) > 10:
        asked[:] = asked[-10:]
    history = conv.setdefault("question_history", [])
    if question not in history:
        history.append(question)
    if len(history) > 10:
        history[:] = history[-10:]
    conv["last_bot_question"] = question
    conv["last_question"] = question
    conv["profiling_questions_asked"] = conv.get("profiling_questions_asked", 0) + 1
    # Track per-slot ask count (language-agnostic)
    slot = _question_to_slot(question)
    if slot != "general":
        slot_asks = conv.setdefault("slot_asks", {})
        slot_asks[slot] = slot_asks.get(slot, 0) + 1
    slot   = _get_question_slot(question)
    domain = _detect_domain(profile) or ""
    conv["pending_question"] = {"slot": slot, "domain": domain, "question": question}
    if question in (REFINEMENT_Q_HE, REFINEMENT_Q_EN):
        conv["refinement_asked"] = True


# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------

def _detect_domain(profile: dict) -> Optional[str]:
    if profile.get("open_to_all"):
        return None
    interests_lower = set(i.lower() for i in profile.get("career_interests", []))
    skills_lower    = set(s.lower() for s in profile.get("skills", []))
    prev_roles      = " ".join(profile.get("experience", {}).get("previous_roles", [])).lower()

    if interests_lower & {"qa", "בדיקות תוכנה", "software testing", "quality assurance"} \
            or skills_lower & {"qa", "selenium", "cypress", "appium", "postman"}:
        return "qa"
    if interests_lower & {"דאטה", "bi", "ניתוח מערכות", "ניתוח נתונים", "מדעי נתונים"} \
            or skills_lower & {"sql", "mysql", "postgresql", "excel", "power bi", "tableau",
                               "looker", "qlik", "bi", "etl"}:
        return "data"
    if interests_lower & {"חינוך", "הוראה"} \
            or any("מורה" in i or "teacher" in i for i in profile.get("career_interests", [])):
        return "education"
    if interests_lower & {"אבטחת מידע", "סייבר", "cyber security", "information security",
                          "soc", "grc", "infosec"} \
            or skills_lower & {"cyber security", "siem"}:
        return "cyber"
    if interests_lower & {"פיתוח תוכנה", "תכנות", "הנדסת תוכנה"} \
            or skills_lower & {"programming", "java", "javascript", "typescript", "python", "react",
                               "angular", "vue", "node.js", "c#", "php", "ruby", "swift", "kotlin"}:
        return "software"
    if interests_lower & {"ניהול משרד", "אדמיניסטרציה", "ניהול עסקים", "ניהול עסקי",
                          "business administration", "office manager"}:
        return "business"
    if any(kw in prev_roles for kw in ("משרד", "מנהל", "אדמיני", "office", "admin", "business")) \
            and interests_lower & {"ניהול", "תפעול", "אדמיניסטרציה", "ניהול משרד"}:
        return "business"
    if interests_lower and interests_lower <= {"משאבי אנוש", "שירות לקוחות", "הדרכה", "customer success"}:
        return "people"
    if interests_lower & {"משאבי אנוש", "גיוס"}:
        return "hr"
    if interests_lower & {"מכירות", "ניהול לקוחות"}:
        return "sales"
    if "שירות לקוחות" in interests_lower:
        return "service"
    if interests_lower & {"כספים", "חשבונאות", "פיננסים"}:
        return "finance"
    if interests_lower & {"שיווק", "תוכן", "יחסי ציבור"}:
        return "marketing"
    if interests_lower & {"עיצוב", "ux/ui"}:
        return "design"
    if interests_lower & {"בריאות", "סיעוד", "רפואה"}:
        return "healthcare"
    if interests_lower & {"עבודה סוציאלית", "פסיכולוגיה"}:
        return "social"
    if interests_lower & {"משפטים", "ייעוץ משפטי"}:
        return "law"
    if interests_lower & {"לוגיסטיקה", "שרשרת אספקה"}:
        return "logistics"
    if interests_lower & {"תפעול", "ניהול פרויקטים"}:
        return "operations"
    if interests_lower & {"מוצר", "ניהול מוצר"}:
        return "product"
    if "הנדסה" in interests_lower:
        return "engineering"
    if "ניהול" in interests_lower:
        return "management"
    return None


# ---------------------------------------------------------------------------
# Context-aware question
# ---------------------------------------------------------------------------

OPEN_TO_ALL_Q_HE = "מה יותר מעניין אותך — אנשים, נתונים, ניהול, יצירה או טכנולוגיה?"
OPEN_TO_ALL_Q_EN = "What draws you more — people, data, management, creativity, or tech?"
DIRECTION_MISSING_Q_HE = "איזה תחום או תפקיד מעניין אותך?"
DIRECTION_MISSING_Q_EN = "What field or role interests you?"


def _has_strong_constraint(profile: dict) -> bool:
    wp  = profile.get("work_preferences", {})
    sal = profile.get("salary_expectation", {})
    return bool(
        wp.get("work_type") or wp.get("work_mode")
        or sal.get("preferred") or sal.get("min")
        or profile.get("location_preference", {}).get("primary")
    )


def next_context_aware_question(profile: dict, lang: str) -> Optional[str]:
    domain = _detect_domain(profile)
    is_he  = lang != "English"
    exp    = profile.get("experience", {})
    has_exp = (exp.get("years") is not None or bool(exp.get("seniority"))
               or bool(exp.get("experience_answered")))
    has_loc = _location_known(profile)
    skills  = profile.get("skills", [])
    specific_skills = [s for s in skills if s not in ("Programming", "Design", "Cyber Security")]
    history = profile.get("conversation", {}).get("question_history", [])
    recent  = set(history[-2:])

    def pick(q):
        return q if q not in recent else None

    def _loc_q():
        country = profile.get("country_preference", "")
        if not country:
            return pick(COUNTRY_Q_HE if is_he else COUNTRY_Q_EN)
        if country == "Israel" and not profile.get("location_preference", {}).get("primary"):
            return pick(ISRAEL_AREA_Q_HE if is_he else ISRAEL_AREA_Q_EN)
        return None

    def exp_then_loc(exp_q_he, exp_q_en):
        if not has_exp:
            q = pick(exp_q_he if is_he else exp_q_en)
            if q:
                return q
        if not has_loc:
            return _loc_q()
        return None

    if profile.get("open_to_all") and domain is None:
        if _has_strong_constraint(profile):
            return None
        q = pick(OPEN_TO_ALL_Q_HE if is_he else OPEN_TO_ALL_Q_EN)
        return q or pick(DIRECTION_MISSING_Q_HE if is_he else DIRECTION_MISSING_Q_EN)

    domain_map = {
        "data":        ("כמה ניסיון יש לך בדאטה/BI?", "How much data/BI experience do you have?"),
        "qa":          ("כמה ניסיון יש לך בבדיקות תוכנה?", "How much QA/testing experience do you have?"),
        "software":    (None, None),  # handled below
        "cyber":       (None, None),  # handled below
        "hr":          ("יש לך ניסיון בגיוס או משאבי אנוש?", "Do you have HR or recruiting experience?"),
        "sales":       ("כמה ניסיון יש לך במכירות?", "How much sales experience do you have?"),
        "service":     ("יש לך ניסיון בשירות לקוחות?", "Do you have customer service experience?"),
        "marketing":   ("יש לך ניסיון בשיווק דיגיטלי או תוכן?", "Do you have digital marketing or content experience?"),
        "finance":     ("כמה ניסיון יש לך בתחום הכספים?", "How much finance experience do you have?"),
        "healthcare":  ("יש לך רישיון או ניסיון בתחום הרפואי?", "Do you have a license or medical experience?"),
        "social":      ("יש לך ניסיון בעבודה סוציאלית או ייעוץ?", "Do you have social work or counseling experience?"),
        "law":         ("יש לך רישיון עורך דין או ניסיון משפטי?", "Are you a licensed attorney?"),
        "logistics":   ("יש לך ניסיון בלוגיסטיקה, רכש או שרשרת אספקה?", "Do you have logistics experience?"),
        "operations":  ("יש לך ניסיון בתפעול או ניהול פרויקטים?", "Do you have ops or PM experience?"),
        "product":     ("יש לך ניסיון בניהול מוצר?", "Do you have product management experience?"),
        "engineering": ("יש לך ניסיון בתחום ההנדסה?", "Do you have engineering experience?"),
        "management":  ("יש לך ניסיון בניהול?", "Do you have management experience?"),
        "design":      ("יש לך תיק עבודות או ניסיון בעיצוב?", "Do you have a portfolio or design experience?"),
        "business":    ("יש לך ניסיון בתחום?", "Do you have experience in this field?"),
        "people":      ("מעדיפ/ה עבודה מול לקוחות, הדרכה, משאבי אנוש או טיפול?",
                        "Do you prefer customer-facing, training, HR, or care roles?"),
        "education":   (None, None),  # handled below
    }

    if domain == "software":
        if not specific_skills:
            q = pick("יש שפה או תחום שמעניין אותך — Python, Java, Frontend?" if is_he
                     else "Any preferred language — Python, Java, Frontend?")
            if q:
                return q
        return exp_then_loc("כמה ניסיון יש לך בפיתוח?", "How much development experience do you have?")

    if domain == "cyber":
        if not has_exp:
            q = pick("יש לך ניסיון באבטחת מידע, רשתות או IT?" if is_he
                     else "Do you have experience in cyber security, networking, or IT?")
            if q:
                return q
        interests_text = " ".join(profile.get("career_interests", []) + profile.get("skills", [])).lower()
        has_spec = any(kw in interests_text for kw in ["soc", "grc", "pentest", "network security",
                                                        "cloud security", "application security"])
        if not has_spec:
            q = pick("מעניין אותך יותר SOC, רשתות, GRC או בדיקות חדירות?" if is_he
                     else "Are you more interested in SOC, networking, GRC, or penetration testing?")
            if q:
                return q
        if not has_loc:
            return _loc_q()
        return None

    if domain == "education":
        if not has_loc:
            q = _loc_q()
            if q:
                return q
        if not has_exp:
            return pick("יש לך תעודת הוראה או ניסיון בהוראה?" if is_he
                        else "Do you have a teaching certificate or teaching experience?")
        return None

    if domain and domain in domain_map:
        he_q, en_q = domain_map[domain]
        if he_q:
            return exp_then_loc(he_q, en_q)

    return next_onboarding_question(profile, lang)


def next_onboarding_question(profile: dict, lang: str) -> Optional[str]:
    questions = ONBOARDING_QUESTIONS_EN if lang == "English" else ONBOARDING_QUESTIONS_HE
    history = profile.get("conversation", {}).get("question_history", [])
    last_q = history[-1] if history else ""
    for field, question in questions:
        check = PROFILE_FIELD_CHECK.get(field, lambda p: False)
        if not check(profile):
            if question == last_q:
                continue
            return question
    return None


# ---------------------------------------------------------------------------
# Short reply helpers
# ---------------------------------------------------------------------------

def _join(lst, n=5):
    return ", ".join(lst[:n])


def _build_update_ack(updates: dict, lang: str, direction_changed: bool = False) -> str:
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
    interests = profile.get("career_interests", [])
    main = interests[0] if interests else ""
    if jobs:
        if search_metadata.get("expanded", False):
            return ("מצאתי מעט התאמות באזור שבחרת, אז הרחבתי לאזורים קרובים." if lang != "English"
                    else "Few matches nearby, so I expanded to adjacent areas.")
        if search_metadata.get("was_relaxed"):
            return ("מצאתי כמה משרות שיכולות להתאים לפי מה שסיפרת:" if lang != "English"
                    else "Found some jobs that might fit based on what you shared:")
        if main and lang != "English":
            return "מצאתי משרות " + main + " מתאימות לסטודנטים וג'וניורים."
        return "Found matching jobs for students and juniors, ranked by fit."
    return ("לא מצאתי משרות מתאימות במאגר הנוכחי, אבל אפשר לשנות תחום/אזור ולנסות שוב."
            if lang != "English" else "No matching jobs found. Try a different field or region.")


def _top_categories_from_jobs(jobs: list, top_n: int = 4) -> list:
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
                   auto_searched: bool = False, domain_reply_hint: str = "",
                   pending_domain_q: Optional[str] = None,
                   decided_action: dict = None) -> str:
    soft = soft or {}
    ack  = _build_update_ack(updates, lang, direction_changed)
    is_student   = profile.get("experience", {}).get("seniority") in ("סטודנט/ית", "student")
    has_interests = bool(profile.get("career_interests"))
    has_location  = bool(profile.get("location_preference", {}).get("primary"))

    if _is_offtopic(message):
        return ("אני מתמקד בחיפוש עבודה וקריירה." if lang != "English"
                else "I focus on job search and career guidance.")

    if intent == "reset_profile":
        return ("הפרופיל אופס. מה למדת?" if lang != "English" else "Profile reset. What did you study?")

    if direction_changed and updates.get("career_interests"):
        new_dir = _join(updates["career_interests"], 2)
        if jobs:
            return ("אעבור לכיוון " + new_dir + ". מצאתי " + str(len(jobs)) + " משרות." if lang != "English"
                    else "Switching to " + new_dir + ". Found " + str(len(jobs)) + " jobs.")
        return ("אעבור לכיוון " + new_dir + "." if lang != "English" else "Switching to " + new_dir + ".")

    open_to_all = bool(profile.get("open_to_all"))

    if jobs or (intent == "search_jobs" and not direction_changed) or auto_searched:
        if jobs:
            if is_student and has_interests:
                return _student_job_reply(profile, jobs, search_metadata, lang)
            if search_metadata.get("expanded", False):
                return ("מצאתי מעט התאמות באזור שבחרת, אז הרחבתי לאזורים קרובים." if lang != "English"
                        else "Few matches nearby, so I expanded to adjacent areas.")
            if search_metadata.get("was_relaxed"):
                return ("מצאתי כמה משרות שיכולות להתאים לפי מה שסיפרת:" if lang != "English"
                        else "Found some jobs that might fit based on what you shared:")
            if open_to_all and not has_interests:
                cats = _top_categories_from_jobs(jobs)
                if cats and lang != "English":
                    return ("מצאתי משרות בכמה כיוונים. הכי רלוונטיים: "
                            + ", ".join(cats[:4]) + ". איזה כיוון תרצ/י לראות קודם?")
                elif cats:
                    return "Found jobs across: " + ", ".join(cats[:4]) + ". Which direction first?"
            return ("מצאתי משרות מתאימות. דירגתי אותן לפי התאמה לפרופיל שלך." if lang != "English"
                    else "Found matching jobs, ranked by profile fit.")
        if open_to_all:
            return (DIRECTION_MISSING_Q_HE if lang != "English" else DIRECTION_MISSING_Q_EN)
        return ("לא מצאתי משרות מתאימות במאגר הנוכחי, אבל אפשר לשנות תחום/אזור ולנסות שוב."
                if lang != "English"
                else "No matching jobs found in the current database. Try a different field or region.")

    if intent == "expand_location":
        if not jobs:
            return ("לא נמצאו משרות גם לאחר הרחבה." if lang != "English"
                    else "No jobs found even after expanding.")
        used_loc = search_metadata.get("used_location", "")
        return ("הרחבתי ל" + used_loc + ". נמצאו " + str(len(jobs)) + " משרות." if lang != "English"
                else "Expanded to " + used_loc + ". Found " + str(len(jobs)) + " jobs.")

    if soft and soft.get("possible_career_directions") and not updates.get("career_interests"):
        return _build_soft_reply(soft, lang)

    if edu_reply_hint and not domain_answered and not has_location:
        return edu_reply_hint

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
        return ("מחפש משרות מתאימות..." if lang != "English" else "Searching for matching jobs...")

    if intent == "skill_gap_analysis":
        user_skills = set(s.lower() for s in profile.get("skills", []))
        common = ["SQL", "Excel", "Python", "Power BI", "Tableau", "Jira", "Git"]
        missing = [s for s in common if s.lower() not in user_skills]
        if lang != "English":
            return ("כישורים שכדאי לחזק: " + _join(missing, 5) + ".") if missing else "הכישורים שלך נראים טובים!"
        return ("Consider adding: " + _join(missing, 5) + ".") if missing else "Skill set looks solid!"

    if intent == "career_advice":
        interests = profile.get("career_interests", [])
        skills    = profile.get("skills", [])
        if not interests and not skills:
            return UNCERTAINTY_HE if lang != "English" else UNCERTAINTY_EN
        if lang != "English":
            return ("כיווני קריירה מתאימים: " + _join(interests, 3) + ". רוצה לחפש משרות?") if interests \
                else "ספר/י יותר על הרקע שלך ואוכל להמליץ על כיוון."
        return ("Based on your profile: " + _join(interests or ["general"], 3) + ". Want me to search?")

    if intent == "salary_advice":
        sal  = profile.get("salary_expectation", {})
        base = "שכר תלוי בתפקיד, רמת ניסיון ומיקום." if lang != "English" else "Salary depends on role, seniority, location."
        if sal.get("preferred"):
            base += (" יעד שלך: ₪{:,.0f}.".format(sal["preferred"]) if lang != "English"
                     else " Your target: ₪{:,.0f}.".format(sal["preferred"]))
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
# No-repeat safety guard
# ---------------------------------------------------------------------------

def _guard_no_repeat(reply: str, profile: dict, lang: str) -> str:
    history = profile.get("conversation", {}).get("question_history", [])
    if reply not in history[-2:]:
        return reply
    alt = next_context_aware_question(profile, lang)
    if alt and alt not in history[-2:]:
        _record_question(profile, alt)
        return alt
    dir_q = DIRECTION_MISSING_Q_HE if lang != "English" else DIRECTION_MISSING_Q_EN
    if dir_q not in history[-2:]:
        _record_question(profile, dir_q)
        return dir_q
    return ("איזה תפקיד תרצה/י לראות קודם?" if lang != "English"
            else "Which role type would you like to see first?")


# ---------------------------------------------------------------------------
# Central flow controller
# ---------------------------------------------------------------------------

def decide_next_action(profile: dict, updates: dict,
                       domain_answered: bool, domain_reply_hint: str,
                       soft: dict, edu_reply_hint: str,
                       lang: str) -> dict:
    is_he  = lang != "English"
    soft   = soft or {}
    conv   = profile.get("conversation", {})
    asked  = conv.get("asked_questions", conv.get("question_history", []))
    recent = set(asked[-3:])

    refinement_asked    = conv.get("refinement_asked", False)
    refinement_declined = conv.get("refinement_declined", False)
    has_interests = bool(profile.get("career_interests"))
    has_location  = _location_known(profile)
    open_to_all   = bool(profile.get("open_to_all"))

    def _fresh(q):
        return q if q not in recent else None

    def _loc_q_action():
        country = profile.get("country_preference", "")
        if not country:
            q = _fresh(COUNTRY_Q_HE if is_he else COUNTRY_Q_EN)
            if q:
                return {"action": "ask_question", "reply": q,
                        "pending_slot": "country", "reason": "no_country"}
        elif country == "Israel":
            if not profile.get("location_preference", {}).get("primary"):
                q = _fresh(ISRAEL_AREA_Q_HE if is_he else ISRAEL_AREA_Q_EN)
                if q:
                    return {"action": "ask_question", "reply": q,
                            "pending_slot": "location", "reason": "israel_no_area"}
        return None

    # ── 0. Phase-1 profiling gate ─────────────────────────────────────────────
    if not has_enough_profile(profile):
        basic_q = get_next_missing_profile_question(profile, lang)
        if basic_q:
            nq = _fresh(basic_q)
            if nq:
                return {"action": "ask_question", "reply": nq,
                        "pending_slot": _get_question_slot(nq), "reason": "basic_profiling"}

    # ── 1. Domain-based follow-up ─────────────────────────────────────────────
    if domain_answered or domain_reply_hint:
        next_q = next_context_aware_question(profile, lang)
        if next_q:
            nq = _fresh(next_q)
            if nq:
                prefix = (domain_reply_hint + " ") if domain_reply_hint else ""
                return {"action": "ask_question", "reply": prefix + nq,
                        "pending_slot": _get_question_slot(nq), "reason": "domain_follow_up"}

    # ── 2. Education hint ─────────────────────────────────────────────────────
    if edu_reply_hint and not has_location:
        q = _fresh(edu_reply_hint)
        if q:
            return {"action": "ask_question", "reply": q,
                    "pending_slot": "education_follow", "reason": "edu_hint"}

    # ── 3. Normal context-aware Q ─────────────────────────────────────────────
    next_q = next_context_aware_question(profile, lang)
    if next_q:
        nq = _fresh(next_q)
        if nq:
            return {"action": "ask_question", "reply": nq,
                    "pending_slot": _get_question_slot(nq), "reason": "context_q"}

    # ── 4. Soft signal ────────────────────────────────────────────────────────
    if soft and soft.get("possible_career_directions") and not updates.get("career_interests"):
        soft_r = _build_soft_reply(soft, lang)
        if soft_r and _fresh(soft_r):
            return {"action": "ask_question", "reply": soft_r,
                    "pending_slot": "domain", "reason": "soft_signal"}

    # ── 5. Enough info → refinement once, then search ─────────────────────────
    enough = (
        has_enough_profile(profile)
        and (
            (has_interests and has_location)
            or (open_to_all and _has_strong_constraint(profile))
        )
    )
    if enough:
        if not refinement_asked and not refinement_declined:
            ref_q = REFINEMENT_Q_HE if is_he else REFINEMENT_Q_EN
            return {"action": "ask_refinement", "reply": ref_q,
                    "pending_slot": "refinement", "reason": "offer_refinement"}
        return {"action": "run_search", "reply": "", "pending_slot": None,
                "reason": "run_search_after_refinement"}

    # ── 6. Missing critical slot ───────────────────────────────────────────────
    if not has_interests and not open_to_all:
        q = _fresh(DIRECTION_MISSING_Q_HE if is_he else DIRECTION_MISSING_Q_EN)
        if q:
            return {"action": "ask_question", "reply": q,
                    "pending_slot": "domain", "reason": "no_domain"}
    if not has_location:
        loc_act = _loc_q_action()
        if loc_act:
            return loc_act

    # ── 7. Fallback ────────────────────────────────────────────────────────────
    if has_interests or open_to_all:
        return {"action": "run_search", "reply": "", "pending_slot": None,
                "reason": "fallback_search"}
    return {"action": "ask_question",
            "reply": "מה תרצה/י שאחפש עבורך?" if is_he else "What would you like me to search for?",
            "pending_slot": "domain", "reason": "fallback_ask"}


# ---------------------------------------------------------------------------
# Pending question interpreter
# ---------------------------------------------------------------------------

def _interpret_pending_answer(message: str, pending_q: dict, profile: dict) -> dict:
    if not pending_q or pending_q.get("slot") != "experience":
        return {}
    if _is_negative(message):
        return {"experience": {"years": 0, "experience_answered": True, "seniority": "junior"},
                "_slot_answered": "experience_" + pending_q.get("domain", "")}
    if _is_affirmative(message):
        return {"experience": {"experience_answered": True},
                "_slot_answered": "experience_" + pending_q.get("domain", "")}
    return {}


# ---------------------------------------------------------------------------
# Broad direction Q interpreter
# ---------------------------------------------------------------------------

_BROAD_Q_ANSWER_MAP = [
    {"patterns": [r"^אנשים$", r"^people$", r"לעבוד עם אנשים", r"working with people"],
     "career_interests": ["משאבי אנוש", "שירות לקוחות", "הדרכה", "Customer Success"],
     "reply_hint": "מתאים למשאבי אנוש, שירות לקוחות, הדרכה או Customer Success."},
    {"patterns": [r"^נתונים$", r"^data$", r"^מספרים$", r"^analytics$"],
     "career_interests": ["דאטה", "BI", "ניתוח נתונים"], "reply_hint": ""},
    {"patterns": [r"^ניהול$", r"^management$", r"^manage$"],
     "career_interests": ["ניהול", "ניהול פרויקטים", "תפעול"], "reply_hint": ""},
    {"patterns": [r"^יצירה$", r"^creativity$", r"^creative$", r"^עיצוב$", r"^design$"],
     "career_interests": ["עיצוב", "UX/UI", "שיווק יצירתי", "תוכן"], "reply_hint": ""},
    {"patterns": [r"^טכנולוגיה$", r"^technology$", r"^tech$", r"^תכנות$"],
     "career_interests": ["פיתוח תוכנה", "דאטה", "מוצר"], "reply_hint": ""},
    {"patterns": [r"^אבטחה$", r"^סייבר$", r"^cyber$", r"^security$"],
     "career_interests": ["אבטחת מידע", "סייבר", "Cyber Security"],
     "reply_hint": "מתאים לתפקידי אבטחת מידע וסייבר."},
]


def _interpret_broad_q_answer(message: str, lang: str) -> dict:
    tl = message.strip().lower()
    for entry in _BROAD_Q_ANSWER_MAP:
        if any(re.search(p, tl, re.IGNORECASE) for p in entry["patterns"]):
            upd: dict = {"career_interests": entry["career_interests"], "open_to_all": False,
                         "_domain_answered": True}
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
        return {"reply": reply, "profile": profile, "jobs": [], "search_metadata": {},
                "profile_updated": True, "changed_fields": ["career_interests"],
                "should_clear_jobs": False, "intent": "confirm_direction",
                "profile_completeness": profile_completeness(profile), "insights": {}}
    if _is_negative(message):
        profile["conversation"]["pending_career_directions"] = []
        profile["conversation"]["pending_context"] = ""
        reply = HOBBY_ONLY_EN if lang == "English" else HOBBY_ONLY_HE
        return {"reply": reply, "profile": profile, "jobs": [], "search_metadata": {},
                "profile_updated": False, "changed_fields": [],
                "should_clear_jobs": False, "intent": "reject_direction",
                "profile_completeness": profile_completeness(profile), "insights": {}}
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_message(message: str, profile: Optional[dict] = None) -> dict:
    if profile is None:
        profile = empty_profile()

    lang = detect_language(message)
    # Persist language — a single technical English word (SQL, Python, QA…)
    # should NOT override an established Hebrew session.
    conv = profile.setdefault("conversation", {})
    stored_lang = conv.get("language")
    if stored_lang == "Hebrew" and lang == "English":
        # Only keep English if user wrote ≥3 words (a real English sentence)
        if len(message.strip().split()) < 3:
            lang = "Hebrew"
    conv["language"] = lang

    pending_result = _handle_pending_confirmation(message, profile, lang)
    if pending_result is not None:
        return pending_result

    last_q = profile.get("conversation", {}).get("last_question", "")
    _is_refinement_q = last_q in (REFINEMENT_Q_HE, REFINEMENT_Q_EN)

    # Refinement decline -> run search
    if _is_refinement_q and _is_refinement_decline(message):
        has_int = bool(profile.get("career_interests"))
        has_loc = _location_known(profile)
        if has_int and has_loc:
            jobs_ref, meta_ref = [], {}
            try:
                from matching_engine import search_jobs
                jobs_ref, meta_ref = search_jobs(profile, limit=10)
            except Exception as e:
                logger.error("Refinement search: %s", e)
            if not jobs_ref:
                try:
                    import copy as _c
                    from matching_engine import search_jobs as _sj
                    _rp = _c.deepcopy(profile)
                    _rp.pop("country_preference", None)
                    _rp.pop("location_preference", None)
                    jobs_ref, meta_ref = _sj(_rp, limit=10)
                    if jobs_ref:
                        meta_ref["was_relaxed"] = True
                except Exception:
                    pass
            is_stu = profile.get("experience", {}).get("seniority") in ("סטודנט/ית", "student")
            if jobs_ref:
                if meta_ref.get("was_relaxed"):
                    rpl = ("מצאתי כמה משרות שיכולות להתאים לפי מה שסיפרת:" if lang != "English"
                           else "Found some jobs that might fit based on what you shared:")
                elif is_stu:
                    rpl = _student_job_reply(profile, jobs_ref, meta_ref, lang)
                else:
                    rpl = ("מצאתי משרות מתאימות. דירגתי אותן לפי התאמה לפרופיל שלך." if lang != "English"
                           else "Found matching jobs, ranked by profile fit.")
            else:
                rpl = ("לא מצאתי משרות מתאימות במאגר הנוכחי, אבל אפשר לשנות תחום/אזור ולנסות שוב."
                       if lang != "English" else "No matching jobs found. Try a different field or region.")
            return {"reply": rpl, "profile": profile, "jobs": jobs_ref, "intent": "search_jobs",
                    "search_metadata": meta_ref, "insights": {},
                    "profile_completeness": profile_completeness(profile),
                    "profile_updated": False, "changed_fields": [], "should_clear_jobs": False}
        else:
            profile["conversation"]["refinement_declined"] = True
            profile["conversation"].pop("pending_question", None)
            recent3 = set(profile.get("conversation", {}).get("question_history", [])[-3:])
            next_q  = next_context_aware_question(profile, lang)
            if next_q and next_q not in recent3:
                rpl = next_q
            elif not _location_known(profile):
                _cp = profile.get("country_preference", "")
                rpl = (COUNTRY_Q_HE if not _cp else
                       (ISRAEL_AREA_Q_HE if _cp == "Israel" else COUNTRY_Q_HE)) if lang != "English" else \
                      (COUNTRY_Q_EN if not _cp else
                       (ISRAEL_AREA_Q_EN if _cp == "Israel" else COUNTRY_Q_EN))
            elif not profile.get("career_interests"):
                rpl = DIRECTION_MISSING_Q_HE if lang != "English" else DIRECTION_MISSING_Q_EN
            else:
                rpl = "איזה תפקיד תרצה/י לראות?" if lang != "English" else "What kind of role?"
            _record_question(profile, rpl)
            return {"reply": rpl, "profile": profile, "jobs": [], "intent": "update_profile",
                    "search_metadata": {}, "insights": {},
                    "profile_completeness": profile_completeness(profile),
                    "profile_updated": False, "changed_fields": [], "should_clear_jobs": False}

    # Interpret yes/no for pending slot
    pending_q = profile.get("conversation", {}).get("pending_question", {})
    if pending_q:
        pa = _interpret_pending_answer(message, pending_q, profile)
        if pa:
            slot_key = pa.pop("_slot_answered", None)
            profile = merge_profile_updates(profile, pa)
            if slot_key:
                profile.setdefault("conversation", {}).setdefault("answered_slots", []).append(slot_key)
            profile.get("conversation", {}).pop("pending_question", None)

    # Broad open-to-all direction Q
    if profile.get("open_to_all") and last_q in (OPEN_TO_ALL_Q_HE, OPEN_TO_ALL_Q_EN):
        broad_upd = _interpret_broad_q_answer(message, lang)
        if broad_upd:
            profile = merge_profile_updates(profile, broad_upd)

    # Normal processing
    intent  = detect_intent(message, profile)
    updates = extract_profile_updates(message, profile)

    direction_changed  = False
    soft               = {}
    edu_reply_hint     = ""
    domain_answered    = False
    domain_reply_hint  = ""

    if intent == "reset_profile":
        profile = empty_profile()
        profile["conversation"].update({
            "language": lang, "last_bot_question": "", "last_question": "",
            "asked_questions": [], "question_history": [],
            "refinement_asked": False, "refinement_declined": False,
            "pending_question": {}, "answered_slots": [],
            "turn_count": 0, "profiling_questions_asked": 0,
        })
        updates = {}
    else:
        profile = merge_profile_updates(profile, updates)
        direction_changed = profile.get("conversation", {}).pop("career_direction_changed", False)
        soft              = profile.get("conversation", {}).pop("_last_soft", {})
        edu_reply_hint    = profile.get("conversation", {}).pop("_edu_reply_hint", "")
        domain_answered   = profile.get("conversation", {}).pop("_domain_answered", False)
        domain_reply_hint = profile.get("conversation", {}).pop("_domain_reply_hint", "")

    profile["conversation"]["last_intent"] = intent

    if soft and soft.get("possible_career_directions") and not updates.get("career_interests"):
        profile["conversation"]["pending_career_directions"] = soft["possible_career_directions"]
        profile["conversation"]["pending_context"] = soft.get("reply_he", "")

    has_interests  = bool(profile.get("career_interests"))
    has_location   = _location_known(profile)
    newly_has_loc  = (
        updates.get("country_preference") in ("United States", "Global")
        or (updates.get("country_preference") == "Israel"
            and bool(profile.get("location_preference", {}).get("primary")))
        or bool(updates.get("location_preference", {}).get("primary"))
    )
    newly_has_dir  = bool(updates.get("career_interests") or domain_answered or domain_reply_hint)
    open_to_all    = bool(profile.get("open_to_all"))

    _da = decide_next_action(
        profile, updates, domain_answered, domain_reply_hint, soft, edu_reply_hint, lang
    )
    pending_domain_q = next_context_aware_question(profile, lang)

    # Search gate: redirect explicit search request when profile incomplete
    if (intent == "search_jobs"
            and not _is_refinement_q
            and not has_enough_profile(profile)
            and _da["action"] != "run_search"):
        _gate_q = (get_next_missing_profile_question(profile, lang)
                   or next_context_aware_question(profile, lang)
                   or (DIRECTION_MISSING_Q_HE if lang != "English" else DIRECTION_MISSING_Q_EN))
        _record_question(profile, _gate_q)
        _gate_prefix = ("כדי להתאים לך משרות בצורה מדויקת יותר, אני צריך עוד פרט קצר: "
                        if lang != "English" else "To match you better, I need one more detail: ")
        changed_fields = [k for k in updates if k not in
                          ("conversation", "_soft", "_edu_reply_hint", "_domain_answered", "_domain_reply_hint")]
        return {"reply": _gate_prefix + _gate_q, "profile": profile, "jobs": [],
                "intent": "update_profile", "search_metadata": {}, "insights": {},
                "profile_completeness": profile_completeness(profile),
                "profile_updated": bool(changed_fields), "changed_fields": changed_fields,
                "should_clear_jobs": False}

    auto_search = (
        intent not in ("reset_profile", "expand_location")
        and (_da["action"] == "run_search"
             or (has_interests and has_location and newly_has_loc and newly_has_dir))
    )

    jobs           = []
    search_metadata = {}
    should_clear_jobs = direction_changed

    run_search = (intent in ("search_jobs", "expand_location")) or direction_changed or auto_search

    # ── Country gate: country_preference required before first search ──────────
    # Fires even when has_enough_profile() is True and auto_search is set.
    # Bypassed only when: country already set, OR country has been asked ≥2 times
    # (user is refusing to answer), OR user explicitly wants to expand location.
    if run_search and intent != "expand_location" and not profile.get("country_preference"):
        _conv_sa = profile.get("conversation", {}).get("slot_asks", {})
        if _conv_sa.get("country", 0) < 2:
            _cq = ("באיזו מדינה או אזור לחפש? ישראל, ארה״ב, מרחוק או לא משנה?"
                   if lang != "English"
                   else "Which country or region? Israel, US, Remote, or doesn't matter?")
            _record_question(profile, _cq)
            _cf = [k for k in updates if k not in
                   ("conversation", "_soft", "_edu_reply_hint",
                    "_domain_answered", "_domain_reply_hint")]
            return {"reply": _cq, "profile": profile, "jobs": [],
                    "intent": "update_profile", "search_metadata": {}, "insights": {},
                    "profile_completeness": profile_completeness(profile),
                    "profile_updated": bool(_cf), "changed_fields": _cf,
                    "should_clear_jobs": False}

    if run_search:
        try:
            from matching_engine import search_jobs
            loc_override = None
            if intent == "expand_location":
                loc = profile.get("location_preference", {})
                primary = loc.get("primary", "")
                try:
                    from matching_engine import LOCATION_FALLBACKS
                    fallbacks = LOCATION_FALLBACKS.get(primary, ["מרחוק", "תל אביב"])
                    loc_override = fallbacks[0] if fallbacks else None
                except ImportError:
                    pass
            jobs, search_metadata = search_jobs(profile, limit=10, location_override=loc_override)
        except Exception as e:
            logger.error("Job search error: %s", e)
            search_metadata = {"error": str(e)}

        # Relaxed fallback
        if not jobs and intent != "expand_location":
            try:
                import copy as _copy
                from matching_engine import search_jobs as _sj2
                _relaxed = _copy.deepcopy(profile)
                _relaxed.pop("country_preference", None)
                _relaxed.pop("location_preference", None)
                _rjobs, _rmeta = _sj2(_relaxed, limit=10)
                if _rjobs:
                    jobs = _rjobs
                    search_metadata = {**_rmeta, "was_relaxed": True}
            except Exception as e2:
                logger.error("Relaxed search error: %s", e2)

    reply = generate_reply(
        intent, message, profile, updates, jobs, search_metadata, lang,
        direction_changed=direction_changed, soft=soft, edu_reply_hint=edu_reply_hint,
        domain_answered=domain_answered, auto_searched=auto_search,
        domain_reply_hint=domain_reply_hint, pending_domain_q=pending_domain_q,
        decided_action=_da,
    )

    completeness = profile_completeness(profile)
    changed_fields = [k for k in updates if k not in
                      ("conversation", "_soft", "_edu_reply_hint", "_domain_answered", "_domain_reply_hint")]

    return {
        "reply": reply, "profile": profile, "jobs": jobs, "intent": intent,
        "search_metadata": search_metadata, "insights": {},
        "profile_completeness": completeness,
        "profile_updated": bool(changed_fields), "changed_fields": changed_fields,
        "should_clear_jobs": should_clear_jobs,
        "dataset_search_ran": search_metadata.get("dataset_search_ran", False),
        "candidates_scanned": search_metadata.get("candidates_scanned", 0),
        "results_count": search_metadata.get("results_count", 0),
    }
