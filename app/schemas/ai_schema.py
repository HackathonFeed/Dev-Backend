from pydantic import BaseModel, Field


class ValidateIdeaRequest(BaseModel):
    project_title: str = Field(..., min_length=1, max_length=255, alias="projectTitle")
    hackathon_name: str | None = Field(default=None, alias="hackathonName")
    tech_stack: str | None = Field(default=None, alias="techStack")
    concept_pitch: str = Field(..., min_length=1, alias="conceptPitch")

    model_config = {"populate_by_name": True}


class ValidateIdeaResponse(BaseModel):
    feasibility_score: int = Field(alias="feasibilityScore")
    originality_score: int = Field(alias="originalityScore")
    brutalist_directness: int = Field(alias="brutalistDirectness")
    verdict_summary: str = Field(alias="verdictSummary")
    critique: str
    key_strengths: list[str] = Field(alias="keyStrengths")
    required_upgrades: list[str] = Field(alias="requiredUpgrades")
    suggested_teammates: list[str] = Field(alias="suggestedTeammates")
    visual_theme_proposal: str = Field(alias="visualThemeProposal")

    model_config = {"populate_by_name": True}


# ── Copilot Chat ──────────────────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class HackathonContextForChat(BaseModel):
    id: str | None = None
    title: str
    themes: list[str] = Field(default_factory=list)
    deadline: str | None = None
    prize_pool: str | None = None
    mode: str | None = None
    source_platform: str | None = None
    eligibility: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    messages: list[ChatMessageRequest] = Field(..., min_length=1)
    hackathon_context: HackathonContextForChat | None = None


class ChatResponse(BaseModel):
    reply: str


# ── Chat Session Schemas ──────────────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    hackathon_context: HackathonContextForChat | None = None


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    hackathon_context: HackathonContextForChat | None = None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatSessionDetail(BaseModel):
    id: str
    title: str
    hackathon_context: dict | None = None
    created_at: str
    updated_at: str
    messages: list[ChatMessageOut] = []


class ChatSessionListItem(BaseModel):
    id: str
    title: str
    hackathon_title: str | None = None
    created_at: str
    updated_at: str


class SessionChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)


class ProjectSnippet(BaseModel):
    """Lightweight project card returned inside chat responses."""
    id: str
    title: str
    tagline: str | None = None
    url: str
    thumbnail: str | None = None
    technologies: list[str] = []
    hackathon_name: str | None = None
    likes_count: int | None = None
    views: int | None = None
    team_members_count: int = 0
    is_winner: bool = False
    github_url: str | None = None
    demo_url: str | None = None


class SessionChatResponse(BaseModel):
    reply: str
    session_id: str
    message_id: str
    projects: list[ProjectSnippet] | None = None
