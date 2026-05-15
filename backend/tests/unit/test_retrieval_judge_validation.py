"""Tests verifying RetrievalJudge uses Pydantic validation via llm_schemas."""
import ast
from pathlib import Path

JUDGE_PATH = Path(__file__).resolve().parents[2] / "services" / "retrieval_judge.py"


def test_imports_pydantic_schemas():
    text = JUDGE_PATH.read_text()
    assert "from models.llm_schemas import" in text
    assert "extract_json" in text
    assert "QueryRewriteSchema" in text or "QueryRewrite" in text
    assert "GroundingResultSchema" in text or "GroundingResult" in text


def test_parse_json_delegates_to_extract_json():
    """_parse_json should now delegate to extract_json."""
    text = JUDGE_PATH.read_text()
    # Should NOT have the old balanced-brace scanner
    assert "depth = 0" not in text or "extract_json" in text
    # Should delegate
    assert "extract_json(text)" in text


def test_query_rewrite_uses_pydantic():
    """Query rewrite should validate via QueryRewriteSchema."""
    text = JUDGE_PATH.read_text()
    assert "QueryRewriteSchema(**" in text


def test_grounding_uses_pydantic():
    """Grounding verification should validate via GroundingResultSchema."""
    text = JUDGE_PATH.read_text()
    assert "GroundingResultSchema(**" in text


def test_no_manual_json_extraction_in_judge():
    """The old balanced-brace JSON scanner should be removed."""
    text = JUDGE_PATH.read_text()
    # The old code had a depth-tracking brace scanner
    lines = text.split("\n")
    has_depth_loop = False
    for line in lines:
        stripped = line.strip()
        if "depth += 1" in stripped and "ch == '{'" not in stripped:
            has_depth_loop = True
    assert not has_depth_loop, "_parse_json should delegate to extract_json, not have its own brace scanner"
