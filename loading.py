import psycopg


def load_products(
    connection: psycopg.Connection,
    products: list[dict],
) -> None:
    """Insert products or update existing records by source identifier."""

    query = """
        INSERT INTO products (id, title, category, price, stock)
        VALUES (%(id)s, %(title)s, %(category)s, %(price)s, %(stock)s)
        ON CONFLICT (id) DO UPDATE
        SET
            title = EXCLUDED.title,
            category = EXCLUDED.category,
            price = EXCLUDED.price,
            stock = EXCLUDED.stock;
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, products)