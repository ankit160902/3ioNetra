from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from .auth_service import get_mongo_client
from models.product import Product

logger = logging.getLogger(__name__)

class ProductService:
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
        cursor = self.collection.find(query)
        products = []
        for doc in cursor:
            doc = self._serialize_doc(doc)
            products.append(doc)
        return products

    async def search_products(self, query_text: str, life_domain: str = "unknown", limit: int = 5,
                              emotion: str = "", deity: str = "") -> List[Dict[str, Any]]:
        """Search products by name or category with precision and domain context"""
        import re
        # Tokenize and clean
        tokens = re.findall(r'\w+', query_text.lower())
        stop_words = {'i', 'want', 'to', 'buy', 'a', 'the', 'is', 'for', 'in', 'of', 'and', 'my', 'with', 'give', 'me', 'some', 'any', 'essentials', 'requirements', 'needed', 'please', 'take', 'help', 'from', 'book'}
        # Use a list to maintain order but deduplicate
        seen = set()
        keywords = []
        for t in tokens:
            if t not in stop_words and len(t) > 2 and t not in seen:
                keywords.append(t)
                seen.add(t)
        
        if not keywords or self.collection is None:
            return []

        # Strategy:
        # 1. Broad OR search across name, category, and description
        # 2. Ranking: We'll fetch a larger set and rank by term match density and variety
        
        regex_pattern = "|".join(keywords)
        
        query = {
            "is_active": True,
            "$or": [
                {"name": {"$regex": regex_pattern, "$options": "i"}},
                {"category": {"$regex": regex_pattern, "$options": "i"}},
                {"description": {"$regex": regex_pattern, "$options": "i"}}
            ]
        }
        
        # Increase limit to 50 to ensure we find specific items in a large catalog
        cursor = self.collection.find(query).limit(50) 
        raw_products = []
        for doc in cursor:
            doc = self._serialize_doc(doc)
            raw_products.append(doc)
            
        # Re-rank based on keyword match density and multi-term boosting
        def calculate_score(product):
            score = 0
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

            # Multi-term boost: significantly reward products that match more of the search terms
            if matched_keywords > 1:
                score *= (1 + matched_keywords) 

            # Life Domain Category Boosting
            domain_category_map = {
                "career": ["Astrostore", "ASTROLOGY", "Astro List", "Book-now"],
                "relationships": ["Astrostore", "ASTROLOGY", "Pooja Essential", "Astro List"],
                "health": ["Astrostore", "GST-Included"],
                "spiritual": ["Pooja Essential", "Puja Essential", "Spiritual Home", "Astrostore", "Pooja Murti", "Seva", "Puja"],
                "family": ["Pooja Essential", "Puja Essential", "Spiritual Home", "Pooja Murti"],
                "finance": ["Astrostore", "ASTROLOGY", "Astro List", "Book-now"],
                # _update_memory domain labels
                "career & finance": ["Astrostore", "ASTROLOGY", "Astro List", "Book-now"],
                "physical health": ["Astrostore", "GST-Included"],
                "ayurveda & wellness": ["Astrostore", "GST-Included"],
                "yoga practice": ["Astrostore", "GST-Included"],
                "meditation & mind": ["Astrostore", "Pooja Essential"],
                "spiritual growth": ["Pooja Essential", "Spiritual Home", "Astrostore", "Pooja Murti", "Seva"],
            }

            boosted_categories = domain_category_map.get(life_domain.lower(), [])
            if any(cat in product.get("category", "") for cat in boosted_categories):
                score += 25  # Significant boost for domain match

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
            }
            if emotion:
                emotion_cats = emotion_category_boost.get(emotion.lower(), [])
                if any(cat in product.get("category", "") for cat in emotion_cats):
                    score += 15

            # Category Boosts
            # 1. Physical products boost
            physical_categories = ["Astrostore", "Pooja Essential", "Puja Essential", "Spiritual Home"]
            if product.get("category") in physical_categories:
                score += 10

            # 2. Spiritual Services and Astrology boost
            service_categories = ["ASTROLOGY", "Astro List", "Puja", "Seva", "Ank Shastra"]
            if product.get("category") in service_categories:
                score += 15 

            return score

        # Sort by score descending
        sorted_products = sorted(raw_products, key=calculate_score, reverse=True)
        return sorted_products[:limit]

    async def get_recommended_products(self, category: Optional[str] = None, limit: int = 4) -> List[Dict[str, Any]]:
        """Get recommended products, optionally filtered by category"""
        if self.collection is None:
            return []
        query = {"is_active": True}
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        
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

# Singleton instance
_product_service: Optional[ProductService] = None

def get_product_service() -> ProductService:
    global _product_service
    if _product_service is None:
        _product_service = ProductService()
    return _product_service
