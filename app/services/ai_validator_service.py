"""
AI Validator + Copilot service.
Uses AWS Bedrock Amazon Nova for all LLM calls.

Auth priority:
  1. BEDROCK_API_KEY  → REST API with x-api-key header  (recommended)
  2. AWS_ACCESS_KEY_ID / SECRET  → boto3 SigV4  (IAM fallback)
"""
import asyncio
import json
import re

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.ai_schema import (
    ChatRequest,
    ChatResponse,
    HackathonContextForChat,
    ValidateIdeaRequest,
    ValidateIdeaResponse,
)

# ── Constants ─────────────────────────────────────────────────────────────────

VALIDATOR_SYSTEM_PROMPT = """You are the Neural Forge Chief Strategist, an esteemed global hackathon judge, and elite chief systems architect.
Analyze hackathon submissions with directness and engineering clarity.

You MUST respond with ONLY a valid JSON object — no markdown, no code fences, no explanation text.

The JSON must have exactly these keys:
- feasibilityScore: integer 1-10
- originalityScore: integer 1-10
- brutalistDirectness: integer 1-10
- keyStrengths: array of exactly 3 strings
- requiredUpgrades: array of exactly 3 strings
- suggestedTeammates: array of exactly 3 strings
- verdictSummary: string (1-2 sentence bold overview)
- critique: string (detailed markdown review)
- visualThemeProposal: string (front-end visual motif suggestion)

Respond with the raw JSON only. Do not wrap it in ```json or any other formatting."""


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences if the model wrapped JSON anyway."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ── Bedrock call helpers ──────────────────────────────────────────────────────

_EMBED_MODEL = "amazon.titan-embed-text-v2:0"


async def get_bedrock_embedding(text: str) -> list[float] | None:
    """
    Generate a 1024-dim semantic embedding via Amazon Titan Embed Text v2.
    Returns None on failure so callers can fall back gracefully.
    """
    import json as _json

    settings = get_settings()
    region = settings.aws_region
    # Titan has an ~8k token limit — truncate input to be safe
    payload = {"inputText": text[:6000], "dimensions": 1024, "normalize": True}

    if settings.bedrock_api_key:
        url = (
            f"https://bedrock-runtime.{region}.amazonaws.com"
            f"/model/{_EMBED_MODEL}/invoke"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.bedrock_api_key}"},
                )
            if resp.status_code == 200:
                return resp.json().get("embedding")
        except Exception:
            pass
        return None

    # ── boto3 IAM fallback ────────────────────────────────────────────────────
    def _call():
        import boto3

        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.invoke_model(
            modelId=_EMBED_MODEL,
            body=_json.dumps(payload),
            contentType="application/json",
        )
        return _json.loads(response["body"].read()).get("embedding")

    try:
        return await asyncio.to_thread(_call)
    except Exception:
        return None


def _get_bedrock_client():
    """Create a boto3 bedrock-runtime client (IAM auth fallback)."""
    import boto3

    settings = get_settings()
    kwargs: dict = {
        "service_name": "bedrock-runtime",
        "region_name": settings.aws_region,
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(**kwargs)


async def call_bedrock_raw(body: dict) -> dict:
    """
    Low-level Bedrock call — returns the full raw response dict.
    Needed for tool-use loops where the caller inspects stopReason.
    """
    settings = get_settings()
    model_id = settings.bedrock_model_id
    region = settings.aws_region

    if settings.bedrock_api_key:
        url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/converse"
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers={"Authorization": f"Bearer {settings.bedrock_api_key}"},
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Bedrock request failed: {exc}") from exc
        if response.status_code != 200:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"Bedrock error ({response.status_code}): {response.text[:300]}",
            )
        return response.json()

    # ── boto3 IAM fallback ────────────────────────────────────────────────────
    def _call():
        client = _get_bedrock_client()
        kwargs: dict = {
            "modelId": model_id,
            "messages": body["messages"],
            "inferenceConfig": body.get("inferenceConfig", {}),
        }
        if "system" in body:
            kwargs["system"] = body["system"]
        if "toolConfig" in body:
            kwargs["toolConfig"] = body["toolConfig"]
        return client.converse(**kwargs)

    try:
        return await asyncio.to_thread(_call)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"AWS Bedrock request failed: {exc}") from exc


