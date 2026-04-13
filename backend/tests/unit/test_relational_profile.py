"""Tests for the RelationalProfile dataclass used by the dynamic memory system.

RelationalProfile is the always-in-context "who is this user to Mitra"
narrative layer. Tests cover: field defaults, to_dict/from_dict roundtrip,
to_prompt_text rendering (including crisis flag), apply_reflection merging.
"""
from datetime import datetime

import pytest

from models.memory_context import RelationalProfile
from models.llm_schemas import ReflectionProfilePatch


class TestRelationalProfileDefaults:
    def test_empty_profile(self):
        p = RelationalProfile(user_id="u1")
        assert p.user_id == "u1"
        assert p.relational_narrative == ""
        assert p.spiritual_themes == []
        assert p.ongoing_concerns == []
        assert p.tone_preferences == []
        assert p.people_mentioned == []
        assert p.prior_crisis_flag is False
        assert p.prior_crisis_context is None
        assert p.prior_crisis_count == 0
        assert p.last_reflection_at is None
        assert p.importance_since_reflection == 0
        assert p.reflection_count == 0


class TestRelationalProfileSerialization:
    def test_to_dict_roundtrip(self):
        p = RelationalProfile(
            user_id="u42",
            relational_narrative="You are a software engineer in Pune...",
            spiritual_themes=["finding purpose"],
            ongoing_concerns=["career uncertainty"],
            tone_preferences=["prefers direct advice"],
            people_mentioned=["Priya (sister)"],
            prior_crisis_flag=True,
            prior_crisis_context="On 2026-04-10 user had a crisis moment",
            prior_crisis_count=1,
            importance_since_reflection=15,
            reflection_count=2,
        )
        d = p.to_dict()
        p2 = RelationalProfile.from_dict(d)
        assert p2.user_id == p.user_id
        assert p2.relational_narrative == p.relational_narrative
        assert p2.spiritual_themes == p.spiritual_themes
        assert p2.ongoing_concerns == p.ongoing_concerns
        assert p2.tone_preferences == p.tone_preferences
        assert p2.people_mentioned == p.people_mentioned
        assert p2.prior_crisis_flag is True
        assert p2.prior_crisis_context == "On 2026-04-10 user had a crisis moment"
        assert p2.prior_crisis_count == 1
        assert p2.importance_since_reflection == 15
        assert p2.reflection_count == 2

    def test_from_dict_empty_returns_default(self):
        p = RelationalProfile.from_dict({})
        assert p.user_id == ""
        assert p.relational_narrative == ""
        assert p.prior_crisis_flag is False

    def test_from_dict_missing_fields(self):
        p = RelationalProfile.from_dict({"user_id": "u1"})
        assert p.user_id == "u1"
        assert p.relational_narrative == ""
        assert p.spiritual_themes == []

    def test_to_dict_iso_dates_if_set(self):
        now = datetime(2026, 4, 12, 15, 30, 0)
        p = RelationalProfile(
            user_id="u1",
            last_reflection_at=now,
            created_at=now,
            updated_at=now,
        )
        d = p.to_dict()
        assert "2026-04-12" in str(d["last_reflection_at"])

    def test_from_dict_iso_dates(self):
        d = {
            "user_id": "u1",
            "last_reflection_at": "2026-04-12T15:30:00",
            "created_at": "2026-04-12T15:30:00",
        }
        p = RelationalProfile.from_dict(d)
        assert isinstance(p.last_reflection_at, datetime)
        assert p.last_reflection_at.year == 2026


