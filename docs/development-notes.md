# Development Notes

Implementation milestones, key decisions and verification results for Partner Catalog Ingestion.

## 1. Project scope

The project will import a partner's product catalog from a REST API into PostgreSQL. Its scope covers paginated extraction, raw-response retention, validation, database loading and error handling.

A fixed sample dataset served through a local API makes demonstrations repeatable without depending on a public service. Analytics, price history and a storefront are outside the scope. Windows and Linux are target platforms; both must be verified before claiming cross-platform support.

## 2. Repository and Python environment

Initialized a local Git repository with `main` as the primary branch. Implementation changes are developed on feature branches and reviewed through staged diffs before committing. GitHub publication is deferred until a working version is ready.

Created a Python 3.13 virtual environment and selected it in VS Code. Confirmed that the terminal resolves Python to the project's `.venv` directory.

Added `.gitignore` rules for credentials, virtual environments, caches and generated output. The shared `.env.example` provides configuration placeholders; `.env` remains local and untracked.

Added `.gitattributes` to normalize text files to LF across operating systems and avoid line-ending-only diffs.

## 3. Local PostgreSQL service

Added a Docker Compose service using `postgres:16.15-bookworm`.

Key decisions:

- Use a specific image tag rather than `latest` to reduce unintended version changes.
- Bind the host port to `127.0.0.1:5433`, keeping access local and reducing conflicts with an existing PostgreSQL installation.
- Store database files in a named volume so they survive container replacement.
- Require database settings through Compose variable checks instead of silently accepting missing values.

Validated configuration with `docker compose config --quiet`, confirmed startup in the container logs and executed a database identity query through `psql`. The query returned `partner_catalog` and `catalog_app`.

The service configuration and startup instructions were committed and merged from `feature/local-postgres` into `main`.

## 4. Python connection check

Added `check_connection.py` on `feature/python-postgres` to verify host-to-container connectivity, authentication and SQL execution.

The script loads `.env` relative to its own location, while preserving environment variables already supplied by the runtime. It uses Psycopg 3, a five-second connection timeout and context managers to release the cursor and connection.

Runtime dependencies are pinned in `requirements.txt`. The binary Psycopg distribution avoids a local compilation requirement. Installation from the dependency file completed successfully.

### Result handling

Static analysis identified that `fetchone()` can return `None`. Added an explicit guard that raises an error if the diagnostic query returns no row. The returned values are unpacked into named variables before display.

### Verification

Executed `SELECT current_database(), current_user;` from the local Python environment through port 5433. The script returned:

```text
Connected to database: partner_catalog as user: catalog_app
```

This verifies connectivity, password authentication and query execution. It does not yet verify ingestion behavior or failure recovery.

## 5. Demo dataset preparation

Downloaded the full product catalog from
`https://dummyjson.com/products?limit=0` without field filtering.

Preserved the response in `api/catalog-source.json` and created
`api/db.json` with a single top-level `products` collection for JSON Server.
Removed only the response-level pagination metadata; retained all product
fields and nested structures. The prepared file uses UTF-8 without BOM.

Verified that the source record count matched the API's reported total
and that the prepared collection also contained 194 products.

Included the upstream license in `api/DUMMYJSON-LICENSE.txt`.
The committed snapshot will serve as a fixed demo source, avoiding
downloads from the public API during normal project execution.

## 6. Local API service

Added a Docker image using Node.js 22.23.2 and JSON Server 0.17.4.
The image includes the prepared catalog and its upstream license.
The server runs as a non-root user with read-only API access.

Added the `api` service to Docker Compose and exposed it only
on `127.0.0.1:3000`. The service does not depend on PostgreSQL.

Manually verified HTTP 200, a first page of 25 products and
`X-Total-Count: 194`. The second page contained 25 products,
starting at ID 26; the eighth page contained the remaining 19.

## 7. Catalog extraction

Implemented `extract.py` using Requests and a reusable session. API URL and timeout come from environment configuration. The extractor requests 25 products per page, checks HTTP status and requires a JSON list. It stops on an empty page. Record-level validation remains a separate, planned step.

Configured `urllib3.util.Retry` through HTTP adapters instead of adding a separate retry library. The policy allows up to three retries for GET requests, with exponential backoff and retryable statuses 429, 500, 502, 503 and 504. The final HTTP response is checked by `raise_for_status()`.

Used standard Python logging with `python-json-logger` for structured output. Request exceptions and `ValueError` reach the entry-point handler, which logs the failure with exception details and exits with code 1. The success log records the extracted product count.

### Raw responses

Each run receives a UTC timestamp directory under `data/raw/`. Pages are saved as numbered JSON files after the HTTP status check and before parsing. The terminal empty page is retained as part of the received responses.

Response text is written as UTF-8 with newline translation disabled. `pathlib` avoids platform-specific path construction. Raw output is ignored by Git; the fixed source dataset remains versioned. A failed extraction may leave a partial run directory.

### Verification

Manually verified successful extraction of all 194 products. Stopping the API produced retry warnings followed by a structured error log. Restarting the service restored successful extraction. This verifies connection-failure handling; recovery from an actual HTTP 503 response has not yet been exercised.

## 8. Automated tests

Added pytest through `requirements-dev.txt`, which also includes runtime dependencies from `requirements.txt`. Tests use `unittest.mock` for HTTP responses and pytest temporary directories for file output.

Four tests passed on Windows:

- A list response is returned unchanged.
- A non-list response raises `ValueError`.
- An HTTP error propagates without parsing JSON or writing a raw page.
- Raw files preserve response text, including Unicode and newline characters, as UTF-8.

The HTTP-error test simulates an exception from `raise_for_status()`; it does not exercise the retry adapter. Automated pagination, retry and full-pipeline verification remain pending.

## Current limitations

- Product validation, transformation, rejected-record output and PostgreSQL loading remain unimplemented.
- Python runs locally; PostgreSQL and the API are containerized.
- Linux and clean-environment reproduction remain to be checked.
- The database user created through `POSTGRES_USER` has superuser privileges. A separate least-privilege application role is not implemented.
- Editing `.env` does not change credentials in an already initialized database.
- Version pins improve repeatability but do not guarantee indefinite compatibility or immutable image contents.
