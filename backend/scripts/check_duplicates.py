import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_duplicates():
    processed_path = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/processed/processed_data.json")
    if not processed_path.exists():
        print("Processed data not found.")
        return

    print(f"Reading {processed_path}...")
    with open(processed_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    verses = data.get('verses', [])
    print(f"Total verses in file: {len(verses)}")

    # 1. Check by Reference
    refs = {}
    ref_dupes = 0
    for v in verses:
        ref = v.get('reference')
        if ref in refs:
            ref_dupes += 1
        else:
            refs[ref] = True
    
    print(f"Reference-based duplicates: {ref_dupes}")

    # 2. Check by Text content (normalized)
    texts = {}
    text_dupes = []
    for v in verses:
        # Normalize text: lower, strip, remove extra internal whitespace
        raw_text = v.get('text', '')
        normalized_text = " ".join(raw_text.lower().split())
        
        if not normalized_text:
            continue
            
        if normalized_text in texts:
            text_dupes.append({
                'ref1': texts[normalized_text],
                'ref2': v.get('reference'),
                'text_snippet': raw_text[:50] + "..."
            })
        else:
            texts[normalized_text] = v.get('reference')

    print(f"Content-based duplicates (exact after normalization): {len(text_dupes)}")
    
    if text_dupes:
        print("\nExamples of content duplicates:")
        for d in text_dupes[:5]:
            print(f"- '{d['ref1']}' AND '{d['ref2']}' share text: {d['text_snippet']}")

if __name__ == "__main__":
    check_duplicates()
