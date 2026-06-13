"""Subscription management endpoints."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.constants import PROJECT_VIEW_COST, SubscriptionPlan
from app.core.database import get_db
from app.repositories.factory import get_user_repository
from app.schemas.response_schema import APIResponse
from app.schemas.subscription_schema import (
    CreateOrderRequest,
    CreateOrderResponse,
    PaymentPageResponse,
    PlanInfo,
    SubscriptionStatusResponse,
    UpgradePlanRequest,
    VerifyPaymentRequest,
    get_plan_catalogue,
)
from app.services.email_service import EmailService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans", response_model=APIResponse[list[PlanInfo]])
async def list_plans():
    """Return all available subscription plans (includes Payment Page URLs when configured)."""
    return APIResponse(success=True, message="Plans fetched", data=get_plan_catalogue())


@router.get("/me", response_model=APIResponse[SubscriptionStatusResponse])
async def my_subscription(
    current_user=Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's current plan and remaining AI points."""
    data = SubscriptionService.get_status(current_user)
    return APIResponse(success=True, message="Subscription status fetched", data=data)


@router.get("/payment-page/{plan}", response_model=APIResponse[PaymentPageResponse])
async def get_payment_page(
    plan: SubscriptionPlan,
    current_user=Depends(get_current_user),
):
    """
    Return the Razorpay Payment Page URL for a paid plan.
    User pays on Razorpay's hosted page; upgrade is applied via webhook.
    """
    data = SubscriptionService.get_payment_page(plan, current_user.email)
    return APIResponse(success=True, message="Payment page URL fetched", data=data)


@router.post("/razorpay-webhook")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Razorpay webhook for Payment Page payments.
    Configure in Dashboard → Account & Settings → Webhooks.
    Subscribe to: payment.captured
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    SubscriptionService.verify_razorpay_webhook_signature(body, signature)

    payload = json.loads(body)
    await SubscriptionService.handle_payment_page_webhook(payload, db)
    return {"status": "ok"}


@router.post("/claim-upgrade", response_model=APIResponse[SubscriptionStatusResponse])
async def claim_upgrade(
    payload: UpgradePlanRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a recent Razorpay payment for the logged-in user and apply the plan upgrade.
    Called by the frontend after Payment Page checkout (fallback if webhook is delayed).
    """
    data = await SubscriptionService.claim_plan_upgrade(current_user, payload.plan, db)
    return APIResponse(
        success=True,
        message=f"Upgraded to {payload.plan} plan.",
        data=data,
    )


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
    [Legacy] Create a Razorpay payment order for embedded Checkout.
    Prefer GET /payment-page/{plan} when using Razorpay Payment Pages.
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
    [Legacy] Verify Razorpay Checkout payment signature and upgrade the user's plan.
    Not used with Payment Pages — upgrades happen via /razorpay-webhook.
    """
    SubscriptionService.verify_razorpay_signature(
        payload.razorpay_order_id,
        payload.razorpay_payment_id,
        payload.razorpay_signature,
    )

    updated_user = SubscriptionService.apply_upgrade(current_user, payload.plan)
    repo = get_user_repository(db)
    saved = await repo.update(updated_user)
    data = SubscriptionService.get_status(saved)

    expires_str: str | None = None
    if saved.plan_expires_at:
        try:
            raw = saved.plan_expires_at
            if isinstance(raw, str):
                raw = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            expires_str = raw.strftime("%d %B %Y").lstrip("0")
        except Exception:  # noqa: BLE001
            expires_str = str(saved.plan_expires_at)

    EmailService.send_plan_upgrade_bg(
        saved.email,
        saved.name,
        payload.plan,
        expires_str,
    )

    return APIResponse(
        success=True,
        message=f"Payment verified. Upgraded to {payload.plan} plan.",
        data=data,
    )
