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

    for field in ("title", "category"):
        value = product.get(field)

        if not isinstance(value, str):
            errors.append(f"Field '{field}' must be a string.")
        elif not value.strip():
            errors.append(f"Field '{field}' must not be empty.")

    stock = product.get("stock")

    if isinstance(stock, bool) or not isinstance(stock, int):
        errors.append("Field 'stock' must be an integer.")
    elif stock < 0:
        errors.append("Field 'stock' must not be negative.")
        
    return errors