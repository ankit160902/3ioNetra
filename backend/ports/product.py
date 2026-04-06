"""Port interface for product recommendation service."""
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ProductPort(Protocol):
    """Contract for product search and recommendations."""

    async def search_products(
        self,
        query_text: str,
        life_domain: str = "unknown",
        limit: int = 5,
        emotion: str = "",
        deity: str = "",
        allow_category_fallback: bool = True,
    ) -> List[Dict[str, Any]]: ...

    async def get_recommended_products(
        self,
        category: Optional[str] = None,
        limit: int = 4,
    ) -> List[Dict[str, Any]]: ...
