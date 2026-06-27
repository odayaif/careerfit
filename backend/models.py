"""
models.py — Pydantic models for request/response shapes
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------

class Education(BaseModel):
    degree: str = ""
    field: str = ""
    status: str = ""


class Experience(BaseModel):
    years: Optional[float] = None
    previous_roles: List[str] = Field(default_factory=list)
    seniority: str = ""


class SalaryExpectation(BaseModel):
    min: Optional[float] = None
    preferred: Optional[float] = None
    flexible: bool = True


class LocationPreference(BaseModel):
    primary: str = ""
    fallbacks: List[str] = Field(default_factory=list)
    remote_allowed: bool = True
    max_commute_minutes: Optional[int] = None


class WorkStyle(BaseModel):
    personality: List[str] = Field(default_factory=list)
    preferred_environment: str = ""
    communication_style: str = "קצר וממוקד"


class Constraints(BaseModel):
    avoid: List[str] = Field(default_factory=list)
    must_have: List[str] = Field(default_factory=list)


class ConversationMeta(BaseModel):
    language: str = "Hebrew"
    last_question: str = ""
    last_intent: str = ""
    answer_length: str = "short"
    question_history: List[str] = Field(default_factory=list)
    pending_career_directions: List[str] = Field(default_factory=list)
    pending_context: str = ""


class ProfileSignals(BaseModel):
    """Soft profile signals extracted from free-text, casual, or indirect messages."""
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    hobbies: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    personality_traits: List[str] = Field(default_factory=list)
    work_preferences: List[str] = Field(default_factory=list)
    career_values: List[str] = Field(default_factory=list)
    free_notes: List[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    education: Education = Field(default_factory=Education)
    experience: Experience = Field(default_factory=Experience)
    skills: List[str] = Field(default_factory=list)
    career_interests: List[str] = Field(default_factory=list)
    profile_signals: ProfileSignals = Field(default_factory=ProfileSignals)
    salary_expectation: SalaryExpectation = Field(default_factory=SalaryExpectation)
    location_preference: LocationPreference = Field(default_factory=LocationPreference)
    work_style: WorkStyle = Field(default_factory=WorkStyle)
    constraints: Constraints = Field(default_factory=Constraints)
    conversation: ConversationMeta = Field(default_factory=ConversationMeta)


def empty_profile() -> dict:
    return UserProfile().model_dump()


def profile_completeness(profile: dict) -> int:
    """Calculate profile completeness 0–100."""
    score = 0
    edu = profile.get("education", {})
    if edu.get("degree") or edu.get("field"):
        score += 15
    exp = profile.get("experience", {})
    if exp.get("years") is not None or exp.get("previous_roles"):
        score += 15
    if profile.get("skills"):
        score += 20
    if profile.get("career_interests"):
        score += 15
    sal = profile.get("salary_expectation", {})
    if sal.get("min") or sal.get("preferred") or not sal.get("flexible", True):
        score += 10
    loc = profile.get("location_preference", {})
    if loc.get("primary"):
        score += 15
    ws = profile.get("work_style", {})
    if ws.get("preferred_environment"):
        score += 5
    con = profile.get("constraints", {})
    if con.get("avoid") or con.get("must_have"):
        score += 5
    return min(score, 100)


# ---------------------------------------------------------------------------
# API Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    profile: Optional[Dict[str, Any]] = None


class JobResult(BaseModel):
    job_id: str
    title: str
    company_name: str
    location: str
    location_area: str
    job_category: str
    work_type: str
    experience_level: str
    salary_display: str
    match_score: float
    similarity_score: float
    match_reasons: List[str]
    warnings: List[str]
    missing_skills: List[str]
    anomaly_flags: List[str]
    application_url: Optional[str] = None
    job_posting_url: Optional[str] = None


class SearchMetadata(BaseModel):
    primary_location: str = ""
    used_location: str = ""
    expanded: bool = False
    reason: str = ""
    total_searched: int = 0
    total_returned: int = 0


class ChatResponse(BaseModel):
    reply: str
    profile: Dict[str, Any]
    jobs: List[Dict[str, Any]] = Field(default_factory=list)
    intent: str = ""
    search_metadata: Dict[str, Any] = Field(default_factory=dict)
    insights: Dict[str, Any] = Field(default_factory=dict)
    profile_completeness: int = 0
    profile_updated: bool = False
    changed_fields: List[str] = Field(default_factory=list)
    should_clear_jobs: bool = False
    # Dataset debug fields — proof the DB was actually searched
    dataset_search_ran: bool = False
    candidates_scanned: int = 0
    results_count: int = 0


class ProfileUpdateRequest(BaseModel):
    profile: Dict[str, Any]


class JobSearchRequest(BaseModel):
    profile: Dict[str, Any]
    limit: int = 10
    location_override: Optional[str] = None
