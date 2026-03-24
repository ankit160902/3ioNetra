"""
Export the embedding model (multilingual-e5-large) to ONNX INT8 format
for ~30-50ms faster inference per embedding call.

Usage:
    pip install optimum[onnxruntime] onnxruntime
    python scripts/export_onnx.py

The exported model will be saved to ./models/e5-large-onnx/
Set EMBEDDING_ONNX_ENABLED=true and EMBEDDING_ONNX_PATH=./models/e5-large-onnx
in your .env to use it.
"""

import os
import sys
from pathlib import Path

def main():
    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction, ORTQuantizer
        from optimum.onnxruntime.configuration import AutoQuantizationConfig
        from transformers import AutoTokenizer
    except ImportError:
        print("Error: Install required packages first:")
        print("  pip install optimum[onnxruntime] onnxruntime")
        sys.exit(1)

    model_name = "intfloat/multilingual-e5-large"
    output_dir = Path(__file__).parent.parent / "models" / "e5-large-onnx"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting {model_name} to ONNX...")

    # Export to ONNX
    model = ORTModelForFeatureExtraction.from_pretrained(model_name, export=True)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Save the base ONNX model
    onnx_base_dir = output_dir / "base"
    onnx_base_dir.mkdir(exist_ok=True)
    model.save_pretrained(onnx_base_dir)
    tokenizer.save_pretrained(onnx_base_dir)

    print(f"Base ONNX model saved to {onnx_base_dir}")

    # Quantize to INT8
    print("Quantizing to INT8...")
    quantizer = ORTQuantizer.from_pretrained(onnx_base_dir)
    qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=True)
    quantizer.quantize(save_dir=output_dir, quantization_config=qconfig)

    # Copy tokenizer files to final output dir
    tokenizer.save_pretrained(output_dir)

    print(f"Quantized ONNX model saved to {output_dir}")
    print(f"\nTo use: set these in .env:")
    print(f"  EMBEDDING_ONNX_ENABLED=true")
    print(f"  EMBEDDING_ONNX_PATH={output_dir}")

    # Verify
    print("\nVerifying exported model...")
    loaded = ORTModelForFeatureExtraction.from_pretrained(output_dir)
    inputs = tokenizer("query: test embedding", return_tensors="pt")
    outputs = loaded(**inputs)
    print(f"Output shape: {outputs.last_hidden_state.shape}")
    print("Export and verification successful!")


if __name__ == "__main__":
    main()
