import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
import requests

import extract


def test_main_fetches_all_pages_before_loading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configuration = {
        "API_BASE_URL": "http://catalog.test",
        "API_TIMEOUT_SECONDS": "10",
        "POSTGRES_HOST": "database.test",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_catalog",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
    }

    for name, value in configuration.items():
        monkeypatch.setenv(name, value)

    # Keep configuration and generated files isolated from the local project.
    monkeypatch.setattr(extract, "__file__", str(tmp_path / "extract.py"))
    monkeypatch.setattr(extract, "load_dotenv", Mock())

    first_product = {
        "id": 1,
        "title": "First product",
        "category": "beauty",
        "price": 19.99,
        "stock": 10,
    }
    second_product = {
        "id": 2,
        "title": "Second product",
        "category": "beauty",
        "price": 25,
        "stock": 5,
    }

    pages = [[first_product], [second_product], []]
    responses = []

    for products in pages:
        response = Mock(spec=requests.Response)
        response.text = json.dumps(products)
        response.json.return_value = products
        responses.append(response)

    session = MagicMock(spec=requests.Session)
    session.__enter__.return_value = session
    session.get.side_effect = responses

    monkeypatch.setattr(extract.requests, "Session", Mock(return_value=session))

    connect = MagicMock()
    load_products = Mock()

    monkeypatch.setattr(extract.psycopg, "connect", connect)
    monkeypatch.setattr(extract, "load_products", load_products)

    extract.main()

    requested_pages = [
        request.kwargs["params"]["_page"]
        for request in session.get.call_args_list
    ]

    assert requested_pages == [1, 2, 3]

    connection = connect.return_value.__enter__.return_value
    load_products.assert_called_once_with(
        connection,
        [
            {**first_product, "price": Decimal("19.99")},
            {**second_product, "price": Decimal("25")},
        ],
    )

    raw_files = sorted((tmp_path / "data" / "raw").glob("*/page_*.json"))

    assert [path.name for path in raw_files] == [
        "page_0001.json",
        "page_0002.json",
        "page_0003.json",
    ]
    assert [
        json.loads(path.read_text(encoding="utf-8"))
        for path in raw_files
    ] == pages

def test_main_does_not_load_products_when_later_page_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configuration = {
        "API_BASE_URL": "http://catalog.test",
        "API_TIMEOUT_SECONDS": "10",
        "POSTGRES_HOST": "database.test",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_catalog",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
    }

    for name, value in configuration.items():
        monkeypatch.setenv(name, value)

    monkeypatch.setattr(extract, "__file__", str(tmp_path / "extract.py"))
    monkeypatch.setattr(extract, "load_dotenv", Mock())

    product = {
        "id": 1,
        "title": "First product",
        "category": "beauty",
        "price": 19.99,
        "stock": 10,
    }

    first_response = Mock(spec=requests.Response)
    first_response.text = json.dumps([product])
    first_response.json.return_value = [product]

    session = MagicMock(spec=requests.Session)
    session.__enter__.return_value = session
    session.get.side_effect = [
        first_response,
        requests.ConnectionError("Simulated connection failure"),
    ]

    monkeypatch.setattr(extract.requests, "Session", Mock(return_value=session))

    connect = MagicMock()
    load_products = Mock()

    monkeypatch.setattr(extract.psycopg, "connect", connect)
    monkeypatch.setattr(extract, "load_products", load_products)

    with pytest.raises(
        requests.ConnectionError,
        match="Simulated connection failure",
    ):
        extract.main()

    requested_pages = [
        request.kwargs["params"]["_page"]
        for request in session.get.call_args_list
    ]

    assert requested_pages == [1, 2]
    connect.assert_not_called()
    load_products.assert_not_called()

    raw_files = list((tmp_path / "data" / "raw").glob("*/page_*.json"))

    assert len(raw_files) == 1
    assert raw_files[0].name == "page_0001.json"
    assert json.loads(raw_files[0].read_text(encoding="utf-8")) == [product]

def test_main_loads_valid_products_and_saves_rejected_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configuration = {
        "API_BASE_URL": "http://catalog.test",
        "API_TIMEOUT_SECONDS": "10",
        "POSTGRES_HOST": "database.test",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_catalog",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
    }

    for name, value in configuration.items():
        monkeypatch.setenv(name, value)

    monkeypatch.setattr(extract, "__file__", str(tmp_path / "extract.py"))
    monkeypatch.setattr(extract, "load_dotenv", Mock())

    valid_product = {
        "id": 1,
        "title": "  First product  ",
        "category": "beauty",
        "price": 19.99,
        "stock": 10,
    }
    invalid_product = {
        "id": 2,
        "title": "Second product",
        "category": "beauty",
        "price": 25,
        "stock": -1,
    }

    pages = [[valid_product, invalid_product], []]
    responses = []

    for products in pages:
        response = Mock(spec=requests.Response)
        response.text = json.dumps(products)
        response.json.return_value = products
        responses.append(response)

    session = MagicMock(spec=requests.Session)
    session.__enter__.return_value = session
    session.get.side_effect = responses

    monkeypatch.setattr(extract.requests, "Session", Mock(return_value=session))

    connect = MagicMock()
    load_products = Mock()

    monkeypatch.setattr(extract.psycopg, "connect", connect)
    monkeypatch.setattr(extract, "load_products", load_products)

    extract.main()

    connection = connect.return_value.__enter__.return_value
    load_products.assert_called_once_with(
        connection,
        [
            {
                "id": 1,
                "title": "First product",
                "category": "beauty",
                "price": Decimal("19.99"),
                "stock": 10,
            }
        ],
    )

    rejected_files = list((tmp_path / "data" / "rejected").glob("*.json"))

    assert len(rejected_files) == 1

    rejected_products = json.loads(
        rejected_files[0].read_text(encoding="utf-8")
    )

    assert rejected_products == [
        {
            "record": invalid_product,
            "errors": ["Field 'stock' must not be negative."],
        }
    ]    