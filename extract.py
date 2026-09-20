import logging
import os
import json
from pathlib import Path
from datetime import datetime, timezone

import requests
import psycopg
from loading import load_products
from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from validation import validate_product
from transformation import transform_product

logger = logging.getLogger(__name__)

def save_raw_page(
        response_text: str,
        page: int,
        output_dir: Path,
) -> None:
    """Save an API response body without parsing or transforming it."""

    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"page_{page:04d}.json"
    file_path.write_text(
        response_text,
        encoding="utf-8",
        newline="",
    )

def fetch_page(
    session: requests.Session,
    base_url: str,
    page: int,
    page_size: int,
    timeout: float,
    output_dir: Path,
) -> list:
    """Fetch one catalog page and require a JSON list response."""

    response = session.get(
        f"{base_url}/products",
        params={"_page": page, "_limit": page_size},
        timeout=timeout,
    )
    response.raise_for_status()
    save_raw_page(response.text, page, output_dir)
    products = response.json()

    if not isinstance(products, list):
        raise ValueError(f"Expected a product list on page {page}.")

    return products

def save_rejected_products(
    rejected_products: list,
    output_path: Path,
) -> None:
    """Save rejected source records together with validation errors."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            rejected_products,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")

def main() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
    )

    # Resolve configuration independently of the working directory.
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, override=False)

    base_url = os.environ["API_BASE_URL"].rstrip("/")
    timeout = float(os.environ["API_TIMEOUT_SECONDS"])

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output_dir = env_path.parent / "data" / "raw" / run_id

    page = 1
    page_size = 25
    all_products = []

    # Retry transient failures for catalog reads; fail immediately
    # on HTTP errors outside the retry policy.
    retry_policy = Retry(
        total=3,
        backoff_factor=1,
        allowed_methods={"GET"},
        status_forcelist=[429, 500, 502, 503, 504],
        other=0,
        raise_on_status=False,  # Preserve the final response for raise_for_status().
    )

    with requests.Session() as session:
        session.mount("http://", HTTPAdapter(max_retries=retry_policy))
        session.mount("https://", HTTPAdapter(max_retries=retry_policy))

        while True:
            products = fetch_page(
                session=session,
                base_url=base_url,
                page=page,
                page_size=page_size,
                timeout=timeout,
                output_dir=output_dir
            )

            if not products:
                break

            all_products.extend(products)
            page += 1

        valid_products = []
    rejected_products = []

    for product in all_products:
        errors = validate_product(product)

        if errors:
            rejected_products.append(
                {
                    "record": product,
                    "errors": errors,
                }
            )
        else:
            valid_products.append(transform_product(product))

    rejected_path = env_path.parent / "data" / "rejected" / f"{run_id}.json"
    save_rejected_products(rejected_products, rejected_path)

    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as connection:
        load_products(connection, valid_products)

    logger.info(
        "Catalog ingestion completed",
        extra={
            "product_count": len(all_products),
            "valid_count": len(valid_products),
            "rejected_count": len(rejected_products),
            "loaded_count": len(valid_products),
        },
    )


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ValueError, psycopg.Error):
        logger.exception("Catalog ingestion failed")
        raise SystemExit(1)