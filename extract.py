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
    return response.json()


def main() -> None:
    # Resolve configuration independently of the working directory.
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, override=False)

    base_url = os.environ["API_BASE_URL"].rstrip("/")
    timeout = float(os.environ["API_TIMEOUT_SECONDS"])

    with requests.Session() as session:
        products = fetch_page(
            session=session,
            base_url=base_url,
            page=1,
            page_size=25,
            timeout=timeout,
        )

    print(f"Received products: {len(products)}")


if __name__ == "__main__":
    main()