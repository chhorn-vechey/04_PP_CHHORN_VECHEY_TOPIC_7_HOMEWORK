import copy
from typing import Any, Dict, List, Optional

INITIAL_CATALOG: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "ThinkPad Carbon Ultrabook",
        "category": "Laptops",
        "price": 1299.99,
        "stock": 5,
        "description": "Slim 14-inch professional business laptop with high performance.",
    },
    2: {
        "id": 2,
        "name": "MacBook Air 13-inch",
        "category": "Laptops",
        "price": 999.00,
        "stock": 0,
        "description": "Lightweight Apple M-series laptop, currently out of stock.",
    },
    3: {
        "id": 3,
        "name": "Pro Wireless Noise-Cancelling Headphones",
        "category": "Audio",
        "price": 199.99,
        "stock": 14,
        "description": "Over-ear active noise cancelling headphones with 30-hour battery life.",
    },
    4: {
        "id": 4,
        "name": "Mechanical Gaming Keyboard RGB",
        "category": "Accessories",
        "price": 89.50,
        "stock": 8,
        "description": "Tactile switch mechanical keyboard with customizable backlighting.",
    },
    5: {
        "id": 5,
        "name": "4K Ultra-Wide Monitor 34-inch",
        "category": "Displays",
        "price": 450.00,
        "stock": 3,
        "description": "Curved productivity and gaming monitor with HDR support.",
    },
}

_catalog: Dict[int, Dict[str, Any]] = copy.deepcopy(INITIAL_CATALOG)


def reset_catalog() -> None:
    global _catalog
    _catalog = copy.deepcopy(INITIAL_CATALOG)


def search_products(query: str) -> Dict[str, Any]:
    cleaned_query = query.strip().lower()
    matches: List[Dict[str, Any]] = []

    for product in _catalog.values():
        if (
            cleaned_query in product["name"].lower()
            or cleaned_query in product["category"].lower()
            or cleaned_query in product["description"].lower()
        ):
            matches.append({
                "id": product["id"],
                "name": product["name"],
                "category": product["category"],
                "price": product["price"],
            })

    return {
        "status": "success",
        "count": len(matches),
        "results": matches,
    }


def check_stock(product_id: int) -> Dict[str, Any]:
    product = _catalog.get(product_id)
    if not product:
        return {
            "status": "error",
            "error_code": "PRODUCT_NOT_FOUND",
            "message": f"Product with ID {product_id} does not exist in the catalog.",
        }

    return {
        "status": "success",
        "product_id": product_id,
        "name": product["name"],
        "stock": product["stock"],
        "in_stock": product["stock"] > 0,
    }


def buy_product(product_id: int, quantity: int = 1) -> Dict[str, Any]:
    product = _catalog.get(product_id)
    if not product:
        return {
            "status": "error",
            "error_code": "PRODUCT_NOT_FOUND",
            "message": f"Product with ID {product_id} does not exist in the catalog.",
        }

    if product["stock"] < quantity:
        return {
            "status": "error",
            "error_code": "INSUFFICIENT_STOCK",
            "message": f"Cannot purchase {quantity} units of '{product['name']}'. Only {product['stock']} units available.",
            "available_stock": product["stock"],
        }

    product["stock"] -= quantity
    total_cost = round(product["price"] * quantity, 2)

    return {
        "status": "success",
        "message": f"Successfully purchased {quantity}x '{product['name']}'.",
        "product_id": product_id,
        "quantity": quantity,
        "unit_price": product["price"],
        "total_cost": total_cost,
        "remaining_stock": product["stock"],
    }


def delete_product(product_id: int) -> Dict[str, Any]:
    if product_id not in _catalog:
        return {
            "status": "error",
            "error_code": "PRODUCT_NOT_FOUND",
            "message": f"Product with ID {product_id} cannot be deleted because it does not exist.",
        }

    deleted_item = _catalog.pop(product_id)
    return {
        "status": "success",
        "message": f"Product '{deleted_item['name']}' (ID: {product_id}) was successfully deleted from catalog.",
    }


AVAILABLE_TOOLS = {
    "search_products": search_products,
    "check_stock": check_stock,
    "buy_product": buy_product,
    "delete_product": delete_product,
}
