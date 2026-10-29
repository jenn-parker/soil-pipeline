# Soil Metric Ingestion Pipeline

FastAPI service for creating soil sample records, identifying sample owners and collectors, and importing soil samples from CSV batches. The API uses PostgreSQL through SQLAlchemy's async engine.

## Run locally with Docker Compose

Requirements: Docker Desktop or another Docker Engine with the Compose plugin.

LocalStack also requires an auth token. Get one from the [LocalStack web app](https://app.localstack.cloud), then export it in your shell before starting Compose. Keep the token private and do not commit it to the repository. Leave it set in that same shell for later `docker compose` commands, including `logs`, `exec`, and `down`, because Compose reads the variable when it evaluates the configuration.

```bash
export LOCALSTACK_AUTH_TOKEN='YOUR_LOCALSTACK_AUTH_TOKEN'
docker compose up --build
```

The API listens on <http://localhost:8000>. Compose starts PostgreSQL 16/PostGIS and LocalStack. The PostGIS service is pinned to `linux/amd64` because the selected official image does not publish an ARM64 build; on Apple Silicon it runs under emulation and may be slower. The API uses PostGIS for relational and geospatial sample queries, and archives CSV uploads in S3. LocalStack creates the `soil-pipeline-batches` bucket (configurable with `S3_BATCH_BUCKET`) and persists its data in a named volume. LocalStack is exposed at <http://localhost:4566>. The local AWS credentials and database credentials are examples; do not use them in a deployed environment.

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

Use Python 3.11 and a running PostgreSQL database. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@localhost:5432/soil_db'
export AWS_ENDPOINT_URL_S3='http://localhost:4566'
export AWS_REGION='us-east-1'
export AWS_ACCESS_KEY_ID='test'
export AWS_SECRET_ACCESS_KEY='test'
export S3_BATCH_BUCKET='soil-pipeline-batches'
uvicorn app.main:app --reload
```

The database must have PostGIS installed and the extension enabled before starting the app. The S3 endpoint and bucket must also be available for CSV uploads; start Compose's LocalStack service with `docker compose up localstack` or point these settings to an AWS account. On a fresh database, apply [migration 000](migrations/000_enable_postgis.sql); the current app startup then creates missing tables. On an existing database, apply migrations 000 through 004 in order; `create_all` does not add columns or indexes or alter existing column types. Migration 004 converts existing timezone-naive `sampled_at` values to UTC-aware timestamps, assuming the stored naive values represent UTC. The database role must be allowed to create the PostGIS extension, or an administrator should install it first. Production should run schema migrations as a deployment step rather than relying on each API replica's startup `create_all` call.

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

The suite covers request validation, recommendation status and opt-in behavior, and S3 client configuration/error handling. Database queries and S3 calls are mocked, so these tests do not require a running PostgreSQL/PostGIS or LocalStack service.

## API routes

All application routes are prefixed with `/api/v1`.

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

The map endpoint takes `west`, `south`, `east`, and `north` bounding-box coordinates, plus an optional `limit` (default 1,000; maximum 5,000). It returns GeoJSON features with sample ID, field, date, and pH properties. Open <http://localhost:8000/map> for the built-in Leaflet map. The map loads Leaflet and OpenStreetMap tiles from their public services. Soil test results and provenance records are linked by `sample_id` when they are created; the migration backfills links for existing matching records and copies provenance coordinates when a soil result has no coordinates.

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

Compose overrides the container command to enable reload and mounts the source tree for development. The standalone image is intended for deployment and does not include that development mount.

## Deploying to EKS

`k8s/soil-pipeline.yaml` is a starter Kubernetes Deployment, Service, and AWS Application Load Balancer Ingress. It is not a complete EKS or AWS infrastructure deployment. For the database, use Amazon RDS for PostgreSQL with a PostgreSQL version that supports the PostGIS features used by this app. Before applying the manifest:

1. Build and push the image to an ECR repository, then replace `REPLACE_WITH_ECR_IMAGE_URI` in the manifest with its full image URI.
2. Replace `REPLACE_WITH_API_HOSTNAME` with the API hostname.
3. Put RDS in private subnets in the EKS VPC. Configure the RDS security group to allow inbound TCP port 5432 from the EKS application pod security group (with Security Groups for Pods) or the EKS node security group, as appropriate for the cluster. Keep public accessibility disabled and do not allow database ingress from the public internet.
4. Create the `soil-pipeline-secrets` Kubernetes Secret. Its `DATABASE_URL` should use the RDS endpoint, port, database name, username, and password, for example `postgresql+asyncpg://APP_USER:URL_ENCODED_PASSWORD@RDS_ENDPOINT:5432/soil_db`. URL-encode special characters in the username or password. Optionally add `OPENAI_API_KEY` to enable requested AI explanations. Use a secure secret delivery process; do not reuse local Compose credentials.
5. Before production, configure verified TLS for the async PostgreSQL driver. The current `app/database.py` does not yet load an RDS CA bundle or pass an SSL context to `asyncpg`, so setting `DATABASE_URL` alone is not sufficient to guarantee certificate and hostname verification. A suitable implementation pattern is:

   ```python
   import os
   import ssl

   connect_args = {}
   ca_bundle = os.getenv("DATABASE_SSL_CA")
   if ca_bundle:
       connect_args["ssl"] = ssl.create_default_context(cafile=ca_bundle)

   engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
   ```

   The SSL context verifies the server certificate and hostname. Obtain the current AWS RDS CA bundle from AWS, make it available in the API container (for example, mount it read-only from a Kubernetes ConfigMap), and set `DATABASE_SSL_CA` to its mounted path. Keep the CA bundle current according to AWS certificate rotation notices. For production, require this setting at startup rather than silently allowing an unverified or plaintext connection. The RDS PostgreSQL SSL guide covers `verify-full` and CA trust requirements: <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html>.
6. Apply the database schema before starting the API. Migration 000 enables PostGIS; migrations 001 through 004 add batch and spatial/link columns and convert `sampled_at` to a timezone-aware UTC column. **The repository does not yet include a baseline migration for the core model tables**; migrations 001 and 002 assume those tables already exist. Add and review a baseline migration for the current models, then run migration 000, the baseline, and migrations 001 through 004 in order. Migration 004 assumes existing naive `sampled_at` values represent UTC. The startup `Base.metadata.create_all()` only creates missing tables and does not upgrade existing tables, so use a migration step/job for deployments and do not rely on every API replica to modify the schema.
7. Ensure the EKS cluster has the AWS Load Balancer Controller installed and configured, and verify the API can resolve and connect to the private RDS endpoint.
8. Apply the Kubernetes manifest:

   ```bash
   kubectl apply -f k8s/soil-pipeline.yaml
   ```

The EKS template includes readiness and liveness probes, resource requests and limits, and a restricted container security context. Configure `S3_BATCH_BUCKET` and grant the pod's IAM role permission to write objects to that bucket; leave `AWS_ENDPOINT_URL_S3` unset in AWS so the SDK uses AWS endpoints and workload credentials. The EKS cluster, VPC, ECR repository, S3 bucket, RDS instance, database subnet/security groups, DNS, TLS certificate, IAM roles, and controller are not provisioned by this repository.

## Local AWS service choices

LocalStack currently emulates S3 for raw CSV archival. PostgreSQL/PostGIS remains the application database because the API relies on relational links and native spatial queries. DynamoDB is not added: batch status and validation errors already belong to the relational batch record, and copying them to DynamoDB would create a second source of truth without a current access-pattern benefit. Add SQS or DynamoDB later if batch processing becomes asynchronous or a measured workload needs a separate key-value access path.
