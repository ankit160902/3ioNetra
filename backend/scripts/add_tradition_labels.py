#!/usr/bin/env python3
"""
Add tradition labels to verses.json.

Maps scripture names to their dharmic tradition (vedanta, itihasa, shruti, yoga, etc.)
so Gate 6 (tradition diversity) and the tradition bonus in reranking can operate.

Run:  cd backend && python scripts/add_tradition_labels.py
"""

import json
import sys
from pathlib import Path

SCRIPTURE_TO_TRADITION = {
    "Bhagavad Gita": "vedanta",
    "Mahabharata": "itihasa",
    "Ramayana": "itihasa",
    "Rig Veda": "shruti",
    "Atharva Veda": "shruti",
    "Yajur Veda": "shruti",
    "Sama Veda": "shruti",
    "Patanjali Yoga Sutras": "yoga",
    "Charaka Samhita (Ayurveda)": "ayurveda",
    "Hindu Temples": "kshetra",
    "Meditation and Mindfulness": "yoga",
    "Sanatan Scriptures": "smriti",
    "Upanishads": "vedanta",
}


def _guess_tradition(scripture_name: str) -> str:
    """Try exact match, then substring match, then default to 'general'."""
    if scripture_name in SCRIPTURE_TO_TRADITION:
        return SCRIPTURE_TO_TRADITION[scripture_name]
    lower = scripture_name.lower()
    for key, tradition in SCRIPTURE_TO_TRADITION.items():
        if key.lower() in lower or lower in key.lower():
            return tradition
    return "general"


def main():
    base = Path(__file__).resolve().parent.parent
    verses_path = base / "data" / "processed" / "verses.json"

    if not verses_path.exists():
        print(f"ERROR: {verses_path} not found. Run ingest_all_data.py first.")
        sys.exit(1)

    print(f"Loading {verses_path}...")
    with open(verses_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    verses = payload.get("verses", payload) if isinstance(payload, dict) else payload
    if isinstance(payload, dict) and "verses" in payload:
        verse_list = payload["verses"]
    else:
        verse_list = payload

    labeled = 0
    tradition_counts = {}
    for verse in verse_list:
        scripture = verse.get("scripture", "")
        tradition = _guess_tradition(scripture)
        verse["tradition"] = tradition
        labeled += 1
        tradition_counts[tradition] = tradition_counts.get(tradition, 0) + 1

    print(f"\nLabeled {labeled} verses:")
    for t, c in sorted(tradition_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:15s} {c:>6d}")

    # Write back
    with open(verses_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"\nSaved to {verses_path}")


if __name__ == "__main__":
    main()
