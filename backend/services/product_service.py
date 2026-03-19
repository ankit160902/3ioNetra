from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from .auth_service import get_mongo_client

logger = logging.getLogger(__name__)

class ProductService:
    # Domain → categories map (used for reranking boosts AND category-level fallback)
    DOMAIN_CATEGORY_MAP = {
        "career": ["Astrostore", "ASTROLOGY", "Astro List", "Book-now", "Mangal"],
        "relationships": ["Astrostore", "ASTROLOGY", "Pooja Essential", "Astro List", "Mangal"],
        "health": ["Astrostore", "GST-Included"],
        "spiritual": [
            "Pooja Essential", "Puja Essential", "Spiritual Home", "Astrostore",
            "Pooja Murti", "Seva", "Puja", "members-form",
            "Sculptures & Statues", "Chadhawa", "lord vishnu",
            "bhagwan krishna blessings", "flower offering to maa durga", "Bhajan Clubbing",
        ],
        "family": ["Pooja Essential", "Puja Essential", "Spiritual Home", "Pooja Murti", "Sculptures & Statues"],
        "finance": ["Astrostore", "ASTROLOGY", "Astro List", "Book-now", "Mangal"],
        "education": ["Astrostore", "Astro List"],
        "self-improvement": [
            "Astrostore", "Astro List",
            "Abundance alignment", "Abundance Mindset", "Conscious Parenting",
        ],
        # _update_memory domain labels
        "career & finance": ["Astrostore", "ASTROLOGY", "Astro List", "Book-now", "Mangal"],
        "physical health": ["Astrostore", "GST-Included"],
        "ayurveda & wellness": ["Astrostore", "GST-Included"],
        "yoga practice": ["Astrostore", "GST-Included"],
        "meditation & mind": ["Astrostore", "Pooja Essential"],
        "spiritual growth": [
            "Pooja Essential", "Spiritual Home", "Astrostore", "Pooja Murti", "Seva", "members-form",
            "Sculptures & Statues", "Chadhawa", "lord vishnu",
            "bhagwan krishna blessings", "flower offering to maa durga", "Bhajan Clubbing",
        ],
    }

    def __init__(self):
        self.db = get_mongo_client()
        self.collection = self.db["products"] if self.db is not None else None

    @staticmethod
    def _serialize_doc(doc: dict) -> dict:
        """Convert MongoDB doc fields to JSON-safe types."""
        doc["_id"] = str(doc["_id"])
        for key in ("created_at", "updated_at"):
            if key in doc and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        return doc

    async def get_all_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Fetch all products from the collection"""
        if self.collection is None:
            return []
        query = {"is_active": True} if active_only else {}
        try:
            cursor = self.collection.find(query)
            products = []
            for doc in cursor:
                doc = self._serialize_doc(doc)
                products.append(doc)
            return products
        except Exception as e:
            logger.error(f"get_all_products DB error: {e}")
            return []

    async def search_products(self, query_text: str, life_domain: str = "unknown", limit: int = 5,
                              emotion: str = "", deity: str = "") -> List[Dict[str, Any]]:
        """Search products by name or category with precision and domain context"""
        import re
        # Tokenize and clean
        tokens = re.findall(r'\w+', query_text.lower())
        stop_words = {'i', 'want', 'to', 'buy', 'a', 'the', 'is', 'for', 'in', 'of', 'and', 'my', 'with', 'give', 'me', 'some', 'any', 'essentials', 'requirements', 'needed', 'please', 'take', 'help', 'from'}
        # Use a list to maintain order but deduplicate
        seen = set()
        keywords = []
        for t in tokens:
            if t not in stop_words and len(t) > 2 and t not in seen:
                keywords.append(t)
                seen.add(t)

        if not keywords or self.collection is None:
            return []

        # Primary path: MongoDB $text search using the products_text_search
        # index (Issue 29). Falls back to regex if text index is unavailable.
        search_string = " ".join(keywords)
        raw_products = []
        used_text_search = False

        try:
            text_query = {
                "$text": {"$search": search_string},
                "is_active": True,
            }
            cursor = self.collection.find(
                text_query,
                {"_text_score": {"$meta": "textScore"}},
            ).sort([("_text_score", {"$meta": "textScore"})]).limit(50)

            for doc in cursor:
                doc = self._serialize_doc(doc)
                raw_products.append(doc)
            used_text_search = True
        except Exception as e:
            logger.warning(f"$text search failed, falling back to regex: {e}")
            # Fallback: regex-based search if text index is unavailable
            regex_pattern = "|".join(re.escape(kw) for kw in keywords)
            query = {
                "is_active": True,
                "$or": [
                    {"name": {"$regex": regex_pattern, "$options": "i"}},
                    {"category": {"$regex": regex_pattern, "$options": "i"}},
                    {"description": {"$regex": regex_pattern, "$options": "i"}},
                ],
            }
            cursor = self.collection.find(query).limit(50)
            for doc in cursor:
                doc = self._serialize_doc(doc)
                raw_products.append(doc)
            
        # Re-rank based on keyword match density and multi-term boosting
        def calculate_score(product):
            # When $text search was used, seed score from textScore (Issue 29).
            # textScore * 10 gives a range (~5-20) comparable to keyword boosts.
            score = product.get("_text_score", 0) * 10 if used_text_search else 0
            matched_keywords = 0
            name_lower = product.get("name", "").lower()
            cat_lower = product.get("category", "").lower()
            desc_lower = product.get("description", "").lower()
            
            for kw in keywords:
                has_match = False
                if kw in name_lower:
                    score += 15 # Even higher weight for name
                    has_match = True
                if kw in cat_lower:
                    score += 5  
                    has_match = True
                if kw in desc_lower:
                    score += 1  
                    has_match = True
                
                if has_match:
                    matched_keywords += 1

            # Multi-term boost: additive bonus per extra match (avoids multiplicative distortion)
            if matched_keywords > 1:
                score += 10 * (matched_keywords - 1)

            # Life Domain Category Boosting (uses class-level DOMAIN_CATEGORY_MAP)
            boosted_categories = ProductService.DOMAIN_CATEGORY_MAP.get(life_domain.lower(), [])
            if any(cat in product.get("category", "") for cat in boosted_categories):
                score += 30  # Domain match boost (higher than emotion)

            # Deity name boost
            if deity:
                deity_lower = deity.lower()
                if deity_lower in name_lower:
                    score += 30
                if deity_lower in desc_lower:
                    score += 10

            # Emotion category boost
            emotion_category_boost = {
                "anxiety": ["Astrostore"],
                "grief": ["Seva", "Astro List", "Spiritual"],
                "confusion": ["Astro List", "ASTROLOGY", "Ank Shastra"],
                "anger": ["Astrostore"],
                "stress": ["Astrostore", "GST-Included"],
                "fear": ["Astrostore", "Pooja Murti"],
                "hopelessness": ["Astro List", "Spiritual"],
                "sadness": ["Astrostore", "Astro List"],
                "loneliness": ["Astrostore", "GST-Included", "Astro List"],
                "frustration": ["Astrostore", "Astro List"],
                "despair": ["Astro List", "Spiritual", "Seva"],
                "shame": ["Astro List", "Astrostore"],
                "guilt": ["Seva", "Astro List", "Astrostore"],
                "jealousy": ["Astrostore"],
            }
            if emotion:
                emotion_cats = emotion_category_boost.get(emotion.lower(), [])
                if any(cat in product.get("category", "") for cat in emotion_cats):
                    score += 20  # Emotion boost (lower than domain)

            # Category Boosts
            # 1. Physical products boost
            physical_categories = [
                "Astrostore", "Pooja Essential", "Puja Essential", "Spiritual Home",
                "Sculptures & Statues", "Chadhawa", "lord vishnu", "Pooja Murti",
                "flower offering to maa durga", "bhagwan krishna blessings",
            ]
            if product.get("category") in physical_categories:
                score += 10

            # 2. Spiritual Services and Astrology boost
            service_categories = [
                "ASTROLOGY", "Astro List", "Puja", "Seva", "Ank Shastra",
                "Book-now", "members-form", "Mangal", "Bhajan Clubbing",
                "Abundance alignment", "Abundance Mindset", "Conscious Parenting",
            ]
            if product.get("category") in service_categories:
                score += 15

            # 3. Price-tier moderation: mildly boost accessible items, penalize expensive ones
            price = product.get("amount", 0)
            if isinstance(price, (int, float)):
                if price <= 999:
                    score += 5
                elif price >= 3000:
                    score -= 5

            return score

        # Sort by score descending
        sorted_products = sorted(raw_products, key=calculate_score, reverse=True)

        # Clean up internal _text_score field before returning (Issue 29)
        for p in sorted_products:
            p.pop("_text_score", None)

        # Deduplicate products by name (catalog may have duplicate entries)
        seen_names = set()
        deduped = []
        for p in sorted_products:
            if p["name"] not in seen_names:
                seen_names.add(p["name"])
                deduped.append(p)

        # Category-level diversity: max 2 products per subcategory name pattern
        # Prevents returning 3 Rose Quartz variants or 3 similar Moon Lamps
        diverse = []
        pattern_counts: Dict[str, int] = {}
        max_per_pattern = 2
        for p in deduped:
            # Extract a normalised pattern from product name: first two significant words
            name_words = re.findall(r'[a-zA-Z]+', p.get("name", "").lower())
            pattern_key = " ".join(name_words[:2]) if len(name_words) >= 2 else p.get("name", "").lower()
            count = pattern_counts.get(pattern_key, 0)
            if count < max_per_pattern:
                diverse.append(p)
                pattern_counts[pattern_key] = count + 1
            if len(diverse) >= limit:
                break

        # Category-level fallback: fill remaining slots from domain-relevant categories
        if len(diverse) < limit and life_domain:
            fallback_categories = self.DOMAIN_CATEGORY_MAP.get(life_domain.lower(), [])
            if fallback_categories and self.collection is not None:
                existing_names = {p.get("name") for p in diverse}
                cat_query = {
                    "is_active": True,
                    "category": {"$in": fallback_categories},
                }
                try:
                    cat_cursor = self.collection.find(cat_query).limit(limit * 3)
                    fallback_pool = []
                    for doc in cat_cursor:
                        doc = self._serialize_doc(doc)
                        if doc.get("name") not in existing_names:
                            fallback_pool.append(doc)
                except Exception as e:
                    logger.warning(f"Category fallback query failed: {e}")
                    fallback_pool = []

                # Score and sort fallback products
                fallback_pool.sort(key=calculate_score, reverse=True)

                for p in fallback_pool:
                    if len(diverse) >= limit:
                        break
                    if p["name"] in seen_names:
                        continue
                    name_words = re.findall(r'[a-zA-Z]+', p.get("name", "").lower())
                    pattern_key = " ".join(name_words[:2]) if len(name_words) >= 2 else p.get("name", "").lower()
                    count = pattern_counts.get(pattern_key, 0)
                    if count < max_per_pattern:
                        diverse.append(p)
                        seen_names.add(p["name"])
                        pattern_counts[pattern_key] = count + 1

        return diverse[:limit]

    async def get_recommended_products(self, category: Optional[str] = None, limit: int = 4) -> List[Dict[str, Any]]:
        """Get recommended products, optionally filtered by category"""
        if self.collection is None:
            return []
        query = {"is_active": True}
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        
        try:
            cursor = self.collection.find(query).limit(limit)
            products = []
            for doc in cursor:
                doc = self._serialize_doc(doc)
                products.append(doc)

            # If no products found in category, return top active products
            if not products and category:
                cursor = self.collection.find({"is_active": True}).limit(limit)
                for doc in cursor:
                    doc = self._serialize_doc(doc)
                    products.append(doc)

            return products
        except Exception as e:
            logger.error(f"get_recommended_products DB error: {e}")
            return []

# Singleton instance
_product_service: Optional[ProductService] = None

def get_product_service() -> ProductService:
    global _product_service
    if _product_service is None:
        _product_service = ProductService()
    return _product_service
