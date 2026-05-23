from fastapi import APIRouter

from app.schemas.ai_schema import ValidateIdeaRequest, ValidateIdeaResponse
from app.schemas.response_schema import APIResponse
from app.services.ai_validator_service import AIValidatorService

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/validate-idea", response_model=APIResponse[ValidateIdeaResponse])
async def validate_idea(payload: ValidateIdeaRequest):
    service = AIValidatorService()
    data = await service.validate_idea(payload)
    return APIResponse(
        success=True,
        message="Idea validated successfully",
        data=data,
    )
