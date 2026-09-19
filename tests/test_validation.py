import pytest

from validation import validate_product


def test_validate_product_accepts_positive_integer_id() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
    }

    errors = validate_product(product)

    assert errors == []


def test_validate_product_rejects_non_object_record() -> None:
    errors = validate_product(["unexpected", "list"])

    assert errors == ["Product must be a JSON object."]


@pytest.mark.parametrize(
    "product",
    [
        {},
        {"id": None},
        {"id": "1"},
        {"id": 1.5},
        {"id": True},
        {"id": False},
    ],
)
def test_validate_product_rejects_invalid_id_type(product: dict) -> None:
    product = {
        **product,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
    }

    errors = validate_product(product)

    assert errors == ["Field 'id' must be an integer."]


@pytest.mark.parametrize("product_id", [0, -1])
def test_validate_product_rejects_non_positive_id(product_id: int) -> None:
    product = {
        "id": product_id,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
    }

    errors = validate_product(product)

    assert errors == ["Field 'id' must be greater than zero."]


@pytest.mark.parametrize("field", ["title", "category"])
@pytest.mark.parametrize("value", [None, 123, True, "", "   "])
def test_validate_product_rejects_invalid_text_fields(
    field: str,
    value: object,
) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
    }
    product[field] = value

    errors = validate_product(product)

    if isinstance(value, str):
        expected_error = f"Field '{field}' must not be empty."
    else:
        expected_error = f"Field '{field}' must be a string."

    assert errors == [expected_error]


@pytest.mark.parametrize("stock", [0, 10])
def test_validate_product_accepts_non_negative_stock(stock: int) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": stock,
    }

    errors = validate_product(product)

    assert errors == []


@pytest.mark.parametrize("stock", [None, "10", 1.5, True, False])
def test_validate_product_rejects_invalid_stock_type(stock: object) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": stock,
    }

    errors = validate_product(product)

    assert errors == ["Field 'stock' must be an integer."]


def test_validate_product_rejects_negative_stock() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": -1,
    }

    errors = validate_product(product)

    assert errors == ["Field 'stock' must not be negative."]


def test_validate_product_rejects_missing_stock() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
    }

    errors = validate_product(product)

    assert errors == ["Field 'stock' must be an integer."]