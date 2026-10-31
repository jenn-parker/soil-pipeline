# Deployment and Demo Runbook

This runbook covers the supported local demo workflow and the AWS foundation workflow. It does not provision application hosting. The project is intentionally kept undeployed until a live demonstration is needed.

## Prerequisites

- Docker with Compose support, such as OrbStack or Docker Desktop.
- Node.js and npm for the frontend.
- Python 3.11+ for local test execution outside Docker.
- Terraform 1.8+ for AWS infrastructure changes.
- An AWS account only when applying the `infra` configuration.

## Local demo

### 1. Configure local secrets

Create or update `.env` at the repository root. Keep it untracked. For LocalStack, provide the token in the same shell used for Compose commands:

```bash
export LOCALSTACK_AUTH_TOKEN='your-localstack-token'
```

For API-key mode, Compose supplies a development-only default key. For the Cognito demo, set the Cognito values documented in the README and use the callback URL `http://localhost:5173/auth/callback`.

### 2. Start the backend services

From the repository root:

```bash
docker compose up -d --build
```

The API is available at <http://localhost:8000>. Compose applies the Alembic migrations before starting the API.

### 3. Start the frontend

In a second terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 > /tmp/soil-pipeline-vite.log 2>&1 &
```

Open <http://localhost:5173>.

### 4. Verify the services

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
```

Sign in through the frontend, then verify that the map loads. Add a sample manually or upload the demo CSV to exercise ownership and map behavior.

### 5. Load the attributed demo data

The representative Iowa records are documented in [`data/seed/README.md`](../data/seed/README.md). The data is derived from USDA NRCS SSURGO and is clearly labeled as representative demo data rather than physical farm samples.

## Common local operations

View service status:

```bash
docker compose ps
```

View API logs:

```bash
docker compose logs -f web
```

Stop services while preserving local data:

```bash
docker compose down
```

Reset the disposable local database and LocalStack data:

```bash
docker compose down --volumes
```

Use the reset command only when local data can be recreated.

## Validation before sharing the project

Run the same checks used by GitHub Actions:

```bash
.venv/bin/python -m pytest -q
cd frontend && npm ci && npm run lint && npm run build
cd ../infra && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
cd .. && docker build --tag soil-pipeline-api:check .
```

The Python path should be adjusted to the local virtual environment. Do not commit generated frontend output, Terraform state, `.terraform`, or local environment files.

## AWS foundation workflow

The AWS workflow is optional and is not required for the local demo.

1. Sign in with the dedicated Terraform IAM Identity Center permission set.
2. Confirm the active account and role:

   ```bash
   aws sts get-caller-identity --profile soil-pipeline-terraform
   ```

3. Review `infra/terraform.tfvars` locally. Never commit real values or Terraform state.
4. Confirm `enable_pod_identity = false` unless an existing EKS cluster is explicitly in scope.
5. Initialize and review the plan:

   ```bash
   cd infra
   AWS_PROFILE=soil-pipeline-terraform terraform init
   AWS_PROFILE=soil-pipeline-terraform terraform plan
   ```

6. Apply only after reviewing the plan:

   ```bash
   AWS_PROFILE=soil-pipeline-terraform terraform apply
   ```

7. Capture the Cognito outputs for local configuration:

   ```bash
   AWS_PROFILE=soil-pipeline-terraform terraform output
   ```

The current Terraform configuration creates AWS authentication, storage, and IAM foundation resources. It does not create EKS, application compute, a production database, or a public endpoint.

## Cleanup

If the AWS foundation is no longer needed, review the Terraform plan and destroy only the project resources:

```bash
AWS_PROFILE=soil-pipeline-terraform terraform plan -destroy
AWS_PROFILE=soil-pipeline-terraform terraform destroy
```

Before destroying, verify that no important objects remain in the versioned S3 bucket. Terraform may not remove a non-empty bucket automatically.

## Cost and safety checks

- Keep the AWS Budget alert enabled.
- Do not enable EKS Pod Identity unless an existing EKS cluster is part of the test.
- Do not put AWS access keys, Cognito secrets, LocalStack tokens, or session cookies in Git.
- Prefer short-lived IAM Identity Center sessions over long-lived IAM user keys.
- Use a separate sandbox account for experiments.
- Check the AWS Billing dashboard after applying or destroying infrastructure.

## Future live deployment checklist

Before deploying publicly, add and document:

- Container image publishing and immutable tags.
- Managed PostgreSQL/PostGIS and migration execution.
- Secret storage and rotation.
- HTTPS and a custom domain.
- Network controls and least-privilege runtime access.
- GitHub Actions OIDC deployment role.
- Centralized logs, metrics, alerts, and a rollback procedure.

