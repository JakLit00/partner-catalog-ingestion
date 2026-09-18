import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


def main() -> None:
    # Locate .env relative to this script, regardless of the working directory.
    env_path = Path(__file__).resolve().parent / ".env"

    # Environment variables supplied by the runtime take precedence over .env.
    load_dotenv(env_path, override=False)

    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user;")
            result = cursor.fetchone()

        if result is None:
            raise RuntimeError("Database connection check returned no row.")

        database_name, user_name = result
        print(f"Connected to database: {database_name} as user: {user_name}")


if __name__ == "__main__":
    main()
