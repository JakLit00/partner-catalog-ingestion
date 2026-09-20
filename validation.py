import math

BIGINT_MAX = 9_223_372_036_854_775_807

def validate_product(product: object) -> list[str]:
    """Return validation errors for a source product record."""

    if not isinstance(product, dict):
        return ["Product must be a JSON object."]

    errors = []
    product_id = product.get("id")

    # Booleans are subclasses of int but are not valid product identifiers.
    if isinstance(product_id, bool) or not isinstance(product_id, int):
        errors.append("Field 'id' must be an integer.")
    elif product_id <= 0:
        errors.append("Field 'id' must be greater than zero.")
    elif product_id > BIGINT_MAX:
        errors.append("Field 'id' exceeds the BIGINT range.")

    for field in ("title", "category"):
        value = product.get(field)

        if not isinstance(value, str):
            errors.append(f"Field '{field}' must be a string.")
        elif not value.strip():
            errors.append(f"Field '{field}' must not be empty.")
        elif "\x00" in value:
            # PostgreSQL text columns cannot store NUL characters.
            errors.append(f"Field '{field}' must not contain NUL characters.")

    stock = product.get("stock")

    if isinstance(stock, bool) or not isinstance(stock, int):
        errors.append("Field 'stock' must be an integer.")
    elif stock < 0:
        errors.append("Field 'stock' must not be negative.")
    elif stock > BIGINT_MAX:
        errors.append("Field 'stock' exceeds the BIGINT range.")

    price = product.get("price")

    if isinstance(price, bool) or not isinstance(price, (int, float)):
        errors.append("Field 'price' must be a number.")
    elif isinstance(price, float) and not math.isfinite(price):
        errors.append("Field 'price' must be finite.")
    elif price < 0:
        errors.append("Field 'price' must not be negative.")

    return errors