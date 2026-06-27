"""
nlp_engine.py — Stage 3: NLP for Hebrew/English/Mixed input.
No external API required — pure regex + keyword matching.
"""
import re
import copy
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def detect_language(text):
    heb_words = re.findall(r"[א-ת]+", text)
    eng_words = re.findall(r"[a-zA-Z]{3,}", text)
    heb = len(heb_words)
    eng = len(eng_words)
    if heb == 0 and eng == 0:
        return "Hebrew"
    if heb > 0 and heb >= eng:
        return "Hebrew"
    if heb > 0 and eng > heb * 3:
        return "Mixed"
    if heb == 0 and eng > 0:
        return "English"
    return "Hebrew"

# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

KNOWN_SKILLS = [
    "sql","mysql","postgresql","oracle","nosql","mongodb",
    "python","scala","java","javascript","typescript","c#","php","ruby","swift","kotlin",
    "excel","power bi","tableau","looker","qlik",
    "pandas","numpy","scikit-learn","tensorflow","pytorch","keras",
    "spark","hadoop","airflow","dbt","snowflake","redshift",
    "etl","bi","data warehouse",
    "react","angular","vue","node","django","flask","fastapi",
    "spring","aws","azure","gcp","docker","kubernetes","terraform",
    "git","github","jira","confluence","agile","scrum",
    "crm","sap","salesforce","hubspot","zendesk","word","powerpoint",
]

SKILL_CANONICAL = {
    "sql":"SQL","mysql":"MySQL","postgresql":"PostgreSQL","oracle":"Oracle",
    "nosql":"NoSQL","mongodb":"MongoDB","python":"Python","scala":"Scala",
    "java":"Java","javascript":"JavaScript","typescript":"TypeScript",
    "c#":"C#","php":"PHP","ruby":"Ruby","swift":"Swift","kotlin":"Kotlin",
    "excel":"Excel","power bi":"Power BI","tableau":"Tableau","looker":"Looker","qlik":"Qlik",
    "pandas":"Pandas","numpy":"NumPy","scikit-learn":"scikit-learn",
    "tensorflow":"TensorFlow","pytorch":"PyTorch","keras":"Keras",
    "spark":"Spark","hadoop":"Hadoop","airflow":"Airflow","dbt":"dbt",
    "snowflake":"Snowflake","redshift":"Redshift","etl":"ETL","bi":"BI",
    "data warehouse":"Data Warehouse","react":"React","angular":"Angular",
    "vue":"Vue","node":"Node.js","django":"Django","flask":"Flask",
    "fastapi":"FastAPI","spring":"Spring","aws":"AWS","azure":"Azure",
    "gcp":"GCP","docker":"Docker","kubernetes":"Kubernetes","terraform":"Terraform",
    "git":"Git","github":"GitHub","jira":"Jira","confluence":"Confluence",
    "agile":"Agile","scrum":"Scrum","crm":"CRM","sap":"SAP",
    "salesforce":"Salesforce","hubspot":"HubSpot","zendesk":"Zendesk",
    "word":"Word","powerpoint":"PowerPoint",
}

SKILL_PATTERNS = [
    re.compile(r"\b" + re.escape(s) + r"\b", re.IGNORECASE)
    for s in KNOWN_SKILLS
]


def extract_skills(text):
    found = set()
    tl = text.lower()
    for skill, pat in zip(KNOWN_SKILLS, SKILL_PATTERNS):
        if pat.search(tl):
            found.add(SKILL_CANONICAL.get(skill, skill.title()))
    # Explicit skill lists
    list_re = re.findall(
        r"(?:יודע[את]?|knows?|skilled? in|proficient in|experience (?:with|in))"
        r"\s*[:—]?\s*([^\.\n]+)",
        text, re.IGNORECASE
    )
    for chunk in list_re:
        for part in re.split(r"[,;ו\-]", chunk):
            p = part.strip().strip("'\"")
            if 2 < len(p) < 40:
                pl = p.lower()
                if pl in SKILL_CANONICAL:
                    found.add(SKILL_CANONICAL[pl])
    return sorted(found)


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

DEGREE_PATTERNS = [
    (r"\bphd\b|doctor(?:ate)?|דוקטור", "PhD"),
    (r"\bm\.?sc\b|master|מ\.?א\b|תואר שני", "מוסמך"),
    (r"\bmba\b", "MBA"),
    (r"\bb\.?sc\b|\bb\.?a\b|bachelor|תואר ראשון|בוגר|לומד[ת]?|סטודנט", "תואר ראשון"),
    (r"diploma|תעודה", "דיפלומה"),
    (r"matriculation|בגרות", "בגרות"),
]

FIELD_PATTERNS = [
    (r"computer science|מדעי המחשב|\bcs\b", "מדעי המחשב"),
    (r"information systems?|מערכות מידע", "מערכות מידע"),
    (r"data science|מדעי נתונים", "מדעי נתונים"),
    (r"software eng|הנדסת תוכנה", "הנדסת תוכנה"),
    (r"electrical eng|הנדסת חשמל", "הנדסת חשמל"),
    (r"industrial eng|הנדסה תעשייתית", "הנדסה תעשייתית"),
    (r"business admin|ניהול עסקים|mba", "ניהול עסקים"),
    (r"economics|כלכלה", "כלכלה"),
    (r"accounting|חשבונאות", "חשבונאות"),
    (r"statistics|סטטיסטיקה", "סטטיסטיקה"),
    (r"math(?:ematics)?|מתמטיקה", "מתמטיקה"),
    (r"marketing|שיווק", "שיווק"),
    (r"law|משפטים|משפט", "משפטים"),
    (r"education|חינוך|הוראה|pedagog", "חינוך"),
    (r"psychology|פסיכולוגיה", "פסיכולוגיה"),
    (r"social work|עבודה סוציאלית|רווחה", "עבודה סוציאלית"),
    (r"communication|תקשורת|יחסי ציבור", "תקשורת"),
    (r"nursing|סיעוד|מדעי הסיעוד", "סיעוד"),
    (r"management(?!\s+information)|ניהול(?!\s+(?:עסקים|מידע|מוצר))", "ניהול"),
    (r"business\s+management|ניהול\s+עסקים", "ניהול עסקים"),
]

STATUS_PATTERNS = [
    (r"סטודנט[ית]?|studying|לומד[ת]?\s*(?:כרגע|עכשיו)|שנה [א-ד]\b", "סטודנט/ית"),
    (r"בוגר[ת]?|graduated|finished|סיימ[תי]", "בוגר/ת"),
]


def extract_education(text):
    result = {}
    tl = text.lower()
    for pat, label in DEGREE_PATTERNS:
        if re.search(pat, tl, re.IGNORECASE):
            result["degree"] = label
            break
    for pat, label in FIELD_PATTERNS:
        if re.search(pat, tl, re.IGNORECASE):
            result["field"] = label
            break
    for pat, label in STATUS_PATTERNS:
        if re.search(pat, tl, re.IGNORECASE):
            result["status"] = label
            break
    return result


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------

_YEAR_WORD_MAP = [
    (r"(?<!\d)עשר\s+שנים", 10),
    (r"(?<!\d)תשע\s+שנים", 9),
    (r"(?<!\d)שמונה\s+שנים", 8),
    (r"(?<!\d)שבע\s+שנים", 7),
    (r"(?<!\d)שש\s+שנים", 6),
    (r"(?<!\d)חמש\s+שנים", 5),
    (r"(?<!\d)ארבע\s+שנים", 4),
    (r"(?<!\d)שלוש?\s+שנים", 3),
    (r"(?<!\d)שנתיים", 2),
    (r"(?<!\d)שנה(?:\s+אחת)?(?!\s*\d)", 1),
]


