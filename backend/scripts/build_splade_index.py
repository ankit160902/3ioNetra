#!/usr/bin/env python3
"""
Build SPLADE++ sparse retrieval index.

Encodes all verse texts through the SPLADE model and saves
sparse representations as a CSR matrix for fast dot-product retrieval.

Requires: transformers, scipy
Model: naver/splade-cocondenser-ensembledistil (~600MB)

Run:  cd backend && python scripts/build_splade_index.py
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np


def main():
    base = Path(__file__).resolve().parent.parent
    processed = base / "data" / "processed"
    verses_path = processed / "verses.json"

    if not verses_path.exists():
        print(f"ERROR: {verses_path} not found")
        sys.exit(1)

    print("Loading verses...")
    with open(verses_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    verses = payload.get("verses", payload) if isinstance(payload, dict) else payload
    print(f"Loaded {len(verses)} verses")

    # Load SPLADE model
    print("Loading SPLADE model...")
    try:
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer
    except ImportError:
        print("ERROR: transformers and torch required. Install with:")
        print("  pip install transformers torch")
        sys.exit(1)

    model_name = "naver/splade-cocondenser-ensembledistil"

    # Check local cache
    local_path = base / "models" / "splade"
    if local_path.exists() and os.listdir(str(local_path)):
        model_name = str(local_path)
        print(f"Using cached model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForMaskedLM.from_pretrained(model_name)
    model.eval()

    # Save locally if downloaded from Hub
    if not local_path.exists() or not os.listdir(str(local_path)):
        os.makedirs(str(local_path), exist_ok=True)
        tokenizer.save_pretrained(str(local_path))
        model.save_pretrained(str(local_path))
        print(f"Saved model to {local_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"Model on device: {device}")

    # Encode verses in batches
    from scipy.sparse import csr_matrix, vstack

    batch_size = 32
    all_sparse = []
    vocab_size = tokenizer.vocab_size
    t_start = time.time()

    for batch_start in range(0, len(verses), batch_size):
        batch_end = min(batch_start + batch_size, len(verses))
        batch_texts = []
        for v in verses[batch_start:batch_end]:
            parts = [v.get("text", ""), v.get("meaning", ""), v.get("topic", "")]
            batch_texts.append(" ".join(p for p in parts if p)[:512])

        tokens = tokenizer(batch_texts, return_tensors="pt", padding=True,
                           truncation=True, max_length=256).to(device)

        with torch.no_grad():
            output = model(**tokens)
            # SPLADE: log(1 + ReLU(logits)) * attention_mask, then max-pool
            logits = output.logits
            splade_rep = torch.log1p(torch.relu(logits))
            # Max-pool over sequence length
            attention_mask = tokens["attention_mask"].unsqueeze(-1)
            splade_rep = (splade_rep * attention_mask).max(dim=1).values

        # Convert to sparse
        splade_np = splade_rep.cpu().numpy()
        sparse_batch = csr_matrix(splade_np)
        all_sparse.append(sparse_batch)

        if (batch_start // batch_size) % 100 == 0:
            elapsed = time.time() - t_start
            done = batch_end
            rate = done / elapsed if elapsed > 0 else 0
            eta = (len(verses) - done) / rate if rate > 0 else 0
            print(f"  {done}/{len(verses)} ({rate:.0f} docs/s, ETA {eta:.0f}s)")

    # Stack all batches
    print("Stacking sparse matrices...")
    from scipy.sparse import save_npz
    splade_matrix = vstack(all_sparse)
    print(f"SPLADE index shape: {splade_matrix.shape}, nnz: {splade_matrix.nnz}")

    out_path = processed / "splade_index.npz"
    save_npz(str(out_path), splade_matrix)
    elapsed = time.time() - t_start
    print(f"Saved SPLADE index to {out_path} ({elapsed:.1f}s total)")


if __name__ == "__main__":
    main()
