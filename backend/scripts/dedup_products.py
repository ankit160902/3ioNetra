"""Deduplicate products by normalized name.

Groups products by lowercased, whitespace-stripped name. For each group
with size > 1, keeps the one with the longest description and marks
others as is_active=false. Safe to re-run.

Usage:
    python scripts/dedup_products.py              # dry-run
    python scripts/dedup_products.py --write       # actually deactivate duplicates
"""

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.auth_service import get_mongo_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize product name for comparison."""
    return " ".join(name.lower().strip().split())


def main():
    parser = argparse.ArgumentParser(description="Deduplicate products")
    parser.add_argument("--write", action="store_true", help="Actually deactivate duplicates")
    args = parser.parse_args()

    db = get_mongo_client()
    if db is None:
        logger.error("MongoDB not available")
        return 1

    collection = db["products"]
    all_products = list(collection.find({"is_active": True}))
    logger.info(f"Total active products: {len(all_products)}")

    # Group by normalized name
    groups = defaultdict(list)
    for p in all_products:
        key = normalize_name(p.get("name", ""))
        groups[key].append(p)

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    logger.info(f"Found {len(duplicates)} duplicate groups")

    deactivated = 0
    for name, products in duplicates.items():
        # Keep the one with the longest description
        products.sort(key=lambda p: len(p.get("description", "") or ""), reverse=True)
        keeper = products[0]
        to_deactivate = products[1:]

        logger.info(f"\nDuplicate group: '{name}' ({len(products)} copies)")
        logger.info(f"  Keeping: _id={keeper['_id']} (desc={len(keeper.get('description', '') or '')} chars)")

        for dup in to_deactivate:
            logger.info(f"  Deactivating: _id={dup['_id']} (desc={len(dup.get('description', '') or '')} chars)")
            if args.write:
                collection.update_one(
                    {"_id": dup["_id"]},
                    {"$set": {"is_active": False, "dedup_reason": f"duplicate of {keeper['_id']}"}},
                )
                deactivated += 1

    mode = "DEACTIVATED" if args.write else "DRY-RUN"
    logger.info(f"\n{mode}: {deactivated} products deactivated across {len(duplicates)} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