def extract_experience(text):
    result = {}

    # Numeric years ("3 years", "3 שנים")
    yr = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:years?|שנ[יהם]|שנות)\s*(?:of\s+)?(?:experience|ניסיון)?",
        text, re.IGNORECASE
    )
    if yr:
        result["years"] = float(yr.group(1))

    # Hebrew word-based years ("שנה", "שנתיים", "שלוש שנים" …)
    if "years" not in result:
        for pat, val in _YEAR_WORD_MAP:
            if re.search(pat, text, re.IGNORECASE):
                result["years"] = float(val)
                break

    # Seniority signals
    if re.search(r"\bjunior\b|ג'וניור|entry level|מתחיל", text, re.IGNORECASE):
        result["seniority"] = "ג'וניור"
    elif re.search(r"\bsenior\b|בכיר", text, re.IGNORECASE):
        result["seniority"] = "בכיר"
    elif re.search(r"\bmid\b|ביניים|intermediate", text, re.IGNORECASE):
        result["seniority"] = "ביניים"
    elif re.search(r"intern|סטודנט|התמחות", text, re.IGNORECASE):
        result["seniority"] = "סטודנט/ית"

    # "אין לי ניסיון" / "no experience"
    if re.search(r"אין לי ניסיון|no experience|without experience|ללא ניסיון", text, re.IGNORECASE):
        result["years"] = 0
        if not result.get("seniority"):
            result["seniority"] = "ג'וניור"

    # Role extraction — explicit "worked as X" or "was X" style text
    role_re = re.findall(
        r"(?:worked?\s+(?:as|in)|עבדת?י\s+כ[ּ]?|ניסיון\s+ב|תפקיד[יי]?)\s*([^,\.\n!?]{3,50})",
        text, re.IGNORECASE
    )
    # "הייתי / שימשתי / כיהנתי [time?] [role]"
    role_re2 = re.findall(
        r"(?:הייתי|שימשתי|כיהנתי)\s+(?:(?:שנה(?:\s+אחת)?|שנתיים|שלוש?\s+שנים|\d+\s*שנ[יהם])\s+)?(?:כ[ּ]?|ב[ּ]?)?\s*([^\.,\n!?]{3,50})",
        text, re.IGNORECASE
    )
    # "עבדתי [time] ב/כ [role]"
    role_re3 = re.findall(
        r"עבדת?י\s+(?:(?:שנה(?:\s+אחת)?|שנתיים|\d+\s*שנ[יהם])\s+)?(?:ב[ּ]?|כ[ּ]?)?\s*([^\.,\n!?]{3,50})",
        text, re.IGNORECASE
    )
    all_roles = [r.strip() for r in (role_re + role_re2 + role_re3) if r.strip()]
    if all_roles:
        result["previous_roles"] = list(dict.fromkeys(all_roles))[:5]

    return result


# ---------------------------------------------------------------------------
# Salary
# ---------------------------------------------------------------------------

def extract_salary(text):
    """Extract salary expectation from text.
    Handles: "15000", "15K", "15k", "15 אלף", "15,000", "מעל 15 אלף", "שכר 15 אלף".
    """
    result = {}
    tl = text.lower()

    def _parse_salary_token(token: str) -> float:
        """Convert a raw token like '15k', '15,000', '15' (in אלף context) to float."""
        raw = token.replace(",", "").strip()
        if raw.endswith("k"):
            return float(raw[:-1]) * 1000
        return float(raw)

    # Pattern 1: explicit Hebrew "אלף" multiplier — "15 אלף", "מעל 15 אלף", "שכר 15 אלף"
    alef_match = re.search(
        r"(\d[\d,]*)(?:\s*-\s*\d[\d,]*)?\s*אלף",
        text, re.IGNORECASE
    )
    if alef_match:
        val = float(alef_match.group(1).replace(",", "")) * 1000
        if 1000 < val < 100000:
            result["preferred"] = val
            result["min"] = val * 0.85
            result["flexible"] = False

    # Pattern 2: keyword-prefixed number — "שכר 15000", "salary 15k", "ציפיות 15,000"
    if not result:
        sal = re.search(
            r"(?:שכר|salary|expect|ציפיות|מינימום|minimum|מעל|above|over)[^\d]*(\d[\d,\.]*[kK]?)",
            text, re.IGNORECASE
        )
        if sal:
            try:
                val = _parse_salary_token(sal.group(1))
                if 1000 < val < 100000:
                    result["preferred"] = val
                    result["min"] = val * 0.85
                    result["flexible"] = False
            except ValueError:
                pass

    # Pattern 3: bare 5-digit number with currency hint — "15000 שקל"
    if not result:
        sal = re.search(
            r"(\d{4,6})\s*(?:שקל|ils|nis|per month|לחודש|₪)",
            text, re.IGNORECASE
        )
        if sal:
            try:
                val = _parse_salary_token(sal.group(1))
                if 1000 < val < 100000:
                    result["preferred"] = val
                    result["min"] = val * 0.85
                    result["flexible"] = False
            except ValueError:
                pass

    if re.search(r"גמיש|flexible|לא קריטי|not important|open to|פתוח", text, re.IGNORECASE):
        result["flexible"] = True
    return result


# ---------------------------------------------------------------------------
# Work preferences (type + mode)
# ---------------------------------------------------------------------------

def extract_work_preferences(text: str) -> dict:
    """Extract work_type and work_mode from a message.

    work_type: full_time | part_time
    work_mode: hybrid | remote | onsite
    """
    result = {}
    tl = text.lower()

    # work_type
    if re.search(r"משרה מלאה|full[- ]?time|משרה מלאה", tl):
        result["work_type"] = "full_time"
    elif re.search(r"משרה חלקית|part[- ]?time|חצי משרה|חלקי", tl):
        result["work_type"] = "part_time"

    # work_mode
    if re.search(r"היברידי|hybrid", tl):
        result["work_mode"] = "hybrid"
    elif re.search(r"מרחוק|remote|work from home|מהבית", tl):
        result["work_mode"] = "remote"
    elif re.search(r"מהמשרד|פרונטלי|onsite|in.office|ממשרד", tl):
        result["work_mode"] = "onsite"

    return result


# ---------------------------------------------------------------------------
# Open-to-all detection
# ---------------------------------------------------------------------------

_OPEN_TO_ALL_PATTERNS = [
    r"^הכל$", r"^הכול$",
    r"פתוח[הי]?\s+(?:ל(?:הכ[לו]|כ[לו]))",
    r"לא\s+משנה\s+לי",
    r"אין\s+לי\s+כיוון",
    r"open\s+to\s+(?:anything|everything|all)",
    r"כל\s+(?:תחום|עבודה|כיוון|משרה)",
    r"מוכ[הן]\s+לכל",
    r"לא\s+בררנ",          # "לא בררנית", "לא בררן"
]


def is_open_to_all(message: str) -> bool:
    """Return True when the user signals they are open to any career direction."""
    tl = message.strip().lower()
    return any(re.search(p, tl, re.IGNORECASE) for p in _OPEN_TO_ALL_PATTERNS)


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

AREA_KEYWORDS = {
    "השרון": ["השרון","הרצליה","רעננה","כפר סבא","הוד השרון","נתניה","sharon","herzliya","raanana","netanya"],
    "תל אביב": ["תל אביב","תל-אביב","tel aviv","tlv","jaffa"],
    "המרכז": ["המרכז","רמת גן","פתח תקווה","גבעתיים","center","central","ramat gan"],
    "השפלה": ["השפלה","ראשון לציון","רחובות","מודיעין","rishon","rehovot"],
    "ירושלים": ["ירושלים","jerusalem"],
    "הצפון": ["הצפון","חיפה","haifa","north"],
    "הדרום": ["הדרום","באר שבע","beer sheva","south"],
    "מרחוק": ["remote","מרחוק","היברידי","hybrid","home","מהבית"],
}


# ---------------------------------------------------------------------------
# Country preference extraction
# ---------------------------------------------------------------------------

# Priority order matters: United States must come before Global, since "US" could
# overlap with general patterns.  Checked in order: Israel → United States → Global.
_COUNTRY_PATTERNS: dict = {
    "Israel": [
        r"^ישראל$",
        r"^israel$",
        r"^il$",
        r"\bבישראל\b",
        r"\bבארץ\b",
        r"השוק הישראלי",
        r"אזור בישראל",
        r"עיר.*בישראל",
        r"בישראל.*אזור",
    ],
    "United States": [
        r"^ארה[\"״]?ב$",
        r"^ארצות הברית$",
        r"^united states$",
        r"^usa$",
        r"^u\.s\.a?\.?$",
        r"^us$",
        r"\bבארה[\"״]?ב\b",
        r"\bבארצות הברית\b",
        r"\bamerica\b",
        r"\bארה[\"״]ב\b",
        r"\bארצות הברית\b",
        r"\bunited states\b",
        r"\busa\b",
        r"\bu\.s\.\b",
    ],
    "Global": [
        r"^לא משנה$",
        r"^הכל$",
        r"^הכול$",
        r"^anywhere$",
        r"^global$",
        r"^worldwide$",
        r"לא משנה לי",
        r"לא אכפת לי",
        r"כל מקום",
        r"בכל העולם",
        r"בכל מקום",
        r"\banywhere\b",
        r"\bglobal\b",
        r"\bworldwide\b",
    ],
}


def extract_country_preference(text: str) -> Optional[str]:
    """
    Extract country_preference from a user message.

    Returns one of: "Israel", "United States", "Global", or None.

    Priority: Israel > United States > Global.
    The function checks the whole message but is careful not to false-positive on
    words like 'ישראל' that appear only inside a city name (e.g. 'בית שמש' contains no
    country reference).
    """
    tl = text.strip()
    for country, patterns in _COUNTRY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, tl, re.IGNORECASE):
                return country
    return None


def extract_location(text):
    result = {}
    tl = text.lower()
    found_areas = []
    for area, keywords in AREA_KEYWORDS.items():
        if any(kw.lower() in tl for kw in keywords):
            found_areas.append(area)
    if found_areas:
        if "מרחוק" in found_areas:
            result["remote_allowed"] = True
            found_areas.remove("מרחוק")
        if found_areas:
            result["primary"] = found_areas[0]
            result["fallbacks"] = found_areas[1:]
    if re.search(r"hybrid|היברידי", tl):
        result["remote_allowed"] = True
        result["preferred_environment"] = "היברידי"
    elif re.search(r"\bremote\b|מרחוק|work from home|מהבית", tl):
        result["remote_allowed"] = True
        result["preferred_environment"] = "מרחוק"
    elif re.search(r"\boffice\b|משרד|in person|in-person", tl):
        result["preferred_environment"] = "משרד"
    return result


