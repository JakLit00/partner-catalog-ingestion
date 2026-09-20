from decimal import Decimal


def transform_product(product: dict) -> dict:
    """Prepare a validated source product for database loading."""

    return {
        "id": product["id"],
        "title": product["title"].strip(),
        "category": product["category"].strip(),
        "price": Decimal(str(product["price"])),
        "stock": product["stock"],
    }