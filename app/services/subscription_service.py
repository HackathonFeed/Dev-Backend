"""Subscription & AI-points service."""
import base64
import hashlib
import hmac
import time
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
    build_billing_success_url,
    build_payment_page_url,
    get_plan_catalogue,
)

PLAN_RANK: dict[SubscriptionPlan, int] = {
    SubscriptionPlan.HACKER: 0,
    SubscriptionPlan.BUILDER: 1,
    SubscriptionPlan.CHAMPION: 2,
}


class SubscriptionService:
    # ── Read helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def list_plans() -> list[PlanInfo]:
        return get_plan_catalogue()

    @staticmethod
    def get_payment_page(plan: SubscriptionPlan, email: str, user_id: str) -> PaymentPageResponse:
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

        settings = get_settings()
        success_url = build_billing_success_url(settings.frontend_url, plan)

        return PaymentPageResponse(
            plan=plan,
            plan_name=plan_info.name,
            price_inr=plan_info.price_inr,
            payment_page_url=build_payment_page_url(
                plan_info.payment_page_url,
                email,
                user_id,
                plan.value,
            ),
            checkout_note=(
                "Pay on Razorpay using the same email as your HackathonFeed account. "
                "Your plan upgrades automatically after payment."
            ),
            success_redirect_url=success_url,
        )

    @staticmethod
    def plan_from_amount_paise(amount_paise: int) -> SubscriptionPlan | None:
        """Map captured payment amount (paise) to a subscription plan."""
        matches = [
            plan_info.key
            for plan_info in PLAN_CATALOGUE
            if plan_info.price_inr > 0 and plan_info.price_inr * 100 == amount_paise
        ]
        if len(matches) == 1:
            return matches[0]
        return matches[0] if matches else None

    @staticmethod
    def _resolve_plan_from_payment(payment: dict[str, Any]) -> SubscriptionPlan | None:
        """Prefer plan in Razorpay notes (needed when test prices collide at ₹1)."""
        notes = payment.get("notes") or {}
        if isinstance(notes, dict):
            raw = notes.get("plan") or notes.get("subscription_plan")
            if raw:
                try:
                    return SubscriptionPlan(str(raw).lower())
                except ValueError:
                    logger.warning(f"Unknown plan in Razorpay notes: {raw!r}")

        amount_paise = payment.get("amount")
        if amount_paise is None:
            return None
        return SubscriptionService.plan_from_amount_paise(int(amount_paise))

    @staticmethod
    def _extract_payment_email(payment: dict[str, Any]) -> str:
        notes = payment.get("notes") or {}
        note_email = None
        if isinstance(notes, dict):
            note_email = notes.get("email") or notes.get("customer_email")
        raw = payment.get("email") or note_email or ""
        return str(raw).strip().lower()

    @staticmethod
    def _extract_payment_user_id(payment: dict[str, Any]) -> str | None:
        notes = payment.get("notes") or {}
        if not isinstance(notes, dict):
            return None
        raw = notes.get("user_id") or notes.get("hackathonfeed_user_id")
        if not raw:
            return None
        return str(raw).strip()

    @staticmethod
    async def _fetch_razorpay_payment(payment_id: str) -> dict[str, Any] | None:
        auth = SubscriptionService._razorpay_auth_header()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.razorpay.com/v1/payments/{payment_id}",
                headers={"Authorization": auth},
            )
        if resp.status_code != 200:
            logger.warning(
                f"Razorpay payment fetch failed for {payment_id}: "
                f"{resp.status_code} {resp.text[:200]}"
            )
            return None
        return resp.json()

    @staticmethod
    async def _resolve_user_for_payment(
        payment: dict[str, Any],
        db: AsyncSession,
        *,
        expected_user: User | None = None,
    ) -> User | None:
        repo = get_user_repository(db)

        note_user_id = SubscriptionService._extract_payment_user_id(payment)
        if note_user_id:
            try:
                import uuid

                user = await repo.get_by_id(uuid.UUID(note_user_id))
                if user is not None:
                    return user
            except ValueError:
                logger.warning(f"Invalid user_id in Razorpay notes: {note_user_id!r}")

        email = SubscriptionService._extract_payment_email(payment)
        if email:
            user = await repo.get_by_email(email)
            if user is not None:
                return user

        if expected_user is not None:
            payment_email = SubscriptionService._extract_payment_email(payment)
            if not payment_email:
                logger.info(
                    f"Claiming payment {payment.get('id')} for {expected_user.email} "
                    "(no email on payment; trusted logged-in claim)"
                )
                return expected_user

        return None

    @staticmethod
    def _razorpay_auth_header() -> str:
        settings = get_settings()
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Razorpay API credentials are not configured.",
            )
        secret = settings.razorpay_key_secret.strip().replace(" ", "")
        credentials = base64.b64encode(f"{settings.razorpay_key_id}:{secret}".encode()).decode()
        return f"Basic {credentials}"

    @staticmethod
    def _payment_matches_plan(payment: dict[str, Any], plan: SubscriptionPlan) -> bool:
        notes = payment.get("notes") or {}
        if isinstance(notes, dict):
            note_plan = notes.get("plan") or notes.get("subscription_plan")
            if note_plan:
                return str(note_plan).lower() == plan.value
        resolved = SubscriptionService._resolve_plan_from_payment(payment)
        return resolved == plan

    @staticmethod
    async def _find_recent_captured_payment(
        email: str,
        amount_paise: int,
        *,
        user_id: str | None = None,
        plan: SubscriptionPlan | None = None,
    ) -> dict[str, Any] | None:
        """Look up a recent captured Razorpay payment for email + amount."""
        since = int(time.time()) - 6 * 3600
        auth = SubscriptionService._razorpay_auth_header()

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.razorpay.com/v1/payments",
                params={"from": since, "count": 100},
                headers={"Authorization": auth},
            )

        if resp.status_code != 200:
            logger.warning(f"Razorpay payments list failed: {resp.status_code} {resp.text[:200]}")
            return None

        target_email = email.strip().lower()
        fallback: dict[str, Any] | None = None
        for payment in resp.json().get("items", []):
            if payment.get("status") != "captured":
                continue
            if int(payment.get("amount", 0)) != amount_paise:
                continue
            if plan is not None and not SubscriptionService._payment_matches_plan(payment, plan):
                continue

            note_user_id = SubscriptionService._extract_payment_user_id(payment)
            if user_id and note_user_id == user_id:
                return payment

            payment_email = SubscriptionService._extract_payment_email(payment)
            if payment_email and payment_email == target_email:
                return payment

            if fallback is None and user_id:
                fallback = payment

        return fallback

    @staticmethod
    async def _persist_plan_upgrade(
        user: User,
        plan: SubscriptionPlan,
        db: AsyncSession,
    ) -> User:
        repo = get_user_repository(db)
        return await repo.update_plan(user.id, plan.value, PLAN_POINTS[plan])

    @staticmethod
    async def _notify_plan_upgrade(user: User, plan: SubscriptionPlan) -> None:
        from app.services.email_service import EmailService

        expires_str: str | None = None
        if user.plan_expires_at:
            try:
                raw = user.plan_expires_at
                if isinstance(raw, str):
                    raw = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                expires_str = raw.strftime("%d %B %Y").lstrip("0")
            except Exception:  # noqa: BLE001
                expires_str = str(user.plan_expires_at)

        await EmailService.send_plan_upgrade(user.email, user.name, plan, expires_str)

    @staticmethod
    async def claim_plan_upgrade(
        user: User,
        plan: SubscriptionPlan,
        db: AsyncSession,
        *,
        payment_id: str | None = None,
    ) -> SubscriptionStatusResponse:
        """
        After Payment Page checkout, verify a captured Razorpay payment for this
        user and apply the plan upgrade (fallback when webhook delivery is delayed).
        """
        if PLAN_RANK[user.subscription_plan] >= PLAN_RANK[plan]:
            return SubscriptionService.get_status(user)

        plan_info = next((p for p in PLAN_CATALOGUE if p.key == plan), None)
        if not plan_info or plan_info.price_inr == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan.")

        amount_paise = plan_info.price_inr * 100
        payment: dict[str, Any] | None = None

        if payment_id:
            payment = await SubscriptionService._fetch_razorpay_payment(payment_id.strip())
            if payment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found on Razorpay yet. Wait a few seconds and refresh.",
                )
            if payment.get("status") != "captured":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Payment is not completed yet. Finish checkout on Razorpay first.",
                )
            if int(payment.get("amount", 0)) != amount_paise:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment amount does not match the selected plan.",
                )
            owner = await SubscriptionService._resolve_user_for_payment(
                payment,
                db,
                expected_user=user,
            )
            if owner is None or str(owner.id) != str(user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This payment does not belong to your HackathonFeed account.",
                )
        else:
            try:
                payment = await SubscriptionService._find_recent_captured_payment(
                    user.email,
                    amount_paise,
                    user_id=str(user.id),
                    plan=plan,
                )
            except HTTPException as exc:
                if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                    raise
                payment = None

            if payment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "No matching payment found yet. Pay on Razorpay using the same "
                        f"email as your account ({user.email}), then try again."
                    ),
                )

        saved = await SubscriptionService._persist_plan_upgrade(user, plan, db)
        await SubscriptionService._notify_plan_upgrade(saved, plan)
        logger.info(
            f"Claimed upgrade for {user.email} to {plan} "
            f"(payment {payment.get('id')})"
        )
        return SubscriptionService.get_status(saved)

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
        event = payload.get("event")
        if event != "payment.captured":
            logger.info(f"Ignoring Razorpay webhook event: {event}")
            return

        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id")
        email = SubscriptionService._extract_payment_email(payment)
        amount_paise = payment.get("amount")

        if not payment_id or amount_paise is None:
            logger.warning(
                "Incomplete Razorpay webhook payload: "
                f"payment_id={payment_id!r} email={email!r} amount={amount_paise!r} "
                f"keys={list(payment.keys())}"
            )
            return

        plan = SubscriptionService._resolve_plan_from_payment(payment)
        if plan is None:
            logger.warning(
                f"Unmapped Razorpay payment: amount={amount_paise} paise "
                f"(payment {payment_id}, email {email}, notes {payment.get('notes')!r})"
            )
            return

        repo = get_user_repository(db)
        user = await SubscriptionService._resolve_user_for_payment(payment, db)
        if user is None:
            logger.warning(
                f"No HackathonFeed user for Razorpay payment "
                f"(payment {payment_id}, email {email!r}, notes {payment.get('notes')!r})"
            )
            return

        if PLAN_RANK[user.subscription_plan] >= PLAN_RANK[plan]:
            logger.info(f"User {email} already on {user.subscription_plan}; skipping webhook upgrade")
            return

        saved = await SubscriptionService._persist_plan_upgrade(user, plan, db)
        await SubscriptionService._notify_plan_upgrade(saved, plan)
        logger.info(f"Upgraded {email} to {plan} via webhook (payment {payment_id})")
