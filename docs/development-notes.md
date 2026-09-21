# Development Notes

The project was built from the storage and source boundaries inward: local services, extraction, validation, transformation and loading. Cross-platform checks and a subsequent review added pipeline tests, stricter input checks, error context, code quality tooling and separate database roles. PostgreSQL integration tests then extended CI to cover real transactions and role permissions.

## 1. Source and local infrastructure

The business scenario is a local copy of a partner's product catalog. Source IDs identify products across imports, while names, categories, prices and stock can be refreshed.

A fixed DummyJSON snapshot supplies 194 realistic records without introducing a separate data-generation task. `api/catalog-source.json` retains the source response. `api/db.json` keeps the product collection without the response-level pagination wrapper. The upstream license is stored alongside the dataset.

JSON Server 0.17.4 exposes that collection in read-only mode using `_page` and `_limit`. The API runs as the non-root `node` user in a Node.js 22.23.2 container. Node.js is not needed in the host Python environment.

Docker Compose runs the API and PostgreSQL 16.15 with loopback host bindings on ports 3000 and 5433. PostgreSQL listens on 5432 inside the container; the alternate host port avoids a common conflict with locally installed databases. A named volume preserves data and roles across container replacement.

## 2. Configuration and HTTP extraction

`check_connection.py` established database connectivity before the importer was added. It reports the connected database and user and uses a five-second connection timeout.

Python resolves `.env` relative to the script, independently of the terminal's working directory. Environment variables take precedence because `load_dotenv` uses `override=False`. The importer checks seven required client settings for missing or blank values. It also rejects nonpositive or non-finite timeouts and ports outside the integer range 1–65535 before contacting the API.

`extract.py` retrieves 25 products per page until it receives an empty list. The bundled catalog yields seven full pages, one page of 19 products and an empty ninth page. Extraction finishes before database loading starts. A later-page failure therefore cannot load a partial catalog.

`create_http_session()` centralizes the HTTP adapter configuration. Requests and `urllib3.util.Retry` provide three retries for eligible failures, GET-only retry behavior, a backoff factor of 1, and retryable statuses 429, 500, 502, 503 and 504. The final response is passed to `raise_for_status()`. urllib3's default Retry-After handling is retained.

The timeout applies to request operations, not the whole import. Retry delays and multiple pages extend the total duration. The policy does not guarantee retrying every failure while consuming a response body. Pagination uses the empty-list contract; it does not reconcile totals against the API's `X-Total-Count` header.

## 3. Raw responses, validation and rejection reports

Successful HTTP response bodies are saved before JSON parsing. Each run has a UTC timestamp identifier and a directory under `data/raw/`. Files preserve response text as UTF-8 without newline translation; they are not captures of HTTP headers or compressed network bytes. The final empty page records the termination response.

`validation.py` returns error messages rather than raising for each invalid record. Its contract is:

- `id`: integer from 1 to the PostgreSQL `BIGINT` maximum.
- `title` and `category`: nonblank strings without NUL characters.
- `stock`: integer from 0 to the `BIGINT` maximum.
- `price`: finite, nonnegative `int` or `float`.

Booleans are rejected explicitly because they are Python integer subclasses. Numeric strings are not silently converted. Integer bounds and the NUL check prevent predictable database failures from reaching the transaction.

Rejected records and their errors are written to `data/rejected/<run_id>.json`. The review exposed a serialization issue: rejecting an infinite price did not prevent Python's default JSON encoder from writing a nonstandard `Infinity` token into the report.

`make_json_safe()` now creates a report representation recursively, replacing non-finite numbers with `"NaN"`, `"Infinity"` or `"-Infinity"`. `allow_nan=False` enforces standard JSON output. Source objects are not mutated, and their raw responses remain separate. These strings are a reporting convention; the report cannot distinguish them from identical strings already present in the source without consulting the raw response.

## 4. Transformation and transactional loading

`transformation.py` returns a new dictionary containing the five database fields. It trims title and category and converts prices with `Decimal(str(value))`. This avoids directly converting a float's full binary approximation, but does not recover precision lost during JSON parsing. Unconstrained PostgreSQL `NUMERIC` avoids an arbitrary rounding rule; the source supplies no currency field.

`sql/001_create_products.sql` defines a primary key, required columns and named constraints for positive IDs, nonnegative stock and finite nonnegative prices. Its text checks reject empty or ordinary-space-only values through `btrim()`. Python's `strip()` check also rejects other whitespace-only strings, so the text checks are not identical.

`loading.py` receives an existing connection and uses parameterized `executemany()` with `INSERT ... ON CONFLICT (id) DO UPDATE`. Values remain separate from SQL text. The caller owns the transaction: the Psycopg connection context commits after successful loading and rolls back on an exception. Individual records are not committed separately.

