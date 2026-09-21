from collections.abc import Iterator

import psycopg
import pytest
from psycopg.conninfo import make_conninfo


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests against the disposable PostgreSQL instance.",
    )


@pytest.fixture
def postgres_test_conninfo(request: pytest.FixtureRequest) -> str:
    if not request.config.getoption("--run-integration"):
        pytest.skip("Use --run-integration to run PostgreSQL integration tests.")

    # Connect only to the dedicated test instance; do not load the project .env.
    return make_conninfo(
        host="127.0.0.1",
        port=55432,
        dbname="partner_catalog_test",
        user="catalog_ingestor",
        password="integration_app_password",
        connect_timeout=5,
    )


@pytest.fixture
def empty_products(postgres_test_conninfo: str) -> Iterator[None]:
    """Isolate tests by clearing products in the disposable database."""

    admin_conninfo = make_conninfo(
        postgres_test_conninfo,
        user="integration_admin",
        password="integration_admin_password",
    )

    with psycopg.connect(admin_conninfo, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE public.products;")

            try:
                yield
            finally:
                cursor.execute("TRUNCATE TABLE public.products;")
