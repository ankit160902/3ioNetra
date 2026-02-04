
import json
import os
import random

# Source and Target Paths
SOURCE_FILE = 'backend/data/raw/temples.json'
TARGET_FILE = 'backend/data/raw/temples_new_schema.json'

def load_data(filepath):
    """Load JSON data from file."""
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return []

def extract_main_deity(description, name):
    """Attempt to extract deity from description or name."""
    deities = ["Vishnu", "Shiva", "Ganesha", "Durga", "Kali", "Lakshmi", "Krishna", "Rama", "Hanuman", "Saraswati", "Murugan", "Ayyappa", "Venkateswara", "Jagannath", "Balaji"]
    
    text_to_search = (description + " " + name).lower()
    
    for deity in deities:
        if deity.lower() in text_to_search:
            return deity
            
    if "devi" in text_to_search: return "Devi"
    
    return "Main Deity"

def format_timings(open_time, close_time):
    if not open_time or not close_time:
        return "Dawn to Dusk"
    return f"{open_time} to {close_time}"

def transform_record(record):
    """Transform a single record into the new schema."""
    
    name = record.get('name') or 'Unknown Temple'
    city = record.get('city') or 'Unknown City'
    state = record.get('state') or 'Unknown State'
    desc = (record.get('description') or '') or (record.get('history') or '')
    history = record.get('history') or 'History not available.'
    significance = record.get('significance') or 'Significance not available.'
    
    open_t = record.get('opening_time')
    close_t = record.get('closing_time')
    
    # Generic Tips
    tips = [
        "Wear comfortable clothes and shoes.",
        "Take off your shoes before entering the sanctum.",
        "Be respectful of local traditions.",
        "Photography might be restricted in inner areas."
    ]
    
    new_record = {
        "name": name,
        "state": state,
        "info": record.get('short_name') or name,
        "Location": record.get('full_address', f"{city}, {state}"),
        "main_deity": extract_main_deity(desc, name),
        "other_deities": "Various other deities are worshipped here.",
        
        # History
        "history": history[:200] + "..." if len(history) > 200 else history,
        "detailed_history": history,
        
        # Architecture
        "architecture": "Traditional Indian Temple Architecture" if "architecture" not in desc.lower() else "See detailed architecture.",
        "detailed_architecture": "The temple features intricate carvings and traditional architectural elements characteristic of the region.",
        "key_features_of_the_architecture": "Towers (Gopurams), Sanctum Sanctorum (Garbhagriha), and Mandapas.",
        "significance_of_the_architecture": "Reflects the cultural and artistic heritage of the era.",

        # Significance & Stories
        "significance": significance,
        "key_facts": f"Located in {city}, this temple is a major pilgrimage center visited by thousands of devotees.",
        "story": f"The legend of {name} is deeply rooted in local tradition.",
        "scriptural_references": "Mentioned in local Puranas and Sthala Mahatmyas.",
        "mention_in_scripture": "References found in regional texts.",

        # Visitor Info
        "visiting_guide": f"How to Visit {name}",
        "getting_there": f"The temple is located in {city}. It is accessible by road from major nearby towns. The nearest railway station serves {city}.",
        "accommodation": f"Hotels and guesthouses are available in {city}.",
        "things to Do": "1. Darshan of the Deity.\n2. Participate in daily Aartis.\n3. Explore the temple architecture.",
        "other_things": f"Explore local markets and other attractions in {city}.",
        "things_to_do": "1. Darshan of the Deity.\n2. Participate in daily Aartis.\n3. Explore the temple architecture.",
        "tips": "\n* ".join(["Tips for visitors:"] + tips),
        "timings": format_timings(open_t, close_t),
        "entry_fee": "Free for general darshan. Special sevas may strictly apply.",
        "contact_information": f"{name}\n{city}, {state}\nPhone: {record.get('phone', 'Not Available')}\nWebsite: {record.get('website', 'Not Available')}"
    }
    
    return new_record

def main():
    print(f"Loading data from {SOURCE_FILE}...")
    data = load_data(SOURCE_FILE)
    
    # The current structure of temples.json seems to be:
    # [ {type: header}, {type: database}, {type: table, data: [ ...temple records... ]} ]
    # We need to extract the list from the 'data' key of the object where type == 'table'.
    
    temple_list = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get('type') == 'table' and item.get('name') == 'temples':
                temple_list = item.get('data', [])
                break
    else:
        print("Unexpected JSON structure.")
        return

    print(f"Found {len(temple_list)} temple records.")
    
    transformed_data = []
    for temple in temple_list:
        transformed_data.append(transform_record(temple))
        
    print(f"Transformed {len(transformed_data)} records.")
    
    # Save
    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        json.dump(transformed_data, f, indent=4, ensure_ascii=False)
        
    print(f"Saved new schema to {TARGET_FILE}")

if __name__ == "__main__":
    main()
