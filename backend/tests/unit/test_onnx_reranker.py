"""Test ONNXReranker produces scores equivalent to PyTorch CrossEncoder."""
import os
import pytest
import numpy as np

RERANKER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "reranker")
ONNX_PATH = os.path.join(RERANKER_DIR, "onnx", "model.onnx")


@pytest.fixture
def pairs():
    return [
        ["What is dharma?", "Dharma is the cosmic order that sustains the universe."],
        ["How to meditate?", "The Ganges river flows through Varanasi."],
        ["Tell me about karma", "Karma is the law of cause and effect in Hindu philosophy."],
    ]


# Session-scoped so only one ONNX InferenceSession is allocated per test run.
# Loading the 560 MB model twice in the same process exhausts memory on constrained hardware.
@pytest.fixture(scope="session")
def onnx_reranker():
    if not os.path.exists(ONNX_PATH):
        pytest.skip("ONNX model not exported")
    from rag.onnx_reranker import ONNXReranker
    return ONNXReranker(RERANKER_DIR)


@pytest.mark.skipif(not os.path.exists(ONNX_PATH), reason="ONNX model not exported")
def test_onnx_reranker_predict(onnx_reranker, pairs):
    scores = onnx_reranker.predict(pairs)
    assert len(scores) == 3
    assert scores[0] > scores[1], "Relevant pair should outscore irrelevant"
    assert scores[2] > scores[1], "Karma pair should outscore river pair"


@pytest.mark.skipif(not os.path.exists(ONNX_PATH), reason="ONNX model not exported")
def test_onnx_vs_pytorch_equivalence(onnx_reranker, pairs):
    import torch
    from sentence_transformers import CrossEncoder
    # Force CPU to avoid CUDA OOM when GPU memory is already occupied by embeddings.
    # Pass torch.nn.Identity() explicitly to suppress the default sigmoid and get raw
    # logits — matching what ONNXReranker.predict() returns (raw logits, pre-sigmoid).
    pytorch = CrossEncoder(RERANKER_DIR, device="cpu")
    onnx_scores = onnx_reranker.predict(pairs)
    pytorch_scores = pytorch.predict(pairs, activation_fct=torch.nn.Identity()).tolist()
    for i, (o, p) in enumerate(zip(onnx_scores, pytorch_scores)):
        assert abs(o - p) < 0.1, f"Pair {i}: ONNX={o:.4f} vs PyTorch={p:.4f} differ by {abs(o-p):.4f}"


@pytest.mark.skipif(not os.path.exists(ONNX_PATH), reason="ONNX model not exported")
def test_onnx_reranker_empty_input(onnx_reranker):
    scores = onnx_reranker.predict([])
    assert scores == []
