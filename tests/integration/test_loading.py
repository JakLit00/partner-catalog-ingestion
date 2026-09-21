from decimal import Decimal

import psycopg
import pytest
from psycopg import sql

from loading import load_products


def test_database_is_initialized_for_application_role(
    postgres_test_conninfo: str,
) -> None:
    with psycopg.connect(postgres_test_conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_user,
                    to_regclass('public.products') IS NOT NULL;
                """
            )
            result = cursor.fetchone()

    assert result == (
        "partner_catalog_test",
        "catalog_ingestor",
        True,
    )


@pytest.mark.usefixtures("empty_products")
def test_load_products_inserts_and_commits_product(
    postgres_test_conninfo: str,
) -> None:
    product = {
        "id": 1,
        "title": "Test product",
        "category": "beauty",
        "price": Decimal("19.99"),
        "stock": 10,
    }

    with psycopg.connect(postgres_test_conninfo) as connection:
        load_products(connection, [product])

    with psycopg.connect(postgres_test_conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, category, price, stock
                FROM public.products
                ORDER BY id;
                """
            )
            rows = cursor.fetchall()

    assert rows == [
        (1, "Test product", "beauty", Decimal("19.99"), 10),
    ]


@pytest.mark.usefixtures("empty_products")
def test_load_products_updates_existing_product_without_duplicates(
    postgres_test_conninfo: str,
) -> None:
    original_product = {
        "id": 1,
        "title": "Original product",
        "category": "beauty",
        "price": Decimal("19.99"),
        "stock": 10,
    }
    updated_product = {
        "id": 1,
        "title": "Updated product",
        "category": "skin-care",
        "price": Decimal("24.50"),
        "stock": 5,
    }

    with psycopg.connect(postgres_test_conninfo) as connection:
        load_products(connection, [original_product])

    with psycopg.connect(postgres_test_conninfo) as connection:
        load_products(connection, [updated_product])

    with psycopg.connect(postgres_test_conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, category, price, stock
                FROM public.products
                ORDER BY id;
                """
            )
            rows = cursor.fetchall()

    assert rows == [
        (1, "Updated product", "skin-care", Decimal("24.50"), 5),
    ]


@pytest.mark.usefixtures("empty_products")
def test_load_products_rolls_back_all_changes_when_stock_is_invalid(
    postgres_test_conninfo: str,
) -> None:
    original_product = {
        "id": 1,
        "title": "Original product",
        "category": "beauty",
        "price": Decimal("19.99"),
        "stock": 10,
    }
    updated_product = {
        **original_product,
        "price": Decimal("24.50"),
    }
    new_product = {
        "id": 2,
        "title": "New product",
        "category": "beauty",
        "price": Decimal("9.99"),
        "stock": 5,
    }
    invalid_product = {
        "id": 3,
        "title": "Invalid product",
        "category": "beauty",
        "price": Decimal("14.99"),
        "stock": -1,
    }

    with psycopg.connect(postgres_test_conninfo) as connection:
        load_products(connection, [original_product])

    with pytest.raises(psycopg.errors.CheckViolation) as error:
        with psycopg.connect(postgres_test_conninfo) as connection:
            load_products(
                connection,
                [updated_product, new_product, invalid_product],
            )

    assert error.value.diag.constraint_name == "products_stock_non_negative"

    with psycopg.connect(postgres_test_conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, category, price, stock
                FROM public.products
                ORDER BY id;
                """
            )
            rows = cursor.fetchall()

    assert rows == [
        (1, "Original product", "beauty", Decimal("19.99"), 10),
    ]


@pytest.mark.usefixtures("empty_products")
@pytest.mark.parametrize(
    "statement",
    [
        sql.SQL("DELETE FROM public.products;"),
        sql.SQL("TRUNCATE TABLE public.products;"),
        sql.SQL("DROP TABLE public.products;"),
        sql.SQL("CREATE TABLE public.permission_probe (id INTEGER);"),
    ],
    ids=["delete", "truncate", "drop_table", "create_table"],
)
def test_application_role_rejects_forbidden_operations(
    postgres_test_conninfo: str,
    statement: sql.SQL,
) -> None:
    with psycopg.connect(postgres_test_conninfo) as connection:
        try:
            with connection.cursor() as cursor:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(statement)
        finally:
            connection.rollback()
