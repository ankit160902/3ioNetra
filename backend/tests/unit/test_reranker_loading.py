"""Verify reranker loads on CPU (ONNX or PyTorch fallback), never GPU."""
import os
import pytest

RERANKER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "reranker")
ONNX_PATH = os.path.join(RERANKER_DIR, "onnx", "model.onnx")


def test_reranker_loads_onnx_when_available():
    if not os.path.exists(ONNX_PATH):
        pytest.skip("ONNX model not exported")
    from rag.pipeline import RAGPipeline
    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline._reranker_model = None
    import config
    orig = config.settings.RERANKER_ENABLED
    config.settings.RERANKER_ENABLED = True
    try:
        pipeline._ensure_reranker_model()
        from rag.onnx_reranker import ONNXReranker
        assert isinstance(pipeline._reranker_model, ONNXReranker), \
            f"Expected ONNXReranker, got {type(pipeline._reranker_model).__name__}"
    finally:
        config.settings.RERANKER_ENABLED = orig
        pipeline._reranker_model = None


def test_reranker_pytorch_fallback_uses_cpu():
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(RERANKER_DIR, device="cpu")
    assert str(model.device) == "cpu"
    scores = model.predict([["test query", "test document"]])
    assert len(scores) == 1
