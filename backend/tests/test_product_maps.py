"""
Product Map Keyword Validator for 3ioNetra
==========================================
Validates that every keyword in the 5 product maps (EMOTION, DEITY, DOMAIN,
CONCEPT, PRACTICE) matches at least one product in the catalog (products.json).

Catches dead keywords (match zero products) before they cause silent failures
in the recommendation engine.

Usage:
    cd backend && python3 tests/test_product_maps.py
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load product catalog
# ---------------------------------------------------------------------------
PRODUCTS_PATH = Path(__file__).parent.parent / "scripts" / "products.json"


def load_products():
    with open(PRODUCTS_PATH) as f:
        return json.load(f)


def keyword_matches_product(keyword: str, product: dict) -> bool:
    """Check if a keyword matches a product's name or description (case-insensitive)."""
    kw = keyword.lower()
    name = product.get("name", "").lower()
    desc = product.get("description", "").lower()
    cat = product.get("category", "").lower()
    return kw in name or kw in desc or kw in cat


# ---------------------------------------------------------------------------
# Product maps (mirrored from companion_engine.py)
# ---------------------------------------------------------------------------
EMOTION_PRODUCT_MAP = {
    "anxiety": ["Inner Peace", "Antidepression", "Amethyst", "Rose Quartz", "Black Tourmaline", "7 Chakra", "incense"],
    "grief": ["consultation", "seva", "pind daan", "Rose Quartz", "Rudraksha"],
    "confusion": ["consultation", "astrology", "Lapis Lazuli", "Amethyst", "7 Chakra"],
    "anger": ["Anger Relief", "Black Tourmaline", "Carnelian", "incense", "Smoky Quartz"],
    "hopelessness": ["consultation", "Rose Quartz", "Inner Peace", "Antidepression", "7 Chakra"],
    "stress": ["Antidepression", "Inner Peace", "Amethyst", "Smoky Quartz", "Ultimate Wellness", "incense"],
    "fear": ["Triple Protection", "Black Tourmaline", "Hanuman", "Panchmukhi", "5 Mukhi Rudraksha"],
    "sadness": ["Rose Quartz", "Antidepression", "consultation", "Inner Peace"],
    "loneliness": ["Rose Quartz", "Inner Peace", "consultation", "7 Chakra"],
    "frustration": ["Anger Relief", "Smoky Quartz", "Black Tourmaline", "Tiger Eye", "consultation"],
    "shame": ["Rose Quartz", "consultation", "Amethyst", "Inner Peace"],
    "despair": ["consultation", "Antidepression", "Rose Quartz", "7 Chakra", "seva"],
    "guilt": ["Rose Quartz", "consultation", "Amethyst", "seva"],
    "jealousy": ["Black Tourmaline", "Triple Protection", "Rose Quartz"],
}

DEITY_PRODUCT_MAP = {
    "krishna": ["Krishna", "Radha Krishna", "3D lamp", "Krishna Murti", "Puja Box", "Light Frame"],
    "shiva": ["Shiva", "Rudraksha", "3D Shiva", "Shiva 3D Light", "1 Mukhi", "5 Mukhi"],
    "hanuman": ["Hanuman", "Panchamukhi", "3D Hanuman", "Hanuman Bell", "Hanuman Yantra", "Brass Idol"],
    "ganesh": ["Ganesh", "Ganesha", "murti", "3D Ganesh", "Ganesh 3D Light", "Ganapati"],
    "lakshmi": ["Lakshmi", "Pyrite", "prosperity", "Lakshmi Charan", "Lakshmi Kuber", "7 Mukhi Rudraksha"],
    "durga": ["Durga", "murti", "Mundeshwari", "Shakti"],
    "saraswati": ["Saraswati", "Education", "Lakshmi Ganesh Saraswati"],
    "shrinathji": ["Shrinathji", "3D box", "golden arch"],
    "vishnu": ["Vishnu", "Vishnusahasranam", "Sudarshan"],
    "surya": ["Surya", "Abhimantrit Surya", "copper wall hanging"],
    "kali": ["Kali", "Bhairav", "Triple Protection"],
    "naag": ["Naagdev", "Kaal Sarp", "Nag", "serpent", "Sade Sati"],
    "ram": ["Ram", "Hanuman", "Brass Idol"],
    "murugan": ["Karungali", "Murugan", "Vel"],
}

