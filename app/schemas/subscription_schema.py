from datetime import datetime
from urllib.parse import urlencode

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
    payment_page_url: str | None = None


class SubscriptionStatusResponse(BaseModel):
    plan: SubscriptionPlan
    ai_points: int            # −1 = unlimited
    ai_message_cost: int
    messages_remaining: int   # −1 = unlimited
    plan_expires_at: datetime | None


class UpgradePlanRequest(BaseModel):
    plan: SubscriptionPlan
    payment_id: str | None = None


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


class PaymentPageResponse(BaseModel):
    plan: SubscriptionPlan
    plan_name: str
    price_inr: int
    payment_page_url: str
    checkout_note: str
    success_redirect_url: str | None = None


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


def get_plan_catalogue() -> list[PlanInfo]:
    """Return plans with Razorpay Payment Page URLs when configured."""
    from app.core.config import get_settings

    settings = get_settings()
    page_urls = {
        SubscriptionPlan.BUILDER: settings.razorpay_payment_page_builder_url,
        SubscriptionPlan.CHAMPION: settings.razorpay_payment_page_champion_url,
    }
    enriched: list[PlanInfo] = []
    for plan in PLAN_CATALOGUE:
        page_url = page_urls.get(plan.key)
        enriched.append(plan.model_copy(update={"payment_page_url": page_url}) if page_url else plan)
    return enriched


def build_payment_page_url(
    base_url: str,
    email: str | None = None,
    user_id: str | None = None,
) -> str:
    """Append Razorpay prefill + notes so webhook/claim can match the payer."""
    query: dict[str, str] = {}
    if email:
        query["prefill[email]"] = email
        query["prefill[contact]"] = ""
        query["notes[email]"] = email.lower()
    if user_id:
        query["notes[user_id]"] = user_id

    if not query:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(query)}"


def build_billing_success_url(frontend_base: str | None, plan: SubscriptionPlan) -> str | None:
    base = (frontend_base or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/billing/success?plan={plan.value}"
