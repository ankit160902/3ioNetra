"""Tests for MemoryUpdater extracted from CompanionEngine."""
import importlib.util
from pathlib import Path

from models.session import SessionState, SignalType
from models.memory_context import ConversationMemory, UserStory

# Load directly to avoid services/__init__.py chain
_path = str(Path(__file__).resolve().parents[2] / "services" / "memory_updater.py")
_spec = importlib.util.spec_from_file_location("memory_updater", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
update_memory = _mod.update_memory


def _make_session() -> SessionState:
    s = SessionState()
    s.memory = ConversationMemory(story=UserStory())
    return s


class TestEmotionDetection:
    def test_detects_sadness(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I feel so sad and lonely today")
        assert s.memory.story.emotional_state == "Sadness & Grief"
        assert SignalType.EMOTION in s.signals_collected

    def test_detects_anxiety(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I'm really anxious about my exam deadline")
        assert s.memory.story.emotional_state == "Anxiety & Fear"

    def test_detects_anger(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I am so angry and frustrated with my boss")
        assert s.memory.story.emotional_state == "Anger & Frustration"

    def test_detects_confusion(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I feel lost and confused about my purpose in life, existential void")
        assert s.memory.story.emotional_state == "Confusion & Doubt"

    def test_detects_gratitude(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I'm feeling so grateful and blessed today, morning meditation was beautiful")
        assert s.memory.story.emotional_state == "Gratitude & Peace"


class TestDomainDetection:
    def test_detects_career(self):
        s = _make_session()
        update_memory(s.memory, s, "My boss is giving me too many deadlines at work")
        assert s.memory.story.life_area == "Career & Finance"

    def test_detects_family(self):
        s = _make_session()
        update_memory(s.memory, s, "My parents and kids are having a tough time at home")
        assert s.memory.story.life_area == "Family"

    def test_detects_spiritual(self):
        s = _make_session()
        update_memory(s.memory, s, "I want to understand the Bhagavad Gita and dharma more deeply")
        assert s.memory.story.life_area == "Spiritual Growth"

    def test_fallback_general_life(self):
        s = _make_session()
        update_memory(s.memory, s, "I moved to a new city and don't know anyone here")
        assert s.memory.story.life_area is not None


class TestSpecialIntents:
    def test_verse_request(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "Can you give me a verse from the Gita about peace?")
        assert "Verse Request" in topics
        assert s.memory.readiness_for_wisdom >= 0.6

    def test_product_inquiry(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I want to buy a rudraksha mala")
        assert "Product Inquiry" in topics

    def test_routine_request(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "Can you give me a daily morning yoga and meditation routine?")
        assert "Routine Request" in topics

    def test_puja_guidance(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "How do I setup a home temple and perform puja?")
        assert "Puja Guidance" in topics

    def test_diet_plan(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "Give me an ayurvedic diet plan for pitta dosha meals")
        assert "Diet Plan" in topics

    def test_temple_interest(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I want to visit Kashi temple for darshan")
        assert s.memory.story.temple_interest is not None


class TestReadinessBoosters:
    def test_long_message_boosts_readiness(self):
        s = _make_session()
        long_msg = "I have been struggling with a lot of anxiety at work " * 5
        update_memory(s.memory, s, long_msg)
        assert s.memory.readiness_for_wisdom > 0.0

    def test_wellness_question_boosts_readiness(self):
        s = _make_session()
        update_memory(s.memory, s, "how do i practice mindfulness meditation technique?")
        assert s.memory.readiness_for_wisdom >= 0.3

    def test_primary_concern_set_on_first_message(self):
        s = _make_session()
        update_memory(s.memory, s, "I lost my grandfather last week and I'm devastated")
        assert s.memory.story.primary_concern != ""


class TestReturnValue:
    def test_returns_turn_topics_list(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "I'm anxious about work")
        assert isinstance(topics, list)
        assert len(topics) > 0

    def test_empty_message_returns_empty(self):
        s = _make_session()
        topics = update_memory(s.memory, s, "ok")
        assert isinstance(topics, list)
