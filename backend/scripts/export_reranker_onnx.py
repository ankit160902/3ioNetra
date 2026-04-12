"""Export bge-reranker-v2-m3 to ONNX format for CPU inference.

Usage: python scripts/export_reranker_onnx.py
Output: models/reranker/onnx/model.onnx + tokenizer files
"""
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def export():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "reranker")
    out_dir = os.path.join(src_dir, "onnx")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Loading PyTorch model from {src_dir}...")
    tokenizer = AutoTokenizer.from_pretrained(src_dir)
    model = AutoModelForSequenceClassification.from_pretrained(src_dir)
    model.eval()

    dummy = tokenizer(
        ["What is dharma?"],
        ["Dharma is the cosmic law and order"],
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )

    onnx_path = os.path.join(out_dir, "model.onnx")
    print(f"Exporting to {onnx_path}...")
    with torch.no_grad():
        torch.onnx.export(
            model,
            (dummy["input_ids"], dummy["attention_mask"]),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "logits": {0: "batch"},
            },
            opset_version=14,
        )

    for fname in ["tokenizer.json", "tokenizer_config.json",
                   "special_tokens_map.json", "sentencepiece.bpe.model", "config.json"]:
        src = os.path.join(src_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, out_dir)

    import onnxruntime as ort
    import numpy as np
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    out = sess.run(None, {
        "input_ids": dummy["input_ids"].numpy(),
        "attention_mask": dummy["attention_mask"].numpy(),
    })
    print(f"ONNX verification OK — output shape: {out[0].shape}, score: {out[0][0]}")
    print(f"Exported to: {out_dir}")


if __name__ == "__main__":
    export()
