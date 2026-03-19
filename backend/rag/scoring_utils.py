from typing import Dict


def get_doc_score(doc: Dict) -> float:
    """Return the best available numeric score from a retrieved document.
    Fallback order: final_score > rerank_score > score > 0.0"""
    return float(
        doc.get("final_score")
        or doc.get("rerank_score")
        or doc.get("score")
        or 0.0
    )
