#!/usr/bin/env python3
"""
Comprehensive test suite for ALL 23 RAKS Pipeline Improvement items.

Tests are organized by phase and can run without a live backend — they test
the code at the unit/integration level using imports and mocks where needed.

Run:  cd backend && python3 -m pytest tests/test_raks_pipeline.py -v
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

# Ensure backend is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings


# =====================================================================
# ALREADY-DONE ITEMS (7) — Verify they haven't regressed
# =====================================================================

class TestAlreadyDoneItems:
    """Verify the 7 pre-existing RAKS items are still intact."""

    def test_min_similarity_score(self):
        """Item P0-1: MIN_SIMILARITY_SCORE default is 0.28 (may be overridden by .env)"""
        # Default in code is 0.28; .env may override to 0.12 or similar
        assert settings.MIN_SIMILARITY_SCORE > 0
        assert settings.MIN_SIMILARITY_SCORE <= 0.5

    def test_adaptive_candidate_pool_settings(self):
        """Item P1: Adaptive candidate pool sizes exist"""
        assert hasattr(settings, 'CANDIDATE_POOL_KEYWORD')
        assert hasattr(settings, 'CANDIDATE_POOL_DEFAULT')
        assert hasattr(settings, 'CANDIDATE_POOL_THEMATIC')
        assert hasattr(settings, 'CANDIDATE_POOL_COMPARATIVE')
        assert settings.CANDIDATE_POOL_KEYWORD < settings.CANDIDATE_POOL_DEFAULT
        assert settings.CANDIDATE_POOL_DEFAULT < settings.CANDIDATE_POOL_THEMATIC
        assert settings.CANDIDATE_POOL_THEMATIC <= settings.CANDIDATE_POOL_COMPARATIVE

    def test_reranker_caching_config(self):
        """Item P1: RAG search cache TTL exists"""
        assert settings.RAG_SEARCH_CACHE_TTL > 0

    def test_candidate_pool_sizing(self):
        """Item P1: _get_candidate_pool_size returns different sizes by intent."""
        from rag.pipeline import RAGPipeline
        from models.session import IntentType
        p = RAGPipeline()
        # Need _sanskrit_terms for _get_candidate_pool_size
        p._sanskrit_terms = frozenset()
        assert p._get_candidate_pool_size("compare gita ramayana", None) == settings.CANDIDATE_POOL_COMPARATIVE
        assert p._get_candidate_pool_size("what is karma", IntentType.ASKING_INFO) == settings.CANDIDATE_POOL_KEYWORD
        assert p._get_candidate_pool_size("I feel sad", IntentType.EXPRESSING_EMOTION) == settings.CANDIDATE_POOL_THEMATIC
        assert p._get_candidate_pool_size("help me", IntentType.SEEKING_GUIDANCE) == settings.CANDIDATE_POOL_DEFAULT


# =====================================================================
# PHASE 1 — Pure Code Changes (7 items)
# =====================================================================

class TestPhase1DynamicCuratedThreshold:
    """Item 1.1: Dynamic Curated Injection Threshold"""

    def test_config_settings_exist(self):
        assert hasattr(settings, 'CURATED_FLOOR')
        assert hasattr(settings, 'CURATED_RATIO')
        assert settings.CURATED_FLOOR == 0.35
        assert settings.CURATED_RATIO == 0.6

    def test_dynamic_threshold_calculation(self):
        """Threshold = max(floor, top_fused * ratio)"""
        floor = settings.CURATED_FLOOR
        ratio = settings.CURATED_RATIO
        # When top score is high (0.9), threshold should be 0.9*0.6=0.54 > floor(0.35)
        top_fused = 0.9
        threshold = max(floor, top_fused * ratio)
        assert threshold == pytest.approx(0.54, abs=0.01)
        # When top score is low (0.3), threshold should be floor(0.35) > 0.3*0.6=0.18
        top_fused_low = 0.3
        threshold_low = max(floor, top_fused_low * ratio)
        assert threshold_low == floor

    def test_code_uses_dynamic_threshold(self):
        """Verify pipeline.py uses _dynamic_curated_threshold, not CURATED_VIABILITY_THRESHOLD."""
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert '_dynamic_curated_threshold' in src
        assert 'CURATED_FLOOR' in src
        assert 'CURATED_RATIO' in src


class TestPhase1AdaptiveGate1:
    """Item 1.2: Adaptive Gate 1 Threshold"""

    def test_config_ratios_exist(self):
        assert settings.RELEVANCE_RATIO_EMOTIONAL == 0.40
        assert settings.RELEVANCE_RATIO_CITATION == 0.55
        assert settings.RELEVANCE_RATIO_GUIDANCE == 0.45
        assert settings.RELEVANCE_RATIO_DEFAULT == 0.50

    def test_emotional_is_loosest(self):
        """Emotional queries should have the loosest threshold (lowest ratio)."""
        assert settings.RELEVANCE_RATIO_EMOTIONAL < settings.RELEVANCE_RATIO_DEFAULT
        assert settings.RELEVANCE_RATIO_EMOTIONAL < settings.RELEVANCE_RATIO_CITATION

    def test_citation_is_strictest(self):
        """Citation/info queries need precision — strictest ratio."""
        assert settings.RELEVANCE_RATIO_CITATION > settings.RELEVANCE_RATIO_DEFAULT
        assert settings.RELEVANCE_RATIO_CITATION > settings.RELEVANCE_RATIO_GUIDANCE

    def test_gate_relevance_adapts_by_intent(self):
        """Gate 1 should use different ratios for different intents."""
        from services.context_validator import ContextValidator
        from models.session import IntentType

        cv = ContextValidator()
        docs = [
            {"final_score": 0.8, "text": "top doc"},
            {"final_score": 0.45, "text": "mid doc"},
            {"final_score": 0.30, "text": "low doc"},
        ]

        # Emotional intent (ratio=0.40): threshold = max(0.28, 0.8*0.40) = 0.32
        result_emotional = cv._gate_relevance(docs.copy(), 0.28, IntentType.EXPRESSING_EMOTION)
        # Should keep top + mid (0.45 > 0.32), drop low (0.30 < 0.32)
        assert len(result_emotional) == 2

        # Citation intent (ratio=0.55): threshold = max(0.28, 0.8*0.55) = 0.44
        result_citation = cv._gate_relevance(docs.copy(), 0.28, IntentType.ASKING_INFO)
        # Should keep only top (0.8 > 0.44) and mid (0.45 > 0.44), drop low
        assert len(result_citation) == 2

        # With a stricter min_score
        docs_tight = [
            {"final_score": 0.8, "text": "top"},
            {"final_score": 0.42, "text": "mid"},
        ]
        result_strict = cv._gate_relevance(docs_tight.copy(), 0.28, IntentType.ASKING_INFO)
        # threshold = max(0.28, 0.8*0.55) = 0.44, so 0.42 < 0.44 → dropped
        assert len(result_strict) == 1


class TestPhase1CitationLookup:
    """Item 1.3: Citation Lookup Short-Circuit"""

    def test_citation_patterns_exist(self):
        from rag.pipeline import _CITATION_PATTERNS
        assert len(_CITATION_PATTERNS) >= 6

    def test_citation_regex_matches(self):
        """Verify regex patterns match common citation formats."""
        from rag.pipeline import _CITATION_PATTERNS
        test_cases = [
            ("BG 2.47", True),
            ("Bhagavad Gita 3:19", True),
            ("gita 18.66", True),
            ("yoga sutra 1.2", True),
            ("Rig Veda 1.1", True),
            ("hello world", False),
        ]
        for query, should_match in test_cases:
            matched = any(p.search(query) for p in _CITATION_PATTERNS)
            assert matched == should_match, f"Query '{query}' should {'match' if should_match else 'not match'}"

    def test_citation_lookup_method_exists(self):
        from rag.pipeline import RAGPipeline
        p = RAGPipeline()
        assert hasattr(p, '_try_citation_lookup')

    def test_citation_lookup_returns_none_without_index(self):
        from rag.pipeline import RAGPipeline
        p = RAGPipeline()
        p._reference_index = {}
        result = p._try_citation_lookup("BG 2.47")
        assert result is None

    def test_citation_lookup_finds_verse(self):
        from rag.pipeline import RAGPipeline
        p = RAGPipeline()
        p.verses = [{"reference": "Bhagavad Gita Chapter 2, Verse 47", "text": "karmanye vadhikaraste", "scripture": "Bhagavad Gita"}]
        p._reference_index = {"bhagavad gita chapter 2, verse 47": 0}
        result = p._try_citation_lookup("BG 2.47")
        assert result is not None
        assert len(result) == 1
        assert result[0]["score"] == 1.0


class TestPhase1MemoryDeduplication:
    """Item 1.4: Memory Deduplication"""

    def test_config_settings(self):
        assert settings.MEMORY_DEDUP_THRESHOLD == 0.85
        assert settings.MEMORY_MAX_RESULTS == 5

    def test_dedup_logic(self):
        """Simulate the dedup algorithm to ensure near-duplicates are removed."""
        dedup_threshold = settings.MEMORY_DEDUP_THRESHOLD

        # Create 3 vectors: 2 nearly identical, 1 distinct
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([0.99, 0.1, 0.0], dtype=np.float32)  # very similar to a
        vec_c = np.array([0.0, 0.0, 1.0], dtype=np.float32)  # distinct

        results = [
            ("memory_a", 0.9, vec_a),
            ("memory_b", 0.85, vec_b),
            ("memory_c", 0.8, vec_c),
        ]

        deduped = []
        deduped_vecs = []
        for text, score, vec in results:
            if score < settings.MEMORY_SIMILARITY_THRESHOLD:
                continue
            is_dup = any(
                float(np.dot(vec, kv) / (np.linalg.norm(vec) * np.linalg.norm(kv) + 1e-9)) > dedup_threshold
                for kv in deduped_vecs
            )
            if not is_dup:
                deduped.append(text)
                deduped_vecs.append(vec)
            if len(deduped) >= settings.MEMORY_MAX_RESULTS:
                break

        # vec_b should be deduped (too similar to vec_a)
        assert len(deduped) == 2
        assert "memory_a" in deduped
        assert "memory_c" in deduped
        assert "memory_b" not in deduped


class TestPhase1PersistentTranslationCache:
    """Item 1.5: Persistent Translation Cache"""

    def test_config_path_exists(self):
        assert hasattr(settings, 'TRANSLATION_CACHE_PATH')
        assert settings.TRANSLATION_CACHE_PATH != ""

    def test_shelve_integration_in_code(self):
        """Verify pipeline.py imports shelve and uses it in _translate_query."""
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert 'import shelve' in src
        assert 'shelve.open' in src
        assert 'Translation disk-cache HIT' in src

    def test_shelve_roundtrip(self):
        """Verify shelve works correctly as a persistent cache."""
        import shelve
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_cache")
            # Write
            with shelve.open(db_path) as db:
                db["key123"] = "translated text"
            # Read
            with shelve.open(db_path) as db:
                assert "key123" in db
                assert db["key123"] == "translated text"


class TestPhase1QueryLogging:
    """Item 1.6: Query Logging Pipeline"""

    def test_config_settings(self):
        assert settings.QUERY_LOG_ENABLED is True
        assert settings.QUERY_LOG_PATH != ""

    def test_query_logger_service_exists(self):
        from services.query_logger import QueryLogger, get_query_logger
        logger = get_query_logger()
        assert isinstance(logger, QueryLogger)

    def test_query_logger_initialize_and_log(self):
        """Test the full lifecycle: init → log → verify."""
        from services.query_logger import QueryLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_queries.db")
            ql = QueryLogger(db_path)

            async def _run():
                await ql.initialize()
                assert ql.available is True
                await ql.log(
                    query="what is karma",
                    intent="ASKING_INFO",
                    life_domain="ethics",
                    num_results=3,
                    top_score=0.85,
                    latency_ms=120,
                )
                # Verify by reading back
                import aiosqlite
                async with aiosqlite.connect(db_path) as db:
                    cursor = await db.execute("SELECT COUNT(*) FROM queries")
                    row = await cursor.fetchone()
                    assert row[0] == 1

                    cursor = await db.execute("SELECT query, intent FROM queries")
                    row = await cursor.fetchone()
                    assert row[0] == "what is karma"
                    assert row[1] == "ASKING_INFO"
                await ql.close()

            asyncio.run(_run())

    def test_main_py_initializes_logger(self):
        with open(Path(__file__).parent.parent / 'main.py') as f:
            src = f.read()
        assert 'get_query_logger' in src
        assert 'await get_query_logger().initialize()' in src


class TestPhase1ScoringFormula:
    """Item 1.7: Scoring Formula Update"""

    def test_reranker_weight(self):
        assert settings.RERANKER_WEIGHT == 0.75

    def test_tradition_bonus(self):
        assert hasattr(settings, 'TRADITION_BONUS')
        assert settings.TRADITION_BONUS == 0.05

    def test_tradition_bonus_in_pipeline(self):
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert 'TRADITION_BONUS' in src
        assert 'doc_tradition' in src


# =====================================================================
# PHASE 2 — Code + Data Scripts (6 items)
# =====================================================================

class TestPhase2TraditionLabels:
    """Item 2.1: Tradition Labels on verses.json"""

    def test_script_exists(self):
        script = Path(__file__).parent.parent / 'scripts' / 'add_tradition_labels.py'
        assert script.exists()

    def test_scripture_to_tradition_mapping(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
        from add_tradition_labels import SCRIPTURE_TO_TRADITION
        assert "Bhagavad Gita" in SCRIPTURE_TO_TRADITION
        assert SCRIPTURE_TO_TRADITION["Bhagavad Gita"] == "vedanta"
        assert SCRIPTURE_TO_TRADITION["Ramayana"] == "itihasa"
        assert SCRIPTURE_TO_TRADITION["Rig Veda"] == "shruti"
        assert SCRIPTURE_TO_TRADITION["Patanjali Yoga Sutras"] == "yoga"
        assert SCRIPTURE_TO_TRADITION["Charaka Samhita (Ayurveda)"] == "ayurveda"

    def test_tradition_indices_built_in_pipeline(self):
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert '_tradition_indices' in src


class TestPhase2Gate6TraditionDiversity:
    """Item 2.2: Gate 6 — Tradition Diversity"""

    def test_config_setting(self):
        assert settings.MAX_DOCS_PER_TRADITION == 3

    def test_gate_tradition_diversity_method(self):
        from services.context_validator import ContextValidator
        cv = ContextValidator()

        docs = [
            {"tradition": "vedanta", "final_score": 0.9, "text": "a"},
            {"tradition": "vedanta", "final_score": 0.8, "text": "b"},
            {"tradition": "vedanta", "final_score": 0.7, "text": "c"},
            {"tradition": "vedanta", "final_score": 0.6, "text": "d"},  # Should be capped
            {"tradition": "itihasa", "final_score": 0.85, "text": "e"},
            {"tradition": "yoga", "final_score": 0.75, "text": "f"},
        ]
        result = cv._gate_tradition_diversity(docs, max_per_tradition=3)
        # 3 vedanta + 1 itihasa + 1 yoga = 5 (4th vedanta dropped)
        assert len(result) == 5
        vedanta_count = sum(1 for d in result if d.get("tradition") == "vedanta")
        assert vedanta_count == 3

    def test_curated_exempt(self):
        """Curated concept docs should bypass tradition cap."""
        from services.context_validator import ContextValidator
        cv = ContextValidator()
        docs = [
            {"tradition": "vedanta", "source": "curated_concept", "final_score": 0.9, "text": "a"},
            {"tradition": "vedanta", "source": "curated_concept", "final_score": 0.8, "text": "b"},
            {"tradition": "vedanta", "final_score": 0.7, "text": "c"},
            {"tradition": "vedanta", "final_score": 0.6, "text": "d"},
            {"tradition": "vedanta", "final_score": 0.5, "text": "e"},
            {"tradition": "vedanta", "final_score": 0.4, "text": "f"},
        ]
        result = cv._gate_tradition_diversity(docs, max_per_tradition=3)
        # 2 curated (exempt) + 3 normal vedanta = 5 (6th dropped)
        assert len(result) == 5

    def test_general_tradition_uncapped(self):
        """Docs with 'general' tradition should never be capped."""
        from services.context_validator import ContextValidator
        cv = ContextValidator()
        docs = [{"tradition": "general", "final_score": 0.5 + i * 0.01, "text": str(i)} for i in range(10)]
        result = cv._gate_tradition_diversity(docs, max_per_tradition=3)
        assert len(result) == 10  # All kept — general is uncapped


class TestPhase2DomainAffinity:
    """Item 2.3: Expand Domain Affinity to 80+"""

    def test_at_least_80_entries(self):
        from rag.pipeline import DOMAIN_SCRIPTURE_AFFINITY
        assert len(DOMAIN_SCRIPTURE_AFFINITY) >= 80, f"Only {len(DOMAIN_SCRIPTURE_AFFINITY)} entries"

    def test_multi_scripture_coverage(self):
        """Key domains should map to multiple scriptures, not just Gita."""
        from rag.pipeline import DOMAIN_SCRIPTURE_AFFINITY
        multi_scripture_domains = ["family", "courage", "meditation", "health", "marriage"]
        for domain in multi_scripture_domains:
            assert domain in DOMAIN_SCRIPTURE_AFFINITY, f"Missing domain: {domain}"
            assert len(DOMAIN_SCRIPTURE_AFFINITY[domain]) >= 2, f"Domain '{domain}' should map to 2+ scriptures"

    def test_new_emotion_domains_present(self):
        from rag.pipeline import DOMAIN_SCRIPTURE_AFFINITY
        new_emotions = ["anxiety", "despair", "joy", "gratitude", "hope"]
        for emo in new_emotions:
            assert emo in DOMAIN_SCRIPTURE_AFFINITY, f"Missing emotion domain: {emo}"

    def test_all_scriptures_represented(self):
        """All 11 scriptures should appear as values across the map."""
        from rag.pipeline import DOMAIN_SCRIPTURE_AFFINITY
        all_scriptures = set()
        for affinities in DOMAIN_SCRIPTURE_AFFINITY.values():
            all_scriptures.update(affinities.keys())
        expected = {"bhagavad gita", "ramayana", "mahabharata", "patanjali yoga sutras",
                    "charaka samhita", "atharva veda", "rig veda"}
        for s in expected:
            assert s in all_scriptures, f"Scripture '{s}' not represented in domain affinity map"


class TestPhase2CorpusManifest:
    """Item 2.4: Corpus Manifest"""

    def test_script_exists(self):
        assert (Path(__file__).parent.parent / 'scripts' / 'generate_corpus_manifest.py').exists()

    def test_pipeline_loads_manifest(self):
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert 'corpus_manifest.json' in src
        assert 'Corpus manifest v' in src


class TestPhase2CrossRefs:
    """Item 2.5: Cross-Reference Index"""

    def test_script_exists(self):
        assert (Path(__file__).parent.parent / 'scripts' / 'generate_cross_refs.py').exists()

    def test_pipeline_loads_cross_refs(self):
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert 'cross_refs.json' in src
        assert '_cross_refs' in src
        assert 'Cross-ref expansion' in src


class TestPhase2SectionChunks:
    """Item 2.6: L1 Section Chunks"""

    def test_config_setting(self):
        assert settings.SECTION_CHUNKS_ENABLED is True

    def test_script_exists(self):
        assert (Path(__file__).parent.parent / 'scripts' / 'generate_section_chunks.py').exists()

    def test_pipeline_integrates_sections(self):
        with open(Path(__file__).parent.parent / 'rag' / 'pipeline.py') as f:
            src = f.read()
        assert '_section_verses' in src
        assert '_section_embeddings' in src
        assert 'Section chunk boost' in src


# =====================================================================
# PHASE 3 — Major Data/Model Projects (3 items)
# =====================================================================

class TestPhase3CuratedConcepts:
    """Item 3.1: Curated Concepts 16→200"""

    def test_script_exists(self):
        assert (Path(__file__).parent.parent / 'scripts' / 'generate_curated_concepts.py').exists()

    def test_concept_seed_coverage(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
        from generate_curated_concepts import CONCEPT_SEEDS
        total = sum(len(v) for v in CONCEPT_SEEDS.values())
        assert total >= 200, f"Only {total} concept seeds (need 200+)"
        assert len(CONCEPT_SEEDS) >= 8, "Need at least 8 categories"


class TestPhase3SPLADE:
    """Item 3.2: SPLADE++ Integration"""

    def test_config_settings(self):
        assert hasattr(settings, 'SPLADE_ENABLED')
        assert settings.SPLADE_ENABLED is True  # Enabled (index built)
        assert settings.SPLADE_MODEL == "naver/splade-cocondenser-ensembledistil"

    def test_script_exists(self):
        assert (Path(__file__).parent.parent / 'scripts' / 'build_splade_index.py').exists()

    def test_pipeline_has_splade_method(self):
        from rag.pipeline import RAGPipeline
        p = RAGPipeline()
        assert hasattr(p, '_keyword_score_splade')

    def test_splade_fallback_to_bm25(self):
        """When SPLADE is not loaded, should fall back to BM25."""
        from rag.pipeline import RAGPipeline
        p = RAGPipeline()
        p._splade_index = None
        p._splade_model = None
        p.verses = [{"text": "test verse", "meaning": "", "topic": "", "scripture": "Test"}]
        p._precompute_bm25_stats()
        # Should not crash, falls back to BM25
        result = p._keyword_score_splade("karma")
        assert isinstance(result, np.ndarray)


class TestPhase3SanskritOntology:
    """Item 3.3: Sanskrit Concept Ontology"""

    def test_service_exists(self):
        from services.concept_ontology import ConceptOntology, get_concept_ontology
        ontology = get_concept_ontology()
        assert isinstance(ontology, ConceptOntology)
        assert ontology.available is True

    def test_detect_concepts(self):
        from services.concept_ontology import get_concept_ontology
        ontology = get_concept_ontology()
        # "karma" should be detected
        detected = ontology.detect_concepts("what is nishkama karma in daily life")
        assert len(detected) > 0
        assert "Nishkama Karma" in detected or "Karma" in detected

    def test_get_related_concepts(self):
        from services.concept_ontology import get_concept_ontology
        ontology = get_concept_ontology()
        related = ontology.get_related_concepts("nishkama karma", depth=2)
        assert len(related) > 0
        # Should include related concepts like Karma, Moksha, Svadharma
        related_lower = [r.lower() for r in related]
        assert any("karma" in r or "moksha" in r or "svadharma" in r for r in related_lower), \
            f"Expected karma/moksha/svadharma in related: {related}"

    def test_unknown_concept_returns_empty(self):
        from services.concept_ontology import get_concept_ontology
        ontology = get_concept_ontology()
        related = ontology.get_related_concepts("xyznonexistent")
        assert related == []

    def test_seed_graph_has_nodes_and_edges(self):
        from services.concept_ontology import get_concept_ontology
        ontology = get_concept_ontology()
        assert ontology._graph is not None
        assert ontology._graph.number_of_nodes() >= 100, f"Only {ontology._graph.number_of_nodes()} nodes (need 100+)"
        assert ontology._graph.number_of_edges() >= 100, f"Only {ontology._graph.number_of_edges()} edges (need 100+)"

    def test_expanded_concept_categories(self):
        """Verify expanded SCO covers all major concept categories."""
        from services.concept_ontology import get_concept_ontology
        ontology = get_concept_ontology()
        # Must detect concepts across all categories
        assert ontology.detect_concepts("dosha vata pitta kapha")  # ayurveda
        assert ontology.detect_concepts("yajna puja havan")  # ritual
        assert ontology.detect_concepts("grihastha vanaprastha")  # life stages
        assert ontology.detect_concepts("kundalini asana pranayama")  # yoga extended
        assert ontology.detect_concepts("guru diksha mantra")  # bhakti extended


# =====================================================================
# INTEGRATION: Full validate() chain with all 6 gates
# =====================================================================

class TestFullValidationChain:
    """End-to-end test of the 6-gate validation pipeline."""

    def test_all_6_gates_in_order(self):
        from services.context_validator import ContextValidator
        from models.session import IntentType

        cv = ContextValidator()
        docs = [
            # Good doc — should survive all gates
            {"final_score": 0.9, "text": "The Bhagavad Gita teaches nishkama karma", "scripture": "Bhagavad Gita", "type": "scripture", "tradition": "vedanta"},
            # Low score — Gate 1 drops
            {"final_score": 0.05, "text": "Some low relevance text", "scripture": "Unknown", "type": "scripture", "tradition": "general"},
            # Empty text — Gate 2 drops
            {"final_score": 0.7, "text": "", "scripture": "Test", "type": "scripture", "tradition": "vedanta"},
            # Temple doc for non-temple query — Gate 3 drops
            {"final_score": 0.8, "text": "Temple located at road near complex", "scripture": "Hindu Temples", "type": "temple", "tradition": "kshetra"},
            # Good Ramayana doc
            {"final_score": 0.75, "text": "Rama's journey through the forest teaches us patience", "scripture": "Ramayana", "type": "scripture", "tradition": "itihasa"},
        ]
        result = cv.validate(
            docs=docs,
            intent=IntentType.SEEKING_GUIDANCE,
            query="how to practice detachment",
            min_score=0.28,
        )
        # Should keep the good Gita doc and good Ramayana doc
        assert len(result) >= 1
        assert len(result) <= 3  # max_docs default
        # Temple doc should be removed
        assert not any(d.get("type") == "temple" for d in result)
        # Low score doc should be removed
        assert not any(d.get("final_score", 0) < 0.1 for d in result)


# =====================================================================
# Requirements check
# =====================================================================

class TestRequirements:
    """Verify new dependencies are listed."""

    def test_aiosqlite_in_requirements(self):
        with open(Path(__file__).parent.parent / 'requirements.txt') as f:
            reqs = f.read()
        assert 'aiosqlite' in reqs

    def test_networkx_in_requirements(self):
        with open(Path(__file__).parent.parent / 'requirements.txt') as f:
            reqs = f.read()
        assert 'networkx' in reqs


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
