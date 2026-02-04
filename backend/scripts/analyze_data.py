
import json
import csv
import os
from pathlib import Path
from collections import defaultdict

def get_data():
    raw_dir = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw")
    all_refs = []
    scripture_counts = defaultdict(int)
    duplicates = []
    
    # Track refs to find duplicates
    seen_refs = {} # ref -> [file_path]
    
    # Helper to infer scripture (copied from ingest script logic)
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
                
                # Temple file handling
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
                                        t['state'] = state
                                        temples.append(t)
                    
                    for temple in temples:
                        name = temple.get('name')
                        state = temple.get('state', 'Unknown')
                        if name:
                            ref = f"Temple: {name} ({state})"
                            if ref in seen_refs:
                                seen_refs[ref].append(file_path.name)
                            else:
                                seen_refs[ref] = [file_path.name]
                            scripture_counts[scripture] += 1
                
                # Other JSON files (verses)
                else:
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, list): items.extend(v)
                    
                    for item in items:
                        if not isinstance(item, dict): continue
                        # Use same logic as ingester
                        chapter = item.get('chapter') or item.get('adhyaya') or item.get('book') or item.get('mandala') or item.get('kaanda')
                        verse_num = item.get('verse') or item.get('shloka') or item.get('shloka_number') or item.get('verse_number')
                        if chapter and verse_num:
                            ref = f"{scripture} {chapter}.{verse_num}"
                            if ref in seen_refs:
                                seen_refs[ref].append(file_path.name)
                            else:
                                seen_refs[ref] = [file_path.name]
                            scripture_counts[scripture] += 1
            except Exception as e:
                pass
        
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
                            if ref in seen_refs:
                                seen_refs[ref].append(file_path.name)
                            else:
                                seen_refs[ref] = [file_path.name]
                            scripture_counts[scripture] += 1
            except Exception as e:
                pass

    # Identify duplicates
    duplicates = {ref: files for ref, files in seen_refs.items() if len(files) > 1}
    
    # Prepare list of scriptures and their counts
    print(json.dumps({
        "counts": dict(scripture_counts),
        "total_unique": len(seen_refs),
        "total_duplicates": len(duplicates),
        "duplicate_samples": {k: v for i, (k, v) in enumerate(duplicates.items()) if i < 50}
    }, indent=2))

if __name__ == "__main__":
    get_data()
