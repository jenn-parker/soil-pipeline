#!/bin/bash
set -euo pipefail

bucket="${S3_BATCH_BUCKET:-soil-pipeline-batches}"
awslocal s3api head-bucket --bucket "$bucket" >/dev/null 2>&1 \
  || awslocal s3api create-bucket --bucket "$bucket"
