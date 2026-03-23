"""
Shared user-profile builder used by CompanionEngine and ResponseComposer.
"""
from datetime import datetime
from typing import Dict, Optional

from models.memory_context import ConversationMemory

# Module-level panchang cache — computed once per 30 min, shared across all profile builds
_panchang_cache: Optional[Dict] = None
_panchang_cache_date: Optional[str] = None


def _get_panchang_snapshot() -> Optional[Dict]:
    """Return today's panchang data, cached for the day (resets on date change)."""
    global _panchang_cache, _panchang_cache_date
    today = datetime.now().strftime("%Y-%m-%d")
    if _panchang_cache is not None and _panchang_cache_date == today:
        return _panchang_cache

    try:
        from services.panchang_service import get_panchang_service
        panchang = get_panchang_service()
        if panchang and panchang.available:
            enriched = panchang.get_enriched_panchang(datetime.now())
            if "error" not in enriched:
                _panchang_cache = {
                    "tithi": enriched["tithi"],
                    "tithi_significance": enriched.get("tithi_significance", ""),
                    "tithi_good_for": enriched.get("tithi_good_for", ""),
                    "tithi_vrat": enriched.get("tithi_vrat", ""),
                    "nakshatra": enriched["nakshatra"],
                    "nakshatra_quality": enriched.get("nakshatra_quality", ""),
                    "nakshatra_good_for": enriched.get("nakshatra_good_for", ""),
                    "yoga": enriched["yoga"],
                    "yoga_quality": enriched.get("yoga_quality", ""),
                    "paksha": enriched.get("paksha", ""),
                    "masa": enriched.get("masa", ""),
                    "masa_significance": enriched.get("masa_significance", ""),
                    "festival": enriched.get("festival", ""),
                    "festival_mantra": enriched.get("festival_mantra", ""),
                    "festival_rituals": enriched.get("festival_rituals", ""),
                    "festival_significance": enriched.get("festival_significance", ""),
                    "special_day": enriched.get("special_day", ""),
                    "upcoming_festivals": enriched.get("upcoming_festivals", []),
                }
                _panchang_cache_date = today
                return _panchang_cache
    except Exception:
        pass
    return None


def build_user_profile(memory: ConversationMemory, session=None) -> Dict:
    """Build user profile dict from ConversationMemory + optional SessionState."""
    profile: Dict = {}
    story = memory.story if hasattr(memory, "story") else None

    # User identity fields
    if memory.user_name:
        profile["name"] = memory.user_name
    if memory.user_id:
        profile["user_id"] = memory.user_id
    if getattr(memory, "user_email", None):
        profile["email"] = memory.user_email
    if getattr(memory, "user_phone", None):
        profile["phone"] = memory.user_phone
    if getattr(memory, "user_dob", None):
        profile["dob"] = memory.user_dob
    if getattr(memory, "user_created_at", None):
        profile["created_at"] = memory.user_created_at

    # is_returning_user — prefer session if available, else memory
    if session and getattr(session, "is_returning_user", False):
        profile["is_returning_user"] = True
    elif hasattr(memory, "is_returning_user"):
        profile["is_returning_user"] = memory.is_returning_user

    # Demographics + story fields
    if story:
        for field in [
            "age_group", "gender", "profession", "primary_concern",
            "emotional_state", "life_area", "preferred_deity",
            "location", "spiritual_interests",
        ]:
            val = getattr(story, field, None)
            if val:
                profile[field] = val

    # Spiritual profile
    if story:
        for field in ["rashi", "gotra", "nakshatra", "temple_visits", "purchase_history"]:
            val = getattr(story, field, None)
            if val:
                profile[field] = val

    # Session-specific fields
    if session:
        if getattr(session, "last_suggestions", None):
            profile["last_suggestions"] = session.last_suggestions

    # Panchang context — uses module-level daily cache (avoids recomputing 4-6x per request)
    panchang_snapshot = _get_panchang_snapshot()
    if panchang_snapshot:
        profile["current_panchang"] = panchang_snapshot

    return profile
