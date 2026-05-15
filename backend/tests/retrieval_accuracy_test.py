"""
Retrieval Accuracy Test — Systematic evaluation of RAG pipeline retrieval quality.

Runs 100 benchmark queries against the RAG pipeline and measures:
- Hit@K, Precision@K, Recall@K, MRR
- Scripture-level accuracy
- Temple contamination rate
- Meditation template noise rate
- Per-category and per-language breakdowns
- Ablation tests (min_score, top_k, intent)

Usage:
    cd backend && python3 tests/retrieval_accuracy_test.py
"""

import asyncio
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.pipeline import RAGPipeline
from models.session import IntentType

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BENCHMARK = "retrieval_benchmark_250.json"
BENCHMARK_PATH = Path(__file__).parent / "benchmarks" / (
    sys.argv[sys.argv.index("--benchmark") + 1] if "--benchmark" in sys.argv
    else _DEFAULT_BENCHMARK
)
RESULTS_PATH = Path(__file__).parent / "retrieval_accuracy_results.json"
REPORT_PATH = Path(__file__).parent / "retrieval_accuracy_report.md"

# Map categories to likely intents for the search call
CATEGORY_INTENT_MAP = {
    "dharma": IntentType.SEEKING_GUIDANCE,
    "grief": IntentType.EXPRESSING_EMOTION,
    "karma": IntentType.SEEKING_GUIDANCE,
    "meditation": IntentType.SEEKING_GUIDANCE,
    "anger": IntentType.EXPRESSING_EMOTION,
    "soul/atman": IntentType.ASKING_INFO,
    "liberation/moksha": IntentType.SEEKING_GUIDANCE,
    "family": IntentType.SEEKING_GUIDANCE,
    "devotion": IntentType.SEEKING_GUIDANCE,
    "temple": IntentType.ASKING_INFO,
    "yoga": IntentType.SEEKING_GUIDANCE,
    "ayurveda": IntentType.ASKING_INFO,
    "death": IntentType.EXPRESSING_EMOTION,
    "duty": IntentType.SEEKING_GUIDANCE,
    "love": IntentType.SEEKING_GUIDANCE,
    "fear": IntentType.EXPRESSING_EMOTION,
    "health": IntentType.ASKING_INFO,
    "relationships": IntentType.EXPRESSING_EMOTION,
    "self-worth": IntentType.EXPRESSING_EMOTION,
    "anxiety": IntentType.EXPRESSING_EMOTION,
    "spiritual_practice": IntentType.SEEKING_GUIDANCE,
    "faith": IntentType.EXPRESSING_EMOTION,
    "digital_life": IntentType.EXPRESSING_EMOTION,
    "parenting": IntentType.SEEKING_GUIDANCE,
    "narrative": IntentType.ASKING_INFO,
    "mantra": IntentType.SEEKING_GUIDANCE,
    "off_topic": IntentType.OTHER,
    "procedural": IntentType.SEEKING_GUIDANCE,
    "shame": IntentType.EXPRESSING_EMOTION,
    "guilt": IntentType.EXPRESSING_EMOTION,
    "jealousy": IntentType.EXPRESSING_EMOTION,
    "loneliness": IntentType.EXPRESSING_EMOTION,
    "frustration": IntentType.EXPRESSING_EMOTION,
    "confusion": IntentType.EXPRESSING_EMOTION,
    "hopelessness": IntentType.EXPRESSING_EMOTION,
    "addiction": IntentType.SEEKING_GUIDANCE,
    "pregnancy_fertility": IntentType.SEEKING_GUIDANCE,
    "ethics_moral": IntentType.SEEKING_GUIDANCE,
    "habits_lust": IntentType.SEEKING_GUIDANCE,
    "career_work": IntentType.SEEKING_GUIDANCE,
    "education_exam": IntentType.SEEKING_GUIDANCE,
    "financial_stress": IntentType.EXPRESSING_EMOTION,
    "cross_scripture": IntentType.ASKING_INFO,
    "edge_typo": IntentType.SEEKING_GUIDANCE,
    "edge_codeswitching": IntentType.SEEKING_GUIDANCE,
    "edge_short": IntentType.SEEKING_GUIDANCE,
    "edge_long": IntentType.EXPRESSING_EMOTION,
    "edge_adversarial": IntentType.OTHER,
    "edge_emoji_caps": IntentType.EXPRESSING_EMOTION,
    "story_narrative": IntentType.ASKING_INFO,
    "mantra_specific": IntentType.SEEKING_GUIDANCE,
    "ayurveda_specific": IntentType.ASKING_INFO,
}


# ---------------------------------------------------------------------------
# Ground Truth Matching
# ---------------------------------------------------------------------------

def extract_bg_verse_number(text: str) -> Optional[str]:
    """Extract chapter.verse from a BG verse's text field (e.g., '2.47 Thy right...' -> '2.47')."""
    m = re.match(r"^(\d+\.\d+)", text.strip())
    return m.group(1) if m else None


