import os
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from dotenv import load_dotenv



def fetch_page(
    session: requests.Session,
    base_url: str,
    page: int,
    page_size: int,
    timeout: float,
) -> list:
    """Fetch one catalog page and require a JSON list response."""
    
    response = session.get(
        f"{base_url}/products",
        params={"_page": page, "_limit": page_size},
        timeout=timeout,
    )
    response.raise_for_status()
    products = response.json()

    if not isinstance(products, list):
        raise ValueError(f"Expected a product list on page {page}.")

    return products


def main() -> None:
    # Resolve configuration independently of the working directory.
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, override=False)

    base_url = os.environ["API_BASE_URL"].rstrip("/")
    timeout = float(os.environ["API_TIMEOUT_SECONDS"])

    page = 1
    page_size = 25
    all_products = []

    # Retry transient failures for catalog reads; leave other HTTP errors
    # to raise_for_status() so configuration errors fail immediately.
    retry_policy = Retry(
        total=3,
        backoff_factor=1,
        allowed_methods=["GET"],
        status_forcelist=[429, 500, 502, 503, 504],
        other=0,
        raise_on_status=False, # Preserve the final response for raise_for_status().
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
            )

            if not products:
                break

            all_products.extend(products)
            page += 1

    print(f"Received products: {len(all_products)}")


if __name__ == "__main__":
    main()