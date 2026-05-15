"""
Meditation Template Cleanup — Remove/reclassify generic meditation templates
that cause noise in retrieval for emotional queries.

The ~26 "Meditation and Mindfulness" entries are generic templates (not scripture)
that match broadly to emotional queries like "I feel anxious" or "dealing with anger",
pushing actual scripture results down.

Strategy:
  - Reclassify them as type="procedural" (already are) with explicit topic tags
  - Add "meditation_template" source tag so the pipeline can optionally exclude them
  - Remove entries that are too generic to be useful

Usage:
    cd backend && python3 scripts/cleanup_meditation_templates.py
    cd backend && python3 scripts/cleanup_meditation_templates.py --dry-run
    cd backend && python3 scripts/cleanup_meditation_templates.py --remove  # delete instead of reclassify
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
VERSES_PATH = PROCESSED_DIR / "verses.json"
EMBEDDINGS_PATH = PROCESSED_DIR / "embeddings.npy"


def find_meditation_templates(verses: List[Dict]) -> List[int]:
    """Find indices of meditation template entries."""
    indices = []
    for i, v in enumerate(verses):
        scripture = (v.get("scripture") or "").lower()
        if "meditation" in scripture and "mindfulness" in scripture:
            indices.append(i)
    return indices


def is_too_generic(verse: Dict) -> bool:
    """Check if a meditation entry is too generic to be useful for retrieval."""
    text = (verse.get("text") or "").lower()

    # Generic templates that match too many emotional queries
    generic_patterns = [
        "context:",  # template-style entries
        "guidance:",
        "techniques:",
        "user_experience_level",
        "beginner",
        "intermediate",
        "advanced",
    ]
    generic_count = sum(1 for p in generic_patterns if p in text)
    # If it matches 3+ generic patterns, it's a template
    return generic_count >= 3


def cleanup(verses: List[Dict], remove: bool = False) -> tuple:
    """Clean up meditation templates. Returns (cleaned_verses, removed_count, reclassified_count)."""
    med_indices = find_meditation_templates(verses)
    logger.info(f"Found {len(med_indices)} meditation template entries")

    if not med_indices:
        return verses, 0, 0

    # Show what we found
    for idx in med_indices:
        v = verses[idx]
        text_preview = (v.get("text") or "")[:100].replace("\n", " ")
        logger.info(f"  [{idx}] {v.get('reference', 'no-ref')[:60]} | {text_preview}")

    if remove:
        # Remove all meditation template entries
        indices_set = set(med_indices)
        cleaned = [v for i, v in enumerate(verses) if i not in indices_set]
        return cleaned, len(med_indices), 0
    else:
        # Reclassify: mark as meditation_template source and narrow topic
        reclassified = 0
        to_remove = []
        for idx in med_indices:
            v = verses[idx]
            if is_too_generic(v):
                to_remove.append(idx)
            else:
                v["source"] = "meditation_template"
                v["type"] = "procedural"
                reclassified += 1

        # Remove overly generic ones
        if to_remove:
            indices_set = set(to_remove)
            cleaned = [v for i, v in enumerate(verses) if i not in indices_set]
        else:
            cleaned = verses

        return cleaned, len(to_remove), reclassified


def main():
    parser = argparse.ArgumentParser(description="Clean up meditation template entries")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without changes")
    parser.add_argument("--remove", action="store_true", help="Remove all meditation templates instead of reclassifying")
    args = parser.parse_args()

    if not VERSES_PATH.exists():
        logger.error(f"verses.json not found at {VERSES_PATH}")
        sys.exit(1)

    with open(VERSES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    verses = data.get("verses", [])
    logger.info(f"Loaded {len(verses)} verses")

    # Find and analyze
    med_indices = find_meditation_templates(verses)
    generic_count = sum(1 for i in med_indices if is_too_generic(verses[i]))
    logger.info(f"\nAnalysis:")
    logger.info(f"  Total meditation templates: {len(med_indices)}")
    logger.info(f"  Too generic (will remove): {generic_count}")
    logger.info(f"  Useful (will reclassify): {len(med_indices) - generic_count}")

    if args.dry_run:
        logger.info("\nDry run - no changes made.")
        return

    cleaned, removed, reclassified = cleanup(verses, remove=args.remove)

    if removed == 0 and reclassified == 0:
        logger.info("No changes needed.")
        return

    logger.info(f"\nRemoved {removed}, reclassified {reclassified}")
    logger.info(f"Verse count: {len(verses)} -> {len(cleaned)}")

    # Save updated verses.json
    for v in cleaned:
        v.pop("embedding", None)

    with open(VERSES_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "verses": cleaned,
                "metadata": {
                    "total_verses": len(cleaned),
                    "embedding_dim": data.get("metadata", {}).get("embedding_dim", settings.EMBEDDING_DIM),
                    "embedding_model": data.get("metadata", {}).get("embedding_model", settings.EMBEDDING_MODEL),
                    "scriptures": sorted(set(v.get("scripture", "Unknown") for v in cleaned)),
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # If entries were removed, we need to regenerate embeddings to keep alignment
    if removed > 0 and EMBEDDINGS_PATH.exists():
        logger.info("Entries removed - embeddings.npy is now misaligned.")
        logger.info("Run one of these to fix:")
        logger.info("  python3 scripts/enrich_ramayana_mahabharata.py --embeddings-only")
        logger.info("  python3 scripts/translate_all_scriptures.py --regen-embeddings")
        logger.info("  python3 scripts/ingest_all_data.py")

    logger.info("\nDone!")


if __name__ == "__main__":
    main()
