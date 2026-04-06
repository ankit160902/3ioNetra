"""Tests for Pydantic LLM response models and JSON extraction."""
from models.llm_schemas import (
    IntentAnalysis, IntentEnum, UrgencyEnum,
    QueryRewrite, GroundingResult,
    extract_json,
)


# ---------------------------------------------------------------------------
# IntentAnalysis model
# ---------------------------------------------------------------------------

class TestIntentAnalysis:
    def test_valid_full_response(self):
        data = {
            "intent": "SEEKING_GUIDANCE",
            "emotion": "anxiety",
            "life_domain": "career",
            "entities": {"deity": "hanuman"},
            "urgency": "high",
            "summary": "Stressed about work",
            "needs_direct_answer": True,
            "recommend_products": False,
            "product_search_keywords": ["mala"],
            "product_rejection": False,
            "query_variants": ["work stress help"],
        }
        result = IntentAnalysis(**data)
        assert result.intent == IntentEnum.SEEKING_GUIDANCE
        assert result.emotion == "anxiety"
        assert result.urgency == UrgencyEnum.HIGH
        assert result.entities["deity"] == "hanuman"

    def test_coerces_lowercase_intent(self):
        result = IntentAnalysis(intent="seeking_guidance")
        assert result.intent == IntentEnum.SEEKING_GUIDANCE

    def test_unknown_intent_defaults_to_other(self):
        result = IntentAnalysis(intent="INVALID_INTENT")
        assert result.intent == IntentEnum.OTHER

    def test_missing_fields_use_defaults(self):
        result = IntentAnalysis()
        assert result.intent == IntentEnum.OTHER
        assert result.emotion == "neutral"
        assert result.life_domain == "unknown"
        assert result.urgency == UrgencyEnum.NORMAL
        assert result.needs_direct_answer is False
        assert result.product_search_keywords == []

    def test_empty_emotion_defaults_to_neutral(self):
        result = IntentAnalysis(emotion="")
        assert result.emotion == "neutral"

    def test_none_emotion_defaults_to_neutral(self):
        result = IntentAnalysis(emotion=None)
        assert result.emotion == "neutral"

    def test_emotion_stripped_and_lowered(self):
        result = IntentAnalysis(emotion="  GRIEF  ")
        assert result.emotion == "grief"

    def test_to_dict_matches_legacy_format(self):
        result = IntentAnalysis(intent="GREETING", emotion="joy")
        d = result.to_dict()
        assert d["intent"] == "GREETING"
        assert d["emotion"] == "joy"
        assert isinstance(d["product_search_keywords"], list)

    def test_urgency_coercion(self):
        assert IntentAnalysis(urgency="CRISIS").urgency == UrgencyEnum.CRISIS
        assert IntentAnalysis(urgency="unknown_value").urgency == UrgencyEnum.NORMAL

    def test_from_gemini_json(self):
        """Simulate parsing a real Gemini JSON response."""
        raw = '{"intent":"EXPRESSING_EMOTION","emotion":"grief","life_domain":"family","entities":{},"urgency":"normal","summary":"lost a relative","needs_direct_answer":false,"recommend_products":false,"product_search_keywords":[],"product_rejection":false,"query_variants":[]}'
        import json
        data = json.loads(raw)
        result = IntentAnalysis(**data)
        assert result.intent == IntentEnum.EXPRESSING_EMOTION
        assert result.emotion == "grief"


# ---------------------------------------------------------------------------
# QueryRewrite model
# ---------------------------------------------------------------------------

class TestQueryRewrite:
    def test_valid(self):
        result = QueryRewrite(rewritten_query="spiritual guidance for anxiety")
        assert result.rewritten_query == "spiritual guidance for anxiety"

    def test_empty_default(self):
        result = QueryRewrite()
        assert result.rewritten_query == ""


# ---------------------------------------------------------------------------
# GroundingResult model
# ---------------------------------------------------------------------------

class TestGroundingResult:
    def test_valid(self):
        result = GroundingResult(grounded=True, confidence=0.95, issues="")
        assert result.grounded is True
        assert result.confidence == 0.95

    def test_clamps_confidence(self):
        assert GroundingResult(confidence=1.5).confidence == 1.0
        assert GroundingResult(confidence=-0.5).confidence == 0.0

    def test_invalid_confidence_defaults(self):
        assert GroundingResult(confidence="not_a_number").confidence == 1.0

    def test_defaults(self):
        result = GroundingResult()
        assert result.grounded is True
        assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# JSON extraction utility
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_clean_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_block(self):
        text = '```json\n{"intent": "GREETING"}\n```'
        result = extract_json(text)
        assert result["intent"] == "GREETING"

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"grounded": true, "confidence": 0.8}\nEnd.'
        result = extract_json(text)
        assert result["grounded"] is True

    def test_json_with_escaped_braces_in_strings(self):
        text = '{"field": "value with \\"quotes\\" inside"}'
        result = extract_json(text)
        assert result is not None
        assert "value with" in result["field"]

    def test_empty_string_returns_none(self):
        assert extract_json("") is None
        assert extract_json("   ") is None

    def test_no_json_returns_none(self):
        assert extract_json("This is just regular text") is None

    def test_nested_json(self):
        text = '{"entities": {"deity": "shiva", "ritual": "puja"}}'
        result = extract_json(text)
        assert result["entities"]["deity"] == "shiva"

    def test_markdown_block_without_json_label(self):
        text = '```\n{"intent": "CLOSURE"}\n```'
        result = extract_json(text)
        assert result["intent"] == "CLOSURE"
