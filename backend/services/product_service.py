import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from config import settings
from .auth_service import get_mongo_client

logger = logging.getLogger(__name__)

class ProductService:
    # DOMAIN_CATEGORY_MAP removed — replaced by enriched life_domains field on each product
    # emotion_category_boost removed — replaced by EMOTION_BENEFIT_BRIDGE + enriched benefits field
    # physical_categories / service_categories removed — replaced by enriched product_type field

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
            def _fetch():
                return [self._serialize_doc(doc) for doc in self.collection.find(query)]
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"get_all_products DB error: {e}")
            return []

    # Semantic bridge: user's negative emotion → product's positive benefit attributes
    # This is NOT a product map — it maps human emotions to desirable product qualities.
    # Products are enriched with benefits like "peace", "healing" — this bridges the gap.
    EMOTION_BENEFIT_BRIDGE = {
        "anxiety": ["calm", "peace", "clarity"],
        "grief": ["healing", "peace", "hope"],
        "stress": ["calm", "peace", "clarity"],
        "sadness": ["healing", "peace", "hope"],
        "anger": ["calm", "peace", "clarity"],
        "fear": ["protection", "courage", "strength"],
        "confusion": ["clarity", "focus", "peace"],
        "loneliness": ["devotion", "love", "peace"],
        "hopelessness": ["hope", "healing", "strength"],
        "frustration": ["calm", "clarity", "focus"],
        "shame": ["healing", "peace", "hope"],
        "guilt": ["healing", "peace", "hope"],
        "despair": ["hope", "healing", "strength"],
    }

    async def search_by_metadata(
        self,
        practices: Optional[List[str]] = None,
        deities: Optional[List[str]] = None,
        emotions: Optional[List[str]] = None,
        life_domains: Optional[List[str]] = None,
        product_type: Optional[str] = None,
        benefits: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search products using enriched metadata fields.

        Queries MongoDB's enriched arrays (practices, deities, emotions, life_domains, benefits).
        Returns products matching ANY criteria, ranked by match count (most relevant first).
        This replaces all hardcoded keyword maps with data-driven discovery.
        """
        if self.collection is None:
            return []

        # Build $or conditions from provided criteria
        conditions = []
        if practices:
            conditions.append({"practices": {"$in": practices}})
        if deities:
            conditions.append({"deities": {"$in": deities}})
        if emotions:
            # Also bridge to benefits: user emotion → product benefit
            benefit_targets = set()
            for emo in emotions:
                benefit_targets.update(self.EMOTION_BENEFIT_BRIDGE.get(emo.lower(), []))
            conditions.append({"emotions": {"$in": emotions}})
            if benefit_targets:
                conditions.append({"benefits": {"$in": list(benefit_targets)}})
        if life_domains:
            conditions.append({"life_domains": {"$in": life_domains}})
        if product_type:
            conditions.append({"product_type": product_type})
        if benefits:
            conditions.append({"benefits": {"$in": benefits}})

        if not conditions:
            return []

        query = {"is_active": True, "$or": conditions}

        try:
            def _fetch():
                docs = list(self.collection.find(query).limit(limit * 3))
                results = []
                for doc in docs:
                    doc = self._serialize_doc(doc)
                    # Score by match count: more criteria matched = more relevant
                    match_score = 0
                    if practices and any(p in doc.get("practices", []) for p in practices):
                        match_score += 3  # Practice match is strongest signal
                    if deities and any(d in doc.get("deities", []) for d in deities):
                        match_score += 3  # Deity match is strong
                    if life_domains and any(d in doc.get("life_domains", []) for d in life_domains):
                        match_score += 2
                    if emotions:
                        if any(e in doc.get("emotions", []) for e in emotions):
                            match_score += 2
                        # Also check benefit bridge matches
                        benefit_targets = set()
                        for emo in emotions:
                            benefit_targets.update(self.EMOTION_BENEFIT_BRIDGE.get(emo.lower(), []))
                        if any(b in doc.get("benefits", []) for b in benefit_targets):
                            match_score += 1
                    if benefits and any(b in doc.get("benefits", []) for b in benefits):
                        match_score += 1

                    doc["_metadata_score"] = match_score
                    results.append(doc)

                # Sort by match score descending
                results.sort(key=lambda x: x.get("_metadata_score", 0), reverse=True)

                # Filter: require at least one strong signal (practice=3 or deity=3)
                # This prevents consultation services with only emotion/life_domain matches
                # from appearing as "recommended" for every query.
                MIN_METADATA_SCORE = 3
                results = [r for r in results if r.get("_metadata_score", 0) >= MIN_METADATA_SCORE]

                # Deduplicate by name
                seen_names = set()
                deduped = []
                for r in results:
                    if r["name"] not in seen_names:
                        seen_names.add(r["name"])
                        r.pop("_metadata_score", None)
                        deduped.append(r)
                    if len(deduped) >= limit:
                        break

                return deduped

            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"search_by_metadata error: {e}")
            return []

    async def search_products(self, query_text: str, life_domain: str = "unknown", limit: int = 5,
                              emotion: str = "", deity: str = "",
                              allow_category_fallback: bool = True) -> List[Dict[str, Any]]:
        """Search products by text (for explicit user queries). Uses MongoDB $text search."""
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

        # Inject deity into keywords so MongoDB retrieves deity-relevant products
        if deity and deity.lower() not in seen and len(deity) > 2:
            keywords.insert(0, deity.lower())
            seen.add(deity.lower())

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
            def _text_search():
                cursor = self.collection.find(
                    text_query,
                    {"_text_score": {"$meta": "textScore"}},
                ).sort([("_text_score", {"$meta": "textScore"})]).limit(50)
                return [self._serialize_doc(doc) for doc in cursor]

            raw_products = await asyncio.to_thread(_text_search)
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
            def _regex_search():
                return [self._serialize_doc(doc) for doc in self.collection.find(query).limit(50)]

            raw_products = await asyncio.to_thread(_regex_search)
            
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

            # Multi-term boost: strong bonus when product matches ALL search terms
            if matched_keywords > 1:
                score += 10 * (matched_keywords - 1)
            # Extra bonus for matching ALL keywords — ensures "hanuman murti" ranks
            # Hanuman murtis above generic murtis
            if len(keywords) > 1 and matched_keywords == len(keywords):
                score += 20

            # Life Domain boost (enriched field — replaces hardcoded DOMAIN_CATEGORY_MAP)
            if life_domain and life_domain.lower() in product.get("life_domains", []):
                score += 30

            # Deity boost (enriched field + name match)
            if deity:
                deity_lower = deity.lower()
                if deity_lower in product.get("deities", []):
                    score += 30  # Enriched deity match (strongest)
                elif deity_lower in name_lower:
                    score += 20  # Name text match (fallback)
                elif deity_lower in desc_lower:
                    score += 10

            # Emotion benefit boost (enriched field — replaces hardcoded emotion_category_boost)
            if emotion:
                # Bridge: user emotion → product benefits
                target_benefits = ProductService.EMOTION_BENEFIT_BRIDGE.get(emotion.lower(), [])
                product_benefits = product.get("benefits", [])
                if any(b in product_benefits for b in target_benefits):
                    score += 20
                # Also check direct emotion match on enriched emotions field
                if emotion.lower() in product.get("emotions", []):
                    score += 15

            # Product type boost (enriched field — replaces hardcoded category lists)
            ptype = product.get("product_type", "")
            if ptype == "physical":
                score += 10
            elif ptype in ("service", "consultation"):
                score += 15

            # Price-tier moderation
            price = product.get("amount", 0)
            if isinstance(price, (int, float)):
                if price <= 999:
                    score += 5
                elif price >= 3000:
                    score -= 5

            return score

        # Sort by keyword score descending
        sorted_products = sorted(raw_products, key=calculate_score, reverse=True)

        # Clean up internal _text_score field before returning (Issue 29)
        for p in sorted_products:
            p.pop("_text_score", None)

        # ── Semantic Reranking via Embeddings ──
        # Use the RAG pipeline's embedding model to compute cosine similarity
        # between the conversation context and each product's name+description.
        # This ensures products are semantically relevant (e.g., Vishnu products
        # rank higher when talking about Vishnu, not random Durga murtis).
        try:
            from routers.dependencies import get_rag_pipeline
            rag = get_rag_pipeline()
            if rag and rag.available and rag._embedding_model is not None and sorted_products:
                import numpy as np
                # Build context string from query + deity
                context = query_text
                if deity:
                    context = f"{deity} {context}"

                context_vec = rag._embedding_model.encode(
                    [f"query: {context}"], convert_to_tensor=False, show_progress_bar=False
                )[0]
                context_vec = np.asarray(context_vec, dtype="float32")
                context_norm = np.linalg.norm(context_vec)
                if context_norm > 0:
                    context_vec /= context_norm

                for p in sorted_products:
                    product_text = f"{p.get('name', '')} {p.get('description', '')[:200]}"
                    prod_vec = rag._embedding_model.encode(
                        [f"passage: {product_text}"], convert_to_tensor=False, show_progress_bar=False
                    )[0]
                    prod_vec = np.asarray(prod_vec, dtype="float32")
                    prod_norm = np.linalg.norm(prod_vec)
                    if prod_norm > 0:
                        prod_vec /= prod_norm
                    sim = float(np.dot(context_vec, prod_vec))
                    # Blend: 40% keyword score + 60% semantic similarity (scaled to ~100)
                    keyword_score = calculate_score(p)
                    p["_final_score"] = 0.4 * keyword_score + 0.6 * (sim * 100)

                sorted_products = sorted(sorted_products, key=lambda x: x.get("_final_score", 0), reverse=True)
                for p in sorted_products:
                    p.pop("_final_score", None)
                logger.info(f"Product semantic reranking applied for context='{context[:40]}'")
        except Exception as e:
            logger.warning(f"Semantic reranking skipped (non-fatal): {e}")

        # Minimum relevance gate: drop products below the score floor
        min_score = getattr(settings, 'PRODUCT_MIN_RELEVANCE_SCORE', 15.0)
        pre_filter_count = len(sorted_products)
        sorted_products = [p for p in sorted_products if calculate_score(p) >= min_score]
        if pre_filter_count > 0 and not sorted_products:
            logger.info(f"All {pre_filter_count} products below min relevance score ({min_score}) for query '{query_text[:40]}'")
            return []

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

        # Domain-level fallback: fill remaining slots from life_domain-tagged products
        # Uses enriched life_domains field instead of hardcoded category map
        if allow_category_fallback and len(diverse) < limit and life_domain:
            if self.collection is not None:
                existing_names = {p.get("name") for p in diverse}
                # Query by enriched life_domains field
                cat_query = {
                    "is_active": True,
                    "life_domains": life_domain.lower(),
                }
                try:
                    def _cat_search():
                        results = []
                        for doc in self.collection.find(cat_query).limit(limit * 3):
                            doc = self._serialize_doc(doc)
                            if doc.get("name") not in existing_names:
                                results.append(doc)
                        return results
                    fallback_pool = await asyncio.to_thread(_cat_search)
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
            def _fetch():
                results = [self._serialize_doc(doc) for doc in self.collection.find(query).limit(limit)]
                # If no products found in category, return top active products
                if not results and category:
                    results = [self._serialize_doc(doc) for doc in self.collection.find({"is_active": True}).limit(limit)]
                return results
            return await asyncio.to_thread(_fetch)
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
