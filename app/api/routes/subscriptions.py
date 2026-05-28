"""Subscription management endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.constants import PROJECT_VIEW_COST
from app.core.database import get_db
from app.repositories.factory import get_user_repository
from app.schemas.response_schema import APIResponse
from app.schemas.subscription_schema import (
    PLAN_CATALOGUE,
    CreateOrderRequest,
    CreateOrderResponse,
    PlanInfo,
    SubscriptionStatusResponse,
    UpgradePlanRequest,
    VerifyPaymentRequest,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans", response_model=APIResponse[list[PlanInfo]])
async def list_plans():
    """Return all available subscription plans."""
    return APIResponse(success=True, message="Plans fetched", data=PLAN_CATALOGUE)


@router.get("/me", response_model=APIResponse[SubscriptionStatusResponse])
async def my_subscription(
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's current plan and remaining AI points."""
    data = SubscriptionService.get_status(current_user)
    return APIResponse(success=True, message="Subscription status fetched", data=data)


@router.post("/consume-project-view", response_model=APIResponse[SubscriptionStatusResponse])
async def consume_project_view(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Charge points before revealing a project details modal."""
    SubscriptionService.assert_has_points(current_user, PROJECT_VIEW_COST)
    repo = get_user_repository(db)
    updated_user = await repo.deduct_ai_points(current_user.id, PROJECT_VIEW_COST)
    data = SubscriptionService.get_status(updated_user)
    return APIResponse(success=True, message="Project view unlocked", data=data)


@router.post("/create-order", response_model=APIResponse[CreateOrderResponse])
async def create_order(
    payload: CreateOrderRequest,
    current_user=Depends(get_current_user),
):
    """
    Create a Razorpay payment order for a paid plan.
    Returns the order_id and publishable key needed to open Razorpay Checkout on the frontend.
    """
    data = await SubscriptionService.create_razorpay_order(payload.plan, str(current_user.id))
    return APIResponse(success=True, message="Order created", data=data)


@router.post("/verify-payment", response_model=APIResponse[SubscriptionStatusResponse])
async def verify_payment(
    payload: VerifyPaymentRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify Razorpay payment signature (HMAC-SHA256) and upgrade the user's plan.
    Called by the frontend after Razorpay Checkout succeeds.
    """
    # Verify signature — raises 400 if invalid
    SubscriptionService.verify_razorpay_signature(
        payload.razorpay_order_id,
        payload.razorpay_payment_id,
        payload.razorpay_signature,
    )

    # Signature valid → apply upgrade
    updated_user = SubscriptionService.apply_upgrade(current_user, payload.plan)
    repo = get_user_repository(db)
    saved = await repo.update(updated_user)
    data = SubscriptionService.get_status(saved)
    return APIResponse(
        success=True,
        message=f"Payment verified. Upgraded to {payload.plan} plan.",
        data=data,
    )
