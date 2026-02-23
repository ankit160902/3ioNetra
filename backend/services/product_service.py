from typing import List, Optional, Dict, Any
import logging
from .auth_service import get_mongo_client
from models.product import Product

logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self):
        self.db = get_mongo_client()
        self.collection = self.db["products"]

    async def get_all_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Fetch all products from the collection"""
        query = {"is_active": True} if active_only else {}
        cursor = self.collection.find(query)
        products = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            products.append(doc)
        return products

    async def search_products(self, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search products by name or category using simple text search"""
        # Clean and split the query into tokens
        import re
        tokens = re.findall(r'\w+', query_text.lower())
        # Filter out common short words
        stop_words = {'i', 'want', 'to', 'buy', 'a', 'the', 'is', 'for', 'in', 'of', 'and', 'my'}
        keywords = [t for t in tokens if t not in stop_words and len(t) > 2]
        
        if not keywords:
            return []

        # Build regex that matches any of the keywords
        regex_pattern = "|".join(keywords)
        
        query = {
            "is_active": True,
            "$or": [
                {"name": {"$regex": regex_pattern, "$options": "i"}},
                {"category": {"$regex": regex_pattern, "$options": "i"}},
                {"description": {"$regex": regex_pattern, "$options": "i"}}
            ]
        }
        cursor = self.collection.find(query).limit(limit)
        products = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            products.append(doc)
        return products

    async def get_recommended_products(self, category: Optional[str] = None, limit: int = 4) -> List[Dict[str, Any]]:
        """Get recommended products, optionally filtered by category"""
        query = {"is_active": True}
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        
        cursor = self.collection.find(query).limit(limit)
        products = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            products.append(doc)
        
        # If no products found in category, return top active products
        if not products and category:
            cursor = self.collection.find({"is_active": True}).limit(limit)
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                products.append(doc)
                
        return products

# Singleton instance
_product_service: Optional[ProductService] = None

def get_product_service() -> ProductService:
    global _product_service
    if _product_service is None:
        _product_service = ProductService()
    return _product_service
