"""
Mass Translation Script — Translate ALL scriptures missing English meanings.

Covers the entire corpus (not just Ramayana/Mahabharata), prioritizing by:
  P1: Atharva Veda, key Rig Veda mandalas, key Ramayana kandas, key Mahabharata books
  P2: Remaining Ramayana, remaining Vedas, secondary Mahabharata books
  P3: All other scriptures with Devanagari-only content

Uses Gemini Flash for cost-effective batch translation.

Usage:
    cd backend && python3 scripts/translate_all_scriptures.py
    cd backend && python3 scripts/translate_all_scriptures.py --max-translate 5000
    cd backend && python3 scripts/translate_all_scriptures.py --dry-run
    cd backend && python3 scripts/translate_all_scriptures.py --scripture "Ramayana"
    cd backend && python3 scripts/translate_all_scriptures.py --priority 1
    cd backend && python3 scripts/translate_all_scriptures.py --no-regen-embeddings
    cd backend && python3 scripts/translate_all_scriptures.py --reset-checkpoint
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
VERSES_PATH = PROCESSED_DIR / "verses.json"
EMBEDDINGS_PATH = PROCESSED_DIR / "embeddings.npy"
CHECKPOINT_PATH = PROCESSED_DIR / "mass_translation_checkpoint.json"


# ------------------------------------------------------------------
# Quality validation
# ------------------------------------------------------------------

_BAD_PATTERNS = [
    "[untranslatable]", "i cannot translate", "n/a", "not available",
    "unable to translate", "translation not possible",
]


def _validate_translation(translation: str, original_text: str) -> bool:
    """Validate a translation meets quality standards."""
    if not translation:
        return False
    # Too short or too long
    if len(translation) < 10 or len(translation) > 500:
        return False
    # Check ASCII alpha ratio — reject echoed Devanagari
    alpha_chars = sum(1 for c in translation if c.isascii() and c.isalpha())
    total_chars = len(translation.replace(" ", ""))
    if total_chars > 0 and alpha_chars / total_chars < 0.5:
        return False
    # Known bad patterns
    trans_lower = translation.lower()
    for pattern in _BAD_PATTERNS:
        if pattern in trans_lower:
            return False
    # Check word overlap with original (>80% = just echoed input)
    if original_text:
        orig_words = set(original_text.lower().split())
        trans_words = set(translation.lower().split())
        if orig_words and trans_words:
            overlap = len(orig_words & trans_words) / max(len(trans_words), 1)
            if overlap > 0.8:
                return False
    return True


# ------------------------------------------------------------------
# Adaptive Rate Limiter
# ------------------------------------------------------------------

class AdaptiveRateLimiter:
    """Rate limiter that speeds up on success and backs off on errors."""

    def __init__(self, initial_delay: float = 2.0):
        self.delay = initial_delay
        self._initial = initial_delay
        self._consecutive_successes = 0

    def on_success(self):
        self._consecutive_successes += 1
        # Speed up after 10 consecutive successes
        if self._consecutive_successes >= 10:
            self.delay = max(0.5, self.delay * 0.8)
            self._consecutive_successes = 0

    def on_rate_limit(self):
        self._consecutive_successes = 0
        self.delay = min(120.0, self.delay * 2)

    def on_error(self):
        self._consecutive_successes = 0
        self.delay = min(30.0, self.delay * 1.5)

    def reset(self):
        self.delay = self._initial
        self._consecutive_successes = 0


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_primarily_devanagari(text: str) -> bool:
    if not text:
        return False
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    devanagari = sum(1 for c in chars if '\u0900' <= c <= '\u097F')
    return devanagari / len(chars) > 0.5


def _needs_translation(verse: Dict) -> bool:
    """Check if a verse needs English translation."""
    if verse.get("source") == "curated_narrative":
        return False
    if verse.get("type") == "temple":
        return False
    if verse.get("meaning") and not _is_primarily_devanagari(verse["meaning"]):
        return False
    if verse.get("text") and not _is_primarily_devanagari(verse["text"]):
        return False
    sanskrit = verse.get("text") or verse.get("sanskrit") or ""
    return bool(sanskrit.strip())


def _get_priority_tier(verse: Dict) -> int:
    """Assign priority tier (1=highest, 3=lowest) for translation ordering."""
    scripture = (verse.get("scripture") or "").lower()
    chapter = str(verse.get("chapter") or "").lower()

    # P1: High-value scriptures and chapters
    if "atharva veda" in scripture:
        return 1
    if "rig veda" in scripture and any(m in chapter for m in ["7", "10"]):
        return 1
    if "bhagavad gita" in scripture:
        return 1
    if "ramayana" in scripture and any(k in chapter for k in [
        "sundarakanda", "ayodhyakanda", "yudhhakanda", "balakanda"
    ]):
        return 1
    if "mahabharata" in scripture and chapter in ("1", "6"):
        return 1
    if "patanjali" in scripture:
        return 1
    if "charaka" in scripture:
        return 1

    # P2: Secondary importance
    if "ramayana" in scripture:
        return 2
    if "rig veda" in scripture:
        return 2
    if "mahabharata" in scripture and chapter in ("2", "3", "5", "12", "13"):
        return 2
    if "yajur veda" in scripture:
        return 2

    # P3: Everything else
    return 3


def select_verses_for_translation(
    verses: List[Dict],
    max_total: int = 0,
    scripture_filter: Optional[str] = None,
    priority_filter: Optional[int] = None,
) -> List[Dict]:
    """Select and prioritize verses needing translation across ALL scriptures.

    Args:
        max_total: Maximum verses to select. 0 = unlimited.
        scripture_filter: Only translate this scripture (case-insensitive substring match).
        priority_filter: Only translate this priority tier (1, 2, or 3).
    """
    candidates = [v for v in verses if _needs_translation(v)]

    if not candidates:
        logger.info("No verses need translation")
        return []

    # Apply scripture filter
    if scripture_filter:
        sf_lower = scripture_filter.lower()
        candidates = [v for v in candidates if sf_lower in (v.get("scripture") or "").lower()]
        logger.info(f"Scripture filter '{scripture_filter}': {len(candidates)} candidates")

    # Apply priority filter
    if priority_filter:
        candidates = [v for v in candidates if _get_priority_tier(v) == priority_filter]
        logger.info(f"Priority filter P{priority_filter}: {len(candidates)} candidates")

    # Sort by priority tier
    candidates.sort(key=_get_priority_tier)

    # Count by tier and scripture
    tiers = {1: [], 2: [], 3: []}
    scripture_counts = {}
    for v in candidates:
        tier = _get_priority_tier(v)
        tiers[tier].append(v)
        s = v.get("scripture", "Unknown")
        scripture_counts[s] = scripture_counts.get(s, 0) + 1

    logger.info(f"Verses needing translation: {len(candidates)} total")
    logger.info(f"  P1 (high priority): {len(tiers[1])}")
    logger.info(f"  P2 (medium priority): {len(tiers[2])}")
    logger.info(f"  P3 (lower priority): {len(tiers[3])}")
    logger.info("  By scripture:")
    for s, count in sorted(scripture_counts.items(), key=lambda x: -x[1]):
        logger.info(f"    {s}: {count}")

    if max_total > 0:
        selected = candidates[:max_total]
        logger.info(f"Selected {len(selected)} for translation (cap={max_total})")
    else:
        selected = candidates
        logger.info(f"Selected {len(selected)} for translation (unlimited)")
    return selected


async def batch_translate(verses_to_translate: List[Dict], batch_size: int = 50) -> int:
    """Translate verses using Gemini Flash. Checkpointed for resume."""
    try:
        from google import genai
    except ImportError:
        logger.error("google-genai not available. pip install google-genai")
        return 0

    if not verses_to_translate:
        return 0

    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set")
        return 0

    # Load checkpoint
    translated_refs = set()
    if CHECKPOINT_PATH.exists():
        try:
            with open(CHECKPOINT_PATH, "r") as f:
                ckpt = json.load(f)
            translated_refs = set(ckpt.get("translated_refs", []))
            logger.info(f"Resuming: {len(translated_refs)} already translated")
        except Exception:
            pass

    remaining = [v for v in verses_to_translate if v.get("reference") not in translated_refs]
    if not remaining:
        logger.info("All selected verses already translated (checkpoint)")
        return 0

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    total_translated = 0
    failed_validation = 0
    rate_limiter = AdaptiveRateLimiter(initial_delay=2.0)
    num_batches = (len(remaining) + batch_size - 1) // batch_size
    start_time = time.time()
    batch_times = []

    logger.info(f"Translating {len(remaining)} verses in {num_batches} batches (size={batch_size})...")

    # Determine scriptures in this run for context-aware prompt
    scriptures_in_run = sorted(set(v.get("scripture", "Unknown") for v in remaining))

    for batch_start in range(0, len(remaining), batch_size):
        batch = remaining[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        batch_start_time = time.time()

        # Context-aware translation prompt
        batch_scriptures = sorted(set(v.get("scripture", "") for v in batch))
        lines = [
            f"You are a scholar of Sanatan Dharma translating verses from: {', '.join(batch_scriptures)}.",
            "",
            "INSTRUCTIONS:",
            "1. Translate each Sanskrit/Hindi verse to clear, accessible English.",
            "2. Preserve the spiritual meaning and philosophical depth.",
            "3. Keep translations concise: 1-3 sentences per verse.",
            "4. For mantras and prayers, convey both literal meaning and spiritual significance.",
            "5. If a verse describes a ritual or practice, include the purpose/benefit.",
            "6. Return ONLY a numbered list matching input numbers. Format: N. translation",
            "7. If genuinely untranslatable, write: N. [untranslatable]",
            "",
        ]
        for idx, v in enumerate(batch):
            text = v.get("text") or v.get("sanskrit") or ""
            if not text or (text.isdigit() and len(text) < 5):
                text = v.get("sanskrit") or ""
            scripture = v.get("scripture", "")
            chapter = v.get("chapter", "")
            reference = v.get("reference", "")
            lines.append(f"{idx + 1}. [{scripture} {chapter}] ({reference}) {text[:500]}")

        prompt = "\n".join(lines)

        try:
            response = client.models.generate_content(
                model=settings.GEMINI_FAST_MODEL,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": 8192},
            )

            batch_count = 0
            batch_failed = 0
            if response.text:
                translations = {}
                for line in response.text.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    m = re.match(r"^\*{0,2}(\d+)[:\.\)]\*{0,2}\s*(.*)", line)
                    if m:
                        num = int(m.group(1)) - 1
                        trans = m.group(2).strip().strip("*").strip()
                        if trans and "[untranslatable]" not in trans.lower():
                            translations[num] = trans

                for idx, v in enumerate(batch):
                    if idx in translations:
                        original_text = v.get("text") or v.get("sanskrit") or ""
                        translation = translations[idx]

                        # Quality validation
                        if not _validate_translation(translation, original_text):
                            batch_failed += 1
                            failed_validation += 1
                            continue

                        v["meaning"] = translation
                        if _is_primarily_devanagari(v.get("text", "")):
                            v["text"] = translation
                        translated_refs.add(v.get("reference", ""))
                        total_translated += 1
                        batch_count += 1

            # Progress tracking
            batch_elapsed = time.time() - batch_start_time
            batch_times.append(batch_elapsed)
            elapsed = time.time() - start_time
            avg_batch_time = sum(batch_times) / len(batch_times)
            remaining_batches = num_batches - batch_num
            eta_minutes = (remaining_batches * avg_batch_time) / 60
            rate = total_translated / (elapsed / 60) if elapsed > 0 else 0

            logger.info(
                f"Batch {batch_num}/{num_batches}: "
                f"+{batch_count} translated, {batch_failed} failed validation | "
                f"Total: {total_translated}/{len(remaining)} | "
                f"Rate: {rate:.0f} verses/min | ETA: {eta_minutes:.1f}min"
            )

            # Save checkpoint every batch
            with open(CHECKPOINT_PATH, "w") as f:
                json.dump({
                    "translated_refs": list(translated_refs),
                    "total": total_translated,
                    "failed_validation": failed_validation,
                }, f)

            rate_limiter.on_success()

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                rate_limiter.on_rate_limit()
                logger.warning(f"Rate limited, backing off {rate_limiter.delay:.1f}s")
            else:
                logger.error(f"Translation batch {batch_num} failed: {e}")
                rate_limiter.on_error()

        await asyncio.sleep(rate_limiter.delay)

    elapsed = time.time() - start_time
    logger.info(
        f"Translation complete: {total_translated} verses translated, "
        f"{failed_validation} failed validation, "
        f"in {elapsed / 60:.1f} minutes"
    )
    return total_translated


def regenerate_embeddings(verses: List[Dict]) -> np.ndarray:
    """Regenerate embeddings for all verses."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not available")
        return np.zeros((len(verses), settings.EMBEDDING_DIM), dtype="float32")

    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    use_prefix = "e5" in settings.EMBEDDING_MODEL.lower()

    texts = []
    for v in verses:
        parts = [v.get("text", ""), v.get("sanskrit", ""), v.get("meaning", "")]
        combined = " ".join(p for p in parts if p).strip().replace("\n", " ")[:1000]
        if use_prefix:
            combined = "passage: " + combined
        texts.append(combined)

    logger.info(f"Generating embeddings for {len(texts)} verses (prefix={'passage' if use_prefix else 'none'})...")
    embeddings = model.encode(
        texts,
        convert_to_tensor=False,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    logger.info(f"Embeddings shape: {embeddings.shape}")
    return embeddings.astype("float32")


def save_data(verses: List[Dict], embeddings: np.ndarray):
    """Save verses.json and embeddings.npy."""
    for v in verses:
        v.pop("embedding", None)

    logger.info(f"Saving {len(verses)} verses to {VERSES_PATH}")
    with open(VERSES_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "verses": verses,
                "metadata": {
                    "total_verses": len(verses),
                    "embedding_dim": int(embeddings.shape[1]) if len(embeddings) > 0 else 0,
                    "embedding_model": settings.EMBEDDING_MODEL,
                    "scriptures": sorted(set(v.get("scripture", "Unknown") for v in verses)),
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    logger.info(f"Saving embeddings to {EMBEDDINGS_PATH}")
    np.save(EMBEDDINGS_PATH, embeddings)
    logger.info("Save complete")


async def main():
    parser = argparse.ArgumentParser(description="Mass-translate all scriptures missing English meanings")
    parser.add_argument("--max-translate", type=int, default=0, help="Max verses to translate (0=unlimited)")
    parser.add_argument("--dry-run", action="store_true", help="Count verses needing translation without translating")
    parser.add_argument("--scripture", type=str, default=None, help="Translate only this scripture (substring match)")
    parser.add_argument("--priority", type=int, choices=[1, 2, 3], default=None, help="Translate only this priority tier")
    parser.add_argument("--batch-size", type=int, default=50, help="Verses per API batch")
    parser.add_argument("--reset-checkpoint", action="store_true", help="Clear checkpoint and start fresh")
    parser.add_argument("--no-regen-embeddings", action="store_true", help="Skip automatic embedding regeneration after translation")
    # Legacy flag kept for backward compatibility
    parser.add_argument("--regen-embeddings", action="store_true", help="(Legacy) Force regenerate embeddings")
    args = parser.parse_args()

    # Handle checkpoint reset
    if args.reset_checkpoint and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint cleared")

    # Load existing data
    if not VERSES_PATH.exists():
        logger.error(f"verses.json not found at {VERSES_PATH}. Run ingest_all_data.py first.")
        sys.exit(1)

    with open(VERSES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    verses = data.get("verses", [])
    logger.info(f"Loaded {len(verses)} existing verses")

    # Analyze translation needs
    to_translate = select_verses_for_translation(
        verses,
        max_total=args.max_translate,
        scripture_filter=args.scripture,
        priority_filter=args.priority,
    )

    if args.dry_run:
        logger.info("Dry run complete. No translations performed.")
        return

    if not to_translate:
        logger.info("No verses need translation.")
    else:
        translated = await batch_translate(to_translate, batch_size=args.batch_size)
        logger.info(f"Translated {translated} verses")

    # Auto-regenerate embeddings (default: yes, unless --no-regen-embeddings)
    should_regen = args.regen_embeddings or (not args.no_regen_embeddings and to_translate)
    if should_regen:
        logger.info("\nRegenerating all embeddings...")
        embeddings = regenerate_embeddings(verses)
        save_data(verses, embeddings)
        logger.info("\nReminder: Restart the backend server to rebuild BM25 index with new data.")
    else:
        # Save updated verses.json (translations only, no embedding regen)
        logger.info("Saving updated verses.json...")
        for v in verses:
            v.pop("embedding", None)
        with open(VERSES_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"verses": verses, "metadata": data.get("metadata", {})},
                f,
                ensure_ascii=False,
                indent=2,
            )

    logger.info("\nDone! Run `python3 tests/retrieval_accuracy_test.py` to verify.")


if __name__ == "__main__":
    asyncio.run(main())
