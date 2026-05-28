"""Subscription & AI-points service."""
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.constants import AI_MESSAGE_COST, PLAN_POINTS, SubscriptionPlan
from app.models.user_model import User
from app.schemas.subscription_schema import (
    PLAN_CATALOGUE,
    CreateOrderResponse,
    PlanInfo,
    SubscriptionStatusResponse,
)


class SubscriptionService:
    # ── Read helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def list_plans() -> list[PlanInfo]:
        return PLAN_CATALOGUE

    @staticmethod
    def get_status(user: User) -> SubscriptionStatusResponse:
        points = user.ai_points
        is_unlimited = points == -1
        remaining = -1 if is_unlimited else max(points // AI_MESSAGE_COST, 0)
        return SubscriptionStatusResponse(
            plan=user.subscription_plan,
            ai_points=points,
            ai_message_cost=AI_MESSAGE_COST,
            messages_remaining=remaining,
            plan_expires_at=user.plan_expires_at,
        )

    # ── Points guard (call before every AI message) ───────────────────────────

    @staticmethod
    def assert_has_points(user: User, cost: int = AI_MESSAGE_COST) -> None:
        """Raise 402 if the user has no points left (unlimited plans always pass)."""
        if user.ai_points == -1:          # unlimited
            return
        if user.ai_points < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "code": "insufficient_points",
                    "message": (
                        f"You need {cost} points for this action but only have "
                        f"{user.ai_points}. Upgrade your plan to continue."
                    ),
                    "ai_points": user.ai_points,
                    "required": cost,
                },
            )

    @staticmethod
    def deduct_points(user: User) -> int:
        """Deduct one message cost and return the new balance. No-op for unlimited."""
        if user.ai_points == -1:
            return -1
        user.ai_points = max(user.ai_points - AI_MESSAGE_COST, 0)
        return user.ai_points

    # ── Plan upgrade ─────────────────────────────────────────────────────────

    @staticmethod
    def apply_upgrade(user: User, new_plan: SubscriptionPlan) -> User:
        new_points = PLAN_POINTS[new_plan]
        user.subscription_plan = new_plan
        user.ai_points = new_points
        # Set expiry 30 days from now for paid plans
        if new_plan != SubscriptionPlan.HACKER:
            user.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        else:
            user.plan_expires_at = None
        return user

    # ── Razorpay: create order ────────────────────────────────────────────────

    @staticmethod
    async def create_razorpay_order(plan: SubscriptionPlan, user_id: str) -> CreateOrderResponse:
        """Create a Razorpay payment order for the given paid plan."""
        settings = get_settings()
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment gateway is not configured on this server.",
            )

        plan_info = next((p for p in PLAN_CATALOGUE if p.key == plan), None)
        if not plan_info:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan.")
        if plan_info.price_inr == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This plan is free — no payment required.",
            )

        amount_paise = plan_info.price_inr * 100  # Razorpay works in paise
        credentials = base64.b64encode(
            f"{settings.razorpay_key_id}:{settings.razorpay_key_secret}".encode()
        ).decode()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.razorpay.com/v1/orders",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": f"hf_{user_id[:8]}_{plan}",
                    "notes": {"plan": plan, "user_id": user_id},
                },
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Razorpay order creation failed: {resp.text[:200]}",
            )

        order = resp.json()
        return CreateOrderResponse(
            order_id=order["id"],
            amount=amount_paise,
            currency="INR",
            key_id=settings.razorpay_key_id,
            plan=plan,
            plan_name=plan_info.name,
        )

    # ── Razorpay: verify payment signature ────────────────────────────────────

    @staticmethod
    def verify_razorpay_signature(
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> None:
        """Raise 400 if the Razorpay payment signature is invalid."""
        settings = get_settings()
        if not settings.razorpay_key_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment gateway is not configured on this server.",
            )

        msg = f"{order_id}|{payment_id}".encode()
        expected = hmac.new(
            settings.razorpay_key_secret.encode(),
            msg,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed. Please contact support.",
            )
