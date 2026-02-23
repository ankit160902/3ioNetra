
import json
from pathlib import Path
from collections import Counter

def check_data():
    path = Path("data/processed/processed_data.json")
    if not path.exists():
        print(f"File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    verses = data.get("verses", [])
    print(f"Total verses: {len(verses)}")

    scriptures = [v.get("scripture", "UNKNOWN") for v in verses]
    counts = Counter(scriptures)
    
    print("\nScripture counts:")
    for scripture, count in counts.items():
        print(f"{scripture}: {count}")

    # Check for "yoga" in text content of a few examples if scripture name isn't obvious
    print("\nChecking for specific keywords in scripture names or source:")
    
    # Let's peek at the structure of a 'yoga' or 'meditation' related verse if possible
    # We look for a few examples of non-mahabharata/ramayana verses
    
    others = [v for v in verses if v.get("scripture") not in ["Mahabharata", "Ramayana", "Bhagavad Gita"]]
    if others:
        print(f"\nFound {len(others)} from other sources. First 3 examples:")
        for v in others[:3]:
            print(f"Scripture: {v.get('scripture')}, Reference: {v.get('reference')}, Text snippet: {v.get('text')[:50]}...")
    else:
        print("\nNo verses found outside of common ones (Mahabharata, Ramayana, Bhagavad Gita).")

if __name__ == "__main__":
    check_data()
