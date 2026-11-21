# Hiring Manager Walkthrough

This is a short, self-guided walkthrough for someone reviewing the project
without a live presentation. It is designed to demonstrate both the product
experience and the engineering decisions behind it in roughly five minutes.

## What this project demonstrates

Soil Pipeline is a full-stack soil-data workspace built around four concerns:

- ingesting and validating soil records from individual forms or CSV batches;
- using PostgreSQL/PostGIS for spatial search and reporting;
- enforcing ownership, sharing, archiving, and route-level authorization; and
- operating a realistic OAuth, object-storage, migration, and testing workflow
  without requiring a deployed AWS environment.

The project is intentionally runnable locally. LocalStack replaces S3, while
Terraform documents the AWS authentication, storage, and IAM foundation that a
future deployment would use.

## Start the demo

From the repository root:

```bash
docker compose up -d --build
python scripts/bootstrap_demo.py
cd frontend
npm ci
cp .env.example .env.local
npm run dev -- --host 127.0.0.1
```

Open <http://localhost:5173>. The bootstrap is idempotent and creates
representative reference data plus a small batch owned by the local demo
principal. The default frontend uses the local API-key mode; it is a
development convenience, not a production credential. The Cognito flow is
available separately when demonstrating the OAuth implementation.

## Suggested walkthrough

### 1. Show the product workflow

Start on the map and point out that the data is representative Iowa soil-survey
data, clearly attributed in the repository. Open a marker, change the
measurement used for coloring, and run a nearby report.

Highlight that the report returns ranges and per-measurement sample counts
rather than treating nearby samples as one composite result.

Open the recommendation panel and enter optional crop and management context.
The AI explanation is explicitly opt-in and receives aggregate measurements and
caller-provided context—not exact coordinates or sample identifiers. Its role
is explanation, not agronomic prescription.

### 2. Demonstrate validation and ingestion

Open the CSV format help and upload
`data/seed/demo-owned-batch.csv`. Show the resulting batch status and row
counts, then explain the upload sequence:

1. The entire file is parsed and validated first.
2. A durable PostgreSQL batch intent is committed.
3. The original file is archived in S3/LocalStack.
4. Soil rows and the final batch state are committed together.

Invalid rows produce row-level errors and do not partially create samples.
Coordinates, pH, percentages, measurement ranges, and batch counts are
validated by both the API schemas and database constraints.

### 3. Demonstrate authorization and lifecycle behavior

Open **My samples** and select the bootstrapped owned sample. Show that it can
be edited, shared with a viewer or editor, archived, and restored.

The key point is that authentication and authorization are separate:

- Cognito `sub` values are the ownership identity.
- Access grants prefer stable subject IDs, with normalized email retained for
  compatibility and invitation workflows.
- Editors can update shared samples without becoming owners.
- Archived samples leave normal maps and reports but remain recoverable.

### 4. Close with the engineering overview

The implementation uses React/TypeScript, FastAPI, Pydantic, async SQLAlchemy,
PostgreSQL/PostGIS, and S3-compatible storage. Alembic owns schema evolution;
the integration suite runs migrations against real PostgreSQL and verifies the
live schema.

Authentication supports local API keys and Cognito OAuth authorization code
with PKCE. Cognito sessions use HttpOnly access/refresh cookies, refresh-token
rotation, CSRF protection for browser writes, and refresh-token revocation on
logout.

The repository includes unit tests, Docker-backed integration tests, frontend
lint/build checks, Terraform validation, structured request logging, request
IDs, and safe error responses. It deliberately does not create always-on
compute, networking, or a production database, keeping the portfolio project
reproducible and inexpensive.

## Useful technical discussion points

- **Why PostGIS?** Spatial filtering and radius reports belong in the database,
  with a GiST index supporting the query path.
- **Why a durable upload intent?** PostgreSQL and S3 are separate systems, so
  the intent, lease, conditional finalization, and reconciliation job make
  failure modes explicit.
- **Why stable subjects instead of email ownership?** Email addresses can
  change; Cognito subjects are the durable identity key.
- **Why local emulators?** The project demonstrates the integration boundaries
  without incurring cloud costs or requiring interviewers to provision AWS.
- **What would come next?** A managed deployment would add compute,
  PostgreSQL/PostGIS, networking, secrets, HTTPS ingress, and a controlled
  migration job; those are documented but intentionally outside this portfolio
  scope.

## Quick verification commands

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
python -m pytest -q
./scripts/run_integration_tests.sh
```

The regular suite uses mocks and does not require Docker. The integration
helper requires the Compose PostgreSQL and LocalStack services and cleans up
its generated records and objects.
