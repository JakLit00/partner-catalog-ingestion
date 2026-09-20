# Development Notes

The project was built from the storage and source boundaries inward: local services, extraction, validation, transformation and loading. Cross-platform checks and a subsequent review added pipeline tests, stricter input checks, error context, code quality tooling and separate database roles.

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

Initialization runs the table script before the role script, each with `ON_ERROR_STOP=1` and a single transaction. The role script uses psql's `DBNAME` variable for the connected database and explicitly names `catalog_ingestor`. Its password is set interactively with `\password`, matching the local `.env`; no password is stored in SQL.

This change was applied to the existing volume without deleting data. Editing Compose initialization values does not alter an existing role or password. On a new volume, both scripts and password setup must be performed. Roles are cluster-wide, so the role script is not rerun for every database in an existing cluster.

The separation limits the application's database privileges. Both sets of credentials still reside in the developer's local `.env`; this is not a secret-manager deployment or isolation from someone with access to that file.

## 7. Tests, formatting and CI

The suite has 73 cases: 49 validation, eight extraction/file-output, one transformation, 11 configuration, three pipeline and one HTTP retry case.

Pipeline tests cover complete pagination, failure before loading, and routing valid and rejected records. They replace external connections while exercising the real validation, transformation and file-writing functions. The failure test also links the log's run ID to the raw output directory and checks the failing page.

The retry test starts a temporary HTTP server on loopback using an available port. It responds with 503 and then 200. Two requests for the same path confirm that the production session policy retries, and the final response is saved. The test needs no external API and disables environment proxy settings for its session. It does not measure backoff timing or test exhausted retries.

Ruff 0.16.8 is pinned in `requirements-dev.txt`. `pyproject.toml` sets Python 3.13 as the syntax target, basic correctness rules, import sorting and consistent formatting. `.gitattributes` normalizes tracked text to LF. Tests remain responsible for behavior; formatting checks do not replace them.

The GitHub Actions workflow defines four combinations: Ubuntu and Windows, each with Python 3.13 and 3.14. Each installs development dependencies and runs Ruff checks, a formatting check and pytest. It runs for pushes to `main`, pull requests targeting `main`, and manual dispatch. Permissions are read-only for repository content, credentials are not persisted by checkout, and each job has a ten-minute limit.

CI does not provision PostgreSQL or run `check_rollback.py`. It requires no database secrets. A configured matrix describes the intended checks; successful execution is established by the corresponding Actions run.

## 8. Platform verification

The earlier pipeline version was verified on Windows with Python 3.13.14 and Ubuntu 26.04 in WSL2 with Python 3.14.4. Full ingestion, repeated imports and rollback were checked. Docker Desktop supplied the containers for both environments.

The Linux checkout was placed under `~/projects` and received its own virtual environment and `.env`. Installing the matching `python3.14-venv` package provided `ensurepip`; replacing the system Python was unnecessary. Docker Desktop's WSL integration enabled container access. A fresh session activated the user's configured Docker group membership; socket permissions were not made world-writable.

Using the same Docker engine and Compose project name can reuse the same containers and volume. An earlier initialization check therefore used a separate Compose project and volume, with the ordinary services stopped to free the fixed ports. It loaded 194 products without deleting the original volume.

These earlier WSL checks predate the latest review changes and role separation. The current 73-case suite, Ruff checks, application-role import and rollback were subsequently confirmed on Windows. A full Linux rerun of the final role setup and a GitHub Actions execution are not included in those local results.

## 9. Verification results

Completed checks recorded during development:

- **Code checks:** 73 pytest cases passed; Ruff lint and formatting checks passed on Windows after the code-quality changes.
- **Restricted-role connection:** Python reported `catalog_ingestor` as the connected user.
- **Restricted-role import:** 194 received, 194 valid, zero rejected and 194 loaded.
- **Restricted-role rollback:** the deliberate constraint violation left the original product unchanged.
- **Effective privileges:** SELECT, INSERT and UPDATE allowed; DELETE, TRUNCATE and schema CREATE denied.
- **Repeat and update behavior:** earlier checks retained 194 rows and restored a manually changed price to the source value.
- **Failure paths:** earlier checks with the API stopped, a blank required setting and a simulated raw-file write failure produced controlled failure behavior.
- **Initialization:** an earlier separate-volume check created the table and imported the dataset under WSL2; it preceded the new role script.

Database checks are explicit local checks rather than pytest integration tests. The final role bootstrap has not been recorded as a fresh-volume test, and the four-job CI matrix has not yet been recorded as executed. No separate-machine provisioning result is claimed.

## 10. Remaining boundaries

The workflow keeps the source catalog in memory and has no scheduling, checkpointing, concurrent-run coordination or automatic output retention. The API fixture is fixed; this is not a general connector for arbitrary catalogs.

Dependencies and image tags are pinned, but transitive versions and image digests are not fully locked. Database constraints remain the final boundary for unusual values outside application validation. Further additions should respond to a concrete requirement rather than expand the tool stack for its own sake.
