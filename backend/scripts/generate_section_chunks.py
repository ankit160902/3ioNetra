#!/usr/bin/env python3
"""
Generate L1 section-level chunks from verse data.

Groups verses by (scripture, chapter), creates sliding-window chunks of 8 verses
with stride 4, embeds them, and saves as sections.json + sections_embeddings.npy.

These section chunks enable paragraph-level retrieval for thematic/chapter queries.

Run:  cd backend && python scripts/generate_section_chunks.py
"""

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np


def main():
    base = Path(__file__).resolve().parent.parent
    processed = base / "data" / "processed"
    verses_path = processed / "verses.json"

    if not verses_path.exists():
        print(f"ERROR: {verses_path} not found")
        sys.exit(1)

    print("Loading verses.json...")
    with open(verses_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    verses = payload.get("verses", payload) if isinstance(payload, dict) else payload

    # Group verses by (scripture, chapter)
    groups = defaultdict(list)
    for i, v in enumerate(verses):
        key = (v.get("scripture", ""), str(v.get("chapter", "")))
        groups[key].append((i, v))

    print(f"Found {len(groups)} (scripture, chapter) groups")

    # Generate section chunks with sliding window
    WINDOW_SIZE = 8
    STRIDE = 4
    chunks = []

    for (scripture, chapter), verse_list in groups.items():
        if len(verse_list) < WINDOW_SIZE:
            continue

        # Sort by verse_number if available
        verse_list.sort(key=lambda x: int(x[1].get("verse_number", 0)) if str(x[1].get("verse_number", "")).isdigit() else 0)

        for start in range(0, len(verse_list) - WINDOW_SIZE + 1, STRIDE):
            window = verse_list[start:start + WINDOW_SIZE]

            # Concatenate meanings/text for the chunk
            meanings = []
            verse_refs = []
            for _, v in window:
                text = v.get("meaning") or v.get("text") or v.get("translation") or ""
                if text.strip():
                    meanings.append(text.strip())
                ref = v.get("reference", "")
                if ref:
                    verse_refs.append(ref)

            if not meanings:
                continue

            combined_text = " ".join(meanings)
            first_verse = window[0][1]
            last_verse = window[-1][1]

            chunk = {
                "text": combined_text,
                "scripture": scripture,
                "chapter": chapter,
                "type": "section_chunk",
                "reference": f"{scripture} Ch.{chapter} ({first_verse.get('verse_number', '?')}-{last_verse.get('verse_number', '?')})",
                "verse_refs": verse_refs,
                "topic": first_verse.get("topic", ""),
                "tradition": first_verse.get("tradition", "general"),
            }
            chunks.append(chunk)

    print(f"Generated {len(chunks)} section chunks")

    if not chunks:
        print("No chunks generated — nothing to save")
        return

    # Embed chunks
    print("Loading embedding model...")
    from sentence_transformers import SentenceTransformer

    # Try local model paths first
    model_path = None
    for candidate in ["/app/models/embeddings", str(base / "models" / "embeddings")]:
        if os.path.isdir(candidate) and os.listdir(candidate):
            model_path = candidate
            break
    if model_path is None:
        model_path = "intfloat/multilingual-e5-large"

    model = SentenceTransformer(model_path)
    print(f"Loaded model from {model_path}")

    # Embed with passage prefix (E5 requirement)
    texts = [f"passage: {c['text']}" for c in chunks]

    print(f"Embedding {len(texts)} chunks (batch size 64)...")
    t_start = time.time()
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    elapsed = time.time() - t_start
    print(f"Embedding complete in {elapsed:.1f}s")

    # Save
    sections_path = processed / "sections.json"
    sections_emb_path = processed / "sections_embeddings.npy"

    with open(sections_path, "w", encoding="utf-8") as f:
        json.dump({"sections": chunks}, f, ensure_ascii=False)

    np.save(sections_emb_path, np.array(embeddings, dtype=np.float32))

    print(f"Saved: {sections_path} ({len(chunks)} chunks)")
    print(f"Saved: {sections_emb_path} ({embeddings.shape})")


if __name__ == "__main__":
    main()
