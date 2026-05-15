from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Product(BaseModel):
    name: str
    category: str
    amount: float
    currency: str = "INR"
    description: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Authentic 5-Mukhi Rudraksha Mala",
                "category": "Spiritual Accessories",
                "amount": 499.0,
                "currency": "INR",
                "description": "Natural 5 Mukhi Rudraksha Mala for meditation and chanting.",
                "image_url": "https://example.com/rudraksha.jpg",
                "product_url": "https://my3ionetra.com/products/rudraksha-mala",
                "is_active": True
            }
        }