# ---------------------------------------------------------------------------
# Career interests — with free-text role phrase extraction
# ---------------------------------------------------------------------------

INTEREST_KEYWORDS = {
    "דאטה": ["data analyst","data science","data engineer","דאטה","analytics","bi analyst","מדען נתונים","מנתח נתונים"],
    "ניתוח מערכות": ["system analyst","business analyst","ניתוח מערכות","מנתח מערכות","systems analyst"],
    "פיתוח תוכנה": ["developer","software engineer","programmer","פיתוח","מפתח","software dev","full stack","backend","frontend"],
    "מוצר": ["product manager","product owner","מנהל מוצר","product","מוצר"],
    "שיווק": ["marketing","שיווק","digital marketing","content marketing","brand"],
    "מכירות": ["sales role","מכירות תפקיד"],
    "שירות לקוחות": ["customer service","support specialist","שירות לקוחות","customer success"],
    "משאבי אנוש": ["human resources","recruiter","גיוס","משאבי אנוש","hr specialist","talent"],
    "כספים": ["finance","accounting","כספים","חשבונאות","controller","cfo","financial analyst"],
    "חינוך": ["teacher","מורה","teaching","הוראה","education","מחנך","educator","tutor","מתמטיקה teacher","math teacher","מדעים teacher"],
    "ניהול": ["manager","director","מנהל","ניהול","team lead","vp","head of"],
    "בריאות": ["nurse","doctor","medical","בריאות","רפואה","אחות","therapist","psychologist"],
    "תפעול": ["operations","תפעול","logistics","supply chain","project manager","operations manager"],
}


# ---------------------------------------------------------------------------
# Generic domain/skill words → career interests + implicit skills
# ---------------------------------------------------------------------------
# Catches informal words like "תכנות", "עיצוב", "דאטה" and maps them to
# career_interests so the agent doesn't re-ask for skills.

DOMAIN_SKILL_MAP = [
    # ── SQL / BI database tools → Data domain ────────────────────────────────
    {
        "patterns": [
            r"\bsql\b", r"\bmysql\b", r"\bpostgresql\b", r"\boracle db\b",
        ],
        "career_interests": ["דאטה", "BI"],
        "skills": [],
        "reply_he": "SQL מתאים לדאטה, BI ואנליטיקס.",
    },
    {
        "patterns": [
            r"\bpower bi\b", r"\btableau\b", r"\blooker\b", r"\bqlik\b",
        ],
        "career_interests": ["דאטה", "BI"],
        "skills": [],
        "reply_he": "כלי BI מתאימים לניתוח נתונים ו-BI.",
    },
    {
        "patterns": [r"\bexcel\b"],
        "career_interests": ["דאטה", "BI", "כספים"],
        "skills": [],
        "reply_he": "Excel מתאים לדאטה, BI וכספים.",
    },
    # ── Java / JS / web frameworks → Software domain ─────────────────────────
    {
        "patterns": [
            r"\bjava\b", r"\bkotlin\b", r"\bspring\b",
        ],
        "career_interests": ["פיתוח תוכנה"],
        "skills": [],
        "reply_he": "Java/Kotlin מתאימים לפיתוח Backend.",
    },
    {
        "patterns": [
            r"\bjavascript\b", r"\btypescript\b", r"\breact\b",
            r"\bangular\b", r"\bvue\b", r"\bnode\.?js\b", r"\bnode\b",
            r"\bfrontend\b", r"\bfront.?end\b",
        ],
        "career_interests": ["פיתוח תוכנה"],
        "skills": [],
        "reply_he": "JavaScript/React מתאימים לפיתוח Frontend.",
    },
    # ── Generic programming words → Software domain ───────────────────────────
    {
        "patterns": [
            r"\bתכנות\b", r"\bלתכנת\b", r"\bמתכנת[ת]?\b",
            r"\bקוד\b", r"\bלכתוב קוד\b",
            r"\bprogramming\b", r"\bcoding\b", r"\bcode\b",
            r"\bdevelop(?:er|ment|ing)?\b",
        ],
        "career_interests": ["פיתוח תוכנה", "תכנות"],
        "skills": ["Programming"],
        "reply_he": "",
    },
    # ── QA / Software Testing ─────────────────────────────────────────────────
    {
        "patterns": [
            r"\bqa\b", r"\bquality\s+assurance\b",
            r"\bבדיקות(?:\s+(?:תוכנה|אוטומטיות|ידניות))?\b",
            r"\btester\b", r"\bsoftware\s+test(?:ing|er)?\b",
            r"\bmanual\s+test(?:ing)?\b", r"\bautomation\s+test(?:ing)?\b",
            r"\bselenium\b", r"\bcypress\b",
        ],
        "career_interests": ["QA", "בדיקות תוכנה"],
        "skills": ["QA"],
        "reply_he": "QA ובדיקות תוכנה — תחום עם ביקוש גבוה.",
    },
    # ── Cyber / Information Security ──────────────────────────────────────────
    {
        "patterns": [
            r"\bסייבר\b", r"אבטחת\s+מידע", r"הגנת\s+סייבר",
            r"cyber\s*security", r"\bcyber\b",
            r"\binfosec\b", r"information\s+security",
            r"\bsoc\b", r"\bsiem\b",
            r"penetration\s+test(?:ing)?", r"\bpentest\b",
            r"network\s+security", r"cloud\s+security", r"application\s+security",
            r"\bgrc\b", r"risk\s+(?:and\s+)?compliance",
            r"security\s+analyst", r"security\s+engineer",
            r"אבטחת\s+רשתות", r"אבטחת\s+ענן",
            r"ניהול\s+סיכונים", r"בודק\s+חדירות",
            r"סיכוני\s+סייבר", r"ניתוח\s+אירועי\s+אבטחה",
        ],
        "career_interests": ["אבטחת מידע", "סייבר", "Cyber Security"],
        "skills": ["Cyber Security"],
        "reply_he": "מתאים לתפקידי אבטחת מידע וסייבר.",
    },
    # ── Design / UX ───────────────────────────────────────────────────────────
    {
        "patterns": [
            r"\bעיצוב\b", r"\bלעצב\b", r"\bמעצב[תי]?\b",
            r"\bux\b", r"\bui\b", r"\bux.?ui\b",
            r"\bdesign(?:er|ing)?\b", r"\bgraphic\b",
        ],
        "career_interests": ["עיצוב", "UX/UI"],
        "skills": ["Design"],
        "reply_he": "",
    },
    # ── Data / analytics generic words ───────────────────────────────────────
    {
        "patterns": [
            r"\bדאטה\b", r"\bנתונים\b", r"\banalytics\b",
        ],
        "career_interests": ["דאטה"],
        "skills": [],
        "reply_he": "",
    },
    # ── Content / writing ─────────────────────────────────────────────────────
    {
        "patterns": [
            r"\bכתיבה\b", r"\bwriting\b", r"\bcontent\b", r"\bתוכן\b",
            r"\bcopywriting\b",
        ],
        "career_interests": ["שיווק", "תוכן"],
        "skills": [],
        "reply_he": "",
    },
    # ── Marketing ─────────────────────────────────────────────────────────────
    {
        "patterns": [r"\bשיווק\b", r"\bmarketing\b"],
        "career_interests": ["שיווק"],
        "skills": [],
        "reply_he": "",
    },
    # ── Management ────────────────────────────────────────────────────────────
    {
        "patterns": [r"\bניהול\b", r"\bmanagement\b", r"\bmanag(?:er|ing)\b"],
        "career_interests": ["ניהול"],
        "skills": [],
        "reply_he": "",
    },
    # ── Finance / accounting ──────────────────────────────────────────────────
    {
        "patterns": [r"\bחשבונאות\b", r"\baccounting\b", r"\bfinance\b", r"\bכספים\b"],
        "career_interests": ["כספים"],
        "skills": [],
        "reply_he": "",
    },
    # ── Sales ─────────────────────────────────────────────────────────────────
    {
        "patterns": [r"(?<![א-ת])מכירות|מכירות(?![א-ת])", r"\bsales\b"],
        "career_interests": ["מכירות"],
        "skills": [],
        "reply_he": "",
    },
    # ── People-facing career direction (broad answer to open-to-all Q) ──────────
    {
        "patterns": [
            r"^אנשים$", r"^people$",
            r"לעבוד עם אנשים", r"אוהב[תי]?\s+אנשים",
            r"working with people", r"helping people",
            r"לעזור לאנשים", r"עבודה עם אנשים",
        ],
        "career_interests": ["משאבי אנוש", "שירות לקוחות", "הדרכה", "Customer Success"],
        "skills": [],
        "reply_he": "מתאים למשאבי אנוש, שירות לקוחות, הדרכה או Customer Success.",
    },
    # ── HR / Recruiting ───────────────────────────────────────────────────────
    {
        "patterns": [r"\bמשאבי\s+אנוש\b", r"\bגיוס\b", r"\bhr\b", r"\brecruit"],
        "career_interests": ["משאבי אנוש"],
        "skills": [],
        "reply_he": "",
    },
    # ── Operations ────────────────────────────────────────────────────────────
    {
        "patterns": [r"\bתפעול\b", r"\boperations\b"],
        "career_interests": ["תפעול"],
        "skills": [],
        "reply_he": "",
    },
    # ── Healthcare ────────────────────────────────────────────────────────────
    {
        "patterns": [r"\bסיעוד\b", r"\brn\b", r"\bnurse\b", r"\brpn\b"],
        "career_interests": ["בריאות", "סיעוד"],
        "skills": [],
        "reply_he": "",
    },
]