def normalize_reference(ref: str) -> str:
    """Normalize a ground-truth reference for matching."""
    return ref.strip().lower()


def _strip_scripture_qualifier(name: str) -> str:
    """Strip parenthetical qualifiers: 'charaka samhita (ayurveda)' → 'charaka samhita'."""
    return re.sub(r"\s*\(.*?\)\s*", "", name).strip()


def _scripture_names_match(verse_scripture: str, gt_lower: str) -> bool:
    """Check if scripture names match, handling qualifier differences.

    Handles cases like:
    - verse_scripture="charaka samhita (ayurveda)" vs gt_lower="charaka samhita 1.1"
    - verse_scripture="bhagavad gita" vs gt_lower="bhagavad gita 2.47"
    """
    # Direct check: verse scripture name appears in ground truth
    if verse_scripture in gt_lower:
        return True
    # Strip qualifiers from verse scripture and check again
    stripped = _strip_scripture_qualifier(verse_scripture)
    if stripped and stripped in gt_lower:
        return True
    # Extract scripture name from gt_ref (everything before a number pattern)
    gt_scripture_match = re.match(r"^([a-z\s]+?)(?:\s+\d|\s*$)", gt_lower)
    if gt_scripture_match:
        gt_scripture_name = gt_scripture_match.group(1).strip()
        if gt_scripture_name and gt_scripture_name in verse_scripture:
            return True
    return False


