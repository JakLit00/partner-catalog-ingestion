import logging
import os
import json
import math
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

def create_http_session() -> requests.Session:
    """Create an HTTP session with retries for transient GET failures."""

    retry_policy = Retry(
        total=3,
        backoff_factor=1,
        allowed_methods={"GET"},
        status_forcelist=[429, 500, 502, 503, 504],
        other=0,
        raise_on_status=False,  # Preserve the final HTTP response.
    )

    session = requests.Session()
    session.mount("http://", HTTPAdapter(max_retries=retry_policy))
    session.mount("https://", HTTPAdapter(max_retries=retry_policy))

    return session

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

def make_json_safe(value: object) -> object:
    """Represent non-finite numbers as strings in rejection reports."""

    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"

    if isinstance(value, dict):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [make_json_safe(item) for item in value]

    return value


def save_rejected_products(
    rejected_products: list,
    output_path: Path,
) -> None:
    """Save rejected records and errors as standards-compliant JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_products = make_json_safe(rejected_products)

    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            safe_products,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
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

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    stage = "configuration"
    page = None

    try:
        # Resolve configuration independently of the working directory.
        env_path = Path(__file__).resolve().parent / ".env"
        load_dotenv(env_path, override=False)

        required_variables = (
            "API_BASE_URL",
            "API_TIMEOUT_SECONDS",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        )

        missing_variables = []

        for name in required_variables:
            value = os.environ.get(name)

            if value is None or not value.strip():
                missing_variables.append(name)

        if missing_variables:
            raise ValueError(
                "Missing required configuration variables: "
                + ", ".join(missing_variables)
            )

        base_url = os.environ["API_BASE_URL"].rstrip("/")

        try:
            timeout = float(os.environ["API_TIMEOUT_SECONDS"])
        except ValueError:
            raise ValueError(
                "API_TIMEOUT_SECONDS must be a positive finite number."
            ) from None

        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(
                "API_TIMEOUT_SECONDS must be a positive finite number."
            )

        try:
            postgres_port = int(os.environ["POSTGRES_PORT"])
        except ValueError:
            raise ValueError(
                "POSTGRES_PORT must be an integer between 1 and 65535."
            ) from None

        if not 1 <= postgres_port <= 65535:
            raise ValueError(
                "POSTGRES_PORT must be an integer between 1 and 65535."
            )

        output_dir = env_path.parent / "data" / "raw" / run_id
        page_size = 25
        all_products = []

        stage = "extraction"
        page = 1

        with create_http_session() as session:

            while True:
                products = fetch_page(
                    session=session,
                    base_url=base_url,
                    page=page,
                    page_size=page_size,
                    timeout=timeout,
                    output_dir=output_dir,
                )

                if not products:
                    break

                all_products.extend(products)
                page += 1

        stage = "validation"
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

        stage = "rejection_report"
        rejected_path = env_path.parent / "data" / "rejected" / f"{run_id}.json"
        save_rejected_products(rejected_products, rejected_path)

        stage = "database_loading"

        with psycopg.connect(
            host=os.environ["POSTGRES_HOST"],
            port=postgres_port,
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=5,
        ) as connection:
            load_products(connection, valid_products)

        logger.info(
            "Catalog ingestion completed",
            extra={
                "run_id": run_id,
                "product_count": len(all_products),
                "valid_count": len(valid_products),
                "rejected_count": len(rejected_products),
                "loaded_count": len(valid_products),
            },
        )

    except (requests.RequestException, ValueError, psycopg.Error, OSError):
        error_context: dict[str, str | int | None] = {
            "run_id": run_id,
            "stage": stage,
        }

        if stage == "extraction":
            error_context["page"] = page

        logger.exception(
            "Catalog ingestion failed",
            extra=error_context,
        )
        raise


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ValueError, psycopg.Error, OSError):
        raise SystemExit(1)