# ---------------------------------------------------------------------------
# PROFESSION_MAP — specific job title / role phrases → career domain + reply hint
# Higher priority than DOMAIN_SKILL_MAP; scanned first.
# Catches "מנהלת משרד", "רכזת גיוס", "עורך דין" etc. without requiring study context.
# ---------------------------------------------------------------------------

PROFESSION_MAP = [
    # ── Business / Office / Administration ───────────────────────────────────
    {
        "patterns": [
            r"\bמנהל[ת]?\s+(?:משרד|פעילות|אדמיניסטרציה)\b",
            r"\boffice\s+manager\b",
            r"\bניהול\s+(?:משרד|תפעול)\b",
            r"\bעוזר[ת]?\s+(?:מנהל|להנהלה|מנכ.?ל)\b",
            r"\bמזכיר[ה]?\b",
            r"\bאדמינ(?:יסטרציה|יסטרטור|יסטרטיבי)?\b",
            r"\badmin(?:istration|istrator)?\b",
            r"\boffice\s+admin(?:istrator)?\b",
            r"\bexecutive\s+assistant\b",
            r"\bpersonal\s+assistant\b",
        ],
        "career_interests": ["ניהול משרד", "תפעול", "אדמיניסטרציה"],
        "domain": "business",
        "reply_he": "מתאים לתפקידי ניהול משרד, אדמיניסטרציה ותפעול.",
    },
    # ── Business / Management degree ─────────────────────────────────────────
    {
        "patterns": [
            r"\bניהול\s+עסקים\b",
            r"\bניהול\s+עסקי\b",
            r"\bbusiness\s+administration\b",
            r"\bbusiness\s+management\b",
            r"\bbusiness\s+degree\b",
            r"\bmba\b",
            r"\bתואר\s+(?:ב|ב-)?\s*ניהול\b",
        ],
        "career_interests": ["ניהול", "תפעול", "אדמיניסטרציה", "שיווק"],
        "domain": "business",
        "reply_he": "מתאים לכיווני ניהול, תפעול או אדמיניסטרציה.",
    },
    # ── HR / Recruiting ───────────────────────────────────────────────────────
    {
        "patterns": [
            r"\bרכז[ת]?\s+(?:גיוס|משאבי\s+אנוש|hr)\b",
            r"\bמנהל[ת]?\s+(?:גיוס|hr|משאבי\s+אנוש)\b",
            r"\bhuman\s+resources?\s+(?:manager|specialist|director|coordinator)?\b",
            r"\bhr\s+(?:manager|specialist|generalist|coordinator|business\s+partner)\b",
            r"\brecruiter\b",
            r"\btalent\s+acquisition\b",
            r"\bhead\s+of\s+(?:hr|people|talent)\b",
            r"\bpeople\s+(?:manager|partner|ops|operations)\b",
        ],
        "career_interests": ["משאבי אנוש", "גיוס"],
        "domain": "hr",
        "reply_he": "מתאים לתפקידי גיוס, משאבי אנוש ופיתוח ארגוני.",
    },
    # ── Sales / Business Development ─────────────────────────────────────────
    {
        "patterns": [
            r"\bנציג[ת]?\s+(?:מכירות|שירות\s+לקוחות)\b",
            r"\bמנהל[ת]?\s+(?:מכירות|לקוחות?|מכירה)\b",
            r"\bsales\s+(?:manager|representative|rep|exec|director|associate|lead)\b",
            r"\baccount\s+(?:manager|executive|rep|director)\b",
            r"\bbusiness\s+development\s+(?:manager|rep|executive|director)?\b",
            r"\bcustomer\s+success\s+(?:manager|rep|specialist)?\b",
            r"\bנציג[ת]?\s+מכירות\b",
        ],
        "career_interests": ["מכירות", "ניהול לקוחות"],
        "domain": "sales",
        "reply_he": "מתאים לתפקידי מכירות, ניהול לקוחות ופיתוח עסקי.",
    },
    # ── Customer Service ──────────────────────────────────────────────────────
    {
        "patterns": [
            r"\bנציג[ת]?\s+שירות\b",
            r"\bשירות\s+לקוחות\b",
            r"\bcustomer\s+service\s+(?:rep|specialist|agent|manager)?\b",
            r"\bcustomer\s+support\b",
            r"\bcall\s+center\b",
        ],
        "career_interests": ["שירות לקוחות"],
        "domain": "service",
        "reply_he": "מתאים לתפקידי שירות לקוחות ותמיכה.",
    },
    # ── Healthcare / Medical ──────────────────────────────────────────────────
    {
        "patterns": [
            r"\bאחות\b", r"\bאח\s+(?:רשום|מוסמך)\b",
            r"\bסיעוד\b",
            r"\bרופא[ה]?\b",
            r"\bפסיכולוג[ית]?\b",
            r"\bפסיכיאטר\b",
            r"\bעובד[ת]?\s+סוציאלי[ת]?\b",
            r"\bעבודה\s+סוציאלית\b",
            r"\bregistered\s+nurse\b", r"\brn\b",
            r"\blicensed\s+practical\s+nurse\b",
            r"\bmedical\s+(?:assistant|technician|professional)\b",
            r"\bphysical\s+therapist\b",
            r"\bmental\s+health\s+(?:therapist|counselor)?\b",
            r"\btherapist\b",
            r"\bclinical\b",
        ],
        "career_interests": ["בריאות", "סיעוד"],
        "domain": "healthcare",
        "reply_he": "מתאים לתפקידי בריאות, סיעוד וטיפול.",
    },
    # ── Social Work / Psychology ──────────────────────────────────────────────
    {
        "patterns": [
            r"\bעבודה\s+סוציאלית\b",
            r"\bעובד[ת]?\s+סוציאלי[ת]?\b",
            r"\bפסיכולוג[ית]?\b",
            r"\bsocial\s+work(?:er)?\b",
            r"\bcounselor\b",
            r"\bpsychologist\b",
        ],
        "career_interests": ["עבודה סוציאלית", "פסיכולוגיה"],
        "domain": "social",
        "reply_he": "מתאים לתפקידי עבודה סוציאלית, ייעוץ ופסיכולוגיה.",
    },
    # ── Law / Legal ───────────────────────────────────────────────────────────
    {
        "patterns": [
            r"\bעורך[ת]?\s+דין\b",
            r"\bפרלגל\b",
            r"\blawyer\b",
            r"\battorney\b",
            r"\bparalegal\b",
            r"\blegal\s+(?:counsel|advisor|assistant|secretary|analyst|manager)\b",
            r"\bin-house\s+counsel\b",
        ],
        "career_interests": ["משפטים", "ייעוץ משפטי"],
        "domain": "law",
        "reply_he": "מתאים לתפקידי עורך דין, יועץ משפטי ופרלגל.",
    },
    # ── Logistics / Supply Chain ──────────────────────────────────────────────
    {
        "patterns": [
            r"\bלוגיסטיקה\b",
            r"\bרכש\b",
            r"\bשרשרת\s+אספקה\b",
            r"\bsupply\s+chain\b",
            r"\bprocurement\b",
            r"\bwarehouse\s+(?:manager|supervisor|coordinator)?\b",
            r"\blogistics\s+(?:manager|coordinator|specialist)?\b",
            r"\binventory\s+(?:manager|specialist)?\b",
        ],
        "career_interests": ["לוגיסטיקה", "שרשרת אספקה"],
        "domain": "logistics",
        "reply_he": "מתאים לתפקידי לוגיסטיקה, רכש ושרשרת אספקה.",
    },
    # ── Operations / Project Management ──────────────────────────────────────
    {
        "patterns": [
            r"\bרכז[ת]?\s+תפעול\b",
            r"\boperations\s+(?:manager|coordinator|analyst|director)\b",
            r"\bproject\s+manager\b",
            r"\bprogram\s+manager\b",
            r"\bscrum\s+master\b",
            r"\bsite\s+manager\b",
        ],
        "career_interests": ["תפעול", "ניהול פרויקטים"],
        "domain": "operations",
        "reply_he": "מתאים לתפקידי תפעול וניהול פרויקטים.",
    },
    # ── Product Management ────────────────────────────────────────────────────
    {
        "patterns": [
            r"\bמנהל[ת]?\s+מוצר\b",
            r"\bproduct\s+manager\b",
            r"\bproduct\s+owner\b",
            r"\bpm\s+role\b",
            r"\bgroup\s+product\s+manager\b",
        ],
        "career_interests": ["מוצר", "ניהול מוצר"],
        "domain": "product",
        "reply_he": "מתאים לתפקידי ניהול מוצר ו-PM.",
    },
    # ── Engineering (non-software) ────────────────────────────────────────────
    {
        "patterns": [
            r"\bהנדסת\s+(?:מכונות|חשמל|אזרחית|תעשייתית|כימית|מכניקה)\b",
            r"\bcivil\s+engineer\b",
            r"\bmechanical\s+engineer\b",
            r"\belectrical\s+engineer\b",
            r"\bindustrial\s+engineer\b",
            r"\bchemical\s+engineer\b",
            r"\bstructural\s+engineer\b",
        ],
        "career_interests": ["הנדסה"],
        "domain": "engineering",
        "reply_he": "מתאים לתפקידי הנדסה.",
    },
    # ── Finance / Accounting specific roles ──────────────────────────────────
    {
        "patterns": [
            r"\bחשבונאי[ת]?\b",
            r"\bמנהל[ת]?\s+כספים\b",
            r"\bcontroller\b",
            r"\baccountant\b",
            r"\bfinancial\s+analyst\b",
            r"\bcfo\b",
            r"\bbookkeeper\b",
            r"\bהנהלת\s+חשבונות\b",
        ],
        "career_interests": ["כספים", "חשבונאות"],
        "domain": "finance",
        "reply_he": "מתאים לתפקידי כספים, חשבונאות ופיננסים.",
    },
    # ── Cyber / Information Security roles ───────────────────────────────────
    {
        "patterns": [
            r"\bsoc\s+analyst\b",
            r"\bcyber\s+(?:security\s+)?analyst\b",
            r"\bsecurity\s+analyst\b",
            r"\bsecurity\s+engineer\b",
            r"\bpenetration\s+tester?\b",
            r"\bpentest(?:er)?\b",
            r"\bgrc\s+(?:analyst|specialist|manager)?\b",
            r"\binfosec\s+(?:analyst|engineer|specialist)?\b",
            r"\bjunior\s+soc\b",
            r"\bcloud\s+security\s+(?:analyst|engineer)?\b",
            r"\bnetwork\s+security\s+(?:analyst|engineer)?\b",
            r"\bcybersecurity\s+(?:analyst|engineer|specialist)?\b",
        ],
        "career_interests": ["אבטחת מידע", "סייבר", "SOC", "Cyber Security"],
        "domain": "cyber",
        "reply_he": "מתאים לתפקידי אבטחת מידע, SOC וסייבר.",
    },
    # ── Teaching / Education roles ─────────────────────────────────────────────
    {
        "patterns": [
            r"\bמורה\s+ל[^\s]{2,}\b",
            r"\bמורה\b",
            r"\bמחנכ[תי]?\b",
            r"\bמגיש[תי]?\s+(?:שיעור|שיעורים)\b",
            r"\bteacher\b",
            r"\binstructor\b",
            r"\btutor\b",
            r"\beducator\b",
        ],
        "career_interests": ["חינוך", "הוראה"],
        "domain": "education",
        "reply_he": "מתאים לתפקידי הוראה וחינוך.",
    },
]

