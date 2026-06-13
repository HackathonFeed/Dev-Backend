"""Subscription & AI-points service."""
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import AI_MESSAGE_COST, PLAN_POINTS, SubscriptionPlan
from app.models.user_model import User
from app.repositories.factory import get_user_repository
from app.schemas.subscription_schema import (
    PLAN_CATALOGUE,
    CreateOrderResponse,
    PaymentPageResponse,
    PlanInfo,
    SubscriptionStatusResponse,
    build_payment_page_url,
    get_plan_catalogue,
)


class SubscriptionService:
    # ── Read helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def list_plans() -> list[PlanInfo]:
        return get_plan_catalogue()

    @staticmethod
    def get_payment_page(plan: SubscriptionPlan, email: str) -> PaymentPageResponse:
        """Return the Razorpay Payment Page URL for a paid plan."""
        if plan == SubscriptionPlan.HACKER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The Hacker plan is free — no payment required.",
            )

        plan_info = next((p for p in get_plan_catalogue() if p.key == plan), None)
        if not plan_info or not plan_info.payment_page_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment page is not configured for this plan.",
            )

        return PaymentPageResponse(
            plan=plan,
            plan_name=plan_info.name,
            price_inr=plan_info.price_inr,
            payment_page_url=build_payment_page_url(plan_info.payment_page_url, email),
            checkout_note=(
                "Pay on Razorpay using the same email as your HackathonFeed account. "
                "Your plan upgrades automatically within a minute after payment."
            ),
        )

    @staticmethod
    def plan_from_amount_paise(amount_paise: int) -> SubscriptionPlan | None:
        """Map captured payment amount (paise) to a subscription plan."""
        for plan_info in PLAN_CATALOGUE:
            if plan_info.price_inr > 0 and plan_info.price_inr * 100 == amount_paise:
                return plan_info.key
        return None

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
        # Strip whitespace — .env files sometimes introduce spaces in app passwords
        key_secret = settings.razorpay_key_secret.strip().replace(" ", "")
        expected = hmac.new(
            key_secret.encode(),
            msg,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed. Please contact support.",
            )

    # ── Razorpay Payment Pages: webhook ───────────────────────────────────────

    @staticmethod
    def verify_razorpay_webhook_signature(body: bytes, signature: str) -> None:
        """Raise 400 if the Razorpay webhook signature is invalid."""
        settings = get_settings()
        secret = (settings.razorpay_webhook_secret or "").strip()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Razorpay webhook secret is not configured.",
            )

        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature.",
            )

    @staticmethod
    async def handle_payment_page_webhook(payload: dict[str, Any], db: AsyncSession) -> None:
        """Upgrade a user when Razorpay sends payment.captured from a Payment Page."""
        from app.services.email_service import EmailService

        event = payload.get("event")
        if event != "payment.captured":
            logger.info(f"Ignoring Razorpay webhook event: {event}")
            return

        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id")
        email = (payment.get("email") or "").strip().lower()
        amount_paise = payment.get("amount")

        if not payment_id or not email or amount_paise is None:
            logger.warning(f"Incomplete Razorpay webhook payload: payment_id={payment_id!r} email={email!r}")
            return

        plan = SubscriptionService.plan_from_amount_paise(int(amount_paise))
        if plan is None:
            logger.warning(f"Unmapped Razorpay payment amount: {amount_paise} paise (payment {payment_id})")
            return

        repo = get_user_repository(db)
        user = await repo.get_by_email(email)
        if user is None:
            logger.warning(f"No HackathonFeed user for Razorpay payment email: {email} (payment {payment_id})")
            return

        updated_user = SubscriptionService.apply_upgrade(user, plan)
        saved = await repo.update(updated_user)
        logger.info(f"Upgraded {email} to {plan} via Payment Page (payment {payment_id})")

        expires_str: str | None = None
        if saved.plan_expires_at:
            try:
                raw = saved.plan_expires_at
                if isinstance(raw, str):
                    raw = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                expires_str = raw.strftime("%d %B %Y").lstrip("0")
            except Exception:  # noqa: BLE001
                expires_str = str(saved.plan_expires_at)

        EmailService.send_plan_upgrade_bg(saved.email, saved.name, plan, expires_str)
