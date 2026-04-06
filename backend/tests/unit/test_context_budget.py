"""Tests for ContextBudgetManager."""
import importlib.util
from pathlib import Path

_path = str(Path(__file__).resolve().parents[2] / "services" / "context_budget.py")
_spec = importlib.util.spec_from_file_location("context_budget", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ContextBudgetManager = _mod.ContextBudgetManager
estimate_tokens = _mod.estimate_tokens
trim_conversation_history = _mod.trim_conversation_history
trim_rag_docs = _mod.trim_rag_docs


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_short(self):
        assert estimate_tokens("hello world") > 0

    def test_proportional(self):
        short = estimate_tokens("hello")
        long = estimate_tokens("hello " * 100)
        assert long > short * 10


class TestContextBudgetFit:
    def test_within_budget_no_trim(self):
        mgr = ContextBudgetManager(max_output_tokens=2048)
        sections = {
            "system_instruction": "a" * 2000,
            "current_query": "What is peace?",
            "conversation_history": "a" * 1000,
            "rag_context": "a" * 1000,
        }
        result = mgr.fit(sections)
        # All sections should remain unchanged
        assert result["system_instruction"] == sections["system_instruction"]
        assert result["rag_context"] == sections["rag_context"]
        assert len(mgr.trims_applied) == 0

    def test_over_budget_trims_lowest_priority(self):
        mgr = ContextBudgetManager(max_output_tokens=2048)
        mgr.budget = 2000  # Very tight budget
        sections = {
            "system_instruction": "a" * 4000,  # 1000 tokens, priority 10
            "current_query": "What is peace?",   # ~4 tokens, priority 9
            "verse_history": "b" * 2000,         # 500 tokens, priority 1
            "past_memories": "c" * 2000,         # 500 tokens, priority 2
            "conversation_history": "d" * 2000,  # 500 tokens, priority 5
        }
        result = mgr.fit(sections)
        # verse_history (priority 1) should be trimmed first
        assert result["verse_history"] == "" or len(result["verse_history"]) < len(sections["verse_history"])
        # system_instruction (priority 10) should be untouched
        assert result["system_instruction"] == sections["system_instruction"]
        assert len(mgr.trims_applied) > 0

    def test_never_trims_critical_sections(self):
        mgr = ContextBudgetManager(max_output_tokens=2048)
        mgr.budget = 500  # Extremely tight
        sections = {
            "system_instruction": "a" * 1000,
            "phase_prompt": "b" * 500,
            "current_query": "What should I do?",
        }
        result = mgr.fit(sections)
        # Critical sections (priority >= 8) should never be trimmed
        assert result["system_instruction"] == sections["system_instruction"]
        assert result["phase_prompt"] == sections["phase_prompt"]
        assert result["current_query"] == sections["current_query"]


class TestTrimConversationHistory:
    def test_under_limit_no_trim(self):
        msgs = [{"role": "user", "content": "hello"}] * 5
        result = trim_conversation_history(msgs, max_messages=14, max_tokens=5000)
        assert len(result) == 5

    def test_trims_to_max_messages(self):
        msgs = [{"role": "user", "content": "hello"}] * 20
        result = trim_conversation_history(msgs, max_messages=10)
        assert len(result) <= 10

    def test_trims_to_token_budget(self):
        msgs = [{"role": "user", "content": "a" * 400}] * 20  # ~100 tokens each
        result = trim_conversation_history(msgs, max_messages=20, max_tokens=500)
        assert len(result) <= 6  # ~500 tokens / ~100 per msg

    def test_never_below_minimum(self):
        msgs = [{"role": "user", "content": "a" * 2000}] * 10  # 500 tokens each
        result = trim_conversation_history(msgs, max_messages=10, max_tokens=100)
        assert len(result) >= 4  # MIN_HISTORY_MESSAGES


class TestTrimRagDocs:
    def test_under_limit_no_trim(self):
        docs = [{"text": "verse text", "meaning": "meaning"}] * 3
        result = trim_rag_docs(docs, max_docs=5, max_tokens=5000)
        assert len(result) == 3

    def test_trims_to_max_docs(self):
        docs = [{"text": "verse", "meaning": "meaning"}] * 10
        result = trim_rag_docs(docs, max_docs=3)
        assert len(result) <= 3

    def test_trims_to_token_budget(self):
        docs = [{"text": "a" * 2000, "meaning": "b" * 2000}] * 5  # ~1000 tokens each
        result = trim_rag_docs(docs, max_docs=5, max_tokens=1500)
        assert len(result) <= 2

    def test_truncates_individual_docs_if_needed(self):
        docs = [{"text": "a" * 4000, "meaning": "b" * 4000}]  # 2000 tokens
        result = trim_rag_docs(docs, max_docs=1, max_tokens=500)
        assert len(result) == 1
        # Doc text should be truncated
        total_len = len(result[0].get("text", "")) + len(result[0].get("meaning", ""))
        assert total_len < 8000  # Was 8000 chars, should be much less

    def test_never_below_minimum(self):
        docs = [{"text": "a" * 8000, "meaning": ""}] * 3
        result = trim_rag_docs(docs, max_docs=3, max_tokens=100)
        assert len(result) >= 1  # MIN_RAG_DOCS
