import json

from unittest.mock import Mock
from pathlib import Path

import pytest
import requests

from extract import fetch_page, save_raw_page, save_rejected_products


def test_fetch_page_rejects_non_list_response(tmp_path: Path) -> None:
    session = Mock(spec=requests.Session)
    response = session.get.return_value
    response.json.return_value = {"products": []}
    response.text = '{"products": []}'

    with pytest.raises(ValueError, match="Expected a product list on page 1"):
        fetch_page(
            session=session,
            base_url="http://catalog.test",
            page=1,
            page_size=25,
            timeout=10,
            output_dir=tmp_path,
        )

def test_fetch_page_returns_product_list(tmp_path: Path) -> None:
    products = [{"id": 1, "title": "Test product"}]

    session = Mock(spec=requests.Session)
    response = session.get.return_value
    response.json.return_value = products
    response.text = '[{"id": 1, "title": "Test product"}]'

    result = fetch_page(
        session=session,
        base_url="http://catalog.test",
        page=1,
        page_size=25,
        timeout=10,
        output_dir=tmp_path,
    )

    assert result == products

def test_save_raw_page_preserves_response_text(tmp_path: Path) -> None:
    response_text = '[\n  {"id": 1, "title": "Test Óżśćł@#$"}\n]'
    output_dir = tmp_path / "raw" / "test_run"

    save_raw_page(
        response_text=response_text,
        page=1,
        output_dir=output_dir,
    )

    saved_file = output_dir / "page_0001.json"

    assert saved_file.read_bytes() == response_text.encode("utf-8")

def test_fetch_page_propagates_http_error(tmp_path: Path) -> None:
    session = Mock(spec=requests.Session)
    response = session.get.return_value
    response.raise_for_status.side_effect = requests.HTTPError(
        "503 Server Error: Service Unavailable"
    )

    with pytest.raises(requests.HTTPError):
        fetch_page(
            session=session,
            base_url="http://catalog.test",
            page=1,
            page_size=25,
            timeout=10,
            output_dir=tmp_path,
        )

    response.json.assert_not_called()
    assert list(tmp_path.iterdir()) == []

def test_save_rejected_products_preserves_records_and_errors(
    tmp_path: Path,
) -> None:
    rejected_products = [
        {
            "record": {
                "id": 1,
                "title": "Żółty plecak",
                "category": "bags",
                "stock": -1,
                "price": 19.99,
            },
            "errors": ["Field 'stock' must not be negative."],
        }
    ]
    output_path = tmp_path / "rejected" / "test_run.json"

    save_rejected_products(rejected_products, output_path)

    saved_products = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved_products == rejected_products

@pytest.mark.parametrize(
    ("value", "expected_text"),
    [
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
    ],
)
def test_save_rejected_products_converts_non_finite_numbers(
    tmp_path: Path,
    value: float,
    expected_text: str,
) -> None:
    record = {
        "id": 1,
        "price": value,
        "details": {
            "values": [value, 10, "Original text", None],
        },
    }
    errors = ["Field 'price' must be finite."]
    rejected_products = [{"record": record, "errors": errors}]
    output_path = tmp_path / "rejected" / "test_run.json"

    save_rejected_products(rejected_products, output_path)

    def reject_non_standard_constant(constant: str) -> None:
        raise ValueError(f"Non-standard JSON constant: {constant}")

    saved_products = json.loads(
        output_path.read_text(encoding="utf-8"),
        parse_constant=reject_non_standard_constant,
    )

    assert saved_products == [
        {
            "record": {
                "id": 1,
                "price": expected_text,
                "details": {
                    "values": [expected_text, 10, "Original text", None],
                },
            },
            "errors": errors,
        }
    ]
    assert record["price"] is value
    assert record["details"]["values"][0] is value