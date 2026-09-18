from unittest.mock import Mock

import pytest
import requests

from extract import fetch_page


def test_fetch_page_rejects_non_list_response() -> None:
    session = Mock(spec=requests.Session)
    response = session.get.return_value
    response.json.return_value = {"products": []}

    with pytest.raises(ValueError, match="Expected a product list on page 1"):
        fetch_page(
            session=session,
            base_url="http://catalog.test",
            page=1,
            page_size=25,
            timeout=10,
        )

def test_fetch_page_returns_product_list() -> None:
    products = [{"id": 1, "title": "Test product"}]

    session = Mock(spec=requests.Session)
    response = session.get.return_value
    response.json.return_value = products

    result = fetch_page(
        session=session,
        base_url="http://catalog.test",
        page=1,
        page_size=25,
        timeout=10,
    )

    assert result == products