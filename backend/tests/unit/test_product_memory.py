"""Tests for RelationalProfile product interaction fields and serialization."""
import pytest
from models.memory_context import RelationalProfile


class TestProductFields:
    def test_default_product_preference_is_neutral(self):
        profile = RelationalProfile()
        assert profile.product_preference == "neutral"

    def test_default_product_shown_count_is_zero(self):
        profile = RelationalProfile()
        assert profile.product_shown_count == 0

    def test_default_product_rejection_count_is_zero(self):
        profile = RelationalProfile()
        assert profile.product_rejection_count == 0

    def test_default_product_purchased_items_is_empty(self):
        profile = RelationalProfile()
        assert profile.product_purchased_items == []


class TestProductContext:
    def test_neutral_with_no_history(self):
        profile = RelationalProfile()
        ctx = profile.to_product_context()
        assert "shown 0 times" in ctx
        assert "preference: neutral" in ctx

    def test_opted_out_user(self):
        profile = RelationalProfile()
        profile.product_preference = "opted_out"
        profile.product_last_rejected_at = "2026-04-10"
        ctx = profile.to_product_context()
        assert "opted out" in ctx
        assert "Do not recommend" in ctx

    def test_user_with_history(self):
        profile = RelationalProfile()
        profile.product_shown_count = 4
        profile.product_last_shown_at = "2026-04-10"
        profile.product_rejection_count = 1
        ctx = profile.to_product_context()
        assert "shown 4 times" in ctx
        assert "2026-04-10" in ctx
        assert "rejected 1 time" in ctx

    def test_receptive_user(self):
        profile = RelationalProfile()
        profile.product_preference = "receptive"
        profile.product_shown_count = 3
        ctx = profile.to_product_context()
        assert "preference: receptive" in ctx


class TestProductFieldSerialization:
    def test_roundtrip_preserves_product_fields(self):
        profile = RelationalProfile()
        profile.product_preference = "opted_out"
        profile.product_shown_count = 5
        profile.product_last_shown_at = "2026-04-10"
        profile.product_rejection_count = 2
        profile.product_last_rejected_at = "2026-04-08"
        profile.product_purchased_items = ["Rudraksha Mala"]

        data = profile.to_dict()
        restored = RelationalProfile.from_dict(data)

        assert restored.product_preference == "opted_out"
        assert restored.product_shown_count == 5
        assert restored.product_last_shown_at == "2026-04-10"
        assert restored.product_rejection_count == 2
        assert restored.product_last_rejected_at == "2026-04-08"
        assert restored.product_purchased_items == ["Rudraksha Mala"]