def does_verse_match_reference(verse: Dict, gt_ref: str, match_mode: str = "exact") -> bool:
    """
    Check if a retrieved verse matches a ground-truth reference.

    Match strategies:
    - For 'Bhagavad Gita X.Y': extract verse number from text field
    - For 'Temple: ...': substring match on temple name in verse text/reference
    - For 'Ramayana ...': match scripture + kanda + section.verse in reference
    - For 'Patanjali Yoga Sutras ...': match in reference field
    - For 'Rig Veda / Atharva Veda ...': match in reference field
    - For scripture_level match_mode: just check scripture name
    - For chapter_level match_mode: check scripture + chapter number
    """
    gt_lower = gt_ref.lower().strip()
    verse_scripture = (verse.get("scripture") or "").lower()
    verse_ref = (verse.get("reference") or "").lower()
    verse_text = (verse.get("text") or "").lower()
    verse_source = (verse.get("source") or "").lower()

    # Concept doc matching: "Concept — X" ground truth matches curated_concept docs by reference
    if gt_lower.startswith("concept"):
        return gt_lower in verse_ref

    # If retrieved doc is a curated concept, match by scripture presence in ground truth
    if verse_source == "curated_concept" and match_mode == "scripture_level":
        if verse_scripture and _scripture_names_match(verse_scripture, gt_lower):
            return True

    # Scripture-level matching (for epics/narratives where exact verse matching is unreliable)
    if match_mode == "scripture_level":
        if gt_lower.startswith("temple:"):
            # For temple refs at scripture level, accept any temple doc
            if verse.get("type") == "temple" or "temple" in verse_scripture:
                return True
            return False
        # Check if the scripture names match (handles "Charaka Samhita (Ayurveda)" vs "Charaka Samhita")
        if verse_scripture and _scripture_names_match(verse_scripture, gt_lower):
            return True
        return False

    # Chapter-level matching (for concept queries where any verse from the right chapter counts)
    if match_mode == "chapter_level":
        if gt_lower.startswith("bhagavad gita"):
            if "bhagavad gita" not in verse_scripture:
                return False
            m = re.search(r"bhagavad gita\s+(\d+)\.", gt_lower)
            if m:
                expected_ch = m.group(1)
                actual_cv = extract_bg_verse_number(verse.get("text", ""))
                if actual_cv and actual_cv.startswith(expected_ch + "."):
                    return True
            return False
        if gt_lower.startswith("patanjali"):
            if "patanjali" not in verse_scripture:
                return False
            m = re.search(r"patanjali yoga sutras\s+(\d+)\.", gt_lower)
            if m:
                expected_ch = m.group(1)
                m2 = re.search(r"(\d+)\.", verse_ref)
                if m2 and m2.group(1) == expected_ch:
                    return True
            return False
        # For other scriptures, fall through to exact matching

    # Temple references: "Temple: Kashi Vishwanath (Uttar Pradesh)"
    if gt_lower.startswith("temple:"):
        temple_name = gt_lower.replace("temple:", "").strip()
        # Extract just the temple name (before the parenthetical)
        paren_idx = temple_name.find("(")
        if paren_idx > 0:
            temple_name_short = temple_name[:paren_idx].strip()
        else:
            temple_name_short = temple_name

        if verse.get("type") == "temple":
            if temple_name_short in verse_text or temple_name_short in verse_ref:
                return True
            # Also check the verse field (temple name is often there)
            verse_verse = (verse.get("verse") or "").lower()
            if temple_name_short in verse_verse:
                return True
        return False

    # Bhagavad Gita references: "Bhagavad Gita 2.47"
    if gt_lower.startswith("bhagavad gita"):
        if "bhagavad gita" not in verse_scripture:
            return False
        # Extract expected chapter.verse
        m = re.search(r"bhagavad gita\s+(\d+\.\d+)", gt_lower)
        if not m:
            return False
        expected_cv = m.group(1)
        # Extract actual chapter.verse from text field
        actual_cv = extract_bg_verse_number(verse.get("text", ""))
        return actual_cv == expected_cv

    # Ramayana references: "Ramayana Ayodhya Kanda 16.10"
    if gt_lower.startswith("ramayana"):
        if "ramayana" not in verse_scripture:
            return False
        # Extract kanda and section.verse
        m = re.search(r"ramayana\s+(\w+\s+kanda)\s+(\d+\.\d+)", gt_lower)
        if m:
            expected_kanda = m.group(1).lower()
            expected_sv = m.group(2)
            # Check reference field
            if expected_kanda.split()[0] in verse_ref and expected_sv in verse_ref:
                return True
            # Also check chapter field
            verse_chapter = (verse.get("chapter") or "").lower()
            verse_section = verse.get("section", "")
            verse_vnum = verse.get("verse_number", "")
            if expected_kanda.split()[0] in verse_chapter:
                actual_sv = f"{verse_section}.{verse_vnum}"
                if actual_sv == expected_sv:
                    return True
        # Fallback: check if the kanda name appears in reference
        m2 = re.search(r"ramayana\s+(\w+)", gt_lower)
        if m2:
            kanda_word = m2.group(1).lower()
            if kanda_word in verse_ref or kanda_word in (verse.get("chapter") or "").lower():
                # Check verse number
                m3 = re.search(r"(\d+\.\d+)", gt_lower)
                if m3:
                    expected_sv = m3.group(1)
                    if expected_sv in verse_ref:
                        return True
        return False

    # Patanjali Yoga Sutras: "Patanjali Yoga Sutras 2.49"
    if gt_lower.startswith("patanjali"):
        if "patanjali" not in verse_scripture:
            return False
        m = re.search(r"patanjali yoga sutras\s+(\d+\.\d+)", gt_lower)
        if m:
            expected_sv = m.group(1)
            if expected_sv in verse_ref:
                return True
            # PYS references may be in format "yoga_sutras.transliteration"
            # Check text field for sutra numbering
            verse_text_start = (verse.get("text") or "")[:20]
            if expected_sv in verse_text_start:
                return True
        return False

    # Vedic references: "Rig Veda 10.97.1", "Atharva Veda 2.3.1"
    for veda_name in ["rig veda", "atharva veda", "yajur veda"]:
        if gt_lower.startswith(veda_name):
            if veda_name not in verse_scripture.lower():
                return False
            m = re.search(r"(\d+[\.\d]+)", gt_lower)
            if m:
                expected_num = m.group(1)
                if expected_num in verse_ref:
                    return True
                # For Vedic texts, accept sukta-level match
                # Ground truth "Rig Veda 7.59.12" should match data "Rig Veda 7.59"
                parts = expected_num.split(".")
                if len(parts) >= 3:
                    sukta_level = ".".join(parts[:2])
                    if sukta_level in verse_ref:
                        return True
            return False

    # Generic scripture-level match
    if gt_lower.startswith("sanatan scriptures"):
        return "sanatan" in verse_scripture

    if gt_lower.startswith("charaka samhita"):
        return "charaka" in verse_scripture

    if gt_lower.startswith("mahabharata"):
        return "mahabharata" in verse_scripture

    if gt_lower.startswith("meditation"):
        return "meditation" in verse_scripture

    # Fallback: check if ground truth reference appears as substring in verse reference
    if gt_lower in verse_ref:
        return True

    return False


# ---------------------------------------------------------------------------
# Metrics Computation
# ---------------------------------------------------------------------------

def compute_metrics(
    retrieved: List[Dict],
    gt_refs: List[str],
    match_mode: str = "exact",
    k_values: List[int] = [1, 3, 5, 7],
) -> Dict:
    """Compute IR metrics for a single query."""
    if not gt_refs:
        # Off-topic query: success if nothing relevant retrieved
        return {
            "hit@1": 0, "hit@3": 0, "hit@5": 0, "hit@7": 0,
            "precision@1": 0, "precision@3": 0, "precision@5": 0, "precision@7": 0,
            "recall@1": 0, "recall@3": 0, "recall@5": 0, "recall@7": 0,
            "mrr": 0, "off_topic": True,
            "num_retrieved": len(retrieved),
        }

    metrics = {"off_topic": False, "num_retrieved": len(retrieved)}

    # Find which positions have matches
    match_positions = []
    matched_refs = set()
    for rank, doc in enumerate(retrieved):
        for gt_ref in gt_refs:
            if gt_ref not in matched_refs and does_verse_match_reference(doc, gt_ref, match_mode):
                match_positions.append(rank)
                matched_refs.add(gt_ref)
                break

    # MRR
    if match_positions:
        metrics["mrr"] = 1.0 / (match_positions[0] + 1)
    else:
        metrics["mrr"] = 0.0

    # Hit@K, Precision@K, Recall@K
    for k in k_values:
        hits_in_k = sum(1 for pos in match_positions if pos < k)
        metrics[f"hit@{k}"] = 1.0 if hits_in_k > 0 else 0.0
        metrics[f"precision@{k}"] = hits_in_k / k
        metrics[f"recall@{k}"] = hits_in_k / len(gt_refs)

    return metrics


