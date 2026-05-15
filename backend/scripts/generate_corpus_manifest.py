#!/usr/bin/env python3
"""
Generate corpus_manifest.json — a version/integrity snapshot of the RAG corpus.

Outputs:
  data/processed/corpus_manifest.json

Run:  cd backend && python scripts/generate_corpus_manifest.py
"""

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest for a file (streaming to handle large files)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    base = Path(__file__).resolve().parent.parent
    processed = base / "data" / "processed"
    verses_path = processed / "verses.json"
    embeddings_path = processed / "embeddings.npy"

    if not verses_path.exists():
        print(f"ERROR: {verses_path} not found")
        sys.exit(1)

    print("Loading verses.json...")
    with open(verses_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    verses = payload.get("verses", payload) if isinstance(payload, dict) else payload

    scripture_counts = Counter(v.get("scripture", "Unknown") for v in verses)
    type_counts = Counter(v.get("type", "scripture") for v in verses)
    tradition_counts = Counter(v.get("tradition", "general") for v in verses)

    # Read embedding dimension from npy header without loading the full array
    embedding_dim = 0
    if embeddings_path.exists():
        import numpy as np
        mm = np.load(embeddings_path, mmap_mode="r")
        embedding_dim = mm.shape[1] if mm.ndim == 2 else 0

    manifest = {
        "version": "1.2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verse_count": len(verses),
        "embedding_dim": embedding_dim,
        "embedding_model": "intfloat/multilingual-e5-large",
        "verses_json_sha256": _sha256(verses_path),
        "embeddings_npy_sha256": _sha256(embeddings_path) if embeddings_path.exists() else None,
        "scripture_counts": dict(scripture_counts.most_common()),
        "type_counts": dict(type_counts.most_common()),
        "tradition_counts": dict(tradition_counts.most_common()),
        "changelog": [],
    }

    out_path = processed / "corpus_manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Corpus manifest written to {out_path}")
    print(f"  verses: {manifest['verse_count']}")
    print(f"  dim:    {manifest['embedding_dim']}")
    print(f"  scriptures: {len(scripture_counts)}")
    print(f"  traditions: {len(tradition_counts)}")


if __name__ == "__main__":
    main()