# ---------------------------------------------------------------------------
# Education field → implied career direction + smart reply hint
# ---------------------------------------------------------------------------

EDUCATION_CAREER_MAP = {
    "מדעי המחשב": {
        "career_interests": ["פיתוח תוכנה", "תכנות"],
        "reply_he": "מתאים לכיווני פיתוח. יש שפה או תחום שמעניין אותך?",
    },
    "הנדסת תוכנה": {
        "career_interests": ["פיתוח תוכנה", "הנדסת תוכנה"],
        "reply_he": "מתאים לפיתוח ואינטגרציה. יש שפה שמעניינת אותך?",
    },
    "מערכות מידע": {
        "career_interests": ["ניתוח מערכות", "דאטה", "BI"],
        "reply_he": "מתאים לדאטה, BI או ניתוח מערכות. מה הכיוון שמעניין אותך?",
    },
    "מדעי נתונים": {
        "career_interests": ["דאטה", "פיתוח תוכנה"],
        "reply_he": "מתאים לדאטה, ML ואנליטיקס. יש כיוון ספציפי?",
    },
    "כלכלה": {
        "career_interests": ["כספים", "ניתוח מערכות"],
        "reply_he": "מתאים לכלכלה, פיננסים או אנליזה. מה הכיוון שמעניין אותך?",
    },
    "חשבונאות": {
        "career_interests": ["כספים"],
        "reply_he": "מתאים לחשבונאות, כספים וביקורת. מה הכיוון?",
    },
    "שיווק": {
        "career_interests": ["שיווק"],
        "reply_he": "מתאים לשיווק דיגיטלי, תוכן ומוצר. מה הכיוון שמעניין אותך?",
    },
    "ניהול עסקים": {
        "career_interests": ["ניהול", "תפעול", "שיווק"],
        "reply_he": "מתאים לניהול, תפעול או שיווק. מה הכיוון שמעניין אותך?",
    },
    "חינוך": {
        "career_interests": ["חינוך"],
        "reply_he": "מתאים להוראה וחינוך. באיזה מקצוע תרצה/י ללמד?",
    },
    "מתמטיקה": {
        "career_interests": ["חינוך", "דאטה", "כספים"],
        "reply_he": "מתאים לדאטה, כספים או הוראת מתמטיקה. מה מעניין אותך?",
    },
    "סטטיסטיקה": {
        "career_interests": ["דאטה", "כספים"],
        "reply_he": "מתאים לדאטה ואנליטיקס. יש כיוון ספציפי?",
    },
    "הנדסת חשמל": {
        "career_interests": ["הנדסה"],
        "reply_he": "מתאים להנדסת חשמל ואלקטרוניקה. מה הכיוון?",
    },
    "הנדסה תעשייתית": {
        "career_interests": ["תפעול", "ניהול פרויקטים"],
        "reply_he": "מתאים לתפעול וניהול פרויקטים. מה הכיוון?",
    },
    "ניהול עסקים": {
        "career_interests": ["ניהול", "תפעול", "אדמיניסטרציה", "שיווק"],
        "reply_he": "מתאים לכיווני ניהול, תפעול או אדמיניסטרציה. יש לך ניסיון בתחום?",
    },
    "ניהול": {
        "career_interests": ["ניהול", "תפעול"],
        "reply_he": "מתאים לתפקידי ניהול ותפעול. יש לך ניסיון?",
    },
    "פסיכולוגיה": {
        "career_interests": ["פסיכולוגיה", "עבודה סוציאלית", "משאבי אנוש", "חינוך"],
        "reply_he": "מתאים לייעוץ, עבודה סוציאלית, HR או חינוך. מה מעניין אותך?",
    },
    "עבודה סוציאלית": {
        "career_interests": ["עבודה סוציאלית", "פסיכולוגיה", "חינוך"],
        "reply_he": "מתאים לעבודה סוציאלית, ייעוץ ושיקום. באיזה אזור לחפש?",
    },
    "משפטים": {
        "career_interests": ["משפטים", "ייעוץ משפטי"],
        "reply_he": "מתאים לעריכת דין, ייעוץ משפטי ופרלגל. מה הכיוון?",
    },
    "תקשורת": {
        "career_interests": ["שיווק", "תוכן", "יחסי ציבור"],
        "reply_he": "מתאים לשיווק, תוכן, יחסי ציבור ומדיה. מה מעניין אותך?",
    },
    "סיעוד": {
        "career_interests": ["בריאות", "סיעוד"],
        "reply_he": "מתאים לתפקידי סיעוד ובריאות. באיזה אזור לחפש?",
    },
}

# Role phrases that signal teaching/education even without explicit "מורה"
TEACHING_SIGNALS = [
    "מורה", "teacher", "teaching", "הוראה", "מחנך", "educator", "tutor",
    "מתמטיקה", "פיזיקה", "ביולוגיה", "כימיה", "היסטוריה", "אנגלית כשפה",
    "mathematics", "physics", "biology", "chemistry",
]


def _extract_role_phrases(text):
    """Extract free-text role descriptions after role-signaling phrases."""
    patterns = [
        r"(?:רוצ[הי]|רצ[הי]|מעוניינ[תי]?) (?:להיות|לעבוד כ[ּ]?|לעסוק ב)\s*([^\.,\n]{3,50})",
        r"(?:want to be|want to become|interested in being|i want to be)\s+([^\.,\n]{3,50})",
        r"(?:אני מחפש[תי]?|looking for|מחפש[תי]?) (?:תפקיד של|עבודה כ|a job as|work as|position as)\s*([^\.,\n]{3,50})",
        r"(?:מעניין אותי|interested in|רוצה לעבוד כ)\s+([^\.,\n]{3,50})",
    ]
    phrases = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            phrase = m.group(1).strip().strip("'\".,")
            if 3 < len(phrase) < 60:
                phrases.append(phrase)
    return phrases