def compute_contamination_metrics(retrieved: List[Dict], category: str) -> Dict:
    """Compute temple contamination and meditation template noise metrics."""
    temple_docs = 0
    meditation_template_docs = 0

    for doc in retrieved:
        doc_type = (doc.get("type") or "").lower()
        scripture = (doc.get("scripture") or "").lower()

        if doc_type == "temple" or scripture == "hindu temples":
            temple_docs += 1

        if scripture == "meditation and mindfulness":
            meditation_template_docs += 1

    is_temple_query = category == "temple"

    return {
        "temple_docs": temple_docs,
        "temple_contamination": temple_docs > 0 and not is_temple_query,
        "meditation_template_docs": meditation_template_docs,
        "meditation_noise": meditation_template_docs > 0 and category not in ("meditation", "spiritual_practice"),
    }


def compute_scripture_accuracy(retrieved: List[Dict], gt_refs: List[str], k: int = 3) -> float:
    """Check if the correct scripture (not exact verse) appears in top K results."""
    if not gt_refs:
        return 0.0

    # Extract expected scriptures from ground truth
    expected_scriptures = set()
    for ref in gt_refs:
        ref_lower = ref.lower()
        if ref_lower.startswith("bhagavad gita"):
            expected_scriptures.add("bhagavad gita")
        elif ref_lower.startswith("ramayana"):
            expected_scriptures.add("ramayana")
        elif ref_lower.startswith("mahabharata"):
            expected_scriptures.add("mahabharata")
        elif ref_lower.startswith("patanjali"):
            expected_scriptures.add("patanjali yoga sutras")
        elif ref_lower.startswith("rig veda"):
            expected_scriptures.add("rig veda")
        elif ref_lower.startswith("atharva veda"):
            expected_scriptures.add("atharva veda")
        elif ref_lower.startswith("yajur veda"):
            expected_scriptures.add("yajur veda")
        elif ref_lower.startswith("temple:"):
            expected_scriptures.add("hindu temples")
        elif ref_lower.startswith("charaka samhita"):
            expected_scriptures.add("charaka samhita (ayurveda)")
        elif ref_lower.startswith("sanatan scriptures"):
            expected_scriptures.add("sanatan scriptures")
        elif ref_lower.startswith("meditation"):
            expected_scriptures.add("meditation and mindfulness")

    # Check top K results
    found = set()
    for doc in retrieved[:k]:
        doc_scripture = (doc.get("scripture") or "").lower()
        for exp in expected_scriptures:
            if exp in doc_scripture:
                found.add(exp)

    return len(found) / len(expected_scriptures) if expected_scriptures else 0.0


# ---------------------------------------------------------------------------
# Main Test Runner
# ---------------------------------------------------------------------------

