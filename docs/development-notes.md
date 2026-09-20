# Development Notes

The implementation was built in stages: local infrastructure, source extraction, validation and transformation, database loading, then verification on Windows and Linux. Each stage established a working boundary before the next was connected.

## 1. Scope and source contract

The scenario is a local copy of a partner catalog for applications that need product names, categories, prices and stock levels. The source owns the product ID. Repeated imports refresh that ID rather than append another version of the same product.

A fixed DummyJSON snapshot provides realistic nested records without requiring a data-generation project. The full response was retained in `api/catalog-source.json`; `api/db.json` removes only the response-level pagination wrapper and keeps the product fields. Both collections contain 194 records. The source license is retained alongside them.

JSON Server 0.17.4 serves this snapshot in read-only mode. Its page contract is `_page` and `_limit`, rather than DummyJSON's pagination parameters. Requests receive a JSON list and an `X-Total-Count` header. The importer uses an empty list as the end condition; it does not reconcile its count against the header. A fixed dataset avoids changes between pages during a demonstration.

The API image uses Node.js 22.23.2, contains the dataset and license, and runs as the non-root `node` user. Node.js is a container dependency, not a requirement for the host Python environment.

## 2. Repository and local services

Work was committed in feature branches and merged into `main` with explicit merge commits. The repository keeps source data and schema definitions, while `.gitignore` excludes `.env`, virtual environments, caches and generated output. `.gitattributes` normalizes tracked text to LF across systems.

Docker Compose provides the API and PostgreSQL 16.15. Both host bindings use loopback addresses: `127.0.0.1:3000` for the API and `127.0.0.1:5433` for PostgreSQL. PostgreSQL still listens on port 5432 inside its container. The alternate host port reduces collisions with a host database installation.

A named `postgres_data` volume preserves database contents across container replacement. Initialization credentials apply only to an empty volume; an edited `.env` is not a password-rotation mechanism. The account created by `POSTGRES_USER` is a superuser, which is an explicit local-demo trade-off.

`check_connection.py` established connectivity before ingestion was added. It checks the database and user with `SELECT current_database(), current_user;`, uses a five-second connection timeout and closes database resources through context managers.

## 3. Configuration and extraction

Python resolves `.env` relative to the script, so launching from another working directory does not change which configuration or output directory is used. Runtime environment variables take precedence because `load_dotenv` uses `override=False`.

Before extraction, all seven required settings are checked for missing or blank values. Their names can appear in an error, but the configuration check does not log their values. `API_TIMEOUT_SECONDS` is converted to a number for Requests; `POSTGRES_PORT` is converted before connecting to the database. Host ports remain fixed in Compose and must be kept consistent with client settings.

`extract.py` coordinates the run. A reusable Requests session retrieves 25 products per page, checks HTTP status and requires each parsed response to be a list. The 194-record snapshot yields seven full pages, one 19-record page and an empty ninth page.

HTTP retry behavior belongs to the session adapters. `urllib3.util.Retry` was used because it integrates with Requests without adding a general-purpose retry dependency. The configuration allows three retries for eligible failures, limits methods to GET, sets a backoff factor of 1 and lists 429, 500, 502, 503 and 504 as retryable statuses. The final response remains available for `raise_for_status()`. The adapter retains urllib3's default Retry-After behavior.

The request timeout is not a deadline for the entire run. Retry delays and multiple requests extend total duration. The retry policy also does not imply that every possible failure while consuming a response body will be retried.

## 4. Raw output and rejected records

A UTC timestamp identifies each run. Successful HTTP response bodies are saved before JSON parsing, allowing malformed content to be inspected if parsing fails. Files contain response text encoded as UTF-8 with newline translation disabled; they are not byte-for-byte captures of HTTP headers or compressed wire traffic.

The final empty page is retained because it records the response that ended extraction. Raw files live under `data/raw/<run_id>/`. They are written before the database transaction and remain available if a later stage fails.

Record validation returns a list of errors rather than raising an exception for each invalid product. This allows valid records to continue while rejected records retain their original content and reasons in `data/rejected/<run_id>.json`. An empty rejection list is written for a run with no rejected records.

## 5. Validation and transformation

The validated contract contains five fields:

- `id`: an integer from 1 to 9,223,372,036,854,775,807.
- `title` and `category`: strings that contain non-whitespace content.
- `stock`: an integer from 0 to 9,223,372,036,854,775,807.
- `price`: a finite, nonnegative Python `int` or `float` from the parsed response.

Booleans are rejected explicitly because Python treats them as subclasses of `int`. Numeric strings are not silently converted. The integer limits match PostgreSQL `BIGINT`, preventing predictable database range errors from reaching the loading stage.

`transformation.py` accepts validated records and returns new dictionaries containing only the database fields. It trims outer whitespace and converts prices with `Decimal(str(value))`. This avoids converting the full binary approximation of a float directly into a decimal, but it cannot recover precision already lost during JSON parsing. PostgreSQL uses unconstrained `NUMERIC`, avoiding an arbitrary two-decimal rounding rule. The source does not supply a currency field, so none is assumed.

