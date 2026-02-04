
import json
import csv
import os
from pathlib import Path
from collections import defaultdict

def analyze_raw():
    raw_dir = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw")
    scripture_counts = defaultdict(int)
    seen_refs = defaultdict(list)
    
    def infer_scripture(source):
        source_lower = source.lower()
        if 'bhagavad' in source_lower or 'bhagwad' in source_lower or 'gita' in source_lower:
            return 'Bhagavad Gita'
        elif 'mahabharata' in source_lower:
            return 'Mahabharata'
        elif 'ramayana' in source_lower or 'balakanda' in source_lower or 'ayodhya' in source_lower:
            return 'Ramayana'
        elif 'rigveda' in source_lower:
            return 'Rig Veda'
        elif 'atharvaveda' in source_lower:
            return 'Atharva Veda'
        elif 'yajurveda' in source_lower or 'vajasneyi' in source_lower:
            return 'Yajur Veda'
        elif 'vedas' in source_lower:
            return 'Vedas'
        elif 'temples' in source_lower:
            return 'Hindu Temples'
        else:
            return 'Sanatan Scriptures'

    files = list(raw_dir.glob("*.json")) + list(raw_dir.glob("*.csv"))
    
    for file_path in sorted(files):
        source = file_path.stem
        scripture = infer_scripture(source)
        
        if file_path.suffix == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if "temple" in source.lower():
                    temples = []
                    if isinstance(data, list):
                        for obj in data:
                            if isinstance(obj, dict) and obj.get('type') == 'table':
                                temples.extend(obj.get('data', []))
                            elif isinstance(obj, dict) and 'name' in obj:
                                temples.append(obj)
                    elif isinstance(data, dict):
                        for state, state_temples in data.items():
                            if isinstance(state_temples, list):
                                for t in state_temples:
                                    if isinstance(t, dict):
                                        t['state'] = t.get('state', state)
                                        temples.append(t)
                    
                    for temple in temples:
                        name = temple.get('name')
                        state = temple.get('state', 'Unknown')
                        if name:
                            ref = f"Temple: {name} ({state})"
                            seen_refs[ref].append(file_path.name)
                            scripture_counts[scripture] += 1
                else:
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, list): items.extend(v)
                    
                    for item in items:
                        if not isinstance(item, dict): continue
                        chapter = item.get('chapter') or item.get('adhyaya') or item.get('book') or item.get('mandala') or item.get('kaanda')
                        verse_num = item.get('verse') or item.get('shloka') or item.get('shloka_number') or item.get('verse_number')
                        if chapter and verse_num:
                            ref = f"{scripture} {chapter}.{verse_num}"
                            seen_refs[ref].append(file_path.name)
                            scripture_counts[scripture] += 1
            except: pass
        
        elif file_path.suffix == '.csv':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        row_lower = {k.lower(): v for k, v in row.items()}
                        chapter = row_lower.get('chapter') or row_lower.get('adhyaya')
                        verse_num = row_lower.get('verse') or row_lower.get('shloka') or row_lower.get('shloka_number')
                        if chapter and verse_num:
                            ref = f"{scripture} {chapter}.{verse_num}"
                            seen_refs[ref].append(file_path.name)
                            scripture_counts[scripture] += 1
            except: pass

    duplicates = {ref: files for ref, files in seen_refs.items() if len(files) > 1}
    
    # Sort duplicates by frequency
    sorted_dupes = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)
    
    print("--- DATA SUMMARY ---")
    print(f"Total Unique Records: {len(seen_refs)}")
    for scripture, count in scripture_counts.items():
        print(f"{scripture}: {count} records")
    
    print("\n--- TOP DUPLICATES ---")
    for ref, files in sorted_dupes[:50]:
        print(f"{ref} (found {len(files)} times in {', '.join(set(files))})")

if __name__ == "__main__":
    analyze_raw()
