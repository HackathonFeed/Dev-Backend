from datetime import datetime

from pydantic import BaseModel

from app.core.constants import AI_MESSAGE_COST, PLAN_POINTS, SubscriptionPlan


class PlanInfo(BaseModel):
    key: SubscriptionPlan
    name: str
    price_usd: float          # 0 = free
    price_inr: int            # 0 = free, else rupees (for Razorpay)
    points: int               # −1 = unlimited
    messages_per_cycle: str   # human-readable
    features: list[str]


class SubscriptionStatusResponse(BaseModel):
    plan: SubscriptionPlan
    ai_points: int            # −1 = unlimited
    ai_message_cost: int
    messages_remaining: int   # −1 = unlimited
    plan_expires_at: datetime | None


class UpgradePlanRequest(BaseModel):
    plan: SubscriptionPlan


# ── Razorpay payment schemas ──────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan: SubscriptionPlan


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int           # in paise (INR × 100)
    currency: str         # "INR"
    key_id: str           # Razorpay publishable key
    plan: SubscriptionPlan
    plan_name: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan: SubscriptionPlan


# ── Static plan catalogue ─────────────────────────────────────────────────────

PLAN_CATALOGUE: list[PlanInfo] = [
    PlanInfo(
        key=SubscriptionPlan.HACKER,
        name="Hacker",
        price_usd=0.0,
        price_inr=0,
        points=PLAN_POINTS[SubscriptionPlan.HACKER],
        messages_per_cycle="10 AI messages total",
        features=[
            "50 AI copilot points",
            "Full hackathon feed access",
            "Application tracker",
            "Basic search & filters",
        ],
    ),
    PlanInfo(
        key=SubscriptionPlan.BUILDER,
        name="Builder",
        price_usd=2.4,
        price_inr=199,
        points=PLAN_POINTS[SubscriptionPlan.BUILDER],
        messages_per_cycle="40 AI messages total",
        features=[
            "200 AI copilot points",
            "Full hackathon feed access",
            "Application tracker",
            "Priority hackathon alerts",
            "AI idea validator",
        ],
    ),
    PlanInfo(
        key=SubscriptionPlan.CHAMPION,
        name="Champion",
        price_usd=5.99,
        price_inr=499,
        points=PLAN_POINTS[SubscriptionPlan.CHAMPION],
        messages_per_cycle="Unlimited AI messages — forever",
        features=[
            "Unlimited AI copilot (lifetime)",
            "Everything in Builder",
            "Early access to new features",
            "Badge on leaderboard",
            "Dedicated support",
        ],
    ),
]
