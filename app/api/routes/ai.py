import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.repositories.factory import get_user_repository
from app.schemas.ai_schema import (
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionListItem,
    ChatSessionUpdate,
    SessionChatRequest,
    SessionChatResponse,
    ValidateIdeaRequest,
    ValidateIdeaResponse,
)
from app.schemas.response_schema import APIResponse
from app.services.ai_chat_session_service import AIChatSessionService
from app.services.ai_validator_service import AIValidatorService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/ai", tags=["AI"])


# ── Idea Validator ────────────────────────────────────────────────────────────

@router.post("/validate-idea", response_model=APIResponse[ValidateIdeaResponse])
async def validate_idea(payload: ValidateIdeaRequest):
    service = AIValidatorService()
    data = await service.validate_idea(payload)
    return APIResponse(success=True, message="Idea validated successfully", data=data)


# ── Legacy stateless chat (kept for backward compat) ─────────────────────────

@router.post("/chat", response_model=APIResponse[ChatResponse])
async def copilot_chat(
    payload: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stateless multi-turn chat — costs 5 AI points per message."""
    SubscriptionService.assert_has_points(current_user)
    service = AIValidatorService()
    data = await service.chat(payload)
    # Deduct points after a successful reply
    repo = get_user_repository(db)
    await repo.deduct_ai_points(current_user.id, 5)
    return APIResponse(success=True, message="Reply generated", data=data)


# ── Chat Sessions ─────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=APIResponse[ChatSessionDetail])
async def create_session(
    payload: ChatSessionCreate,
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """Create a new chat session (persisted to Supabase)."""
    svc = AIChatSessionService()
    data = await svc.create_session(current_user.id, payload)
    return APIResponse(success=True, message="Session created", data=data)


@router.get("/sessions", response_model=APIResponse[list[ChatSessionListItem]])
async def list_sessions(
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """List all chat sessions for the current user, newest first."""
    svc = AIChatSessionService()
    data = await svc.list_sessions(current_user.id)
    return APIResponse(success=True, message="Sessions fetched", data=data)


@router.get("/sessions/{session_id}", response_model=APIResponse[ChatSessionDetail])
async def get_session(
    session_id: uuid.UUID,
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """Get a session with its full message history."""
    svc = AIChatSessionService()
    data = await svc.get_session(str(session_id), current_user.id)
    return APIResponse(success=True, message="Session fetched", data=data)


@router.patch("/sessions/{session_id}", response_model=APIResponse[ChatSessionDetail])
async def update_session(
    session_id: uuid.UUID,
    payload: ChatSessionUpdate,
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """Rename a session or change its hackathon context."""
    svc = AIChatSessionService()
    data = await svc.update_session(str(session_id), current_user.id, payload)
    return APIResponse(success=True, message="Session updated", data=data)


@router.delete("/sessions/{session_id}", response_model=APIResponse[None])
async def delete_session(
    session_id: uuid.UUID,
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """Delete a session and all its messages."""
    svc = AIChatSessionService()
    await svc.delete_session(str(session_id), current_user.id)
    return APIResponse(success=True, message="Session deleted", data=None)


@router.post(
    "/sessions/{session_id}/chat",
    response_model=APIResponse[SessionChatResponse],
)
async def session_chat(
    session_id: uuid.UUID,
    payload: SessionChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message in a session. Costs 5 AI points per message."""
    SubscriptionService.assert_has_points(current_user)
    svc = AIChatSessionService()
    data = await svc.send_message(str(session_id), current_user.id, payload)
    # Deduct points after a successful reply
    repo = get_user_repository(db)
    await repo.deduct_ai_points(current_user.id, 5)
    return APIResponse(success=True, message="Reply generated", data=data)
