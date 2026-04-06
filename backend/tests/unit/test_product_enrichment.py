"""Tests for product enrichment Pydantic model."""
from models.product_enrichment import (
    ProductEnrichment, ALLOWED_PRACTICES, ALLOWED_EMOTIONS,
    ALLOWED_LIFE_DOMAINS, ALLOWED_DEITIES, ALLOWED_PRODUCT_TYPES,
)


class TestTagsCleaning:
    def test_lowercases_tags(self):
        e = ProductEnrichment(tags=["Rudraksha", "MALA", "Japa"], benefits=["peace"])
        assert e.tags == ["rudraksha", "mala", "japa"]

    def test_strips_whitespace(self):
        e = ProductEnrichment(tags=["  mala  ", "incense "], benefits=["peace"])
        assert e.tags == ["mala", "incense"]

    def test_caps_at_15(self):
        e = ProductEnrichment(tags=[f"tag{i}" for i in range(20)], benefits=["peace"])
        assert len(e.tags) <= 15

    def test_non_list_defaults(self):
        e = ProductEnrichment(tags="not a list", benefits=["peace"])
        assert e.tags == ["general"]


class TestDeitiesCleaning:
    def test_normalizes_ganesh_variants(self):
        e = ProductEnrichment(tags=["test"], deities=["Ganesha", "Ganapati"], benefits=["peace"])
        assert e.deities == ["ganesh"]

    def test_normalizes_shiva_variants(self):
        e = ProductEnrichment(tags=["test"], deities=["Mahadev", "Shiv"], benefits=["peace"])
        assert "shiva" in e.deities

    def test_filters_invalid_deities(self):
        e = ProductEnrichment(tags=["test"], deities=["shiva", "invalid_deity", "krishna"], benefits=["peace"])
        assert "invalid_deity" not in e.deities
        assert "shiva" in e.deities
        assert "krishna" in e.deities

    def test_empty_deities_ok(self):
        e = ProductEnrichment(tags=["test"], deities=[], benefits=["peace"])
        assert e.deities == []


class TestPracticesCleaning:
    def test_only_allowed_practices(self):
        e = ProductEnrichment(tags=["test"], practices=["japa", "random_practice", "meditation"], benefits=["peace"])
        assert "japa" in e.practices
        assert "meditation" in e.practices
        assert "random_practice" not in e.practices

    def test_all_allowed_practices_valid(self):
        for practice in ALLOWED_PRACTICES:
            e = ProductEnrichment(tags=["test"], practices=[practice], benefits=["peace"])
            assert practice in e.practices


class TestEmotionsCleaning:
    def test_only_allowed_emotions(self):
        e = ProductEnrichment(tags=["test"], emotions=["anxiety", "boredom", "peace"], benefits=["peace"])
        assert "anxiety" in e.emotions
        assert "peace" in e.emotions
        assert "boredom" not in e.emotions

    def test_all_allowed_emotions_valid(self):
        for emotion in ALLOWED_EMOTIONS:
            e = ProductEnrichment(tags=["test"], emotions=[emotion], benefits=["test"])
            assert emotion in e.emotions


class TestLifeDomainsCleaning:
    def test_normalizes_spaces(self):
        e = ProductEnrichment(tags=["test"], life_domains=["self improvement", "self-improvement"], benefits=["peace"])
        assert "self_improvement" in e.life_domains

    def test_deduplicates(self):
        e = ProductEnrichment(tags=["test"], life_domains=["spiritual", "spiritual"], benefits=["peace"])
        assert e.life_domains.count("spiritual") == 1


class TestProductType:
    def test_valid_types(self):
        for pt in ALLOWED_PRODUCT_TYPES:
            e = ProductEnrichment(tags=["test"], product_type=pt, benefits=["peace"])
            assert e.product_type == pt

    def test_invalid_defaults_to_physical(self):
        e = ProductEnrichment(tags=["test"], product_type="unknown", benefits=["peace"])
        assert e.product_type == "physical"


class TestToMongoUpdate:
    def test_returns_all_fields(self):
        e = ProductEnrichment(
            tags=["mala", "rudraksha"],
            deities=["shiva"],
            practices=["japa"],
            emotions=["peace"],
            life_domains=["spiritual"],
            benefits=["concentration"],
            product_type="physical",
            occasion_tags=["daily"],
        )
        update = e.to_mongo_update()
        assert "tags" in update
        assert "deities" in update
        assert "enrichment_version" in update
        assert update["enrichment_version"] == 1
        assert "enriched_at" in update

    def test_simulated_gemini_response(self):
        """Simulate a Gemini enrichment response and validate."""
        gemini_output = {
            "tags": ["rudraksha", "mala", "japa", "108 beads", "5 mukhi", "shiva"],
            "deities": ["Shiva"],
            "practices": ["japa", "meditation", "daily_worship"],
            "emotions": ["anxiety", "stress", "peace", "focus"],
            "life_domains": ["spiritual", "health"],
            "benefits": ["concentration", "protection", "spiritual growth", "calming"],
            "product_type": "physical",
            "occasion_tags": ["daily", "maha_shivratri", "monday"],
        }
        e = ProductEnrichment(**gemini_output)
        assert "shiva" in e.deities
        assert "japa" in e.practices
        assert e.product_type == "physical"
        assert len(e.tags) >= 5

    def test_consultation_product(self):
        """Consultation product with no description."""
        gemini_output = {
            "tags": ["consultation", "astrology", "vedic", "kundli"],
            "deities": [],
            "practices": ["consultation"],
            "emotions": ["confusion", "anxiety", "clarity"],
            "life_domains": ["career", "relationships"],
            "benefits": ["clarity", "guidance", "direction"],
            "product_type": "consultation",
            "occasion_tags": [],
        }
        e = ProductEnrichment(**gemini_output)
        assert e.product_type == "consultation"
        assert e.deities == []
        assert "clarity" in e.emotions