DOMAIN_PRODUCT_MAP = {
    "career": ["Career Success", "Success & Focus", "Tiger Eye", "Pyrite", "consultation", "Money Magnet"],
    "relationships": ["Rose Quartz", "Early Marriage", "consultation", "Life Goal Support"],
    "health": ["Weight Loss", "Headache Relief", "7 Chakra", "bracelet", "Ultimate Wellness", "Diabetes Control"],
    "spiritual": ["Rudraksha", "mala", "incense", "deep", "murti", "Karungali", "yantra"],
    "family": ["puja thali", "deep", "Lakshmi Ganesh", "puja box"],
    "finance": ["Money Magnet", "Dhan Yog", "Pyrite", "Lakshmi", "Career Success", "Lakshmi Pyramid"],
    "education": ["Education", "Success & Focus", "Tiger Eye", "Lapis Lazuli", "consultation"],
    "self-improvement": ["Education", "Success & Focus", "Tiger Eye", "Lapis Lazuli", "consultation", "abundance"],
    "yoga practice": ["incense", "meditation", "7 Chakra", "Amethyst"],
    "meditation & mind": ["Amethyst", "incense", "Smoky Quartz", "Inner Peace", "mala"],
    "ayurveda & wellness": ["Ultimate Wellness", "7 Chakra", "Health & Wealth"],
    "marriage": ["Rose Quartz", "Early Marriage", "consultation", "Lakshmi Ganesh"],
    "parenting": ["Rose Quartz", "puja thali", "Lakshmi Ganesh", "consultation", "Conscious Parenting"],
    "addiction": ["Amethyst", "Black Tourmaline", "consultation", "Rudraksha"],
    "grief & loss": ["Rose Quartz", "seva", "pind daan", "consultation"],
    "self-worth": ["Tiger Eye", "Carnelian", "Rose Quartz", "consultation"],
    "general": ["consultation", "7 Chakra", "Rudraksha", "Rose Quartz", "incense"],
}

CONCEPT_PRODUCT_MAP = {
    "bhakti": ["murti", "puja thali", "deep", "incense", "3D lamp"],
    "vairagya": ["mala", "Rudraksha", "Karungali"],
    "karma": ["seva", "consultation"],
    "dharma": ["mala", "Rudraksha", "consultation"],
    "surrender": ["murti", "deep", "seva"],
    "moksha": ["1 Mukhi Rudraksha", "mala", "Rudraksha"],
    "shakti": ["Durga", "Triple Protection", "Carnelian"],
    "prosperity": ["Dhan Yog", "Money Magnet", "Pyrite", "Lakshmi"],
    "protection": ["Triple Protection", "Black Tourmaline", "Hanuman", "Panchamukhi"],
    "vastu": ["Sudarshan Yantra", "7 Horses", "Surya", "Kurma"],
    "puja": ["puja thali", "incense", "diya", "deep"],
    "healing": ["7 Chakra", "Rose Quartz", "Amethyst", "Ultimate Wellness"],
    "courage": ["Hanuman", "Tiger Eye", "Carnelian", "Triple Protection"],
    "navagraha": ["Navgrah", "Mangal", "Surya", "consultation"],
    "pitru": ["pind daan", "seva", "consultation"],
    "dosh": ["Kaal Sarp", "Mangal", "Sade Sati", "consultation", "yantra"],
    "ank_shastra": ["Ank Shastra", "consultation"],
}

PRACTICE_PRODUCT_MAP = {
    "japa": {"search_keywords": ["rudraksha mala", "mala"]},
    "puja": {"search_keywords": ["puja thali", "incense", "diya", "Kalash", "agardan", "kamandal", "Panch Patra", "chokra"]},
    "meditation": {"search_keywords": ["incense", "Loban", "agarbatti", "Amethyst"]},
    "diya": {"search_keywords": ["deep", "ghee", "diya", "akhand"]},
    "yoga": {"search_keywords": ["yoga", "bracelet"]},
    "tilak": {"search_keywords": ["sindoor", "kumkum", "puja thali"]},
    "abhishek": {"search_keywords": ["abhishek", "Kalash", "puja thali", "ghee"]},
    "havan": {"search_keywords": ["havan", "ghee", "yagya"]},
    "deity_worship": {"search_keywords": ["murti", "brass idol"]},
    "home_temple": {"search_keywords": ["puja box", "3D lamp", "deep", "bell", "aarti", "paduka", "photo frame"]},
    "crystal_healing": {"search_keywords": ["bracelet", "crystal"]},
    "seva": {"search_keywords": ["seva", "pind daan", "ganga aarti"]},
    "consultation": {"search_keywords": ["consultation", "astrology", "Astro List", "Book-now"]},
    "vrat": {"search_keywords": ["puja thali", "incense", "diya"]},
    "sankalpa": {"search_keywords": ["mala", "Rudraksha", "yantra"]},
    "temple_seva": {"search_keywords": ["seva", "annadaan", "kirtan", "shringar", "yagya", "pujan", "Jwala"]},
    "workshop": {"search_keywords": ["HEARTSPACE", "healing", "bhajan", "Rhythm"]},
    "kundli": {"search_keywords": ["consultation", "dosh nivaran", "yantra", "Navgrah"]},
}

