#!/usr/bin/env python3
"""
Generate cross-scripture reference index.

For key verses (Bhagavad Gita, Yoga Sutras, top Rig Veda), find the top-3
most similar verses from OTHER scriptures using pre-computed embeddings.

Outputs:  data/processed/cross_refs.json
Run:      cd backend && python scripts/generate_cross_refs.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

# Key scripture names whose verses we want cross-references for
KEY_SCRIPTURES = {"Bhagavad Gita", "Patanjali Yoga Sutras", "Rig Veda"}
TOP_CROSS_REFS = 3


def main():
    base = Path(__file__).resolve().parent.parent
    processed = base / "data" / "processed"
    verses_path = processed / "verses.json"
    embeddings_path = processed / "embeddings.npy"

    if not verses_path.exists() or not embeddings_path.exists():
        print("ERROR: verses.json or embeddings.npy not found.")
        sys.exit(1)

    print("Loading data...")
    with open(verses_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    verses = payload.get("verses", payload) if isinstance(payload, dict) else payload

    embeddings = np.load(embeddings_path, mmap_mode="r")
    print(f"Loaded {len(verses)} verses, embeddings shape={embeddings.shape}")

    # Group verse indices by scripture
    scripture_to_indices = {}
    for i, v in enumerate(verses):
        s = v.get("scripture", "Unknown")
        if s not in scripture_to_indices:
            scripture_to_indices[s] = []
        scripture_to_indices[s].append(i)

    # Identify source verses (from key scriptures)
    source_indices = []
    for scripture in KEY_SCRIPTURES:
        indices = scripture_to_indices.get(scripture, [])
        source_indices.extend(indices)
        print(f"  {scripture}: {len(indices)} verses")

    print(f"Total source verses: {len(source_indices)}")

    # Build mask of "other scripture" indices for each source scripture
    cross_refs = {}
    t_start = time.time()

    for batch_start in range(0, len(source_indices), 100):
        batch = source_indices[batch_start:batch_start + 100]
        batch_vecs = np.array([embeddings[i] for i in batch], dtype=np.float32)

        # Normalize batch vectors
        norms = np.linalg.norm(batch_vecs, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        batch_vecs = batch_vecs / norms

        # Compute similarities against entire corpus
        sims = batch_vecs @ embeddings.T  # (batch_size, corpus_size)

        for j, src_idx in enumerate(batch):
            src_scripture = verses[src_idx].get("scripture", "")
            src_ref = verses[src_idx].get("reference", f"idx_{src_idx}")

            # Mask same-scripture verses
            scores = sims[j].copy()
            for idx in scripture_to_indices.get(src_scripture, []):
                scores[idx] = -np.inf

            # Top-K from other scriptures
            top_k_indices = np.argpartition(-scores, TOP_CROSS_REFS)[:TOP_CROSS_REFS]
            top_k_indices = top_k_indices[np.argsort(-scores[top_k_indices])]

            refs = []
            for tidx in top_k_indices:
                tidx = int(tidx)
                if scores[tidx] <= 0:
                    continue
                refs.append({
                    "reference": verses[tidx].get("reference", f"idx_{tidx}"),
                    "scripture": verses[tidx].get("scripture", ""),
                    "score": round(float(scores[tidx]), 4),
                })

            if refs:
                cross_refs[src_ref] = refs

        elapsed = time.time() - t_start
        done = batch_start + len(batch)
        print(f"  Processed {done}/{len(source_indices)} ({elapsed:.1f}s)")

    out_path = processed / "cross_refs.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cross_refs, f, ensure_ascii=False)

    print(f"\nCross-reference index: {len(cross_refs)} entries → {out_path}")


if __name__ == "__main__":
    main()
