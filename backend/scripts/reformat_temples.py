import json
import os
import re
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def strip_markdown(text):
    if not text:
        return ""
    # Remove bold/italic symbols
    text = re.sub(r'\*+', '', text)
    # Remove links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove headers
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^-{3,}|_{3,}|\*{3,}$', '', text, flags=re.MULTILINE)
    return text.strip()

def process_temples():
    raw_path = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw/hindu_temples.json")
    output_path = Path("/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/data/raw/hindu_temples_formatted.json")

    if not raw_path.exists():
        logger.error(f"File not found: {raw_path}")
        return

    def handle_duplicates(pairs):
        d = {}
        history_count = 0
        for k, v in pairs:
            if k == "History":
                history_count += 1
                if history_count == 2:
                    d["Detailed History"] = v
                    continue
            d[k] = v
        return d

    with open(raw_path, 'r', encoding='utf-8') as f:
        data = json.load(f, object_pairs_hook=handle_duplicates)

    new_data = {}
    all_temples = []
    
    for state_key, temples in data.items():
        if isinstance(temples, list):
            for t in temples:
                all_temples.append(t)

    for t in all_temples:
        location = t.get("Location", "")
        detected_state = t.get("state", "Unknown")
        
        if "Odisha" in location: detected_state = "Odisha"
        elif "Tamil Nadu" in location: detected_state = "Tamil Nadu"
        elif "Karnataka" in location: detected_state = "Karnataka"
        elif "Andhra Pradesh" in location: detected_state = "Andhra Pradesh"
        elif "Sikkim" in location: detected_state = "Sikkim"
        elif "Arunachal Pradesh" in location: detected_state = "Arunachal Pradesh"
        elif "Assam" in location: detected_state = "Assam"
        elif "Madhya Pradesh" in location: detected_state = "Madhya Pradesh"
        elif "Meghalaya" in location: detected_state = "Meghalaya"
        elif "Manipur" in location: detected_state = "Manipur"
        
        formatted_temple = {
            "name": strip_markdown(t.get("name", "")),
            "state": detected_state,
            "info": strip_markdown(t.get("info", "")),
            "Location": strip_markdown(t.get("Location", "")),
            "Main deity": strip_markdown(t.get("Main deity", "")),
            "Other deities": strip_markdown(t.get("Other deities", "")),
            "History": strip_markdown(t.get("History", "")),
            "Detailed History": strip_markdown(t.get("Detailed History", t.get("story", ""))),
            "Architecture": strip_markdown(t.get("Architecture", "")),
            "Detailed Architecture": strip_markdown(t.get("architecture", "")),
            "Significance": strip_markdown(t.get("Significance", "")),
            "story": strip_markdown(t.get("story", "")),
            "Scriptural References": strip_markdown(t.get("Scriptural References", t.get("mention_in_scripture", ""))),
            "visiting_guide": strip_markdown(t.get("visiting_guide", "")),
            "Timings": strip_markdown(t.get("Timings", "")),
            "Entry Fee": strip_markdown(t.get("Entry Fee", "")),
            "Contact Information": strip_markdown(t.get("Contact Information", "")),
            "Key features of the architecture": strip_markdown(t.get("Key features of the architecture", "")),
            "Significance of the architecture": strip_markdown(t.get("Significance of the architecture", "")),
            "mention_in_scripture": strip_markdown(t.get("mention_in_scripture", ""))
        }

        if detected_state not in new_data:
            new_data[detected_state] = []
        new_data[detected_state].append(formatted_temple)

    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=4, ensure_ascii=False)
    logger.info(f"✓ Overwrote {raw_path} with stripped plain text.")

if __name__ == "__main__":
    process_temples()

if __name__ == "__main__":
    process_temples()
