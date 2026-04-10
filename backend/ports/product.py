"""Port interface for product recommendation service."""
from typing import Any, Dict, List, Optional, Tuple, Protocol, runtime_checkable


@runtime_checkable
class ProductPort(Protocol):
    """Contract for product search and recommendations.

    Apr 2026 redesign: added product_type and price_range filtering
    to support the structured ProductSignal architecture. All search
    methods accept optional type/price filters that flow from the
    IntentAgent's ProductSignal.type_filter field.
    """

    async def search_products(
        self,
        query_text: str,
        life_domain: str = "unknown",
        limit: int = 5,
        emotion: str = "",
        deity: str = "",
        product_type: Optional[str] = None,
        price_range: Optional[Tuple[float, float]] = None,
    ) -> List[Dict[str, Any]]: ...

    async def search_by_metadata(
        self,
        practices: Optional[List[str]] = None,
        deities: Optional[List[str]] = None,
        emotions: Optional[List[str]] = None,
        life_domains: Optional[List[str]] = None,
        product_type: Optional[str] = None,
        benefits: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]: ...

    async def get_recommended_products(
        self,
        category: Optional[str] = None,
        limit: int = 4,
    ) -> List[Dict[str, Any]]: ...
