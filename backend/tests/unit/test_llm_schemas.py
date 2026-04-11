"""Tests for Pydantic LLM response models and JSON extraction."""
from models.llm_schemas import (
    IntentAnalysis, IntentEnum, UrgencyEnum,
    QueryRewrite, GroundingResult,
    extract_json,
    # Dynamic memory system (Apr 2026)
    ExtractedMemory, ExtractionResult,
    MemoryUpdateDecision,
    ReflectionProfilePatch, ReflectionResult,
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


# ---------------------------------------------------------------------------
# Dynamic memory system — Apr 2026
# ---------------------------------------------------------------------------

class TestExtractedMemory:
    def test_valid_minimal(self):
        m = ExtractedMemory(
            text="User is starting a new job next month",
            importance=6,
            sensitivity="personal",
            tone_marker="anticipation",
        )
        assert m.text == "User is starting a new job next month"
        assert m.importance == 6
        assert m.sensitivity == "personal"
        assert m.tone_marker == "anticipation"

    def test_importance_clamped_below_1(self):
        m = ExtractedMemory(text="x", importance=-5, sensitivity="personal")
        assert m.importance == 1

    def test_importance_clamped_above_10(self):
        m = ExtractedMemory(text="x", importance=99, sensitivity="personal")
        assert m.importance == 10

    def test_importance_garbage_defaults_to_5(self):
        m = ExtractedMemory(text="x", importance="nonsense", sensitivity="personal")
        assert m.importance == 5

    def test_invalid_sensitivity_coerced_to_personal(self):
        m = ExtractedMemory(text="x", importance=5, sensitivity="nonsense")
        assert m.sensitivity == "personal"

    def test_tone_marker_defaults_to_neutral(self):
        m = ExtractedMemory(text="x", importance=5, sensitivity="personal")
        assert m.tone_marker == "neutral"

    def test_sensitivity_valid_values_accepted(self):
        for tier in ("trivial", "personal", "sensitive", "crisis"):
            m = ExtractedMemory(text="x", importance=5, sensitivity=tier)
            assert m.sensitivity == tier


class TestExtractionResult:
    def test_empty_facts_is_valid(self):
        r = ExtractionResult(facts=[])
        assert r.facts == []

    def test_default_is_empty(self):
        r = ExtractionResult()
        assert r.facts == []

    def test_multiple_facts(self):
        r = ExtractionResult(facts=[
            {"text": "user is a software engineer", "importance": 5, "sensitivity": "personal"},
            {"text": "user's father passed in February", "importance": 9, "sensitivity": "sensitive"},
        ])
        assert len(r.facts) == 2
        assert r.facts[0].text == "user is a software engineer"
        assert r.facts[1].sensitivity == "sensitive"


class TestMemoryUpdateDecision:
    def test_add_operation(self):
        d = MemoryUpdateDecision(operation="ADD", reason="new fact")
        assert d.operation == "ADD"
        assert d.target_memory_id is None
        assert d.updated_text is None

    def test_update_operation(self):
        d = MemoryUpdateDecision(
            operation="UPDATE",
            target_memory_id="507f1f77bcf86cd799439011",
            updated_text="user is recovering from grief",
            reason="situation evolved",
        )
        assert d.operation == "UPDATE"
        assert d.target_memory_id == "507f1f77bcf86cd799439011"
        assert d.updated_text == "user is recovering from grief"

    def test_delete_operation(self):
        d = MemoryUpdateDecision(
            operation="DELETE",
            target_memory_id="abc123",
            reason="user corrected prior statement",
        )
        assert d.operation == "DELETE"
        assert d.target_memory_id == "abc123"

    def test_noop_operation(self):
        d = MemoryUpdateDecision(operation="NOOP", target_memory_id="xyz", reason="redundant")
        assert d.operation == "NOOP"


class TestReflectionProfilePatch:
    def test_full_patch(self):
        p = ReflectionProfilePatch(
            relational_narrative="You are a software engineer wrestling with career questions.",
            spiritual_themes=["finding purpose"],
            ongoing_concerns=["career uncertainty"],
            tone_preferences=["prefers direct advice"],
            people_mentioned=["Priya (sister)"],
        )
        assert p.relational_narrative.startswith("You are")
        assert len(p.spiritual_themes) == 1
        assert len(p.ongoing_concerns) == 1

    def test_empty_lists_by_default(self):
        p = ReflectionProfilePatch(relational_narrative="")
        assert p.spiritual_themes == []
        assert p.ongoing_concerns == []
        assert p.tone_preferences == []
        assert p.people_mentioned == []


class TestReflectionResult:
    def test_valid(self):
        r = ReflectionResult(
            updated_profile={
                "relational_narrative": "You are ...",
                "spiritual_themes": ["theme1"],
            },
            prune_ids=["abc", "def"],
        )
        assert r.updated_profile.relational_narrative.startswith("You are")
        assert r.updated_profile.spiritual_themes == ["theme1"]
        assert r.prune_ids == ["abc", "def"]

    def test_empty_prune_list(self):
        r = ReflectionResult(
            updated_profile={"relational_narrative": ""},
            prune_ids=[],
        )
        assert r.prune_ids == []
