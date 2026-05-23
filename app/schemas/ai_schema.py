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
