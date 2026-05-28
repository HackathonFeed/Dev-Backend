"""Unit tests for subscription plan constants and the static plan catalogue."""
import pytest

from app.core.constants import (
    AI_MESSAGE_COST,
    PLAN_POINTS,
    PROJECT_VIEW_COST,
    SubscriptionPlan,
)
from app.schemas.subscription_schema import PLAN_CATALOGUE, PlanInfo


# ── PLAN_POINTS ───────────────────────────────────────────────────────────────

class TestPlanPoints:
    def test_hacker_gets_50_points(self):
        assert PLAN_POINTS[SubscriptionPlan.HACKER] == 50

    def test_builder_gets_200_points(self):
        assert PLAN_POINTS[SubscriptionPlan.BUILDER] == 200

    def test_champion_gets_unlimited(self):
        assert PLAN_POINTS[SubscriptionPlan.CHAMPION] == -1

    def test_all_plans_present(self):
        for plan in SubscriptionPlan:
            assert plan in PLAN_POINTS, f"{plan} missing from PLAN_POINTS"

    def test_sentinel_value_for_unlimited_is_negative_one(self):
        """Callers treat -1 as unlimited — verify it's exactly -1."""
        assert PLAN_POINTS[SubscriptionPlan.CHAMPION] == -1


# ── Cost constants ────────────────────────────────────────────────────────────

class TestCostConstants:
    def test_ai_message_cost_is_positive(self):
        assert AI_MESSAGE_COST > 0

    def test_ai_message_cost_value(self):
        assert AI_MESSAGE_COST == 5

    def test_project_view_cost_is_positive(self):
        assert PROJECT_VIEW_COST > 0

    def test_project_view_cost_value(self):
        assert PROJECT_VIEW_COST == 10

    def test_hacker_can_afford_at_least_one_message(self):
        assert PLAN_POINTS[SubscriptionPlan.HACKER] >= AI_MESSAGE_COST

    def test_builder_can_afford_multiple_messages(self):
        builder_msgs = PLAN_POINTS[SubscriptionPlan.BUILDER] // AI_MESSAGE_COST
        assert builder_msgs >= 10


# ── PLAN_CATALOGUE ────────────────────────────────────────────────────────────

class TestPlanCatalogue:
    def test_catalogue_has_three_plans(self):
        assert len(PLAN_CATALOGUE) == 3

    def test_all_subscription_plans_in_catalogue(self):
        keys = {p.key for p in PLAN_CATALOGUE}
        assert keys == {SubscriptionPlan.HACKER, SubscriptionPlan.BUILDER, SubscriptionPlan.CHAMPION}

    def test_hacker_plan_is_free(self):
        hacker = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.HACKER)
        assert hacker.price_inr == 0
        assert hacker.price_usd == 0.0

    def test_builder_plan_price_inr(self):
        builder = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.BUILDER)
        assert builder.price_inr == 199

    def test_champion_plan_price_inr(self):
        champion = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.CHAMPION)
        assert champion.price_inr == 499

    def test_hacker_points_match_constant(self):
        hacker = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.HACKER)
        assert hacker.points == PLAN_POINTS[SubscriptionPlan.HACKER]

    def test_builder_points_match_constant(self):
        builder = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.BUILDER)
        assert builder.points == PLAN_POINTS[SubscriptionPlan.BUILDER]

    def test_champion_points_match_constant(self):
        champion = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.CHAMPION)
        assert champion.points == PLAN_POINTS[SubscriptionPlan.CHAMPION]

    def test_each_plan_has_features(self):
        for plan in PLAN_CATALOGUE:
            assert len(plan.features) > 0, f"{plan.key} has no features"

    def test_each_plan_has_name(self):
        for plan in PLAN_CATALOGUE:
            assert plan.name, f"{plan.key} has no name"

    def test_plan_info_is_pydantic_model(self):
        for plan in PLAN_CATALOGUE:
            assert isinstance(plan, PlanInfo)

    def test_champion_is_lifetime(self):
        champion = next(p for p in PLAN_CATALOGUE if p.key == SubscriptionPlan.CHAMPION)
        assert "lifetime" in champion.messages_per_cycle.lower() or champion.points == -1