def extract_career_interests(text):
    """Extract career interests. Returns list of interest tags + free-text roles."""
    # Guard: if message is purely about avoidance, skip
    if re.search(
        r"(?:^|\s)(?:לא רוצ[הי]|don.?t want|avoid|לא מעוניינ|not interested|אין לי עניין)(?:\s|$)",
        text, re.IGNORECASE
    ) and not re.search(
        r"(?:רוצ[הי]|want|מעניין|interested)\s+(?!לא)", text, re.IGNORECASE
    ):
        return []

    tl = text.lower()
    found = []

    # 1. Match against interest_re capture groups (explicit "I want X" phrases)
    interest_re = re.findall(
        r"(?:רוצ[הי]|מחפש[תי]?|interested in|want a?n?\s+|looking for|prefer|מעניין אותי|אני מחפש)"
        r"\s+([^\.\n,]{3,60})",
        text, re.IGNORECASE
    )
    for chunk in interest_re:
        cl = chunk.lower()
        for cat, kws in INTEREST_KEYWORDS.items():
            if any(kw.lower() in cl for kw in kws):
                if cat not in found:
                    found.append(cat)

    # 2. Broad keyword scan
    for cat, kws in INTEREST_KEYWORDS.items():
        if any(kw.lower() in tl for kw in kws) and cat not in found:
            found.append(cat)

    # 3. Special: detect teaching role even without explicit interest phrase
    if any(kw.lower() in tl for kw in TEACHING_SIGNALS):
        if "חינוך" not in found:
            found.append("חינוך")

    # 4. Extract free-text role phrases (stored directly so matching engine can use them)
    role_phrases = _extract_role_phrases(text)
    for phrase in role_phrases:
        pl = phrase.lower()
        # Avoid duplicating already-mapped categories
        if not any(pl in cat.lower() or cat.lower() in pl for cat in found):
            found.append(phrase)

    return found[:6]


# ---------------------------------------------------------------------------
# Career direction change detection
# ---------------------------------------------------------------------------

CAREER_CHANGE_PATTERNS = [
    r"\bבעצם\b",
    r"משנ[הי] כיוון",
    r"לא דאטה",
    r"לא sql",
    r"לא פיתוח",
    r"לא מכירות",
    r"(?:אני )?רוצ[הי] להיות",
    r"(?:אני )?מעדיפ[הי]? להיות",
    r"(?:אני )?מחפש[תי]? עכשיו",
    r"שינית[יי]? דעה|שינוי כיוון",
    r"\bforget that\b",
    r"\bactually\b",
    r"\binstead\b",
    r"\bi want to be\b",
    r"\bi changed my mind\b",
    r"\bnot data\b",
    r"\bnot sql\b",
    r"\bnot (a )?developer\b",
    r"different (field|career|direction|role)",
    r"כיוון אחר|תחום אחר",
    r"לא בתחום ה",
    r"במקום (דאטה|פיתוח|sql|מכירות)",
    r"העדפה חדשה|כוון אחר",
]


def detect_career_direction_change(message: str, current_profile: dict) -> bool:
    """
    Returns True if the user is clearly pivoting to a different career direction.
    Also returns True if they explicitly name a new role that contradicts existing interests.
    """
    tl = message.lower()
    for pat in CAREER_CHANGE_PATTERNS:
        if re.search(pat, tl, re.IGNORECASE):
            return True

    # Check if user mentions a category that is completely different from existing interests
    current_interests = current_profile.get("career_interests", [])
    if not current_interests:
        return False

    new_interests = extract_career_interests(message)
    if not new_interests:
        return False

    # If ALL new interests are different from ALL current interests, it's a direction change
    current_lower = set(ci.lower() for ci in current_interests)
    new_lower = set(ni.lower() for ni in new_interests)
    overlap = current_lower & new_lower
    # No overlap → direction change; small overlap with "גם" → not a change
    has_also = bool(re.search(r"\bגם\b|\balso\b|\band\b", tl))
    if not overlap and not has_also and new_interests:
        return True

    return False


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def extract_constraints(text):
    result = {"avoid": [], "must_have": []}
    tl = text.lower()
    avoid_subjects = {
        "מכירות": ["sales","מכירות","selling"],
        "משמרות": ["shifts","משמרות","night shift"],
        "נסיעות ארוכות": ["long commute","נסיעות ארוכות"],
        "עבודה פיזית": ["physical work","פיזי","warehouse"],
    }
    has_avoid = bool(re.search(
        r"לא רוצ[הי]|don.?t want|avoid|לא מעוניינ|not interested",
        tl, re.IGNORECASE
    ))
    if has_avoid:
        for label, keywords in avoid_subjects.items():
            if any(kw in tl for kw in keywords):
                if label not in result["avoid"]:
                    result["avoid"].append(label)
    if re.search(r"חייב|must have|required|דרוש", tl):
        if re.search(r"remote|מרחוק", tl):
            result["must_have"].append("מרחוק")
        if re.search(r"hybrid|היברידי", tl):
            result["must_have"].append("היברידי")
    return result


# ---------------------------------------------------------------------------
# Main profile extraction and merge
# ---------------------------------------------------------------------------

