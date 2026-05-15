"""Pydantic model for product metadata enrichment.

Validates Gemini auto-tagging output before storing in MongoDB.
Each field has constrained allowed values to prevent garbage data.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Allowed values (canonical lists)
# ---------------------------------------------------------------------------

ALLOWED_PRACTICES = {
    "japa", "puja", "meditation", "yoga", "havan", "abhishek", "aarti",
    "seva", "vrat", "darshan", "consultation", "crystal_healing",
    "home_temple", "daily_worship", "pranayama", "sankalpa", "kirtan",
}

ALLOWED_EMOTIONS = {
    "anxiety", "stress", "grief", "anger", "confusion", "fear",
    "loneliness", "hopelessness", "sadness", "frustration", "shame",
    "guilt", "peace", "joy", "gratitude", "focus", "courage",
    "protection", "prosperity", "healing", "love", "hope",
    "calm", "clarity", "strength", "devotion",
}

ALLOWED_LIFE_DOMAINS = {
    "spiritual", "career", "relationships", "family", "health",
    "education", "finance", "self_improvement", "marriage",
    "parenting", "wellness", "meditation",
}

ALLOWED_PRODUCT_TYPES = {"physical", "service", "consultation", "experience"}

ALLOWED_DEITIES = {
    "shiva", "vishnu", "krishna", "rama", "hanuman", "ganesh", "ganesha",
    "durga", "lakshmi", "saraswati", "kali", "parvati", "surya",
    "shrinathji", "murugan", "naag", "dhanvantari", "radha",
    "sita", "balaji", "mahadev", "nandi",
}


# ---------------------------------------------------------------------------
# Enrichment model
# ---------------------------------------------------------------------------

class ProductEnrichment(BaseModel):
    """Validated metadata for a single product. Output of Gemini enrichment."""

    tags: List[str] = Field(default_factory=list, min_length=1, max_length=15)
    deities: List[str] = Field(default_factory=list, max_length=5)
    practices: List[str] = Field(default_factory=list, max_length=8)
    emotions: List[str] = Field(default_factory=list, max_length=10)
    life_domains: List[str] = Field(default_factory=list, max_length=5)
    benefits: List[str] = Field(default_factory=list, min_length=1, max_length=8)
    product_type: str = "physical"
    occasion_tags: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if not isinstance(v, list):
            return ["general"]
        return [t.strip().lower() for t in v if isinstance(t, str) and t.strip()][:15]

    @field_validator("deities", mode="before")
    @classmethod
    def clean_deities(cls, v):
        if not isinstance(v, list):
            return []
        cleaned = []
        for d in v:
            if isinstance(d, str):
                d = d.strip().lower()
                # Normalize common variations
                if d in ("ganesh", "ganesha", "ganapati"):
                    d = "ganesh"
                if d in ("mahadev", "shiv"):
                    d = "shiva"
                if d in ("ram",):
                    d = "rama"
                if d in ALLOWED_DEITIES:
                    cleaned.append(d)
        return list(set(cleaned))[:5]

    @field_validator("practices", mode="before")
    @classmethod
    def clean_practices(cls, v):
        if not isinstance(v, list):
            return []
        return [p.strip().lower() for p in v
                if isinstance(p, str) and p.strip().lower() in ALLOWED_PRACTICES][:8]

    @field_validator("emotions", mode="before")
    @classmethod
    def clean_emotions(cls, v):
        if not isinstance(v, list):
            return []
        return [e.strip().lower() for e in v
                if isinstance(e, str) and e.strip().lower() in ALLOWED_EMOTIONS][:10]

    @field_validator("life_domains", mode="before")
    @classmethod
    def clean_life_domains(cls, v):
        if not isinstance(v, list):
            return []
        cleaned = []
        for d in v:
            if isinstance(d, str):
                d = d.strip().lower().replace(" ", "_").replace("-", "_")
                if d in ALLOWED_LIFE_DOMAINS:
                    cleaned.append(d)
        return list(set(cleaned))[:5]

    @field_validator("benefits", mode="before")
    @classmethod
    def clean_benefits(cls, v):
        if not isinstance(v, list):
            return ["general"]
        return [b.strip().lower() for b in v if isinstance(b, str) and b.strip()][:8]

    @field_validator("product_type", mode="before")
    @classmethod
    def clean_product_type(cls, v):
        if isinstance(v, str) and v.strip().lower() in ALLOWED_PRODUCT_TYPES:
            return v.strip().lower()
        return "physical"

    @field_validator("occasion_tags", mode="before")
    @classmethod
    def clean_occasion_tags(cls, v):
        if not isinstance(v, list):
            return []
        return [t.strip().lower() for t in v if isinstance(t, str) and t.strip()][:10]

    def to_mongo_update(self) -> dict:
        """Return a dict suitable for MongoDB $set operation."""
        return {
            "tags": self.tags,
            "deities": self.deities,
            "practices": self.practices,
            "emotions": self.emotions,
            "life_domains": self.life_domains,
            "benefits": self.benefits,
            "product_type": self.product_type,
            "occasion_tags": self.occasion_tags,
            "enrichment_version": 1,
            "enriched_at": datetime.utcnow().isoformat(),
        }
