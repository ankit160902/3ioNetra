"""Tests for SignalCollector extracted from CompanionEngine."""
import importlib.util
from pathlib import Path

from models.session import SessionState, SignalType
from models.memory_context import ConversationMemory, UserStory

# Load signal_collector directly to avoid services/__init__.py chain
_sc_path = str(Path(__file__).resolve().parents[2] / "services" / "signal_collector.py")
_spec = importlib.util.spec_from_file_location("signal_collector", _sc_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
collect_signals_from_analysis = _mod.collect_signals_from_analysis


def _make_session() -> SessionState:
    s = SessionState()
    s.memory = ConversationMemory(story=UserStory())
    return s


class TestLifeDomainSignal:
    def test_sets_life_area_and_signal(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"life_domain": "career", "emotion": "neutral"})
        assert s.memory.story.life_area == "career"
        assert SignalType.LIFE_DOMAIN in s.signals_collected

    def test_ignores_unknown_domain(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"life_domain": "unknown"})
        assert s.memory.story.life_area is None
        assert SignalType.LIFE_DOMAIN not in s.signals_collected

    def test_ignores_empty_domain(self):
        s = _make_session()
        collect_signals_from_analysis(s, {})
        assert SignalType.LIFE_DOMAIN not in s.signals_collected


class TestEmotionSignal:
    def test_sets_emotion_and_signal(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"emotion": "grief"})
        assert s.memory.story.emotional_state == "grief"
        assert SignalType.EMOTION in s.signals_collected

    def test_ignores_neutral_emotion(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"emotion": "neutral"})
        assert s.memory.story.emotional_state is None
        assert SignalType.EMOTION not in s.signals_collected


class TestEntityEnrichment:
    def test_sets_deity(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"entities": {"deity": "krishna"}})
        assert s.memory.story.preferred_deity == "krishna"

    def test_sets_ritual_as_concern(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"entities": {"ritual": "puja"}})
        assert s.memory.story.primary_concern == "Performing puja"

    def test_sets_summary_as_concern(self):
        s = _make_session()
        collect_signals_from_analysis(s, {"summary": "User is stressed about exams"})
        assert s.memory.story.primary_concern == "User is stressed about exams"

    def test_empty_entities_no_change(self):
        s = _make_session()
        s.memory.story.preferred_deity = "shiva"
        collect_signals_from_analysis(s, {"entities": {}})
        assert s.memory.story.preferred_deity == "shiva"


class TestCombinedSignals:
    def test_all_fields_set(self):
        s = _make_session()
        collect_signals_from_analysis(s, {
            "life_domain": "spiritual",
            "emotion": "peace",
            "entities": {"deity": "hanuman"},
            "summary": "Seeking mantras for courage",
        })
        assert s.memory.story.life_area == "spiritual"
        assert s.memory.story.emotional_state == "peace"
        assert s.memory.story.preferred_deity == "hanuman"
        assert s.memory.story.primary_concern == "Seeking mantras for courage"
        assert SignalType.LIFE_DOMAIN in s.signals_collected
        assert SignalType.EMOTION in s.signals_collected

    def test_empty_analysis_no_crash(self):
        s = _make_session()
        collect_signals_from_analysis(s, {})
        # Should not raise, no signals added
        assert len(s.signals_collected) == 0
