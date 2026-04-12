"""ONNX Runtime wrapper for bge-reranker-v2-m3 CrossEncoder.

Runs on CPU — no VRAM contention with the embedding model on GPU.
Drop-in replacement for sentence_transformers.CrossEncoder.predict().
"""
import logging
import os
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class ONNXReranker:
    """CPU-based ONNX reranker with CrossEncoder-compatible .predict() API."""

    def __init__(self, model_dir: str):
        import onnxruntime as ort
        from transformers import AutoTokenizer

        onnx_dir = os.path.join(model_dir, "onnx")
        onnx_path = os.path.join(onnx_dir, "model.onnx")

        tokenizer_path = onnx_dir if os.path.exists(os.path.join(onnx_dir, "tokenizer.json")) else model_dir
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.session = ort.InferenceSession(
            onnx_path,
            providers=["CPUExecutionProvider"],
        )
        self.max_length = 512
        logger.info(f"ONNXReranker loaded from {onnx_path} (CPU)")

    def predict(self, pairs: List[List[str]]) -> List[float]:
        """Score query-document pairs. Returns list of float scores."""
        if not pairs:
            return []

        queries = [p[0] for p in pairs]
        documents = [p[1] for p in pairs]

        encoded = self.tokenizer(
            queries,
            documents,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="np",
        )

        outputs = self.session.run(
            None,
            {
                "input_ids": encoded["input_ids"].astype(np.int64),
                "attention_mask": encoded["attention_mask"].astype(np.int64),
            },
        )

        logits = outputs[0]
        if logits.ndim == 2:
            logits = logits[:, 0]
        return logits.tolist()
