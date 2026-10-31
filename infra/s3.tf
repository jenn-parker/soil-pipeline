resource "aws_s3_bucket" "batch_archive" {
  bucket_prefix = var.s3_bucket_prefix

  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
    Purpose   = "soil-batch-archive"
  }
}

resource "aws_s3_bucket_public_access_block" "batch_archive" {
  bucket = aws_s3_bucket.batch_archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "batch_archive" {
  bucket = aws_s3_bucket.batch_archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "batch_archive" {
  bucket = aws_s3_bucket.batch_archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "batch_archive" {
  bucket = aws_s3_bucket.batch_archive.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

data "aws_iam_policy_document" "batch_archive_tls" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.batch_archive.arn,
      "${aws_s3_bucket.batch_archive.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "batch_archive" {
  bucket = aws_s3_bucket.batch_archive.id
  policy = data.aws_iam_policy_document.batch_archive_tls.json
}
