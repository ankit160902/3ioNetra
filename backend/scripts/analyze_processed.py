
import json
from pathlib import Path
from collections import defaultdict

def analyze_processed():
    path = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/processed/processed_data.json")
    if not path.exists():
        print("Processed data not found.")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    verses = data.get('verses', [])
    scripture_counts = defaultdict(int)
    references = defaultdict(list)
    
    for v in verses:
        scripture = v.get('scripture', 'Unknown')
        ref = v.get('reference', 'Unknown')
        scripture_counts[scripture] += 1
        references[ref].append(v)
    
    duplicates = {ref: len(items) for ref, items in references.items() if len(items) > 1}
    
    print(json.dumps({
        "summary": {
            "total_records": len(verses),
            "scripture_breakdown": dict(scripture_counts),
            "total_unique_references": len(references),
            "total_duplicated_references": len(duplicates)
        },
        "duplicate_examples": {k: v for i, (k, v) in enumerate(duplicates.items()) if i < 20}
    }, indent=2))

if __name__ == "__main__":
    analyze_processed()
