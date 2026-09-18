import os
from pathlib import Path

import requests
from dotenv import load_dotenv


def fetch_page(
    session: requests.Session,
    base_url: str,
    page: int,
    page_size: int,
    timeout: float,
) -> list:
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

    with requests.Session() as session:
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