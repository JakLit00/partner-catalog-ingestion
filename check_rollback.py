import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from loading import load_products


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

    connection_settings = {
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.environ["POSTGRES_PORT"]),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "connect_timeout": 5,
    }

    with psycopg.connect(**connection_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, category, price, stock FROM products WHERE id = 1;"
            )
            original = cursor.fetchone()

    if original is None:
        raise RuntimeError("Product 1 is required for the rollback check.")

    product_id, title, category, price, stock = original

    changed_product = {
        "id": product_id,
        "title": title,
        "category": category,
        "price": price + 1,
        "stock": stock,
    }
    invalid_product = {**changed_product, "stock": -1}

    try:
        with psycopg.connect(**connection_settings) as connection:
            load_products(connection, [changed_product, invalid_product])
    except psycopg.errors.CheckViolation:
        pass
    else:
        raise RuntimeError("Expected a database constraint violation.")

    with psycopg.connect(**connection_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, category, price, stock FROM products WHERE id = 1;"
            )
            actual = cursor.fetchone()

    if actual != original:
        raise RuntimeError("Rollback check failed: the product changed.")

    print("Rollback verified: the original product is unchanged.")


if __name__ == "__main__":
    main()