def extract_profile_updates(message, current_profile):
    """Extract all profile updates from a message.
    Handles formal fields, education→career inference, domain skill words,
    student detection, and soft/semantic signals."""
    updates = {}
    lang = detect_language(message)
    updates["conversation"] = {"language": lang}

    edu = extract_education(message)
    if edu:
        updates["education"] = edu

    exp = extract_experience(message)
    if exp:
        updates["experience"] = exp

    skills = extract_skills(message)
    if skills:
        updates["skills"] = skills

    # ── Student detection ─────────────────────────────────────────────────────
    _is_student = bool(re.search(
        r"\bסטודנט[ית]?\b|\bלומד[ת]\b|\bstudent\b|\bstudying\b|\bשנה [א-ד]\b",
        message, re.IGNORECASE
    ))
    if _is_student:
        exp_upd = updates.setdefault("experience", {})
        if not exp_upd.get("seniority") and not current_profile.get("experience", {}).get("seniority"):
            exp_upd["seniority"] = "סטודנט/ית"
        if exp_upd.get("years") is None and current_profile.get("experience", {}).get("years") is None:
            exp_upd["years"] = 0

    # Detect career direction change BEFORE extracting interests
    direction_changed = detect_career_direction_change(message, current_profile)

    interests = extract_career_interests(message)
    if interests:
        updates["career_interests"] = interests
        if direction_changed:
            updates["career_direction_changed"] = True

    # ── Education → career direction inference ────────────────────────────────
    # Guard: only infer career direction from education field when the user is
    # actually talking about their own study background (has degree or is a student).
    # A field appearing alone (e.g. "מתמטיקה" in "מורה למתמטיקה") should NOT
    # trigger career-direction inference — the field is the teaching subject, not
    # the user's degree.
    edu_has_study_context = bool(
        (edu or {}).get("degree") or (edu or {}).get("status") or _is_student
    )
    # When using the current profile's stored field, context is already established
    _stored_edu_field = current_profile.get("education", {}).get("field")
    edu_field = (edu or {}).get("field") if edu_has_study_context else None
    if edu_field is None and _stored_edu_field:
        edu_field = _stored_edu_field  # carry-forward from previous turn (safe)

    if edu_field and edu_field in EDUCATION_CAREER_MAP and edu_has_study_context:
        mapping = EDUCATION_CAREER_MAP[edu_field]
        existing = current_profile.get("career_interests", [])
        cur_ci = updates.get("career_interests", list(existing))
        new_from_edu = [i for i in mapping["career_interests"] if i not in cur_ci]
        if new_from_edu:
            updates["career_interests"] = cur_ci + new_from_edu
        # Only emit the smart reply hint when education was freshly mentioned
        if edu and edu_has_study_context and not direction_changed:
            updates["_edu_reply_hint"] = mapping["reply_he"]

    # ── Profession/role phrases → career interests (PRIORITY over DOMAIN_SKILL_MAP) ─
    # Catches specific job titles and role descriptions:
    # "מנהלת משרד", "רכזת גיוס", "עורך דין", "business administration" etc.
    tl_msg = message.lower()
    _prof_matched = False
    for pm_entry in PROFESSION_MAP:
        if any(re.search(pat, tl_msg, re.IGNORECASE) for pat in pm_entry["patterns"]):
            existing_ci = current_profile.get("career_interests", [])
            cur_ci = updates.get("career_interests", list(existing_ci))
            new_interests = [i for i in pm_entry["career_interests"] if i not in cur_ci]
            if new_interests:
                updates["career_interests"] = cur_ci + new_interests
            updates["_domain_answered"] = True
            hint = pm_entry.get("reply_he", "")
            if hint:
                updates["_domain_reply_hint"] = hint
            _prof_matched = True
            break  # Most specific match wins

    # ── Generic domain/skill words → career interests ─────────────────────────
    # Catches words like "תכנות", "עיצוב", "דאטה", "SQL" the user says informally.
    # Only scanned when PROFESSION_MAP had no match.
    if not _prof_matched:
        for dm_entry in DOMAIN_SKILL_MAP:
            if any(re.search(pat, tl_msg, re.IGNORECASE) for pat in dm_entry["patterns"]):
                existing_ci = current_profile.get("career_interests", [])
                cur_ci = updates.get("career_interests", list(existing_ci))
                new_interests = [i for i in dm_entry["career_interests"] if i not in cur_ci]
                if new_interests:
                    updates["career_interests"] = cur_ci + new_interests
                for s in dm_entry.get("skills", []):
                    existing_sk = current_profile.get("skills", []) + updates.get("skills", [])
                    if s not in existing_sk:
                        updates.setdefault("skills", list(current_profile.get("skills", [])))
                        updates["skills"].append(s)
                updates["_domain_answered"] = True
                # Carry skill-level domain inference reply (e.g. "SQL מתאים לדאטה, BI.")
                hint = dm_entry.get("reply_he", "")
                if hint and not updates.get("_domain_reply_hint"):
                    updates["_domain_reply_hint"] = hint
                # No break — scan all entries so multi-domain messages (e.g. "SQL QA") get all interests

    # ── Open-to-all detection ─────────────────────────────────────────────────
    # Must run BEFORE DOMAIN_SKILL_MAP so "הכל" doesn't pick up a domain keyword.
    if is_open_to_all(message):
        updates["open_to_all"] = True
        # Don't add career_interests — they stay empty so the agent asks a broad Q

    salary = extract_salary(message)
    if salary:
        updates["salary_expectation"] = salary

    # ── Work preferences (type + mode) ────────────────────────────────────────
    work_prefs = extract_work_preferences(message)
    if work_prefs:
        existing_wp = current_profile.get("work_preferences", {})
        merged_wp = {**existing_wp, **work_prefs}
        updates["work_preferences"] = merged_wp

    # ── Country preference ────────────────────────────────────────────────────
    # Must run before location so we know whether to capture Israeli area.
    country_pref = extract_country_preference(message)
    if country_pref:
        updates["country_preference"] = country_pref

    # ── Location / area (Israeli) ─────────────────────────────────────────────
    # Only extract an Israeli area when:
    #   (a) user already has country=Israel, OR
    #   (b) an Israeli area keyword is detected and no country yet (→ infer Israel)
    # Do NOT set location_area for US or Global searches.
    loc = extract_location(message)
    if loc:
        current_country = current_profile.get("country_preference", "") or country_pref or ""
        # Detect whether a concrete Israeli area was found (not just "מרחוק")
        has_israel_area = "primary" in loc and loc["primary"] != "מרחוק"

        # If no country set yet but Israeli area detected → infer Israel
        if has_israel_area and not current_country:
            updates.setdefault("country_preference", "Israel")
            current_country = "Israel"

        # Only store area when relevant to Israel
        area_relevant = (current_country in ("Israel", ""))
        loc_upd = {}
        if area_relevant:
            if "primary" in loc:
                loc_upd["primary"] = loc["primary"]
            if "fallbacks" in loc:
                loc_upd["fallbacks"] = loc["fallbacks"]
        if "remote_allowed" in loc:
            loc_upd["remote_allowed"] = loc["remote_allowed"]
        ws_upd = {}
        if "preferred_environment" in loc:
            ws_upd["preferred_environment"] = loc["preferred_environment"]
        if loc_upd:
            updates["location_preference"] = loc_upd
        if ws_upd:
            updates["work_style"] = ws_upd

    constraints = extract_constraints(message)
    if constraints["avoid"] or constraints["must_have"]:
        updates["constraints"] = constraints

    # --- Soft / semantic signal extraction ---
    soft = interpret_free_text_signal(message, current_profile)
    if soft:
        updates["_soft"] = soft  # passed through to agent_logic

    return updates


def merge_profile_updates(current, updates):
    """
    Merge updates into current profile.
    - If career_direction_changed=True, REPLACE career_interests instead of appending.
    - profile_signals are merged list-by-list (append, dedupe).
    - _soft, _edu_reply_hint, _domain_answered are consumed here and passed via conversation.
    """
    profile = copy.deepcopy(current)
    direction_changed = updates.pop("career_direction_changed", False)
    soft = updates.pop("_soft", {})  # consumed by agent_logic
    edu_reply_hint = updates.pop("_edu_reply_hint", "")
    domain_answered = updates.pop("_domain_answered", False)
    domain_reply_hint = updates.pop("_domain_reply_hint", "")  # skill-level ack

    def merge_list(base_list, new_list):
        return base_list + [x for x in new_list if x not in base_list]

    def merge_dict(base, upd):
        for k, v in upd.items():
            if k == "career_interests" and direction_changed:
                base[k] = v
            elif k == "profile_signals" and isinstance(v, dict):
                # Deep merge profile_signals lists
                ps = base.setdefault("profile_signals", {})
                for sig_type, sig_vals in v.items():
                    ps[sig_type] = merge_list(ps.get(sig_type, []), sig_vals)
            elif isinstance(v, dict) and isinstance(base.get(k), dict):
                merge_dict(base[k], v)
            elif isinstance(v, list) and isinstance(base.get(k), list):
                base[k] = merge_list(base[k], v)
            else:
                if v is not None and v != "" and v != []:
                    base[k] = v

    merge_dict(profile, updates)

    # Merge profile_signals from soft signals
    if soft.get("profile_signals"):
        ps = profile.setdefault("profile_signals", {})
        for sig_type, sig_vals in soft["profile_signals"].items():
            ps[sig_type] = merge_list(ps.get(sig_type, []), sig_vals)

    # Merge avoidance from soft signals
    if soft.get("add_constraints_avoid"):
        avoid = profile.setdefault("constraints", {}).setdefault("avoid", [])
        for a in soft["add_constraints_avoid"]:
            if a not in avoid:
                avoid.append(a)

    # Store direction change flag for agent_logic
    if direction_changed:
        profile.setdefault("conversation", {})["career_direction_changed"] = True
    else:
        profile.setdefault("conversation", {}).pop("career_direction_changed", None)

    # Pass meta signals through conversation for agent_logic to read
    if soft:
        profile.setdefault("conversation", {})["_last_soft"] = soft
    if edu_reply_hint:
        profile.setdefault("conversation", {})["_edu_reply_hint"] = edu_reply_hint
    if domain_answered:
        profile.setdefault("conversation", {})["_domain_answered"] = True
    if domain_reply_hint:
        profile.setdefault("conversation", {})["_domain_reply_hint"] = domain_reply_hint

    return profile


def build_profile_text(profile):
    """Build a text representation of the profile for TF-IDF matching.
    Career interests are repeated 3× for stronger signal.
    Confirmed soft signals (interests) also included."""
    parts = []

    # Career interests: repeat 3× for stronger signal
    interests = profile.get("career_interests", [])
    for _ in range(3):
        parts.extend(interests)

    # Skills
    parts.extend(profile.get("skills", []))

    edu = profile.get("education", {})
    if edu.get("field"):
        parts.append(edu["field"])
    if edu.get("degree"):
        parts.append(edu["degree"])

    exp = profile.get("experience", {})
    if exp.get("seniority"):
        parts.append(exp["seniority"])
    if exp.get("previous_roles"):
        parts.extend(exp["previous_roles"])

    ws = profile.get("work_style", {})
    if ws.get("preferred_environment"):
        parts.append(ws["preferred_environment"])

    # Include soft signals (interests + hobbies) with lower weight (1×)
    ps = profile.get("profile_signals", {})
    parts.extend(ps.get("interests", []))
    parts.extend(ps.get("hobbies", []))

    return " ".join(filter(None, parts))


# ---------------------------------------------------------------------------
# Soft / semantic signal interpretation
# ---------------------------------------------------------------------------