async def call_bedrock_converse(
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.75,
) -> str:
    """Simple converse — no tools, returns reply text. Uses call_bedrock_raw internally."""
    body = {
        "system": [{"text": system}],
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    result = await call_bedrock_raw(body)
    try:
        return result["output"]["message"]["content"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Bedrock returned an unexpected response structure.",
        ) from exc


# ── Copilot system prompt (shared with session service) ───────────────────────

def build_copilot_system_prompt(
    ctx: "HackathonContextForChat | None",
    tech_summary: str = "",
    top_projects_preview: str = "",
    hackathon_projects_preview: str = "",
) -> str:
    base = (
        "You are a Hackathon Build Copilot — an elite AI assistant that helps developers "
        "plan, build, and win hackathons.\n"
        "You combine the strategic thinking of a hackathon judge, the technical depth of a "
        "senior engineer, and the execution speed of a startup founder.\n\n"
        "Rules:\n"
        "- Be direct, specific, and actionable. Never give generic advice.\n"
        "- Every suggestion must be concrete and immediately buildable.\n"
        "- When asked for ideas, give structured suggestions with: concept, tech fit, "
        "  MVP scope, winning angle.\n"
        "- When asked for a build plan, give time-boxed phases with specific tasks.\n"
        "- Format responses in clear markdown with headers, bullet points, and code "
        "  blocks where useful.\n"
        "- Keep responses focused — no filler, no disclaimers.\n"
        "- CRITICAL: Whenever a user asks to see projects, examples, what others built, "
        "  asks for inspiration, mentions the project gallery or database, or asks 'what "
        "  projects do you have' — you MUST call the search_projects tool immediately. "
        "  NEVER make up, hallucinate, or invent fictional projects.\n"
        "- CRITICAL: When search_projects returns results, your text response must be "
        "  MAXIMUM 2 sentences — one brief intro line like 'Here are 5 blockchain projects "
        "  from HackFeed:' and optionally one sentence of insight. NOTHING ELSE. "
        "  Do NOT list project names, descriptions, tech stacks, GitHub links, or winning "
        "  angles in your text — the project cards in the UI already show all of that.\n"
        "- CRITICAL: NEVER mix fictional/invented project concepts with real DB results. "
        "  If you suggested an idea earlier (like 'AI-Powered Moderator Tool'), that is NOT "
        "  a HackFeed project. Only list projects that literally came from search_projects.\n"
        "- Do NOT tell the user to 'scroll sideways', 'click VIEW', or give any UI "
        "  navigation instructions — the user can see the cards themselves.\n"
    )

    db_guide = ""
    if tech_summary or top_projects_preview or hackathon_projects_preview:
        hack_section = (
            f"\nProjects relevant to this hackathon's themes (use these as inspiration):\n"
            f"{hackathon_projects_preview}\n"
            if hackathon_projects_preview else ""
        )
        projects_section = (
            f"\nTop projects in HackFeed overall (most liked):\n{top_projects_preview}\n"
            if top_projects_preview else ""
        )
        tech_section = (
            f"\nAvailable technology filters (use EXACT names):\n  {tech_summary}\n"
            if tech_summary else ""
        )

        # Build the search guidance — different advice when hackathon context exists
        if hackathon_projects_preview and ctx:
            themes_str = ", ".join(ctx.themes[:3]) if ctx.themes else ctx.title
            hack_search_hint = (
                f"  • For projects related to THIS hackathon → call search_projects with "
                f'search="{themes_str}" to find thematically relevant results.\n'
            )
        else:
            hack_search_hint = ""

        db_guide = (
            "\n\nHACKFEED DATABASE CONTEXT:\n"
            + hack_section
            + projects_section
            + tech_section
            + "\nHow to call search_projects:\n"
            + hack_search_hint
            + "  • Any general project request / inspiration → call with ONLY limit=5 "
            "(no search, no technology). Always returns results.\n"
            "  • Tech-specific (user mentions React, Python, Solidity, AI, etc.) → "
            "use technology= with an EXACT name from the list above.\n"
            "  • Winners only → set winner_only=true.\n"
            "  • NEVER use search= for vague queries — it matches titles/taglines only.\n"
        )

    if not ctx:
        return (
            base
            + db_guide
            + "\nNo specific hackathon has been selected. Give general hackathon strategy "
            "advice but remind the user to select a hackathon for personalized guidance."
        )

    themes_str = ", ".join(ctx.themes) if ctx.themes else "Not specified"
    tags_str = ", ".join(ctx.tags) if ctx.tags else "None"
    eligibility_str = ", ".join(ctx.eligibility) if ctx.eligibility else "Open to all"
    deadline_str = ctx.deadline or "Not specified"
    prize_str = ctx.prize_pool or "Not specified"
    mode_str = (ctx.mode or "unknown").upper()
    platform_str = ctx.source_platform or "Unknown"

    hackathon_block = f"""
ACTIVE HACKATHON CONTEXT
========================
Title        : {ctx.title}
Platform     : {platform_str}
Mode         : {mode_str}
Deadline     : {deadline_str}
Prize Pool   : {prize_str}
Themes       : {themes_str}
Tags         : {tags_str}
Eligibility  : {eligibility_str}
========================

Use this context in every response. All advice must be specific to this hackathon's theme,
timeline, and requirements. When the user asks for ideas, ensure they fit the themes above.
When giving a build plan, factor in the deadline.
"""
    return base + hackathon_block + db_guide


# ── AIValidatorService ────────────────────────────────────────────────────────

class AIValidatorService:

    def _check_configured(self) -> None:
        settings = get_settings()
        has_api_key = bool(
            settings.bedrock_api_key
            and settings.bedrock_api_key not in {"your-bedrock-api-key", "YOUR_BEDROCK_API_KEY"}
        )
        has_iam = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
        if not has_api_key and not has_iam:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "AWS Bedrock is not configured. "
                    "Set BEDROCK_API_KEY (or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) "
                    "in the backend .env and restart."
                ),
            )

    # ── Idea Validator ────────────────────────────────────────────────────────

    async def validate_idea(self, payload: ValidateIdeaRequest) -> ValidateIdeaResponse:
        self._check_configured()

        user_prompt = (
            f"Evaluate the following Hackathon project pitch:\n"
            f'- Project Title: "{payload.project_title}"\n'
            f'- Target Hackathon: "{payload.hackathon_name or "Any global hackathon"}"\n'
            f'- Technologies: "{payload.tech_stack or "Not specified"}"\n'
            f'- Concept Pitch: "{payload.concept_pitch}"\n\n'
            "Return the evaluation as a raw JSON object with no markdown wrapping."
        )

        raw_text = await call_bedrock_converse(
            system=VALIDATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            max_tokens=2048,
            temperature=0.5,
        )

        cleaned = _strip_json_fences(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI model returned non-JSON output: {cleaned[:200]}",
            ) from exc

        return ValidateIdeaResponse.model_validate(data)

    # ── Legacy stateless chat ─────────────────────────────────────────────────

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        self._check_configured()

        system_prompt = build_copilot_system_prompt(payload.hackathon_context)
        messages = [
            {"role": msg.role, "content": [{"text": msg.content}]}
            for msg in payload.messages
        ]

        reply_text = await call_bedrock_converse(
            system=system_prompt,
            messages=messages,
            max_tokens=2048,
            temperature=0.75,
        )
        return ChatResponse(reply=reply_text)
