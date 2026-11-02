# Soil Pipeline

[![CI](https://github.com/jenn-parker/soil-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/jenn-parker/soil-pipeline/actions/workflows/ci.yml)

Licensed under the [MIT License](LICENSE).

A containerized FastAPI service for creating soil sample records, identifying sample owners and collectors, and importing soil samples from CSV batches. It uses PostgreSQL/PostGIS through SQLAlchemy's async engine and archives uploaded CSV files in S3-compatible object storage.

## Contents

- [Architecture and capabilities](#architecture-and-capabilities)
- [Product walkthrough](#product-walkthrough)
- [Demo soil data and attribution](#demo-soil-data-and-attribution)
- [Run locally with Docker Compose](#run-locally-with-docker-compose)
- [Run the API without Docker](#run-the-api-without-docker)
- [API documentation](#api-documentation)
- [Tests](#tests)
- [Database migrations](#database-migrations)
- [API routes](#api-routes)
  - [Authentication and authorization](#authentication-and-authorization)
  - [Sample ownership and sharing](#sample-ownership-and-sharing)

## Architecture and capabilities

- FastAPI endpoints with Pydantic request validation.
- PostgreSQL and PostGIS for relational data and spatial queries.
- A GiST index on `soil_samples.location` for location-based reports and map queries.
- S3-compatible archival of accepted CSV uploads through LocalStack in local development or AWS S3 in a deployed environment.
- Optional, request-level AI explanations using aggregate soil measurements and caller-provided management context.
- A Kubernetes reference manifest for a possible existing-cluster deployment; it is not the current deployment path and does not provision AWS infrastructure.

The detailed deployment architecture is documented in
[`docs/architecture.md`](docs/architecture.md). The repeatable local demo and
AWS foundation procedures are documented in the
[`deployment runbook`](docs/deployment-runbook.md).
The interview-ready walkthrough is in the
[`demo script`](docs/demo-script.md).

## Product walkthrough

The application screenshots in
[`docs/screenshots/`](docs/screenshots/) provide a quick visual overview of the
dashboard, map interactions, sample entry, and owned-sample management flow.
They use sanitized demo data and are kept separate from the implementation
documentation so the README remains easy to scan. See the
[screenshot gallery](docs/screenshots/README.md) for captions and context.

The repository contains application code, Alembic migrations, legacy raw SQL migrations, tests, a Dockerfile, a local Compose environment, a CI workflow, Terraform configuration for the AWS security and storage foundation, and a starter Kubernetes manifest. The CI workflow validates backend tests, frontend lint/build, Terraform configuration, and the API Docker image on pushes to `main` and pull requests.

The workflow performs validation only. It does not deploy infrastructure or application images, and it does not require AWS credentials in GitHub Actions. Deployment can be added later using GitHub OIDC and a narrowly scoped AWS role.

## Demo soil data and attribution

The map demo can be populated with the records in
[`data/seed/ssurgo-iowa-demo.csv`](data/seed/ssurgo-iowa-demo.csv). These ten
Iowa locations are representative points derived from USDA Natural Resources
Conservation Service (NRCS) Soil Survey Geographic Database (SSURGO) data. The
pH, organic matter, and texture values come from the dominant component's
surface horizon returned by the USDA Soil Data Access service.

These are soil-survey representative locations, not claims that physical farm
samples were collected at the displayed coordinates. The repository preserves
the source description and repeatable local loader in
[`data/seed/README.md`](data/seed/README.md) and
[`scripts/seed_ssurgo_demo.sql`](scripts/seed_ssurgo_demo.sql).

Source credit:

- USDA NRCS, [Soil Survey Geographic Database (SSURGO)](https://www.nrcs.usda.gov/resources/data-and-reports/soil-survey-geographic-database-ssurgo)
- USDA NRCS, [Soil Data Access web service](https://sdmdataaccess.sc.egov.usda.gov/WebServiceHelp.aspx)

## Run locally with Docker Compose

Requirements: OrbStack or another Docker-compatible engine with the Compose plugin. Docker Desktop is not required if OrbStack is installed.

Create the local environment file from the committed sample, then replace the
LocalStack token and generate a session secret:

```bash
cp .env.sample .env
openssl rand -hex 32
```

Put the generated value in `AUTH_SESSION_SECRET`. The sample defaults to the
API-key provider; the Cognito OAuth setup is documented below. The real `.env`
file is ignored by Git.

LocalStack also requires an auth token. Get one from the [LocalStack web app](https://app.localstack.cloud), then export it in your shell before starting Compose. Keep the token private and do not commit it to the repository. Leave it set in that same shell for later `docker compose` commands, including `logs`, `exec`, and `down`, because Compose reads the variable when it evaluates the configuration.

```bash
export LOCALSTACK_AUTH_TOKEN='YOUR_LOCALSTACK_AUTH_TOKEN'
docker compose up --build
```

The API listens on <http://localhost:8000>. Compose starts PostgreSQL 16/PostGIS and LocalStack. The PostGIS service is pinned to `linux/amd64` because the selected official image does not publish an ARM64 build; on Apple Silicon it runs under emulation and may be slower. LocalStack creates the `soil-pipeline-batches` bucket (configurable with `S3_BATCH_BUCKET`) and persists its data in a named volume. LocalStack is exposed at <http://localhost:4566>. The local AWS credentials and database credentials are examples; do not use them in a deployed environment.

Compose runs `alembic upgrade head` before starting the development API. Alembic is the source of truth for schema changes; the legacy numbered SQL files are retained for reference and are not run by Compose. For production, apply the Alembic migrations as a deployment step or migration job before starting API replicas.

Inspect local S3 objects with the AWS CLI (or `awslocal` if installed):

```bash
aws --endpoint-url http://localhost:4566 s3 ls s3://soil-pipeline-batches/ --recursive
```

Stop the services with:

```bash
docker compose down
```

To also delete the local database and S3 volumes and their data, run `docker compose down --volumes`.

## Run the API without Docker

Use a local Python environment (Python 3.12 is the current recommended development version) and a running PostgreSQL database. The Dockerfile currently uses Python 3.11. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@localhost:5432/soil_db'
export AWS_ENDPOINT_URL_S3='http://localhost:4566'
export AWS_REGION='us-east-1'
export AWS_ACCESS_KEY_ID='test'
export AWS_SECRET_ACCESS_KEY='test'
export S3_BATCH_BUCKET='soil-pipeline-batches'
uvicorn app.main:app --reload
```

The database must have PostGIS installed and the extension enabled before starting the app. The S3 endpoint and bucket must also be available for CSV uploads; start Compose's LocalStack service with `docker compose up localstack` or point these settings to an AWS account. Alembic's initial revision creates PostGIS, the current application tables, and their indexes. Existing databases created by the former `create_all()` workflow should be checked against the current models and then stamped at the current revision rather than replaying the initial `CREATE TABLE` migration:

```bash
docker compose run --rm web alembic stamp head
```

Only use that stamping command when the existing schema already matches the current models. For a disposable local database, reset the volumes and let Compose recreate everything:

```bash
docker compose down --volumes
docker compose up --build
```

## API documentation

With the API running:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI document: <http://localhost:8000/openapi.json>

## Tests

Install the development dependencies and run the unit/API tests from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

GitHub Actions reports backend coverage and requires at least 80% total
coverage. The coverage configuration excludes application startup wiring,
logging bootstrap, and exception-handler clauses so the threshold focuses on
normal application behavior rather than setup and defensive plumbing.

The suite covers request validation, recommendation status and opt-in behavior, and S3 client configuration/error handling. Database queries and S3 calls are mocked, so these tests do not require a running PostgreSQL/PostGIS or LocalStack service.

The service integration tests are opt-in. The following workflow uses the LocalStack CLI-managed emulator and the project’s PostgreSQL container; it does not provision or contact AWS:

```bash
docker compose up -d db
lstk start
aws --endpoint-url http://localhost.localstack.cloud:4566 \
  s3 mb s3://soil-pipeline-batches 2>/dev/null || true

export DATABASE_URL='postgresql+asyncpg://earth_user:earth_password@localhost:5432/soil_db'
export AWS_ENDPOINT_URL_S3='http://localhost.localstack.cloud:4566'
export AWS_ACCESS_KEY_ID='test'
export AWS_SECRET_ACCESS_KEY='test'
export S3_BATCH_BUCKET='soil-pipeline-batches'
alembic upgrade head
RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration -q
```

If you use Compose to run LocalStack instead, start it with `docker compose up -d localstack` and use `http://localhost:4566` for `AWS_ENDPOINT_URL_S3`. Do not run both LocalStack instances on port 4566. The tests exercise the real CSV upload path, PostgreSQL persistence, and LocalStack object storage; they clean up their generated sample, batch, and archive after completion.

To reconcile old S3 batch archives that are not referenced by PostgreSQL, run the maintenance job with a grace period. The default is 24 hours:

```bash
python -m app.jobs.reconcile_batch_archives --grace-hours 24
```

The upload flow persists a durable archive intent and a two-hour lease before writing to S3. The two-hour lease is an explicit operational assumption: CSV uploads are expected to finish well within that limit. Finalization uses the archive generation and lease as a conditional database transition, so stale workers cannot overwrite a newer state. The job scans only `soil-batches/`, retains referenced and active leased objects, fences expired pending leases, and deletes only stale objects confirmed to be unreferenced. Run it from a scheduled worker or cron job with the same database and S3 configuration as the API.

For a local cron schedule, use the project virtual environment and load the ignored `.env` file so the job has the database and LocalStack settings:

```cron
*/15 * * * * cd /absolute/path/to/soil-pipeline && set -a && . ./.env && set +a && ./.venv/bin/python -m app.jobs.reconcile_batch_archives --grace-hours 24 >> /tmp/soil-pipeline-reconcile.log 2>&1
```

The job logs scan, reference, deletion, and deletion-failure counts. It exits non-zero when any deletion fails, allowing cron monitoring or a process supervisor to alert on failures.

## Database migrations

Alembic is the schema migration tool for new changes. The database URL is read from `DATABASE_URL`, which uses the same async PostgreSQL URL as the application:

```bash
alembic upgrade head
alembic current
alembic history
```

Create a new revision after changing the SQLAlchemy models, review the generated operations, and test both upgrade and downgrade paths before applying it to a shared database:

```bash
alembic revision --autogenerate -m "describe the schema change"
```

The Alembic environment limits autogeneration to the application schema and
excludes the PostGIS-managed `spatial_ref_sys` table. Always review an
autogenerated migration before applying it; the filter prevents extension
catalog noise but does not replace migration review. GeoAlchemy2's Alembic
helpers also render spatial types and indexes and register spatial operations
for autogenerated revisions.

The initial Alembic revision represents the current application schema. The older files in `migrations/` document the pre-Alembic migration history and should not be applied on top of a database already managed by Alembic.

## API routes

All application routes are prefixed with `/api/v1`.

### Authentication and authorization

The API supports two authentication providers. Local Compose uses bearer API keys by default. Configure `AUTH_API_KEYS` as a semicolon-separated list of `key=scope,scope` entries. Compose supplies a development-only default key named `local-demo-key`; replace it before sharing the service:

```bash
export AUTH_API_KEYS='replace-with-a-long-random-key=soil:read,soil:write,batch:upload'
docker compose up --build
```

Send the key as an authorization header:

```bash
curl -H 'Authorization: Bearer replace-with-a-long-random-key' \
  'http://localhost:8000/api/v1/reports/soil-ranges?latitude=41.88&longitude=-93.10&radius_km=10'
```

To try authenticated endpoints in Swagger UI during local development:

1. Open <http://localhost:8000/docs>.
2. Click **Authorize**.
3. Enter `local-demo-key`.
4. Click **Authorize**.

The `local-demo-key` value is a Compose-only development credential. Replace
it before sharing the service or deploying it anywhere.

All `/api/v1` routes require `soil:read`. Create and upload operations additionally require `soil:write` or `batch:upload`. Liveness and readiness endpoints remain unauthenticated for container orchestration. The React frontend is the application interface; its API requests use the authenticated Cognito session.

This API-key mechanism is intentionally lightweight for the demo. A production deployment should replace it with JWT validation against an OIDC provider such as Amazon Cognito while retaining the route-level scopes.

The Terraform configuration provisions an Amazon Cognito User Pool, an OAuth app client, and the custom scopes used by the API. To use the real Cognito provider locally after applying Terraform, set the outputs in the Compose environment:

```bash
export AUTH_PROVIDER=cognito
export COGNITO_ISSUER="$(terraform -chdir=infra output -raw cognito_issuer)"
export COGNITO_APP_CLIENT_ID="$(terraform -chdir=infra output -raw cognito_app_client_id)"
export COGNITO_LOGIN_DOMAIN="$(terraform -chdir=infra output -raw cognito_login_domain)"
export AUTH_SESSION_SECRET="$(openssl rand -hex 32)"
docker compose up --build
```

Open <http://localhost:8000/auth/login> to sign in through Cognito Managed Login. The callback exchanges the authorization code with PKCE, stores the access token in an HttpOnly cookie, and redirects to the map. The `/auth/logout` endpoint clears the local cookies and redirects through Cognito logout.

The Cognito validator accepts only signed access tokens issued by the configured User Pool, checks `token_use=access`, validates the app client ID, and enforces the route scopes. The Kubernetes manifest uses Cognito mode and requires the Terraform Cognito outputs plus a strong `AUTH_SESSION_SECRET` to replace its placeholders before deployment.

### Sample ownership and sharing

New samples and CSV batches record the authenticated Cognito user's stable `sub`
as the creator. Existing SSURGO demo records have no creator and remain visible
as shared reference data. A creator can update or delete their own samples and
grant another signed-in user either `viewer` or `editor` access by email. Email
is normalized for sharing lookup, while Cognito `sub` remains the ownership
identifier because email addresses can change.

Map and report queries are scoped to reference records, owned records, and
records shared with the current user. The sample management routes are:

- `GET /api/v1/soil-samples/{sample_id}` — read an accessible sample.
- `PUT /api/v1/soil-samples/{sample_id}` — update an owned or editor-shared sample.
- `DELETE /api/v1/soil-samples/{sample_id}` — delete an owned sample.
- `GET|POST /api/v1/soil-samples/{sample_id}/access` — list or grant access as the owner.
- `DELETE /api/v1/soil-samples/{sample_id}/access/{email}` — revoke access as the owner.

Owners can archive a sample with `POST /api/v1/soil-samples/{sample_id}/archive`.
Archived samples are excluded from maps, reports, and normal sample reads while
remaining in the database with their ownership and sharing history intact.
Owners can restore them with `POST /api/v1/soil-samples/{sample_id}/restore`.
The dashboard exposes the archive confirmation flow from an owned sample's map
popup. Hard deletion remains available as a separate owner-only API operation.

The dashboard exposes edit, access-management, and archive links only for
samples where the authenticated user has the corresponding capability. The
ownership and archive schema changes are applied by Alembic revisions
`20261101_0002` and `20261101_0003`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/soil-samples` | Create one soil sample from a JSON body. |
| `POST` | `/api/v1/parties` | Create an owner or collector. |
| `POST` | `/api/v1/sample-identifications` | Create sample collection and provenance details. |
| `POST` | `/api/v1/soil-batches` | Upload a CSV file of soil samples as multipart form data (`file`). |
| `GET` | `/api/v1/soil-batches/{batch_id}` | Read batch status, counts, and validation errors. |
| `GET` | `/api/v1/reports/soil-ranges` | Summarize measurements for samples within a radius of a coordinate. |
| `POST` | `/api/v1/recommendations/location` | Create a cautious soil-context brief and report missing recommendation inputs. |
| `GET` | `/api/v1/maps/soil-samples` | Return soil locations as GeoJSON within a bounding box. |

The location report takes `latitude`, `longitude`, and `radius_km` query parameters. For example, `/api/v1/reports/soil-ranges?latitude=41.88&longitude=-93.10&radius_km=10` returns the sample count, earliest/latest `sampled_at` values, and minimum/maximum for each available soil measurement. Each measurement includes its own non-null sample count, since some samples may not have a result for every field. No individual sample records are returned.

The location recommendation brief accepts the same location and radius plus optional crop, state/province, yield goal and unit, soil-test lab/method, previous crop, irrigation, and tillage. It returns nearby sample ranges, the missing context, and a status. Example request:

```json
{
  "latitude": 41.88,
  "longitude": -93.10,
  "radius_km": 2,
  "crop": "corn",
  "state_province": "Iowa",
  "include_ai_explanation": false
}
```

This first pass does not calculate crop suitability or application rates; it deliberately reports when samples are absent or calibrated rules are not configured.

AI explanations are opt-in per request with `include_ai_explanation: true`. Configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL` (defaults to `gpt-6-astra`) for this feature. The model receives only aggregate measurements and caller-provided management context—never exact coordinates or sample IDs—and is instructed to explain the data without prescribing rates. Do not enable it unless sending those aggregates and context to OpenAI is acceptable for your deployment. Without a configured key, an opted-in request with sample data returns `503`; requests that do not opt in remain local. No AI request is made when the search finds no samples.

The map endpoint takes `west`, `south`, `east`, and `north` bounding-box coordinates, plus an optional `limit` (default 1,000; maximum 5,000). It returns GeoJSON features with sample ID, field, date, and pH properties. The React frontend renders the map with Leaflet and OpenStreetMap tiles. Soil test results and provenance records are linked by `sample_id` when they are created; the migration backfills links for existing matching records and copies provenance coordinates when a soil result has no coordinates.

Health endpoints are available at `/health/live` and `/health/ready`. Readiness checks database connectivity.

### Upload a CSV batch

CSV files must be UTF-8 encoded, no larger than 10 MB, and include a `sample_id` column. CSV field names and validation rules match `SoilTestResultCreate` in `app/schemas/soil.py`. For example:

```csv
sample_id,field_name,soil_ph,nitrate_nitrogen_ppm
LAB-1001,North Field,6.4,18.25
LAB-1002,South Field,5.9,12.00
```

The server validates the whole file before inserting records. The original CSV is archived in S3 and each batch response includes its `source_bucket` and `source_key`. If any row is invalid or has a duplicate `sample_id`, the batch is marked `rejected`, no samples from that file are inserted, and row-level errors are returned and stored with the batch. If all rows pass, the batch is marked `completed` and each created soil sample links back to the batch.

Invalid request data returns `422`, duplicate sample identifiers return `409`, and missing party or batch IDs return `404`. A valid location report with no nearby samples returns `200` with `sample_count: 0`, null date bounds, and an empty `measurements` object. Database constraint conflicts return `409`; database availability problems return `503`.

## Docker image

The Dockerfile builds the API image and runs Uvicorn without reload as a non-root user. Build it locally with:

```bash
docker build -t soil-pipeline:local .
```

Compose overrides the container command to run `alembic upgrade head`, then enable Uvicorn reload, and mounts the source tree for development. The standalone image includes the Alembic configuration and revisions but does not automatically run migrations; production should invoke Alembic as a separate deployment step or migration job. The standalone image does not include the Compose development mount.

## Kubernetes reference template

[`k8s/soil-pipeline.yaml`](k8s/soil-pipeline.yaml) is an untested reference
template containing a Kubernetes Deployment, Service, and AWS Application Load
Balancer Ingress. It is not the current deployment path for this project.

The repository does not currently provision or operate:

- A Kubernetes or EKS cluster.
- Application compute or worker nodes.
- An ECR repository or image-publishing workflow.
- Production PostgreSQL/PostGIS or RDS.
- A VPC, subnets, security groups, load balancer, DNS, or TLS certificate.
- Kubernetes secrets or a production migration job.

The manifest contains placeholders and assumes those external resources already
exist. It should not be applied as-is. The supported application environment is
local Docker Compose, and the current Terraform configuration provisions only
the AWS authentication, storage, and IAM foundation described in
[`docs/architecture.md`](docs/architecture.md). A future live deployment can
choose a managed container service such as ECS/Fargate or App Runner without
requiring EKS.

## Local AWS service choices

LocalStack currently emulates S3 for raw CSV archival. PostgreSQL/PostGIS remains the application database because the API relies on relational links and native spatial queries. DynamoDB is not added: batch status and validation errors already belong to the relational batch record, and copying them to DynamoDB would create a second source of truth without a current access-pattern benefit. Add SQS or DynamoDB later if batch processing becomes asynchronous or a measured workload needs a separate key-value access path.
