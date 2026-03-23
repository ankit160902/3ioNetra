"""Shared evaluation utilities for QA and CSV dataset evaluators."""

import json
import logging
import re
from typing import Dict, List, Optional

from constants import HOLLOW_PHRASES, FORMULAIC_ENDINGS

logger = logging.getLogger(__name__)


def run_format_checks(
    response: str,
    safety_flag: Optional[str] = None,
    check_product_link_fail: bool = False,
) -> Dict:
    """
    Run automated format and compliance checks on a bot response.

    Parameters
    ----------
    response : str
        The bot response text.
    safety_flag : str | None
        If set and not "standard", checks for helpline numbers.
    check_product_link_fail : bool
        If True, product link presence is a pass/fail check (CSV path).
        If False, it's informational only (QA path).
    """
    checks: Dict = {}

    # 1. No bullet points
    bullet_lines = re.findall(r"^\s*[-*\u2022]\s+", response, re.MULTILINE)
    checks["no_bullet_points"] = {
        "passed": len(bullet_lines) == 0,
        "detail": f"Found {len(bullet_lines)} bullet point lines",
    }

    # 2. No numbered lists
    numbered_lines = re.findall(r"^\s*\d+[\.\)]\s+", response, re.MULTILINE)
    checks["no_numbered_lists"] = {
        "passed": len(numbered_lines) == 0,
        "detail": f"Found {len(numbered_lines)} numbered list lines",
    }

    # 3. No markdown headers
    header_lines = re.findall(r"^#{1,6}\s+", response, re.MULTILINE)
    checks["no_markdown_headers"] = {
        "passed": len(header_lines) == 0,
        "detail": f"Found {len(header_lines)} markdown headers",
    }

    # 4. No hollow phrases
    resp_lower = response.lower()
    found_hollow = [p for p in HOLLOW_PHRASES if p in resp_lower]
    checks["no_hollow_phrases"] = {
        "passed": len(found_hollow) == 0,
        "detail": f"Found: {found_hollow}" if found_hollow else "Clean",
    }

    # 5. No formulaic endings
    last_sentence = response.strip().split(".")[-1].strip().lower()
    last_line = response.strip().split("\n")[-1].strip().lower()
    found_formulaic = [
        e for e in FORMULAIC_ENDINGS if e in last_sentence or e in last_line
    ]
    checks["no_formulaic_endings"] = {
        "passed": len(found_formulaic) == 0,
        "detail": f"Found: {found_formulaic}" if found_formulaic else "Clean",
    }

    # 6. Verse tag compliance (max 1 pair)
    verse_pairs = re.findall(r"\[VERSE\]", response)
    checks["verse_tag_compliance"] = {
        "passed": len(verse_pairs) <= 1,
        "detail": f"Found {len(verse_pairs)} [VERSE] tags",
    }

    # 7. Response length (100-800 words)
    word_count = len(response.split())
    checks["response_length"] = {
        "passed": 100 <= word_count <= 800,
        "detail": f"{word_count} words",
    }

    # 8a. Safety: helpline present for non-standard safety flags
    if safety_flag and safety_flag.lower() != "standard":
        has_helpline = bool(
            re.search(r"\d{10}|\d{4}[-\s]\d{3,4}[-\s]\d{3,4}", response)
        )
        checks["safety_helpline"] = {
            "passed": has_helpline,
            "detail": f"Safety flag={safety_flag}, helpline={'found' if has_helpline else 'MISSING'}",
        }

    # 8b. Product link check
    has_product_link = "my3ionetra.com" in resp_lower
    if check_product_link_fail:
        checks["no_product_link"] = {
            "passed": not has_product_link,
            "detail": f"Product link {'present' if has_product_link else 'absent'}",
        }
    else:
        checks["product_link"] = {
            "passed": True,  # informational only
            "detail": f"Product link {'present' if has_product_link else 'absent'}",
        }

    return checks


def call_llm_judge(
    genai_client,
    prompt: str,
    fallback_keys: List[str],
) -> Dict:
    """
    Call Gemini Flash as an LLM judge and parse the JSON response.

    Parameters
    ----------
    genai_client : google.genai.Client
        Initialised Gemini client.
    prompt : str
        Fully-formatted judge prompt.
    fallback_keys : list[str]
        Score keys to zero-fill on error (e.g. ["tone_match", ...]).
    """
    try:
        result = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"temperature": 0.1},
        )
        text = result.text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Judge parse error: {e}")
        scores = {k: 0 for k in fallback_keys}
        scores["notes"] = f"Judge error: {str(e)[:100]}"
        return scores
