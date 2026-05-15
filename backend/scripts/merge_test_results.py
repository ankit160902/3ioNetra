#!/usr/bin/env python3
"""
merge_test_results.py

Merges test results from multiple JSON sources into one unified report:
  1. backend/tests/test_results_YYYYMMDD.json       (HTTP runner  - 219 tests)
  2. backend/tests/test_results_unit_YYYYMMDD.json   (unit tests   -  28 tests)
  3. frontend/test-results.json                      (Playwright E2E - 52 tests)

Merge strategy:
  - Start with every result from the HTTP runner as the baseline.
  - For each result in unit / E2E sources:
      * If its test ID already exists and the new status is strictly better,
        override the existing entry (keeps the better evidence).
      * If the test ID is new, append it.
  - Status priority (best -> worst): PASS > PARTIAL > FAIL > SKIP

Outputs:
  - Console summary with before / after comparison.
  - backend/tests/test_results_merged_YYYYMMDD.json
  - backend/tests/test_results_merged_YYYYMMDD.md
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parent.parent          # backend/
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"               # frontend/
TESTS_DIR = BACKEND_ROOT / "tests"

# ---------------------------------------------------------------------------
# Status priority (higher number = better)
# ---------------------------------------------------------------------------
STATUS_PRIORITY: Dict[str, int] = {
    "PASS": 4,
    "PARTIAL": 3,
    "FAIL": 2,
    "SKIP": 1,
}

ALL_STATUSES = ["PASS", "PARTIAL", "FAIL", "SKIP"]


def status_is_better(new_status: str, old_status: str) -> bool:
    """Return True when *new_status* is strictly better than *old_status*."""
    return STATUS_PRIORITY.get(new_status, 0) > STATUS_PRIORITY.get(old_status, 0)


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------

def _find_latest_by_pattern(directory: Path, pattern: str) -> Optional[Path]:
    """Find the file matching *pattern* with the most recent YYYYMMDD date tag.

    *pattern* should contain a single ``*`` where the date appears, e.g.
    ``test_results_*.json`` or ``test_results_unit_*.json``.
    """
    matches: List[Tuple[str, Path]] = []
    for filepath in sorted(directory.glob(pattern)):
        # Extract the YYYYMMDD portion from the filename.
        name = filepath.stem  # e.g. test_results_20260313
        date_match = re.search(r"(\d{8})", name)
        if date_match:
            matches.append((date_match.group(1), filepath))

    if not matches:
        return None

    # Sort by date descending and return the newest.
    matches.sort(key=lambda t: t[0], reverse=True)
    return matches[0][1]


def find_http_runner_file() -> Optional[Path]:
    """Locate the most recent ``test_results_YYYYMMDD.json`` (HTTP runner)."""
    # We want files that match test_results_YYYYMMDD.json but NOT
    # test_results_unit_YYYYMMDD.json or test_results_merged_YYYYMMDD.json.
    candidates: List[Tuple[str, Path]] = []
    for fp in TESTS_DIR.glob("test_results_*.json"):
        name = fp.stem
        # Skip unit and merged variants.
        if "unit" in name or "merged" in name:
            continue
        date_match = re.search(r"(\d{8})", name)
        if date_match:
            candidates.append((date_match.group(1), fp))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


def find_unit_test_file() -> Optional[Path]:
    """Locate the most recent ``test_results_unit_YYYYMMDD.json``."""
    return _find_latest_by_pattern(TESTS_DIR, "test_results_unit_*.json")


def find_e2e_file() -> Optional[Path]:
    """Locate ``frontend/test-results.json`` if it exists."""
    candidate = FRONTEND_ROOT / "test-results.json"
    return candidate if candidate.is_file() else None


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Dict[str, Any]:
    """Load and return a JSON file, or exit with an error message."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: failed to read {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def results_by_id(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index a list of result dicts by their ``id`` field."""
    index: Dict[str, Dict[str, Any]] = {}
    for entry in results:
        tid = entry.get("id", "")
        if tid:
            index[tid] = entry
    return index


# ---------------------------------------------------------------------------
# Segment extraction
# ---------------------------------------------------------------------------

def segment_from_id(test_id: str) -> str:
    """Extract the segment prefix from a test ID.

    Examples:
        "LLM-02"   -> "LLM"
        "RAG-14"   -> "RAG"
        "E2E-01"   -> "E2E"
        "VOICE-03" -> "VOICE"
    """
    parts = test_id.split("-", 1)
    return parts[0] if parts else "UNKNOWN"


