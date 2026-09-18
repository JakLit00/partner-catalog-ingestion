import os
from pathlib import Path

import requests
from dotenv import load_dotenv

def main() -> None:
    # Resolve configuration independently of the working directory.
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, override=False)

    base_url = os.environ['API_BASE_URL']
    timeout = float(os.environ["API_TIMEOUT_SECONDS"])

    with requests.Session() as session:
        response = session.get(
            f"{base_url}/products",
            params={"_page": 1, "_limit": 25},
            timeout=timeout,
        )
        response.raise_for_status()
        products = response.json()

    print(f"Received products: {len(products)}")


if __name__ == "__main__":
    main()