# Each entry: patterns (any match triggers), signals (profile_signals dict),
# career_directions (possible job directions), reply_hint (key for agent_logic),
# reply_he (Hebrew summary for agent reply).
SOFT_SIGNAL_MAP = [
    {
        "patterns": [r"לצייר|ציור|אוהב[תי]? לצייר|drawing\b|artwork|אמנות|מצייר[תי]?"],
        "signals": {"hobbies": ["ציור"], "interests": ["יצירתיות", "עבודה ויזואלית"],
                    "personality_traits": ["יצירתי/ת"]},
        "career_directions": ["עיצוב", "UX/UI", "שיווק יצירתי", "מוצר"],
        "reply_hint": "creative_visual",
        "reply_he": "עדכנתי עניין יצירתי: ציור.",
    },
    {
        "patterns": [r"צילום|לצלם|photography|photographer|מצלמ[תי]?"],
        "signals": {"hobbies": ["צילום"], "interests": ["יצירתיות", "עבודה ויזואלית"],
                    "personality_traits": ["יצירתי/ת"]},
        "career_directions": ["שיווק יצירתי", "מוצר", "UX/UI"],
        "reply_hint": "creative_visual",
        "reply_he": "עדכנתי עניין ויזואלי: צילום.",
    },
    {
        "patterns": [r"לכתוב|כתיבה|writing|כותב[תי]?\b|בלוג"],
        "signals": {"hobbies": ["כתיבה"], "interests": ["תוכן", "ביטוי"],
                    "personality_traits": ["יצירתי/ת", "תקשורתי/ת"]},
        "career_directions": ["שיווק", "תוכן", "מוצר"],
        "reply_hint": "creative_writing",
        "reply_he": "עדכנתי: כתיבה.",
    },
    {
        "patterns": [r"מוזיקה|מנגן[תי]?|נגינה|לשיר|שירה|music\b|musician"],
        "signals": {"hobbies": ["מוזיקה"], "interests": ["יצירתיות"],
                    "personality_traits": ["יצירתי/ת"]},
        "career_directions": ["שיווק יצירתי", "מוצר"],
        "reply_hint": "creative_music",
        "reply_he": "עדכנתי: מוזיקה / נגינה.",
    },
    {
        "patterns": [r"מספרים|חשבון\b|לחשב|אוהב[תי]?\s+מספרים|numbers\b|math\b|calcul"],
        "signals": {"interests": ["עבודה עם מספרים", "ניתוח"],
                    "personality_traits": ["אנליטי/ת"]},
        "career_directions": ["דאטה", "כספים", "BI", "ניתוח מערכות"],
        "reply_hint": "analytical",
        "reply_he": "עדכנתי: עניין בעבודה עם מספרים.",
    },
    {
        "patterns": [r"לעזור לאנשים|לעזור לאחרים|helping people|עבודה עם אנשים|אוהב[תי]?\s+אנשים|עוזר[תי]? לאנשים"],
        "signals": {"interests": ["עבודה עם אנשים", "עזרה לאחרים"],
                    "personality_traits": ["שירותי/ת", "סבלני/ת"]},
        "career_directions": ["משאבי אנוש", "חינוך", "הדרכה"],
        "reply_hint": "people_helper",
        "reply_he": "עדכנתי: עניין בעבודה עם אנשים.",
    },
    {
        "patterns": [r"להסביר|ללמד\b|הוראה|teaching\b|explaining|מלמד[תי]?|מסביר[תי]?|מדריכ[תי]?"],
        "signals": {"interests": ["הדרכה", "הוראה"],
                    "personality_traits": ["תקשורתי/ת", "סבלני/ת"]},
        "career_directions": ["חינוך", "הדרכה"],
        "reply_hint": "teaching",
        "reply_he": "עדכנתי: עניין בהוראה והסברה.",
    },
    {
        "patterns": [r"\bסדר\b|ארגון\b|organized|לארגן|תהליכים\b|processes\b|structured"],
        "signals": {"interests": ["ארגון", "תהליכים"],
                    "personality_traits": ["מסודר/ת"]},
        "career_directions": ["תפעול", "ניהול פרויקטים", "ניתוח מערכות"],
        "reply_hint": "organized",
        "reply_he": "עדכנתי: נטייה לסדר וארגון.",
    },
    {
        "patterns": [r"טכנולוגיה|מחשבים\b|technology\b|tech\b|גאדג'טים|gadgets"],
        "signals": {"interests": ["טכנולוגיה", "חדשנות"],
                    "personality_traits": ["אנליטי/ת"]},
        "career_directions": ["פיתוח תוכנה", "דאטה", "ניתוח מערכות", "מוצר"],
        "reply_hint": "tech",
        "reply_he": "עדכנתי: עניין בטכנולוגיה.",
    },
    {
        "patterns": [r"ספורט\b|sport\b|להתאמן|כושר\b|fitness\b|אתלטי"],
        "signals": {"hobbies": ["ספורט"],
                    "personality_traits": ["אנרגטי/ת", "ממושמע/ת"]},
        "career_directions": [],
        "reply_hint": "hobby_sport",
        "reply_he": "עדכנתי: ספורט כתחביב.",
    },
    {
        "patterns": [r"בישול|לבשל|cooking\b|cook\b|אוכל"],
        "signals": {"hobbies": ["בישול"],
                    "personality_traits": ["יצירתי/ת", "מסודר/ת"]},
        "career_directions": [],
        "reply_hint": "hobby_cooking",
        "reply_he": "עדכנתי: בישול כתחביב.",
    },
    {
        "patterns": [r"עבודה עצמאית|לעבוד לבד|independent work|solo\b|עצמאי[ת]?"],
        "signals": {"work_preferences": ["עבודה עצמאית"],
                    "personality_traits": ["עצמאי/ת"]},
        "career_directions": [],
        "reply_hint": "independent",
        "reply_he": "עדכנתי: העדפה לעבודה עצמאית.",
    },
    {
        "patterns": [r"עבודת צוות|לעבוד עם אנשים|team\b|בצוות|collaborate"],
        "signals": {"work_preferences": ["עבודה בצוות"],
                    "personality_traits": ["חברתי/ת", "שיתופי/ת"]},
        "career_directions": [],
        "reply_hint": "team",
        "reply_he": "עדכנתי: העדפה לעבודה בצוות.",
    },
    {
        "patterns": [r"יציבות|stable job|ביטחון תעסוקתי|secure job"],
        "signals": {"career_values": ["יציבות", "ביטחון תעסוקתי"]},
        "career_directions": [],
        "reply_hint": "stability",
        "reply_he": "עדכנתי: ערך — יציבות.",
    },
    {
        "patterns": [r"התפתחות|growth\b|ללמוד|להתפתח|קידום|learning\b"],
        "signals": {"career_values": ["התפתחות", "למידה"]},
        "career_directions": [],
        "reply_hint": "growth",
        "reply_he": "עדכנתי: ערך — התפתחות.",
    },
    {
        "patterns": [r"איזון|work.life|שעות גמישות|flexible hours"],
        "signals": {"career_values": ["איזון בית-עבודה", "גמישות"]},
        "career_directions": [],
        "reply_hint": "balance",
        "reply_he": "עדכנתי: ערך — איזון בית-עבודה.",
    },
    {
        "patterns": [r"לא יודע[תי]? מה|אין לי כיוון|מתלבט[תי]?|לא בטוח[ה]? |לא ברור לי|don.?t know what|uncertain\b|confused\b"],
        "signals": {"free_notes": ["זקוק/ה להכוונה קריירה"]},
        "career_directions": [],
        "reply_hint": "uncertainty",
        "reply_he": "מה יותר מושך אותך — אנשים, נתונים, יצירה או ניהול?",
    },
]

# Signals that indicate avoidance (add to constraints, not interests)
SOFT_AVOID_PATTERNS = [
    (r"לא אוהב[תי]?\s+(?:לדבר עם לקוח|שירות לקוח|ממשק לקוח)",
     ["שירות לקוחות", "מכירות"]),
    (r"לא אוהב[תי]?\s+(?:לחץ|pressure\b|stressed)",
     ["עבודה בלחץ"]),
    (r"לא אוהב[תי]?\s+(?:משמרות|shifts\b|night shift)",
     ["משמרות"]),
    (r"don't like (?:customers|clients|pressure|shifts)",
     ["שירות לקוחות", "עבודה בלחץ"]),
]


def interpret_free_text_signal(message: str, current_profile: dict) -> dict:
    """
    Interprets free-text, casual, or indirect user messages.
    Returns dict with profile_signals, possible_career_directions, reply_hint, reply_he.
    Returns {} if no soft signals found.
    """
    tl = message.lower()
    result = {
        "profile_signals": {},
        "possible_career_directions": [],
        "reply_hint": None,
        "reply_he": None,
        "add_constraints_avoid": [],
    }
    matched_any = False

    for entry in SOFT_SIGNAL_MAP:
        if any(re.search(pat, tl, re.IGNORECASE) for pat in entry["patterns"]):
            for sig_type, values in entry.get("signals", {}).items():
                bucket = result["profile_signals"].setdefault(sig_type, [])
                for v in values:
                    if v not in bucket:
                        bucket.append(v)
            for d in entry.get("career_directions", []):
                if d not in result["possible_career_directions"]:
                    result["possible_career_directions"].append(d)
            if not result["reply_hint"]:
                result["reply_hint"] = entry.get("reply_hint")
            if not result["reply_he"]:
                result["reply_he"] = entry.get("reply_he")
            matched_any = True

    # Avoidance signals
    for pat, avoids in SOFT_AVOID_PATTERNS:
        if re.search(pat, tl, re.IGNORECASE):
            for a in avoids:
                if a not in result["add_constraints_avoid"]:
                    result["add_constraints_avoid"].append(a)
            matched_any = True

    return result if matched_any else {}
