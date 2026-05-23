import json

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.ai_schema import ValidateIdeaRequest, ValidateIdeaResponse

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SYSTEM_INSTRUCTION = """You are the Neural Forge Chief Strategist, an esteemed global hackathon judge, and elite chief systems architect.
Analyze hackathon submissions with directness and engineering clarity.

Return JSON with:
- feasibilityScore (1-10 integer)
- originalityScore (1-10 integer)
- brutalistDirectness (1-10 integer)
- keyStrengths (exactly 3 strings)
- requiredUpgrades (exactly 3 strings)
- suggestedTeammates (exactly 3 strings)
- verdictSummary (1-2 sentence bold overview)
- critique (detailed markdown review)
- visualThemeProposal (front-end visual motif suggestion)
"""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "feasibilityScore": {"type": "INTEGER"},
        "originalityScore": {"type": "INTEGER"},
        "brutalistDirectness": {"type": "INTEGER"},
        "verdictSummary": {"type": "STRING"},
        "critique": {"type": "STRING"},
        "keyStrengths": {"type": "ARRAY", "items": {"type": "STRING"}},
        "requiredUpgrades": {"type": "ARRAY", "items": {"type": "STRING"}},
        "suggestedTeammates": {"type": "ARRAY", "items": {"type": "STRING"}},
        "visualThemeProposal": {"type": "STRING"},
    },
    "required": [
        "feasibilityScore",
        "originalityScore",
        "brutalistDirectness",
        "verdictSummary",
        "critique",
        "keyStrengths",
        "requiredUpgrades",
        "suggestedTeammates",
        "visualThemeProposal",
    ],
}


class AIValidatorService:
    async def validate_idea(self, payload: ValidateIdeaRequest) -> ValidateIdeaResponse:
        settings = get_settings()
        api_key = settings.gemini_api_key
        if not api_key or api_key in {"MY_GEMINI_API_KEY", "your-gemini-api-key"}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI validation is not configured. Set GEMINI_API_KEY in backend .env and restart the API server.",
            )

        prompt = f"""Evaluate the following Hackathon project pitch:
- Project Title: "{payload.project_title}"
- Target Hackathon: "{payload.hackathon_name or 'Any global hackathon'}"
- Technologies: "{payload.tech_stack or 'Not specified'}"
- Concept Pitch: "{payload.concept_pitch}"
"""

        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    GEMINI_URL,
                    params={"key": api_key},
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI provider request failed: {exc}",
            ) from exc

        if response.status_code != 200:
            detail = response.text[:300]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI provider error ({response.status_code}): {detail}",
            )

        payload_json = response.json()
        try:
            text = payload_json["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI provider returned an invalid response",
            ) from exc

        return ValidateIdeaResponse.model_validate(data)