Repeated imports leave 194 rows. Matching IDs are updated, but absent or rejected source records do not delete old rows. This maintains current incoming values rather than a historical catalog or exact snapshot replacement.

## 5. Logging and review changes

Python logging and `python-json-logger` produce structured console events. A run ID is created before configuration validation, making it available even for early failures. The current stage is one of `configuration`, `extraction`, `validation`, `rejection_report` or `database_loading`. Transformation happens within the validation stage.

Handled failures are logged once in `main()` with exception details, `run_id` and `stage`; extraction errors also include `page`. The exception is re-raised so callers and tests can inspect it. The script entry point converts it to exit code 1 without logging it again.

The success event is emitted after commit and contains received, valid, rejected and loaded counts. `loaded_count` means records submitted to the committed transaction, including updates. A completed run exits with 0 even when some records are rejected. Files written before a failure remain available and do not prove a successful commit.

The review changes addressed concrete gaps: pipeline-level tests, early configuration validation, NUL rejection, JSON-safe rejection output and error context. Extracting session creation allowed the retry test to use the same policy as the importer.

## 6. Database roles and initialization

The original `catalog_app` account remains the administrator and owner of `products`. The importer now connects as `catalog_ingestor`, created by `sql/002_create_app_role.sql`. It has no superuser, database-creation, role-creation, replication or row-security-bypass attributes.

The role receives database `CONNECT`, schema `USAGE`, and table `SELECT`, `INSERT` and `UPDATE`. SELECT is also needed by the upsert's use of existing columns. The role does not own the table. Effective permission checks confirmed that DELETE, TRUNCATE and CREATE in `public` were unavailable in the configured database.

Compose reads `POSTGRES_ADMIN_USER` and `POSTGRES_ADMIN_PASSWORD` for database initialization; Python reads `POSTGRES_USER` and `POSTGRES_PASSWORD`. The account names are deliberately separate even though the historical administrator name contains `app`.

The ordinary local setup runs the table script before the role script, each with `ON_ERROR_STOP=1` and a single transaction. The role script uses psql's `DBNAME` variable for the connected database and explicitly names `catalog_ingestor`. Its password is set interactively with `\password`, matching the local `.env`; no password is stored in SQL.

This change was applied to the existing volume without deleting data. Editing Compose initialization values does not alter an existing role or password. On a new volume, both scripts and password setup must be performed. Roles are cluster-wide, so the role script is not rerun for every database in an existing cluster.

The separation limits the application's database privileges. Both sets of credentials still reside in the developer's local `.env`; this is not a secret-manager deployment or isolation from someone with access to that file.

## 7. Tests, formatting and CI

### Tests without PostgreSQL

The default suite runs 73 cases: 49 validation, eight extraction/file-output, one transformation, 11 configuration, three pipeline and one HTTP retry case. Eight database integration cases are collected but skipped unless `--run-integration` is supplied.

Pipeline tests cover complete pagination, failure before loading, and routing valid and rejected records. They replace external connections while exercising the real validation, transformation and file-writing functions. The failure test also links the log's run ID to the raw output directory and checks the failing page.

The retry test starts a temporary HTTP server on loopback using an available port. It responds with 503 and then 200. Two requests for the same path confirm that the production session policy retries, and the final response is saved. The test needs no external API and disables environment proxy settings for its session. It does not measure backoff timing or test exhausted retries.

### PostgreSQL integration tests

Mocked pipeline tests cannot establish whether Psycopg executes the real SQL correctly or whether PostgreSQL commits, rolls back and enforces permissions as intended. The integration suite exercises `loading.py` against PostgreSQL without replacing its connection or cursor.

`compose.test.yaml` defines the separate `partner-catalog-tests` project. PostgreSQL binds to host loopback on port 55432, leaving the demo database's port 5433 and API's port 3000 available. Database storage uses `tmpfs`, not the demo database's named volume. Stopping the container discards test data.

On a fresh start, the PostgreSQL image executes three read-only mounted initialization files in order:

1. `sql/001_create_products.sql` creates the same table used by the importer.
2. `sql/002_create_app_role.sql` creates the restricted importer role and grants.
3. `tests/integration/init_app_password.sql` reads `TEST_APP_PASSWORD` through psql and sets the role password with SQL-literal quoting.

The test administrator is `integration_admin`; application operations use `catalog_ingestor`. The test passwords are public, disposable values shared by Compose and the pytest configuration. They are unrelated to application secrets. This setup is intended for a trusted local machine or an isolated CI runner, not a shared database deployment.

`tests/conftest.py` adds the explicit `--run-integration` switch. Without it, database fixtures skip before attempting a connection or cleanup. Connection settings target `partner_catalog_test` on port 55432 and do not load the application's `.env`.

