
import json
import csv
import os
from pathlib import Path
from collections import defaultdict

def analyze_raw_temples():
    raw_dir = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw")
    seen_refs = defaultdict(list)
    
    files = list(raw_dir.glob("*.json"))
    
    for file_path in sorted(files):
        source = file_path.stem
        if "temple" not in source.lower():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
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
        except: pass

    duplicates = {ref: files for ref, files in seen_refs.items() if len(files) > 1}
    
    print("--- TEMPLE DUPLICATES ---")
    print(f"Total Unique Temples: {len(seen_refs)}")
    print(f"Total Duplicated Temples: {len(duplicates)}")
    
    sorted_dupes = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)
    for ref, files in sorted_dupes[:50]:
        print(f"{ref} (found {len(files)} times in {', '.join(set(files))})")

if __name__ == "__main__":
    analyze_raw_temples()
