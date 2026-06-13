"""Tests for Razorpay Payment Pages integration."""
import hashlib
import hmac

import pytest
from fastapi import HTTPException

from app.core.constants import SubscriptionPlan
from app.schemas.subscription_schema import build_payment_page_url
from app.services.subscription_service import SubscriptionService


class TestPlanFromAmountPaise:
    def test_builder_amount(self):
        assert SubscriptionService.plan_from_amount_paise(100) == SubscriptionPlan.BUILDER

    def test_champion_amount(self):
        # Same ₹1 test price — amount alone maps to first paid plan (builder)
        assert SubscriptionService.plan_from_amount_paise(100) == SubscriptionPlan.BUILDER


class TestResolvePlanFromPayment:
    def test_notes_plan_wins_over_amount(self):
        payment = {"amount": 100, "notes": {"plan": "champion"}}
        assert SubscriptionService._resolve_plan_from_payment(payment) == SubscriptionPlan.CHAMPION

    def test_unknown_amount_returns_none(self):
        assert SubscriptionService.plan_from_amount_paise(999) is None


class TestBuildPaymentPageUrl:
    def test_appends_prefill_email(self):
        url = build_payment_page_url("https://rzp.io/i/abc123", "user@hackathonfeed.com")
        assert "prefill%5Bemail%5D=user%40hackathonfeed.com" in url
        assert "notes%5Bemail%5D=user%40hackathonfeed.com" in url
        assert url.startswith("https://rzp.io/i/abc123?")

    def test_appends_user_id_note(self):
        url = build_payment_page_url(
            "https://rzp.io/i/abc123",
            "user@hackathonfeed.com",
            "550e8400-e29b-41d4-a716-446655440000",
            "builder",
        )
        assert "notes%5Buser_id%5D=550e8400-e29b-41d4-a716-446655440000" in url
        assert "notes%5Bplan%5D=builder" in url

    def test_preserves_existing_query_string(self):
        url = build_payment_page_url("https://rzp.io/i/abc123?foo=1", "user@test.com")
        assert url.startswith("https://rzp.io/i/abc123?foo=1&")


class TestExtractPaymentEmail:
    def test_top_level_email(self):
        payment = {"email": "User@Example.com", "notes": {}}
        assert SubscriptionService._extract_payment_email(payment) == "user@example.com"

    def test_notes_email_fallback(self):
        payment = {"notes": {"email": "notes@example.com"}}
        assert SubscriptionService._extract_payment_email(payment) == "notes@example.com"


class TestWebhookSignature:
    def test_valid_signature_passes(self, monkeypatch):
        secret = "whsec_test"
        body = b'{"event":"payment.captured"}'
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        class FakeSettings:
            razorpay_webhook_secret = secret

        monkeypatch.setattr(
            "app.services.subscription_service.get_settings",
            lambda: FakeSettings(),
        )
        SubscriptionService.verify_razorpay_webhook_signature(body, signature)

    def test_invalid_signature_raises(self, monkeypatch):
        class FakeSettings:
            razorpay_webhook_secret = "whsec_test"

        monkeypatch.setattr(
            "app.services.subscription_service.get_settings",
            lambda: FakeSettings(),
        )
        with pytest.raises(HTTPException) as exc:
            SubscriptionService.verify_razorpay_webhook_signature(b"{}", "bad-signature")
        assert exc.value.status_code == 400
