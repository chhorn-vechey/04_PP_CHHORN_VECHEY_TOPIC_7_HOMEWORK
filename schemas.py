from typing import Any, Dict
from pydantic import BaseModel, Field, field_validator


class SearchProductsInput(BaseModel):
    query: str = Field(..., min_length=1, description="Keyword or product name to search in the catalog")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return cleaned


class CheckStockInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Unique product ID (must be positive integer)")


class BuyProductInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Unique product ID (must be positive integer)")
    quantity: int = Field(1, gt=0, le=50, description="Quantity to purchase (must be between 1 and 50)")


class DeleteProductInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Unique product ID to delete (must be positive integer)")


TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "search_products": {
        "name": "search_products",
        "description": "Search products in the catalog by name, category, or description keywords.",
        "parameters": SearchProductsInput.model_json_schema(),
        "model": SearchProductsInput,
    },
    "check_stock": {
        "name": "check_stock",
        "description": "Check current stock inventory count and availability for a specific product ID.",
        "parameters": CheckStockInput.model_json_schema(),
        "model": CheckStockInput,
    },
    "buy_product": {
        "name": "buy_product",
        "description": "Purchase a specific quantity of a product by ID. Deducts inventory upon success.",
        "parameters": BuyProductInput.model_json_schema(),
        "model": BuyProductInput,
    },
    "delete_product": {
        "name": "delete_product",
        "description": "Permanently remove a product from the catalog by ID. Restricted to admin role.",
        "parameters": DeleteProductInput.model_json_schema(),
        "model": DeleteProductInput,
    },
}
