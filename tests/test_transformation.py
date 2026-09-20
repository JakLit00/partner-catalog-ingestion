from decimal import Decimal

from transformation import transform_product


def test_transform_product_prepares_database_fields() -> None:
    product = {
        "id": 1,
        "title": "  Test product  ",
        "category": "\tbeauty\n",
        "price": 19.99,
        "stock": 10,
        "description": "Additional source information.",
    }

    result = transform_product(product)

    assert result == {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "price": Decimal("19.99"),
        "stock": 10,
    }
    assert isinstance(result["price"], Decimal)