An administrator fixture truncates the test table before and after each data-changing case. The loader itself always uses the restricted role. These fixtures share one table and are intended for sequential execution; parallel workers must not use the same instance.

The eight cases verify:

- The expected database, application user and initialized table are available.
- An inserted product is committed and visible through a new connection.
- An existing ID is updated across all mutable fields without creating a duplicate.
- Invalid stock raises the expected constraint violation and rolls back both an earlier update and an earlier insert in that transaction.
- Four forbidden operations fail with insufficient privileges: DELETE, TRUNCATE, DROP TABLE and CREATE TABLE.

The rollback case reads the table through a new connection after failure and checks that only the original, unchanged product remains. Permission probes explicitly roll back even if an operation unexpectedly succeeds, preventing the probe from committing changes before reporting a failure.

### Formatting and CI

Ruff 0.16.8 is pinned in `requirements-dev.txt`. `pyproject.toml` sets Python 3.13 as the syntax target, basic correctness rules, import sorting and consistent formatting. `.gitattributes` normalizes tracked text to LF. Tests remain responsible for behavior; formatting checks do not replace them.

The GitHub Actions workflow defines four quality combinations: Ubuntu and Windows, each with Python 3.13 and 3.14. Each installs development dependencies and runs Ruff checks, a formatting check and the default pytest suite.

A fifth job uses Ubuntu and Python 3.13 for PostgreSQL integration tests. It starts `compose.test.yaml` with `--wait`; a TCP health check waits for the database service after initialization. It then runs the eight integration cases, prints database logs on failure, and removes the service with an `always()` cleanup step.

The workflow runs for pushes to `main`, pull requests targeting `main`, and manual dispatch. Repository-content permissions are read-only, credentials are not persisted by checkout, and each job has a ten-minute limit. No application secrets are required. The integration job tests the real database boundary, while the full local API-to-database import remains a manual verification.

## 8. Platform verification

The earlier pipeline version was verified on Windows with Python 3.13.14 and Ubuntu 26.04 in WSL2 with Python 3.14.4. Full ingestion, repeated imports and rollback were checked. Docker Desktop supplied the containers for both environments.

The Linux checkout was placed under `~/projects` and received its own virtual environment and `.env`. Installing the matching `python3.14-venv` package provided `ensurepip`; replacing the system Python was unnecessary. Docker Desktop's WSL integration enabled container access. A fresh session activated the user's configured Docker group membership; socket permissions were not made world-writable.

Using the same Docker engine and Compose project name can reuse the same containers and volume. An earlier initialization check therefore used a separate Compose project and volume, with the ordinary services stopped to free the fixed ports. It loaded 194 products without deleting the original volume.

After the review changes and role separation, the updated project was checked again on Ubuntu in WSL2. All 73 tests passed, Python connected as catalog_ingestor, the importer loaded 194 products, and the rollback check confirmed that the original product was unchanged. The working tree remained clean after execution.

## 9. Verification results

Completed checks recorded during development:

- **Default suite:** 73 passed and eight integration cases skipped when PostgreSQL tests are not requested.
- **Local database tests:** all eight integration cases passed against the disposable PostgreSQL instance on Windows. Ruff lint and formatting checks also passed.
- **CI:** all five jobs passed. Four platform/version combinations ran code-quality checks and the default suite; the Ubuntu integration job passed all eight database cases.
- **Fresh test database:** CI initialized the table and application role from the project SQL scripts, set the test password and connected as the restricted role.
- **Restricted-role import:** the local pipeline reported 194 received, 194 valid, zero rejected and 194 loaded on Windows and Ubuntu in WSL2.
- **Transaction behavior:** automated database tests verified committed inserts, updates without duplicates, and complete rollback after a constraint violation. Manual rollback checks also passed against the demo database.
- **Effective privileges:** SELECT, INSERT and UPDATE worked; integration tests denied DELETE, TRUNCATE, DROP TABLE and CREATE TABLE.
- **Repeat imports:** manual checks retained 194 rows and restored a modified price to the source value.
- **Failure paths:** checks with the API stopped, a blank required setting and a simulated raw-file write failure produced controlled failure behavior.

The earlier WSL2 run covered the 73-case suite and the full demo import with Python 3.14.4. The new database integration job runs on Ubuntu with Python 3.13; it does not establish database integration coverage for every quality-matrix combination. Fresh test database initialization is automated, but full application setup on a separate clean machine has not been recorded.

## 10. Remaining boundaries

The workflow keeps the source catalog in memory and has no scheduling, checkpointing, concurrent-run coordination or automatic output retention. The API fixture is fixed; this is not a general connector for arbitrary catalogs.

Dependencies and image tags are pinned, but transitive versions and image digests are not fully locked. Database constraints remain the final boundary for unusual values outside application validation. Further additions should respond to a concrete requirement rather than expand the tool stack for its own sake.