ALL_MAPS = {
    "EMOTION_PRODUCT_MAP": EMOTION_PRODUCT_MAP,
    "DEITY_PRODUCT_MAP": DEITY_PRODUCT_MAP,
    "DOMAIN_PRODUCT_MAP": DOMAIN_PRODUCT_MAP,
    "CONCEPT_PRODUCT_MAP": CONCEPT_PRODUCT_MAP,
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_maps(products: list) -> dict:
    """Validate all maps and return results."""
    results = {}
    total_keywords = 0
    dead_keywords = 0

    for map_name, product_map in ALL_MAPS.items():
        map_results = {}
        for key, keywords in product_map.items():
            for kw in keywords:
                total_keywords += 1
                matches = [p["name"] for p in products if keyword_matches_product(kw, p)]
                if not matches:
                    dead_keywords += 1
                    map_results.setdefault(key, []).append(kw)

        results[map_name] = map_results

    # Validate PRACTICE_PRODUCT_MAP separately (different structure)
    practice_results = {}
    for practice, config in PRACTICE_PRODUCT_MAP.items():
        for kw in config["search_keywords"]:
            total_keywords += 1
            matches = [p["name"] for p in products if keyword_matches_product(kw, p)]
            if not matches:
                dead_keywords += 1
                practice_results.setdefault(practice, []).append(kw)

    results["PRACTICE_PRODUCT_MAP"] = practice_results

    return {
        "total_keywords": total_keywords,
        "dead_keywords": dead_keywords,
        "dead_by_map": results,
    }


def validate_coverage(products: list) -> dict:
    """Check what percentage of active products are reachable from any map."""
    all_keywords = set()
    for product_map in ALL_MAPS.values():
        for keywords in product_map.values():
            all_keywords.update(kw.lower() for kw in keywords)
    for config in PRACTICE_PRODUCT_MAP.values():
        all_keywords.update(kw.lower() for kw in config["search_keywords"])

    reachable = []
    unreachable = []
    for p in products:
        if not p.get("is_active", True):
            continue
        name_lower = p.get("name", "").lower()
        desc_lower = p.get("description", "").lower()
        cat_lower = p.get("category", "").lower()
        matched = any(
            kw in name_lower or kw in desc_lower or kw in cat_lower
            for kw in all_keywords
        )
        if matched:
            reachable.append(p["name"])
        else:
            unreachable.append(p["name"])

    return {
        "total_active": len(reachable) + len(unreachable),
        "reachable": len(reachable),
        "unreachable_count": len(unreachable),
        "unreachable_names": unreachable,
        "coverage_pct": len(reachable) / (len(reachable) + len(unreachable)) * 100 if (reachable or unreachable) else 0,
    }


def validate_categories(products: list) -> dict:
    """Check which product categories appear in the catalog."""
    categories = {}
    for p in products:
        cat = p.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    return categories


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Product Map Keyword Validator")
    print("=" * 60)

    products = load_products()
    print(f"\nLoaded {len(products)} products from {PRODUCTS_PATH.name}")

    # 1. Dead keyword check
    print("\n--- Dead Keyword Check ---")
    results = validate_maps(products)
    print(f"Total keywords checked: {results['total_keywords']}")
    print(f"Dead keywords (match 0 products): {results['dead_keywords']}")

    has_dead = False
    for map_name, dead_map in results["dead_by_map"].items():
        if dead_map:
            has_dead = True
            print(f"\n  {map_name}:")
            for key, dead_kws in dead_map.items():
                for kw in dead_kws:
                    print(f"    [{key}] '{kw}' -> NO MATCH")

    if not has_dead:
        print("\n  All keywords match at least one product!")

    # 2. Coverage check
    print("\n--- Product Coverage ---")
    coverage = validate_coverage(products)
    print(f"Active products: {coverage['total_active']}")
    print(f"Reachable via maps: {coverage['reachable']} ({coverage['coverage_pct']:.1f}%)")
    print(f"Unreachable: {coverage['unreachable_count']}")
    if coverage["unreachable_names"]:
        print("\n  Unreachable products:")
        for name in sorted(coverage["unreachable_names"])[:20]:
            print(f"    - {name}")
        if len(coverage["unreachable_names"]) > 20:
            print(f"    ... and {len(coverage['unreachable_names']) - 20} more")

    # 3. Category distribution
    print("\n--- Category Distribution ---")
    categories = validate_categories(products)
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Final verdict
    print("\n" + "=" * 60)
    if results["dead_keywords"] == 0:
        print("  PASS: All map keywords are valid")
    else:
        print(f"  WARNING: {results['dead_keywords']} dead keywords found")
    print(f"  Coverage: {coverage['coverage_pct']:.1f}% of products reachable")
    print("=" * 60)

    sys.exit(0 if results["dead_keywords"] == 0 else 1)


if __name__ == "__main__":
    main()
