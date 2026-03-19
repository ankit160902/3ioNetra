#!/usr/bin/env python3
"""
Data Quality Diagnostic Report for 3ioNetra Scripture Data

Analyzes verses.json and embeddings.npy for completeness, consistency,
and potential issues. Prints a formatted report to stdout.

Usage:
    cd backend && python scripts/data_quality_report.py
"""

import json
import sys
import os
import random
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
VERSES_PATH = BACKEND_DIR / "data" / "processed" / "verses.json"
EMBEDDINGS_PATH = BACKEND_DIR / "data" / "processed" / "embeddings.npy"

# Fields we expect every verse to have
EXPECTED_FIELDS = [
    "id", "text", "meaning", "sanskrit", "transliteration",
    "topic", "scripture", "reference", "type", "source",
]

SAMPLE_SIZE = 100  # number of embedding rows to sample for health checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hr(char="=", width=80):
    return char * width


def section(title):
    print(f"\n{hr()}")
    print(f"  {title}")
    print(hr())


def field_is_filled(value):
    """Return True if a field has meaningful content."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

def load_data():
    """Load verses.json and embeddings.npy, return (verses_list, metadata_dict, embeddings_array)."""
    if not VERSES_PATH.exists():
        print(f"ERROR: verses.json not found at {VERSES_PATH}")
        sys.exit(1)
    if not EMBEDDINGS_PATH.exists():
        print(f"ERROR: embeddings.npy not found at {EMBEDDINGS_PATH}")
        sys.exit(1)

    with open(VERSES_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Support both list format and dict-with-verses-key format
    if isinstance(raw, dict):
        verses = raw.get("verses", [])
        metadata = raw.get("metadata", {})
    elif isinstance(raw, list):
        verses = raw
        metadata = {}
    else:
        print("ERROR: Unexpected verses.json root type:", type(raw).__name__)
        sys.exit(1)

    embeddings = np.load(str(EMBEDDINGS_PATH), mmap_mode="r")
    return verses, metadata, embeddings


# ---------------------------------------------------------------------------
# 2. Total counts
# ---------------------------------------------------------------------------

def report_totals(verses, metadata, embeddings):
    section("1. TOTAL COUNTS")
    num_verses = len(verses)
    num_embeddings = embeddings.shape[0]
    emb_dim = embeddings.shape[1] if embeddings.ndim == 2 else "N/A"

    scriptures = set()
    for v in verses:
        s = v.get("scripture")
        if s:
            scriptures.add(s)

    meta_scriptures = metadata.get("scriptures", [])
    meta_total = metadata.get("total_verses", "N/A")
    meta_dim = metadata.get("embedding_dim", "N/A")
    meta_model = metadata.get("embedding_model", "N/A")

    print(f"  Verses in JSON          : {num_verses:,}")
    print(f"  Embedding rows          : {num_embeddings:,}")
    print(f"  Embedding dimension     : {emb_dim}")
    print(f"  Embedding dtype         : {embeddings.dtype}")
    print(f"  Unique scriptures       : {len(scriptures)}")
    print(f"  Metadata total_verses   : {meta_total}")
    print(f"  Metadata embedding_dim  : {meta_dim}")
    print(f"  Metadata embedding_model: {meta_model}")
    if meta_scriptures:
        print(f"  Metadata scriptures     : {', '.join(meta_scriptures)}")

    return num_verses, num_embeddings, emb_dim, scriptures


# ---------------------------------------------------------------------------
# 3. Schema completeness & fill rates
# ---------------------------------------------------------------------------

def report_field_fill_rates(verses):
    section("2. FIELD FILL RATES")

    total = len(verses)
    if total == 0:
        print("  No verses to analyze.")
        return

    # Collect all keys that appear in any verse
    all_keys = set()
    for v in verses:
        all_keys.update(v.keys())

    # Count filled values per field
    filled_counts = Counter()
    for v in verses:
        for key in all_keys:
            if field_is_filled(v.get(key)):
                filled_counts[key] += 1

    # Sort: expected fields first (in order), then others alphabetically
    ordered_keys = []
    for f in EXPECTED_FIELDS:
        if f in all_keys:
            ordered_keys.append(f)
    for k in sorted(all_keys):
        if k not in ordered_keys:
            ordered_keys.append(k)

    print(f"  {'Field':<22} {'Filled':>8} {'Empty':>8} {'Fill %':>8} {'Empty %':>8}")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    low_fill_fields = []
    for key in ordered_keys:
        filled = filled_counts.get(key, 0)
        empty = total - filled
        fill_pct = 100.0 * filled / total
        empty_pct = 100.0 * empty / total
        marker = ""
        if key in EXPECTED_FIELDS and fill_pct < 50.0:
            marker = " <-- LOW"
            low_fill_fields.append((key, fill_pct))
        print(f"  {key:<22} {filled:>8,} {empty:>8,} {fill_pct:>7.1f}% {empty_pct:>7.1f}%{marker}")

    return low_fill_fields


# ---------------------------------------------------------------------------
# 4. Per-scripture breakdown
# ---------------------------------------------------------------------------

def report_scripture_breakdown(verses):
    section("3. PER-SCRIPTURE BREAKDOWN")

    total = len(verses)
    if total == 0:
        print("  No verses to analyze.")
        return

    scripture_counts = Counter()
    for v in verses:
        s = v.get("scripture", "(none)")
        scripture_counts[s] += 1

    print(f"  {'Scripture':<40} {'Count':>8} {'% of Total':>10}")
    print(f"  {'-'*40} {'-'*8} {'-'*10}")

    for scripture, count in scripture_counts.most_common():
        pct = 100.0 * count / total
        print(f"  {scripture:<40} {count:>8,} {pct:>9.1f}%")


# ---------------------------------------------------------------------------
# 5. Topic distribution (top 20)
# ---------------------------------------------------------------------------

def report_topic_distribution(verses):
    section("4. TOPIC DISTRIBUTION (Top 20)")

    topic_counts = Counter()
    no_topic = 0
    for v in verses:
        t = v.get("topic")
        if field_is_filled(t):
            topic_counts[t] += 1
        else:
            no_topic += 1

    total = len(verses)
    print(f"  Verses with topic    : {total - no_topic:,} ({100.0*(total - no_topic)/total:.1f}%)")
    print(f"  Verses without topic : {no_topic:,} ({100.0*no_topic/total:.1f}%)")
    print(f"  Unique topics        : {len(topic_counts):,}")
    print()

    print(f"  {'Topic':<45} {'Count':>8} {'%':>7}")
    print(f"  {'-'*45} {'-'*8} {'-'*7}")
    for topic, count in topic_counts.most_common(20):
        pct = 100.0 * count / total
        display_topic = topic if len(topic) <= 44 else topic[:41] + "..."
        print(f"  {display_topic:<45} {count:>8,} {pct:>6.1f}%")

    if len(topic_counts) > 20:
        remaining = sum(c for _, c in topic_counts.most_common()[20:])
        print(f"  {'... (remaining topics)':<45} {remaining:>8,}")


# ---------------------------------------------------------------------------
# 6. Embedding health check
# ---------------------------------------------------------------------------

def report_embedding_health(embeddings):
    section("5. EMBEDDING HEALTH CHECK")

    num_rows, dim = embeddings.shape
    sample_n = min(SAMPLE_SIZE, num_rows)

    random.seed(42)
    sample_indices = sorted(random.sample(range(num_rows), sample_n))

    nan_count = 0
    zero_count = 0
    norms = []

    for idx in sample_indices:
        row = np.array(embeddings[idx], dtype=np.float64)  # copy from mmap
        if np.any(np.isnan(row)):
            nan_count += 1
        if np.allclose(row, 0.0):
            zero_count += 1
        norm = float(np.linalg.norm(row))
        norms.append(norm)

    norms_arr = np.array(norms)
    norm_mean = float(np.mean(norms_arr))
    norm_std = float(np.std(norms_arr))
    norm_min = float(np.min(norms_arr))
    norm_max = float(np.max(norms_arr))

    # Check how many are approximately unit-normalized (within 5%)
    near_unit = int(np.sum(np.abs(norms_arr - 1.0) < 0.05))

    print(f"  Sample size           : {sample_n} random rows")
    print(f"  Rows with NaN         : {nan_count} / {sample_n}", end="")
    print("  [OK]" if nan_count == 0 else "  [WARNING]")
    print(f"  Zero vectors          : {zero_count} / {sample_n}", end="")
    print("  [OK]" if zero_count == 0 else "  [WARNING]")
    print(f"  L2 norm mean          : {norm_mean:.6f}")
    print(f"  L2 norm std           : {norm_std:.6f}")
    print(f"  L2 norm range         : [{norm_min:.6f}, {norm_max:.6f}]")
    print(f"  Near unit-norm (|n-1|<0.05) : {near_unit} / {sample_n}", end="")
    if near_unit == sample_n:
        print("  [OK - all normalized]")
    elif near_unit > sample_n * 0.9:
        print("  [OK - mostly normalized]")
    else:
        print("  [WARNING - many not normalized]")

    issues = []
    if nan_count > 0:
        issues.append(f"Found {nan_count} rows with NaN values in sample")
    if zero_count > 0:
        issues.append(f"Found {zero_count} zero vectors in sample")
    if norm_std > 0.1:
        issues.append(f"High norm variance (std={norm_std:.4f}) - embeddings may not be normalized")

    return issues


# ---------------------------------------------------------------------------
# 7. Verse/embedding alignment
# ---------------------------------------------------------------------------

def report_alignment(num_verses, num_embeddings):
    section("6. VERSE / EMBEDDING ALIGNMENT")

    if num_verses == num_embeddings:
        print(f"  Verses: {num_verses:,}  |  Embeddings: {num_embeddings:,}  |  ALIGNED [OK]")
        return []
    else:
        diff = abs(num_verses - num_embeddings)
        print(f"  Verses: {num_verses:,}  |  Embeddings: {num_embeddings:,}  |  MISMATCH [WARNING]")
        print(f"  Difference: {diff:,} ({'more verses' if num_verses > num_embeddings else 'more embeddings'})")
        return [f"Verse/embedding count mismatch: {num_verses} vs {num_embeddings} (diff={diff})"]


# ---------------------------------------------------------------------------
# 8. Problematic verses
# ---------------------------------------------------------------------------

def report_problematic_verses(verses):
    section("7. PROBLEMATIC VERSES")

    empty_text = []
    short_text = []
    duplicate_refs = []

    ref_counter = Counter()
    for i, v in enumerate(verses):
        text = v.get("text", "")
        ref = v.get("reference", "")

        # Empty text
        if not field_is_filled(text):
            empty_text.append(i)

        # Very short text (< 10 chars)
        elif isinstance(text, str) and len(text.strip()) < 10:
            short_text.append((i, text.strip(), v.get("scripture", ""), v.get("reference", "")))

        # Track references for duplicate check
        if field_is_filled(ref):
            ref_counter[ref] += 1

    # Find duplicates
    for ref, count in ref_counter.items():
        if count > 1:
            duplicate_refs.append((ref, count))

    # Report empty text
    print(f"  Empty text fields     : {len(empty_text):,}", end="")
    print("  [OK]" if len(empty_text) == 0 else "  [WARNING]")
    if empty_text and len(empty_text) <= 10:
        for idx in empty_text:
            v = verses[idx]
            print(f"    - index {idx}: scripture={v.get('scripture')}, ref={v.get('reference')}")
    elif empty_text:
        for idx in empty_text[:5]:
            v = verses[idx]
            print(f"    - index {idx}: scripture={v.get('scripture')}, ref={v.get('reference')}")
        print(f"    ... and {len(empty_text) - 5} more")

    # Report short text
    print(f"  Very short text (<10) : {len(short_text):,}", end="")
    print("  [OK]" if len(short_text) == 0 else "  [WARNING]")
    if short_text:
        show = short_text[:10]
        for idx, text, scripture, ref in show:
            display_text = repr(text) if len(text) <= 40 else repr(text[:37] + "...")
            print(f"    - index {idx}: {display_text} [{scripture} | {ref}]")
        if len(short_text) > 10:
            print(f"    ... and {len(short_text) - 10} more")

    # Report duplicate references
    print(f"  Duplicate references  : {len(duplicate_refs):,}", end="")
    print("  [OK]" if len(duplicate_refs) == 0 else "  [WARNING]")
    if duplicate_refs:
        dup_sorted = sorted(duplicate_refs, key=lambda x: -x[1])
        show = dup_sorted[:10]
        for ref, count in show:
            display_ref = ref if len(ref) <= 55 else ref[:52] + "..."
            print(f"    - {display_ref} (x{count})")
        if len(duplicate_refs) > 10:
            total_dup_verses = sum(c for _, c in duplicate_refs)
            print(f"    ... and {len(duplicate_refs) - 10} more duplicate refs ({total_dup_verses:,} total duplicate verses)")

    issues = []
    if empty_text:
        issues.append(f"{len(empty_text)} verses have empty text fields")
    if short_text:
        issues.append(f"{len(short_text)} verses have very short text (<10 chars)")
    if duplicate_refs:
        issues.append(f"{len(duplicate_refs)} references appear more than once")
    return issues


# ---------------------------------------------------------------------------
# 9. Summary & recommendations
# ---------------------------------------------------------------------------

def print_summary(all_issues, low_fill_fields):
    section("8. SUMMARY & RECOMMENDATIONS")

    if not all_issues and not low_fill_fields:
        print("  All checks passed. Data looks healthy.")
        print()
        return

    issue_num = 0

    if low_fill_fields:
        for field, pct in low_fill_fields:
            issue_num += 1
            print(f"  [{issue_num}] LOW FILL: '{field}' is only {pct:.1f}% filled.")
            if field == "meaning":
                print(f"       -> Consider enriching verses with meanings/translations")
                print(f"          to improve RAG quality and LLM context.")
            elif field == "transliteration":
                print(f"       -> Adding transliterations would help multilingual search")
                print(f"          and accessibility for non-Sanskrit readers.")
            elif field == "sanskrit":
                print(f"       -> Populating original Sanskrit text improves verse")
                print(f"          citation accuracy.")
            elif field == "topic":
                print(f"       -> Topic tags drive intent-based filtering in ContextValidator.")
                print(f"          Missing topics reduce retrieval precision.")
            else:
                print(f"       -> Filling this field may improve search and response quality.")

    for issue in all_issues:
        issue_num += 1
        print(f"  [{issue_num}] {issue}")
        if "mismatch" in issue.lower():
            print(f"       -> Re-run ingest_all_data.py to regenerate aligned data.")
        elif "NaN" in issue:
            print(f"       -> Investigate embedding generation; NaN values will break")
            print(f"          similarity search. Re-embed affected rows.")
        elif "zero vector" in issue.lower():
            print(f"       -> Zero vectors will match everything equally. Re-embed")
            print(f"          or remove these rows.")
        elif "empty text" in issue.lower():
            print(f"       -> Remove or fill empty-text verses; they waste embedding")
            print(f"          slots and can pollute search results.")
        elif "short text" in issue.lower():
            print(f"       -> Very short texts produce low-quality embeddings.")
            print(f"          Consider merging with adjacent verses or removing.")
        elif "duplicate" in issue.lower():
            print(f"       -> Duplicates inflate results and waste embedding space.")
            print(f"          Deduplicate in the ingestion pipeline.")
        elif "not normalized" in issue.lower() or "norm variance" in issue.lower():
            print(f"       -> Non-unit embeddings affect cosine similarity accuracy.")
            print(f"          Normalize during ingestion with model.encode(normalize=True).")

    print()
    print(f"  Total issues found: {issue_num}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(hr("=", 80))
    print("  3ioNetra Data Quality Diagnostic Report")
    print(hr("=", 80))

    # Load
    verses, metadata, embeddings = load_data()

    all_issues = []

    # 1. Totals
    num_verses, num_embeddings, emb_dim, scriptures = report_totals(verses, metadata, embeddings)

    # 2. Field fill rates
    low_fill_fields = report_field_fill_rates(verses)

    # 3. Scripture breakdown
    report_scripture_breakdown(verses)

    # 4. Topic distribution
    report_topic_distribution(verses)

    # 5. Embedding health
    emb_issues = report_embedding_health(embeddings)
    all_issues.extend(emb_issues)

    # 6. Alignment
    align_issues = report_alignment(num_verses, num_embeddings)
    all_issues.extend(align_issues)

    # 7. Problematic verses
    verse_issues = report_problematic_verses(verses)
    all_issues.extend(verse_issues)

    # 8. Summary
    print_summary(all_issues, low_fill_fields or [])

    print(hr("=", 80))
    print("  Report complete.")
    print(hr("=", 80))


if __name__ == "__main__":
    main()
