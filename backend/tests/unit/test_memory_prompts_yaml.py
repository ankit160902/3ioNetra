"""Smoke tests for the memory_prompts section in spiritual_mitra.yaml.

Validates that the YAML loads cleanly, that the three memory_prompts
sub-keys exist, and that each prompt has the minimum required content
markers (no silent empty prompts).
"""
import yaml
from pathlib import Path

import pytest


_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "spiritual_mitra.yaml"
)


@pytest.fixture(scope="module")
def yaml_data():
    with open(_YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestMemoryPromptsYAML:
    def test_yaml_file_exists(self):
        assert _YAML_PATH.exists(), f"spiritual_mitra.yaml not found at {_YAML_PATH}"

    def test_yaml_parses_cleanly(self, yaml_data):
        assert isinstance(yaml_data, dict)

    def test_memory_prompts_top_level_key_exists(self, yaml_data):
        assert "memory_prompts" in yaml_data, (
            "Top-level 'memory_prompts' key missing from spiritual_mitra.yaml"
        )

    def test_memory_prompts_has_three_subkeys(self, yaml_data):
        mp = yaml_data["memory_prompts"]
        assert "extract" in mp
        assert "update_decision" in mp
        assert "reflect" in mp

    def test_extract_prompt_has_required_markers(self, yaml_data):
        prompt = yaml_data["memory_prompts"]["extract"]
        assert isinstance(prompt, str)
        assert len(prompt) > 500, "extract prompt too short — needs detailed guidance"
        # Must instruct the model to be sparse
        assert "SPARSE" in prompt.upper() or "sparse" in prompt.lower()
        # Must define the four sensitivity tiers
        for tier in ("trivial", "personal", "sensitive", "crisis"):
            assert tier in prompt.lower(), f"sensitivity tier '{tier}' not documented in extract prompt"
        # Must instruct the model about importance
        assert "importance" in prompt.lower()
        # Must require JSON output
        assert "JSON" in prompt.upper() or "json" in prompt.lower()
        # Must explicitly forbid storing verbatim crisis content
        assert "verbatim" in prompt.lower() or "meta-fact" in prompt.lower()

    def test_update_decision_prompt_has_required_markers(self, yaml_data):
        prompt = yaml_data["memory_prompts"]["update_decision"]
        assert isinstance(prompt, str)
        assert len(prompt) > 400
        # Must describe all 4 operations
        for op in ("ADD", "UPDATE", "DELETE", "NOOP"):
            assert op in prompt, f"operation '{op}' not documented in update_decision prompt"
        # Must instruct conservative behavior
        assert "CONSERVATIVE" in prompt.upper() or "conservative" in prompt.lower()
        # Must require JSON output
        assert "JSON" in prompt.upper() or "json" in prompt.lower()

    def test_reflect_prompt_has_required_markers(self, yaml_data):
        prompt = yaml_data["memory_prompts"]["reflect"]
        assert isinstance(prompt, str)
        assert len(prompt) > 400
        # Must describe both jobs: consolidation + pruning
        assert "consolidat" in prompt.lower() or "narrative" in prompt.lower()
        assert "prune" in prompt.lower() or "stale" in prompt.lower()
        # Must mention updated_profile + prune_ids output fields
        assert "updated_profile" in prompt
        assert "prune_ids" in prompt
        # Must forbid verbatim crisis content in the narrative
        assert "crisis" in prompt.lower()
        # Must require JSON output
        assert "JSON" in prompt.upper() or "json" in prompt.lower()

    def test_existing_sections_still_intact(self, yaml_data):
        """Adding memory_prompts must not break existing top-level keys."""
        for key in (
            "system_instruction",
            "phase_prompts",
            "mode_prompts",
            "rag_synthesis",
            "response_constraints",
        ):
            assert key in yaml_data, f"existing top-level key '{key}' missing after edit"

    def test_mode_prompts_all_five_survived(self, yaml_data):
        """The 5-mode response-mode taxonomy must still be complete."""
        mp = yaml_data["mode_prompts"]
        for mode in ("practical_first", "presence_first", "teaching", "exploratory", "closure"):
            assert mode in mp, f"mode_prompts.{mode} missing"
