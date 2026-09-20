import pytest

from validation import validate_product


def test_validate_product_accepts_positive_integer_id() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
        "price": 19.99,
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
        "price": 19.99,
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
        "price": 19.99,
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
        "price": 19.99,
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
        "price": 19.99,
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
        "price": 19.99,
    }

    errors = validate_product(product)

    assert errors == ["Field 'stock' must be an integer."]


def test_validate_product_rejects_negative_stock() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": -1,
        "price": 19.99,
    }

    errors = validate_product(product)

    assert errors == ["Field 'stock' must not be negative."]


def test_validate_product_rejects_missing_stock() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "price": 19.99,
    }

    errors = validate_product(product)

    assert errors == ["Field 'stock' must be an integer."]

@pytest.mark.parametrize("price", [0, 0.0, 20, 19.99])
def test_validate_product_accepts_valid_price(price: int | float) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
        "price": price,
    }

    errors = validate_product(product)

    assert errors == []


@pytest.mark.parametrize(
    ("price", "expected_error"),
    [
        (None, "Field 'price' must be a number."),
        ("19.99", "Field 'price' must be a number."),
        (True, "Field 'price' must be a number."),
        (False, "Field 'price' must be a number."),
        (-1, "Field 'price' must not be negative."),
        (-0.01, "Field 'price' must not be negative."),
        (float("inf"), "Field 'price' must be finite."),
        (float("-inf"), "Field 'price' must be finite."),
        (float("nan"), "Field 'price' must be finite."),
    ],
)
def test_validate_product_rejects_invalid_price(
    price: object,
    expected_error: str,
) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
        "price": price,
    }

    errors = validate_product(product)

    assert errors == [expected_error]


def test_validate_product_rejects_missing_price() -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "stock": 10,
    }

    errors = validate_product(product)

    assert errors == ["Field 'price' must be a number."]

@pytest.mark.parametrize("field", ["id", "stock"])
def test_validate_product_accepts_bigint_max(field: str) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "price": 19.99,
        "stock": 10,
    }
    product[field] = 9_223_372_036_854_775_807

    errors = validate_product(product)

    assert errors == []


@pytest.mark.parametrize("field", ["id", "stock"])
def test_validate_product_rejects_bigint_overflow(field: str) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "price": 19.99,
        "stock": 10,
    }
    product[field] = 9_223_372_036_854_775_808

    errors = validate_product(product)

    assert errors == [f"Field '{field}' exceeds the BIGINT range."]

@pytest.mark.parametrize("field", ["title", "category"])
def test_validate_product_rejects_nul_in_text_fields(field: str) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "price": 19.99,
        "stock": 10,
    }
    product[field] = "Test\x00value"

    errors = validate_product(product)

    assert errors == [
        f"Field '{field}' must not contain NUL characters."
    ]