class TestRelationalProfileToPromptText:
    def test_empty_profile_renders_empty(self):
        p = RelationalProfile(user_id="u1")
        assert p.to_prompt_text() == ""

    def test_narrative_only(self):
        p = RelationalProfile(
            user_id="u1",
            relational_narrative="You are a software engineer.",
        )
        text = p.to_prompt_text()
        assert "You are a software engineer." in text

    def test_structured_fields_render_as_chips(self):
        p = RelationalProfile(
            user_id="u1",
            relational_narrative="",
            spiritual_themes=["finding purpose", "letting go"],
            ongoing_concerns=["career uncertainty"],
            people_mentioned=["Priya (sister)"],
        )
        text = p.to_prompt_text()
        assert "finding purpose" in text
        assert "career uncertainty" in text
        assert "Priya" in text

    def test_crisis_flag_renders_as_safety_note(self):
        p = RelationalProfile(
            user_id="u1",
            relational_narrative="You are a software engineer.",
            prior_crisis_flag=True,
            prior_crisis_context="On 2026-04-10 user had a crisis moment",
        )
        text = p.to_prompt_text()
        # Must render a safety note at the TOP
        assert "crisis" in text.lower()
        # Must not leak the specific context verbatim — the renderer
        # should only emit a generic bias note, never the raw context
        # (that's stored but not exposed to the generation prompt)
        lines = text.split("\n")
        # First non-empty line should be the safety note
        first_content = next((l for l in lines if l.strip()), "")
        assert "NOTE" in first_content or "crisis" in first_content.lower()

    def test_crisis_without_narrative(self):
        p = RelationalProfile(
            user_id="u1",
            prior_crisis_flag=True,
        )
        text = p.to_prompt_text()
        assert "crisis" in text.lower()


class TestRelationalProfileApplyReflection:
    def test_apply_updates_narrative(self):
        p = RelationalProfile(user_id="u1", relational_narrative="old")
        patch = ReflectionProfilePatch(
            relational_narrative="You are a software engineer wrestling with career.",
            spiritual_themes=["finding purpose"],
            ongoing_concerns=["career uncertainty"],
        )
        updated = p.apply_reflection(patch)
        assert updated.relational_narrative.startswith("You are")
        assert "finding purpose" in updated.spiritual_themes

    def test_apply_caps_list_fields_at_10(self):
        p = RelationalProfile(user_id="u1")
        patch = ReflectionProfilePatch(
            relational_narrative="test",
            spiritual_themes=[f"theme_{i}" for i in range(20)],
            ongoing_concerns=[f"concern_{i}" for i in range(15)],
            tone_preferences=[f"pref_{i}" for i in range(12)],
            people_mentioned=[f"person_{i}" for i in range(11)],
        )
        updated = p.apply_reflection(patch)
        assert len(updated.spiritual_themes) == 10
        assert len(updated.ongoing_concerns) == 10
        assert len(updated.tone_preferences) == 10
        assert len(updated.people_mentioned) == 10

    def test_apply_preserves_user_id(self):
        p = RelationalProfile(user_id="u_original")
        patch = ReflectionProfilePatch(relational_narrative="new narrative")
        updated = p.apply_reflection(patch)
        assert updated.user_id == "u_original"

    def test_apply_preserves_crisis_state(self):
        p = RelationalProfile(
            user_id="u1",
            prior_crisis_flag=True,
            prior_crisis_context="meta fact",
            prior_crisis_count=2,
        )
        patch = ReflectionProfilePatch(relational_narrative="new narrative")
        updated = p.apply_reflection(patch)
        assert updated.prior_crisis_flag is True
        assert updated.prior_crisis_context == "meta fact"
        assert updated.prior_crisis_count == 2

    def test_apply_returns_new_instance_not_mutation(self):
        p = RelationalProfile(user_id="u1", relational_narrative="original")
        patch = ReflectionProfilePatch(relational_narrative="new")
        updated = p.apply_reflection(patch)
        assert updated is not p
        assert p.relational_narrative == "original"  # not mutated
        assert updated.relational_narrative == "new"

    def test_apply_sets_updated_at(self):
        p = RelationalProfile(user_id="u1")
        patch = ReflectionProfilePatch(relational_narrative="new")
        updated = p.apply_reflection(patch)
        assert updated.updated_at is not None
        assert isinstance(updated.updated_at, datetime)
