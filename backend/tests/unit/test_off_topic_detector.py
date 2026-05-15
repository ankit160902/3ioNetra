"""Unit tests for services/off_topic_detector.py.

The detector wraps IntentAgent.is_off_topic so the call site doesn't need
to know which dict key holds the boolean. These tests use a stub
PromptManager so they don't depend on the production YAML.
"""

import pytest

from services.off_topic_detector import OffTopicDetector, get_off_topic_detector


class StubPromptManager:
    def __init__(self, redirect_message="STUB_REDIRECT"):
        self._redirect = redirect_message

    def get_value(self, group_name: str, key_path: str, default=None):
        if key_path == "off_topic.redirect_message":
            return self._redirect
        return default


@pytest.fixture
def detector():
    return OffTopicDetector(prompt_manager=StubPromptManager())


# ---------------------------------------------------------------------------
# is_off_topic — pure analysis dict check
# ---------------------------------------------------------------------------

class TestIsOffTopic:
    def test_true_when_flag_set(self, detector):
        assert detector.is_off_topic({"is_off_topic": True})

    def test_false_when_flag_unset(self, detector):
        assert not detector.is_off_topic({"is_off_topic": False})

    def test_false_when_key_missing(self, detector):
        assert not detector.is_off_topic({"intent": "SEEKING_GUIDANCE"})

    def test_false_when_analysis_is_none(self, detector):
        assert not detector.is_off_topic(None)  # type: ignore[arg-type]

    def test_false_when_analysis_is_not_dict(self, detector):
        assert not detector.is_off_topic("not a dict")  # type: ignore[arg-type]

    def test_static_method_works_without_instance(self):
        # Convenience: is_off_topic is callable without constructing the
        # detector, useful for tests / quick checks.
        assert OffTopicDetector.is_off_topic({"is_off_topic": True})


# ---------------------------------------------------------------------------
# Redirect message
# ---------------------------------------------------------------------------

class TestRedirectMessage:
    def test_loads_from_yaml(self, detector):
        assert detector.get_redirect_message() == "STUB_REDIRECT"

    def test_caches_after_first_read(self, detector):
        first = detector.get_redirect_message()
        # Mutate the stub — cached value should still win
        detector._pm._redirect = "CHANGED"  # type: ignore[attr-defined]
        second = detector.get_redirect_message()
        assert first == second == "STUB_REDIRECT"

    def test_safe_fallback_when_yaml_missing(self):
        empty = StubPromptManager(redirect_message="")
        d = OffTopicDetector(prompt_manager=empty)
        msg = d.get_redirect_message()
        assert msg
        # Fallback should still be a polite redirect about scope
        assert "area" in msg.lower() or "questions" in msg.lower()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_singleton_identity(self):
        a = get_off_topic_detector()
        b = get_off_topic_detector()
        assert a is b

    def test_real_yaml_provides_redirect_message(self):
        d = get_off_topic_detector()
        msg = d.get_redirect_message()
        assert msg
        assert len(msg) > 30  # non-trivial content