def compute_segments(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Build a segment -> {status: count} mapping."""
    segments: Dict[str, Dict[str, int]] = defaultdict(lambda: {s: 0 for s in ALL_STATUSES})
    for entry in results:
        seg = segment_from_id(entry.get("id", ""))
        status = entry.get("status", "SKIP")
        if status not in segments[seg]:
            segments[seg][status] = 0
        segments[seg][status] += 1
    return dict(segments)


def compute_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Return aggregate counts per status."""
    counts: Dict[str, int] = {s: 0 for s in ALL_STATUSES}
    for entry in results:
        status = entry.get("status", "SKIP")
        counts[status] = counts.get(status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def merge_results(
    base_results: List[Dict[str, Any]],
    overlay_results: List[Dict[str, Any]],
    source_label: str = "overlay",
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Merge *overlay_results* into *base_results* (mutates base list).

    Returns ``(merged_list, overridden_count, added_count)``.
    """
    index = results_by_id(base_results)
    overridden = 0
    added = 0

    for entry in overlay_results:
        tid = entry.get("id", "")
        if not tid:
            continue

        new_status = entry.get("status", "SKIP")

        if tid in index:
            old_status = index[tid].get("status", "SKIP")
            if status_is_better(new_status, old_status):
                # Override fields from the better source, preserving the id.
                for key in ("status", "details", "latency_ms"):
                    if key in entry:
                        index[tid][key] = entry[key]
                # Annotate where the upgrade came from.
                index[tid]["details"] = (
                    f"[merged from {source_label}] "
                    + index[tid].get("details", "")
                )
                overridden += 1
        else:
            # New test ID -- append to the base list.
            new_entry = deepcopy(entry)
            new_entry["details"] = (
                f"[added from {source_label}] " + new_entry.get("details", "")
            )
            base_results.append(new_entry)
            index[tid] = new_entry
            added += 1

    return base_results, overridden, added


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report_json(
    results: List[Dict[str, Any]],
    timestamp: str,
) -> Dict[str, Any]:
    """Build the merged JSON report structure."""
    counts = compute_counts(results)
    total = len(results)
    pass_rate = round((counts["PASS"] / total * 100) if total else 0.0, 2)
    segments = compute_segments(results)

    # Sort results by ID for deterministic output.
    results_sorted = sorted(results, key=lambda r: r.get("id", ""))

    return {
        "timestamp": timestamp,
        "total": total,
        "counts": counts,
        "pass_rate": pass_rate,
        "segments": segments,
        "results": results_sorted,
    }


def build_report_markdown(report: Dict[str, Any]) -> str:
    """Render a human-readable markdown report from the merged JSON."""
    lines: List[str] = []
    lines.append("# Merged Test Results Report")
    lines.append("")
    lines.append(f"**Generated:** {report['timestamp']}")
    lines.append(f"**Total tests:** {report['total']}")
    lines.append(f"**Pass rate:** {report['pass_rate']}%")
    lines.append("")

    # Counts summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status  | Count |")
    lines.append("|---------|-------|")
    for status in ALL_STATUSES:
        lines.append(f"| {status:<7} | {report['counts'].get(status, 0):>5} |")
    lines.append("")

    # Segment breakdown
    lines.append("## Segment Breakdown")
    lines.append("")
    seg_headers = "| Segment | " + " | ".join(ALL_STATUSES) + " | Total |"
    seg_divider = "|---------|" + "|".join(["-------"] * len(ALL_STATUSES)) + "|-------|"
    lines.append(seg_headers)
    lines.append(seg_divider)
    for seg_name in sorted(report["segments"].keys()):
        seg = report["segments"][seg_name]
        seg_total = sum(seg.get(s, 0) for s in ALL_STATUSES)
        cols = " | ".join(str(seg.get(s, 0)).rjust(5) for s in ALL_STATUSES)
        lines.append(f"| {seg_name:<7} | {cols} | {seg_total:>5} |")
    lines.append("")

    # Detailed results
    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| ID | Title | Priority | Status | Details | Latency (ms) |")
    lines.append("|----|-------|----------|--------|---------|--------------|")
    for r in report["results"]:
        tid = r.get("id", "")
        title = r.get("title", "").replace("|", "\\|")
        priority = r.get("priority", "")
        status = r.get("status", "")
        details = r.get("details", "").replace("|", "\\|")
        latency = r.get("latency_ms", 0)
        lines.append(f"| {tid} | {title} | {priority} | {status} | {details} | {latency} |")
    lines.append("")

    return "\n".join(lines)


def print_comparison(
    label: str,
    before_counts: Dict[str, int],
    after_counts: Dict[str, int],
    before_total: int,
    after_total: int,
) -> None:
    """Print a before / after table to the console."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  {'Status':<10} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-' * 38}")
    for status in ALL_STATUSES:
        b = before_counts.get(status, 0)
        a = after_counts.get(status, 0)
        delta = a - b
        sign = "+" if delta > 0 else ""
        print(f"  {status:<10} {b:>8} {a:>8} {sign + str(delta):>8}")
    print(f"  {'-' * 38}")
    print(f"  {'TOTAL':<10} {before_total:>8} {after_total:>8} {'+' + str(after_total - before_total) if after_total > before_total else str(after_total - before_total):>8}")

    after_pass = after_counts.get("PASS", 0)
    after_rate = round((after_pass / after_total * 100) if after_total else 0.0, 2)
    before_pass = before_counts.get("PASS", 0)
    before_rate = round((before_pass / before_total * 100) if before_total else 0.0, 2)
    print(f"\n  Pass rate: {before_rate}% -> {after_rate}%")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    today_tag = datetime.now().strftime("%Y%m%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------
    # 1. Discover source files
    # ------------------------------------------------------------------
    http_path = find_http_runner_file()
    unit_path = find_unit_test_file()
    e2e_path = find_e2e_file()

    if http_path is None:
        print("ERROR: No HTTP runner results found in", TESTS_DIR, file=sys.stderr)
        print("  Expected pattern: test_results_YYYYMMDD.json", file=sys.stderr)
        sys.exit(1)

    print(f"Sources discovered:")
    print(f"  HTTP runner : {http_path}")
    print(f"  Unit tests  : {unit_path or '(not found)'}")
    print(f"  E2E tests   : {e2e_path or '(not found)'}")

    # ------------------------------------------------------------------
    # 2. Load base results (HTTP runner)
    # ------------------------------------------------------------------
    http_data = load_json(http_path)
    base_results: List[Dict[str, Any]] = deepcopy(http_data.get("results", []))
    before_counts = compute_counts(base_results)
    before_total = len(base_results)

    print(f"\nBaseline (HTTP runner): {before_total} tests")

    # ------------------------------------------------------------------
    # 3. Merge unit test results
    # ------------------------------------------------------------------
    if unit_path is not None:
        unit_data = load_json(unit_path)
        unit_results = unit_data.get("results", [])
        base_results, overridden, added = merge_results(
            base_results, unit_results, source_label="unit"
        )
        print(f"Unit tests: {len(unit_results)} entries -> {overridden} overridden, {added} added")

    # ------------------------------------------------------------------
    # 4. Merge E2E results (optional)
    # ------------------------------------------------------------------
    if e2e_path is not None:
        e2e_data = load_json(e2e_path)
        e2e_results = e2e_data.get("results", [])
        base_results, overridden, added = merge_results(
            base_results, e2e_results, source_label="e2e"
        )
        print(f"E2E tests : {len(e2e_results)} entries -> {overridden} overridden, {added} added")

    # ------------------------------------------------------------------
    # 5. Build merged report
    # ------------------------------------------------------------------
    report = build_report_json(base_results, timestamp)

    after_counts = report["counts"]
    after_total = report["total"]

    # ------------------------------------------------------------------
    # 6. Console summary
    # ------------------------------------------------------------------
    print_comparison(
        "Merge Summary (before -> after)",
        before_counts,
        after_counts,
        before_total,
        after_total,
    )

    # Segment breakdown on console.
    print("Segment breakdown:")
    print(f"  {'Segment':<12}", end="")
    for s in ALL_STATUSES:
        print(f" {s:>8}", end="")
    print(f" {'Total':>8}")
    print(f"  {'-' * 52}")
    for seg_name in sorted(report["segments"].keys()):
        seg = report["segments"][seg_name]
        seg_total = sum(seg.get(s, 0) for s in ALL_STATUSES)
        print(f"  {seg_name:<12}", end="")
        for s in ALL_STATUSES:
            print(f" {seg.get(s, 0):>8}", end="")
        print(f" {seg_total:>8}")
    print()

    # ------------------------------------------------------------------
    # 7. Write output files
    # ------------------------------------------------------------------
    TESTS_DIR.mkdir(parents=True, exist_ok=True)

    json_out = TESTS_DIR / f"test_results_merged_{today_tag}.json"
    md_out = TESTS_DIR / f"test_results_merged_{today_tag}.md"

    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"Merged JSON written to: {json_out}")

    md_content = build_report_markdown(report)
    with open(md_out, "w", encoding="utf-8") as fh:
        fh.write(md_content)
    print(f"Merged Markdown written to: {md_out}")

    print(f"\nDone. {after_total} tests merged, pass rate {report['pass_rate']}%.")


if __name__ == "__main__":
    main()
