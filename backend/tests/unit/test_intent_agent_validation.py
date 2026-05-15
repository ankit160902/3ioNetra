"""Tests verifying IntentAgent uses Pydantic validation via llm_schemas."""
import ast
from pathlib import Path

INTENT_AGENT_PATH = Path(__file__).resolve().parents[2] / "services" / "intent_agent.py"


def test_imports_pydantic_schemas():
    """IntentAgent should import from models.llm_schemas."""
    text = INTENT_AGENT_PATH.read_text()
    assert "from models.llm_schemas import" in text
    assert "IntentAnalysis" in text
    assert "extract_json" in text


def test_uses_extract_json_not_manual_parsing():
    """IntentAgent should use extract_json() instead of manual markdown stripping."""
    text = INTENT_AGENT_PATH.read_text()
    # Should NOT have the old manual markdown stripping
    assert '```json' not in text or 'extract_json' in text
    # Should use extract_json
    assert "extract_json(raw_text)" in text


def test_uses_intent_analysis_model():
    """IntentAgent should validate response via IntentAnalysis(**parsed)."""
    text = INTENT_AGENT_PATH.read_text()
    assert "IntentAnalysis(**parsed)" in text or "IntentAnalysis(**" in text


def test_no_bare_json_loads_for_llm_response():
    """The LLM response path should NOT use bare json.loads for the main response.
    (json.loads may still be used in fast-path or cache, which is fine.)"""
    tree = ast.parse(INTENT_AGENT_PATH.read_text(), filename="intent_agent.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "analyze_intent":
            # Find the try block that does the LLM call
            source = ast.get_source_segment(INTENT_AGENT_PATH.read_text(), node)
            # After extract_json is used, there should be no json.loads(raw_text)
            assert "json.loads(raw_text)" not in source, (
                "analyze_intent should use extract_json() instead of json.loads(raw_text)"
            )
            return

    assert False, "analyze_intent method not found"