async def run_baseline_test(
    pipeline: RAGPipeline,
    queries: List[Dict],
    top_k: int = 7,
    min_score: float = 0.12,
    use_intent: bool = True,
    label: str = "baseline",
) -> List[Dict]:
    """Run all queries through the pipeline and compute metrics."""
    results = []
    total = len(queries)

    _TEMPLE_KEYWORDS = {"temple", "mandir", "pilgrimage", "tirtha", "visit",
                        "darshan", "jyotirlinga", "shrine", "dham",
                        "मंदिर", "तीर्थ", "दर्शन", "ज्योतिर्लिंग", "धाम", "यात्रा"}

    _MEDITATION_KEYWORDS = {"meditation", "meditate", "dhyan", "dhyana", "ध्यान",
                            "mindfulness", "mindful", "vipassana",
                            "breathing exercise", "pranayama", "प्राणायाम"}

    for i, q in enumerate(queries):
        query_text = q["query"]
        category = q["category"]
        language = q.get("language", "en")
        gt_refs = q.get("relevant_references", [])
        alt_refs = q.get("alternative_references", [])
        all_gt_refs = gt_refs + alt_refs
        match_mode = q.get("match_mode", "exact")
        expect_empty = q.get("expect_empty", False)

        intent = CATEGORY_INTENT_MAP.get(category, IntentType.OTHER) if use_intent else None

        # Mirror production: exclude temple docs for non-temple queries
        query_lower = query_text.lower()
        is_temple_query = category == "temple" or any(kw in query_lower for kw in _TEMPLE_KEYWORDS)
        doc_type_filter = None if is_temple_query else ["temple"]

        print(f"  [{i+1}/{total}] {query_text[:60]}...", end="", flush=True)

        # Mirror production: exclude meditation templates unless query is about meditation
        is_meditation_query = any(kw in query_lower for kw in _MEDITATION_KEYWORDS)

        start = time.time()
        try:
            retrieved = await pipeline.search(
                query=query_text,
                top_k=top_k,
                intent=intent,
                min_score=min_score,
                language=language,
                doc_type_filter=doc_type_filter,
            )
            # Post-filter: drop meditation templates for non-meditation queries
            if not is_meditation_query:
                retrieved = [
                    doc for doc in retrieved
                    if not (
                        ("meditation" in (doc.get("scripture") or "").lower()
                         and "mindfulness" in (doc.get("scripture") or "").lower())
                        or (doc.get("source") or "").lower() == "meditation_template"
                    )
                ]
        except Exception as e:
            print(f" ERROR: {e}")
            retrieved = []
        elapsed = time.time() - start

        # Compute metrics (use all_gt_refs which includes alternatives)
        ir_metrics = compute_metrics(retrieved, all_gt_refs, match_mode)
        contamination = compute_contamination_metrics(retrieved, category)
        scripture_acc = compute_scripture_accuracy(retrieved, all_gt_refs, k=3)

        result = {
            "id": q["id"],
            "query": query_text,
            "language": language,
            "category": category,
            "match_mode": match_mode,
            "expect_empty": expect_empty,
            "ground_truth": gt_refs,
            "num_gt_refs": len(gt_refs),
            "retrieved_count": len(retrieved),
            "latency_ms": round(elapsed * 1000, 1),
            "retrieved_docs": [
                {
                    "rank": j + 1,
                    "scripture": doc.get("scripture", ""),
                    "reference": (doc.get("reference") or "")[:100],
                    "type": doc.get("type", ""),
                    "score": round(doc.get("score", 0), 4),
                    "final_score": round(doc.get("final_score", 0), 4),
                    "text_preview": (doc.get("text") or "")[:80],
                    "meaning_preview": (doc.get("meaning") or "")[:80],
                }
                for j, doc in enumerate(retrieved)
            ],
            **ir_metrics,
            "scripture_accuracy@3": scripture_acc,
            **contamination,
        }

        results.append(result)
        mrr_str = f"MRR={ir_metrics['mrr']:.2f}"
        hit3_str = f"Hit@3={'Y' if ir_metrics['hit@3'] else 'N'}"
        contam_str = ""
        if contamination["temple_contamination"]:
            contam_str = f" TEMPLE_CONTAM({contamination['temple_docs']})"
        if contamination["meditation_noise"]:
            contam_str += f" MED_NOISE({contamination['meditation_template_docs']})"
        print(f" {mrr_str} {hit3_str}{contam_str} [{elapsed:.1f}s]")

    return results


async def run_ablation_tests(
    pipeline: RAGPipeline,
    queries: List[Dict],
) -> Dict:
    """Run ablation tests on English benchmark queries (IDs 1-40)."""
    english_queries = [q for q in queries if q["id"] <= 40]
    ablation_results = {}

    # A1: Vary min_score
    print("\n--- Ablation A1: min_score thresholds ---")
    for min_score in [0.05, 0.10, 0.15, 0.20, 0.25]:
        print(f"\n  min_score={min_score}")
        results = await run_baseline_test(
            pipeline, english_queries, top_k=7, min_score=min_score,
            label=f"min_score_{min_score}"
        )
        agg = aggregate_metrics(results)
        ablation_results[f"min_score_{min_score}"] = agg
        print(f"  => MRR={agg['mrr']:.3f} Hit@3={agg['hit@3']:.1%} P@3={agg['precision@3']:.3f}")

    # A2: Vary top_k
    print("\n--- Ablation A2: top_k values ---")
    for top_k in [3, 5, 7, 10]:
        print(f"\n  top_k={top_k}")
        results = await run_baseline_test(
            pipeline, english_queries, top_k=top_k, min_score=0.12,
            label=f"top_k_{top_k}"
        )
        agg = aggregate_metrics(results)
        ablation_results[f"top_k_{top_k}"] = agg
        print(f"  => MRR={agg['mrr']:.3f} Hit@3={agg['hit@3']:.1%} P@3={agg['precision@3']:.3f}")

    # A3: No intent (disable intent-based weighting)
    print("\n--- Ablation A3: No intent weighting ---")
    results = await run_baseline_test(
        pipeline, english_queries, top_k=7, min_score=0.12, use_intent=False,
        label="no_intent"
    )
    agg = aggregate_metrics(results)
    ablation_results["no_intent"] = agg
    print(f"  => MRR={agg['mrr']:.3f} Hit@3={agg['hit@3']:.1%} P@3={agg['precision@3']:.3f}")

    return ablation_results


