"""ONNX Runtime wrapper for bge-reranker-v2-m3 CrossEncoder.

Runs on CPU in a worker process — completely isolated from the main
server's GIL and GPU operations. This prevents the 20x+ slowdown
observed when ONNX inference shares a process with PyTorch/CUDA.

Drop-in replacement for sentence_transformers.CrossEncoder.predict().
"""
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

# Module-level worker pool — one process, reused across requests.
# Lazy-initialized on first predict() call.
_process_pool: ProcessPoolExecutor = None
_model_dir_for_worker: str = None


def _worker_predict(pairs: List[List[str]], model_dir: str) -> List[float]:
    """Run in a separate process — has its own GIL, no contention."""
    import onnxruntime as ort
    from transformers import AutoTokenizer
    import numpy as np

    # Each worker process loads its own model instance (once, cached via global)
    global _worker_session, _worker_tokenizer
    if "_worker_session" not in dir() or _worker_session is None:
        onnx_dir = os.path.join(model_dir, "onnx")
        onnx_path = os.path.join(onnx_dir, "model.onnx")
        tokenizer_path = onnx_dir if os.path.exists(os.path.join(onnx_dir, "tokenizer.json")) else model_dir

        _worker_tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = 4
        sess_opts.inter_op_num_threads = 1
        _worker_session = ort.InferenceSession(
            onnx_path, sess_options=sess_opts, providers=["CPUExecutionProvider"],
        )

    queries = [p[0] for p in pairs]
    documents = [p[1] for p in pairs]
    encoded = _worker_tokenizer(
        queries, documents, padding=True, truncation=True,
        max_length=512, return_tensors="np",
    )
    outputs = _worker_session.run(None, {
        "input_ids": encoded["input_ids"].astype(np.int64),
        "attention_mask": encoded["attention_mask"].astype(np.int64),
    })
    logits = outputs[0]
    if logits.ndim == 2:
        logits = logits[:, 0]
    return logits.tolist()


class ONNXReranker:
    """CPU-based ONNX reranker that runs inference in a separate process.

    The worker process has its own GIL and memory space, preventing the
    20x+ slowdown caused by GIL contention with the main server process.
    """

    def __init__(self, model_dir: str):
        global _process_pool, _model_dir_for_worker
        _model_dir_for_worker = model_dir

        # Verify ONNX model exists
        onnx_path = os.path.join(model_dir, "onnx", "model.onnx")
        if not os.path.exists(onnx_path):
            raise FileNotFoundError(f"ONNX model not found at {onnx_path}")

        # Create a single-worker process pool (lazy — worker loads model on first call)
        if _process_pool is None:
            _process_pool = ProcessPoolExecutor(max_workers=1)

        self._model_dir = model_dir
        logger.info(f"ONNXReranker initialized (worker process pool, model={onnx_path})")

    def predict(self, pairs: List[List[str]]) -> List[float]:
        """Score query-document pairs via worker process. Returns list of float scores."""
        if not pairs:
            return []
        # Submit to worker process and wait for result
        future = _process_pool.submit(_worker_predict, pairs, self._model_dir)
        return future.result(timeout=30)