Validation and transformation are separate functions so their contracts can be tested independently of HTTP, files and database access.

## 6. Schema and transactional loading

`sql/001_create_products.sql` defines the `products` table. Source IDs form the primary key. Required columns use `NOT NULL`; named checks enforce positive IDs, nonblank text, finite nonnegative prices and nonnegative stock. Python validates incoming data for useful rejection messages, while database constraints protect writes through any client.

`loading.py` receives an existing Psycopg connection and transformed records. Named SQL parameters keep values separate from SQL text. `executemany()` applies an `INSERT ... ON CONFLICT (id) DO UPDATE` for each product.

The connection context in `extract.py` owns the transaction. It commits only after the loading function returns successfully and rolls back on an exception. The loader does not commit individual rows. The final success log is emitted after the connection context has completed.

Reimporting the same catalog leaves 194 rows. Incoming values replace the current values for matching IDs. This is an upsert, not a full snapshot replacement: missing or rejected source records do not delete old database rows, and price history is not retained.

## 7. Logging and failure handling

Standard Python logging uses `python-json-logger` to produce JSON console output. The success event includes a UTC `run_id`, received count, valid count, rejected count and loaded count. The run ID matches the output paths. `loaded_count` includes both inserts and updates; it is not a database change count.

The entry point handles Requests errors, `ValueError`, Psycopg errors and `OSError`, logs exception details and exits with code 1. Missing settings are converted into `ValueError` at the configuration boundary. An unrelated `KeyError` is not mislabeled as a configuration issue.

Logging is not a separate audit database. Error events do not currently include the run ID explicitly, files can remain after failed runs, and the implementation has no resume manifest. These boundaries keep the current batch workflow small and explicit.

## 8. Windows and Linux verification

The same code and pinned dependency files were exercised on Windows with Python 3.13.14 and Ubuntu 26.04 in WSL2 with Python 3.14.4. Docker Desktop supplied the containers in both cases; these were not two independent Docker hosts.

For Linux verification, the committed repository was cloned into `~/projects/partner-catalog-ingestion`. A separate `.venv` was created with Ubuntu's Python. Windows virtual environments were not copied. The matching `python3.14-venv` package supplied `ensurepip` support, leaving the system Python version unchanged.

Ubuntu's Docker access was enabled through [Docker Desktop WSL Integration](https://docs.docker.com/desktop/features/wsl/). When the socket belonged to `root:docker`, group membership was checked with `id`, `getent group docker` and `ls -l /var/run/docker.sock`. A fresh session was needed for the already configured group membership to take effect. Socket permissions were not made world-writable.

The Linux checkout needed its own `.env`, since secrets are not part of a Git clone. When connecting to an existing Docker volume, it used that database's credentials. A shared engine and the same Compose project name refer to the same containers and volume; moving the Python process to Linux alone does not create a clean database.

To verify initialization separately, the ordinary services were stopped to release the ports. A separate Compose project named `partner-catalog-clean-check` created a new volume. The DDL was applied and the importer loaded 194 products. The check project was then stopped and the ordinary project restarted. No existing volume was deleted.

The final configuration and file-error handling changes were merged on Windows, pulled into the Linux checkout and checked again with pytest and a complete import.

## 9. Verification results

The pytest suite contains 53 cases: 47 validation cases, five extraction/file-output cases and one transformation case. HTTP responses use `unittest.mock`, and file tests use temporary directories. These tests run without Docker or network access to the API.

Additional checks exercised the operational boundaries:

- **Full import:** 194 received, 194 valid, zero rejected and 194 submitted to a committed transaction.
- **Repeat import:** the database remained at 194 rows.
- **Update behavior:** a manually changed price returned to the source value after another import.
- **Rollback:** `check_rollback.py` sent a valid price update followed by an invalid stock value and verified the original row through a new connection. It passed on Windows and WSL2.
- **API unavailable:** stopping the API produced retry warnings and a final error; restarting it restored successful imports.
- **Missing configuration:** a blank password injected into a child process produced a named configuration error and exit code 1 without editing `.env`.
- **File failure:** a mocked `PermissionError` from raw-file writing produced an error log and exit code 1 before database loading.
- **Empty database:** a separate Compose project was initialized from DDL and loaded successfully under WSL2.

The mocked HTTP-error test checks propagation, not the retry adapter. Actual recovery from HTTP 503, automatic pagination tests and an automated database integration suite are outside the current test coverage. The empty-volume check used an existing Docker installation and available image cache; it was not a separate-machine provisioning test.

## 10. Deliberate boundaries

The project stays focused on one local batch ingestion workflow. It does not require an orchestrator, distributed processing engine or cloud account. The complete source catalog is held in memory, appropriate for this fixed dataset.

Dependency versions and image tags are pinned, but transitive dependencies and image digests are not fully locked. Raw and rejected files need manual retention management. Database constraints can reject unusual values beyond the application contract, in which case the whole load rolls back. These are concrete extension points rather than guarantees implied by the current implementation.