def aggregate_metrics(results: List[Dict]) -> Dict:
    """Aggregate metrics across all queries."""
    n = len(results)
    if n == 0:
        return {}

    agg = {
        "num_queries": n,
        "mrr": sum(r["mrr"] for r in results) / n,
        "hit@1": sum(r["hit@1"] for r in results) / n,
        "hit@3": sum(r["hit@3"] for r in results) / n,
        "hit@5": sum(r["hit@5"] for r in results) / n,
        "hit@7": sum(r["hit@7"] for r in results) / n,
        "precision@1": sum(r["precision@1"] for r in results) / n,
        "precision@3": sum(r["precision@3"] for r in results) / n,
        "precision@5": sum(r["precision@5"] for r in results) / n,
        "precision@7": sum(r["precision@7"] for r in results) / n,
        "recall@3": sum(r["recall@3"] for r in results) / n,
        "recall@7": sum(r["recall@7"] for r in results) / n,
        "scripture_accuracy@3": sum(r["scripture_accuracy@3"] for r in results) / n,
        "temple_contamination_count": sum(1 for r in results if r.get("temple_contamination")),
        "meditation_noise_count": sum(1 for r in results if r.get("meditation_noise")),
        "avg_latency_ms": sum(r["latency_ms"] for r in results) / n,
    }
    return agg


