from unittest.mock import Mock
from pathlib import Path

import pytest
import requests

from extract import fetch_page, save_raw_page


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