def aggregate_by_group(results: List[Dict], group_key: str) -> Dict[str, Dict]:
    """Aggregate metrics grouped by a key (category or language)."""
    groups = defaultdict(list)
    for r in results:
        groups[r[group_key]].append(r)

    return {k: aggregate_metrics(v) for k, v in sorted(groups.items())}


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_report(
    baseline_results: List[Dict],
    overall: Dict,
    by_category: Dict,
    by_language: Dict,
    ablation: Dict,
) -> str:
    """Generate a markdown report."""
    lines = []
    lines.append("# Retrieval Accuracy Test Report")
    lines.append(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total queries: {overall['num_queries']}")
    lines.append(f"Average latency: {overall['avg_latency_ms']:.0f}ms per query")

    # Overall metrics
    lines.append("\n## Overall Metrics\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| MRR | {overall['mrr']:.3f} |")
    lines.append(f"| Hit@1 | {overall['hit@1']:.1%} |")
    lines.append(f"| Hit@3 | {overall['hit@3']:.1%} |")
    lines.append(f"| Hit@5 | {overall['hit@5']:.1%} |")
    lines.append(f"| Hit@7 | {overall['hit@7']:.1%} |")
    lines.append(f"| Precision@3 | {overall['precision@3']:.3f} |")
    lines.append(f"| Recall@3 | {overall['recall@3']:.3f} |")
    lines.append(f"| Recall@7 | {overall['recall@7']:.3f} |")
    lines.append(f"| Scripture Accuracy@3 | {overall['scripture_accuracy@3']:.1%} |")

    # Contamination analysis
    lines.append("\n## Contamination Analysis\n")
    non_temple = [r for r in baseline_results if r["category"] != "temple"]
    temple_contam_queries = [r for r in non_temple if r.get("temple_contamination")]
    med_noise_queries = [r for r in baseline_results if r.get("meditation_noise")]

    lines.append(f"- **Temple contamination**: {len(temple_contam_queries)}/{len(non_temple)} non-temple queries have temple docs in results")
    if temple_contam_queries:
        lines.append("  - Affected queries:")
        for r in temple_contam_queries:
            lines.append(f"    - ID {r['id']}: \"{r['query'][:50]}\" ({r['temple_docs']} temple docs)")

    lines.append(f"- **Meditation template noise**: {len(med_noise_queries)} queries have meditation template docs")
    if med_noise_queries:
        lines.append("  - Affected queries:")
        for r in med_noise_queries:
            lines.append(f"    - ID {r['id']}: \"{r['query'][:50]}\" ({r['meditation_template_docs']} med docs)")

    # Per-category breakdown
    lines.append("\n## Per-Category Breakdown\n")
    lines.append("| Category | N | MRR | Hit@3 | P@3 | R@3 | Scr.Acc@3 | Temple Contam | Med Noise |")
    lines.append("|----------|---|-----|-------|-----|-----|-----------|---------------|-----------|")
    for cat, m in by_category.items():
        lines.append(
            f"| {cat} | {m['num_queries']} | {m['mrr']:.3f} | {m['hit@3']:.1%} | "
            f"{m['precision@3']:.3f} | {m['recall@3']:.3f} | {m['scripture_accuracy@3']:.1%} | "
            f"{m['temple_contamination_count']} | {m['meditation_noise_count']} |"
        )

    # Per-language breakdown
    lines.append("\n## Per-Language Breakdown\n")
    lines.append("| Language | N | MRR | Hit@3 | P@3 | R@3 | Scripture Acc@3 |")
    lines.append("|----------|---|-----|-------|-----|-----|-----------------|")
    for lang, m in by_language.items():
        lines.append(
            f"| {lang} | {m['num_queries']} | {m['mrr']:.3f} | {m['hit@3']:.1%} | "
            f"{m['precision@3']:.3f} | {m['recall@3']:.3f} | {m['scripture_accuracy@3']:.1%} |"
        )

    # Worst 10 queries
    lines.append("\n## Worst 10 Queries (by MRR)\n")
    # Exclude off-topic
    scored = [r for r in baseline_results if not r.get("expect_empty")]
    scored.sort(key=lambda x: x["mrr"])

    for r in scored[:10]:
        lines.append(f"### ID {r['id']}: \"{r['query']}\"")
        lines.append(f"- Category: {r['category']} | Language: {r['language']}")
        lines.append(f"- MRR: {r['mrr']:.3f} | Hit@3: {'Yes' if r['hit@3'] else 'No'} | Hit@7: {'Yes' if r['hit@7'] else 'No'}")
        lines.append(f"- Ground truth: {', '.join(r['ground_truth'][:5])}")
        lines.append(f"- Retrieved ({r['retrieved_count']} docs):")
        for d in r.get("retrieved_docs", [])[:5]:
            contam_flag = ""
            if d["type"] == "temple" and r["category"] != "temple":
                contam_flag = " **[TEMPLE CONTAM]**"
            if d["scripture"] == "Meditation and Mindfulness":
                contam_flag = " **[MED NOISE]**"
            lines.append(
                f"  {d['rank']}. [{d['scripture']}] {d['reference'][:60]} "
                f"(score={d['final_score']:.3f}){contam_flag}"
            )
            if d["text_preview"]:
                lines.append(f"     Text: {d['text_preview'][:70]}...")
        lines.append("")

    # Ablation results
    if ablation:
        lines.append("\n## Ablation Tests (English queries 1-40)\n")

        lines.append("### A1: min_score threshold\n")
        lines.append("| min_score | MRR | Hit@3 | P@3 | R@3 | Temple Contam | Med Noise |")
        lines.append("|-----------|-----|-------|-----|-----|---------------|-----------|")
        for key in sorted(k for k in ablation if k.startswith("min_score")):
            m = ablation[key]
            score = key.replace("min_score_", "")
            lines.append(
                f"| {score} | {m['mrr']:.3f} | {m['hit@3']:.1%} | "
                f"{m['precision@3']:.3f} | {m['recall@3']:.3f} | "
                f"{m['temple_contamination_count']} | {m['meditation_noise_count']} |"
            )

        lines.append("\n### A2: top_k values\n")
        lines.append("| top_k | MRR | Hit@3 | Hit@K | P@3 | R@K | Temple Contam | Med Noise |")
        lines.append("|-------|-----|-------|-------|-----|-----|---------------|-----------|")
        for key in sorted(k for k in ablation if k.startswith("top_k")):
            m = ablation[key]
            k_val = key.replace("top_k_", "")
            hit_k = m.get(f"hit@{k_val}", m.get("hit@7", 0))
            recall_k = m.get(f"recall@{k_val}", m.get("recall@7", 0))
            lines.append(
                f"| {k_val} | {m['mrr']:.3f} | {m['hit@3']:.1%} | {hit_k:.1%} | "
                f"{m['precision@3']:.3f} | {recall_k:.3f} | "
                f"{m['temple_contamination_count']} | {m['meditation_noise_count']} |"
            )

        lines.append("\n### A3: Intent weighting\n")
        if "no_intent" in ablation:
            m = ablation["no_intent"]
            # Find baseline for comparison
            baseline_key = "min_score_0.12" if "min_score_0.12" in ablation else None
            lines.append("| Config | MRR | Hit@3 | P@3 | Temple Contam | Med Noise |")
            lines.append("|--------|-----|-------|-----|---------------|-----------|")
            if baseline_key:
                b = ablation[baseline_key]
                lines.append(
                    f"| With intent | {b['mrr']:.3f} | {b['hit@3']:.1%} | "
                    f"{b['precision@3']:.3f} | {b['temple_contamination_count']} | {b['meditation_noise_count']} |"
                )
            lines.append(
                f"| No intent | {m['mrr']:.3f} | {m['hit@3']:.1%} | "
                f"{m['precision@3']:.3f} | {m['temple_contamination_count']} | {m['meditation_noise_count']} |"
            )

    # Improvement plan
    lines.append("\n## Improvement Plan\n")
    lines.append("Based on the test results, prioritized improvements:\n")

    if overall.get("temple_contamination_count", 0) > 3:
        lines.append("### P0: Temple Contamination Fix")
        lines.append("- Exclude `type: temple` from results unless query explicitly mentions temple/mandir/pilgrimage keywords")
        lines.append(f"- Impact: {overall['temple_contamination_count']} queries currently contaminated\n")

    if overall.get("meditation_noise_count", 0) > 2:
        lines.append("### P0: Meditation Template Cleanup")
        lines.append("- Remove or reclassify the 26 meditation template entries that match emotional queries")
        lines.append(f"- Impact: {overall['meditation_noise_count']} queries currently affected\n")

    if overall.get("mrr", 1) < 0.5:
        lines.append("### P1: Generate English Meanings")
        lines.append("- Use Gemini to batch-generate English summaries for top 2,000 Ramayana/Mahabharata/Veda verses")
        lines.append("- Currently 95.6% have empty `meaning` field, crippling BM25 and semantic search\n")

    if overall.get("scripture_accuracy@3", 1) < 0.7:
        lines.append("### P1: Reclassify Topics")
        lines.append("- Batch-classify verses out of 'Spiritual Wisdom' catch-all into specific topic categories")
        lines.append("- 94% of verses are currently tagged 'Spiritual Wisdom'\n")

    lines.append("### P2: Curated Narrative Documents")
    lines.append("- Create 50-100 synthetic English story summaries for key epic episodes")
    lines.append("- (Rama's exile, Hanuman's leap, Draupadi's disrobing, etc.)\n")

    lines.append("### P2: Separate Indices")
    lines.append("- Route queries to scripture vs temple vs procedural indices based on intent classification\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("  RETRIEVAL ACCURACY TEST")
    print("=" * 70)

    # Load benchmark
    if not BENCHMARK_PATH.exists():
        print(f"ERROR: Benchmark file not found: {BENCHMARK_PATH}")
        sys.exit(1)

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        queries = json.load(f)
    print(f"\nLoaded {len(queries)} benchmark queries from {BENCHMARK_PATH.name}")

    # Initialize pipeline
    print("\nInitializing RAG Pipeline...")
    pipeline = RAGPipeline()
    await pipeline.initialize()

    if not pipeline.available:
        print("ERROR: Pipeline not available. Ensure data/processed/ exists with verses.json + embeddings.npy")
        sys.exit(1)

    print(f"Pipeline ready: {len(pipeline.verses)} verses, dim={pipeline.dim}")

    # Run baseline test
    print(f"\n{'='*70}")
    print("  BASELINE TEST (100 queries, top_k=7, min_score=0.12)")
    print(f"{'='*70}\n")

    start_total = time.time()
    baseline_results = await run_baseline_test(pipeline, queries)
    total_time = time.time() - start_total

    # Compute aggregates
    overall = aggregate_metrics(baseline_results)
    by_category = aggregate_by_group(baseline_results, "category")
    by_language = aggregate_by_group(baseline_results, "language")

    # Print summary
    print(f"\n{'='*70}")
    print("  BASELINE SUMMARY")
    print(f"{'='*70}")
    print(f"  Total time: {total_time:.1f}s ({overall['avg_latency_ms']:.0f}ms/query avg)")
    print(f"  MRR:         {overall['mrr']:.3f}")
    print(f"  Hit@1:       {overall['hit@1']:.1%}")
    print(f"  Hit@3:       {overall['hit@3']:.1%}")
    print(f"  Hit@7:       {overall['hit@7']:.1%}")
    print(f"  Precision@3: {overall['precision@3']:.3f}")
    print(f"  Recall@3:    {overall['recall@3']:.3f}")
    print(f"  Recall@7:    {overall['recall@7']:.3f}")
    print(f"  Scr.Acc@3:   {overall['scripture_accuracy@3']:.1%}")
    print(f"  Temple Contam: {overall['temple_contamination_count']} queries")
    print(f"  Med Noise:     {overall['meditation_noise_count']} queries")

    # Run ablation tests
    print(f"\n{'='*70}")
    print("  ABLATION TESTS (English queries 1-40)")
    print(f"{'='*70}")

    ablation = await run_ablation_tests(pipeline, queries)

    # Save raw results
    output = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_queries": len(queries),
            "total_time_s": round(total_time, 1),
            "pipeline_verses": len(pipeline.verses),
            "pipeline_dim": pipeline.dim,
        },
        "overall": overall,
        "by_category": by_category,
        "by_language": by_language,
        "ablation": ablation,
        "per_query_results": baseline_results,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nRaw results saved to: {RESULTS_PATH}")

    # Generate report
    report = generate_report(baseline_results, overall, by_category, by_language, ablation)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to: {REPORT_PATH}")

    # Final verdict
    print(f"\n{'='*70}")
    if overall["mrr"] < 0.5 or overall["hit@3"] < 0.6:
        print("  VERDICT: RETRIEVAL ACCURACY NEEDS IMPROVEMENT")
        print(f"  MRR={overall['mrr']:.3f} (target >0.5) | Hit@3={overall['hit@3']:.1%} (target >60%)")
        print("  See improvement plan in report.")
    else:
        print("  VERDICT: RETRIEVAL ACCURACY ACCEPTABLE")
        print(f"  MRR={overall['mrr']:.3f} | Hit@3={overall['hit@3']:.1%}")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
