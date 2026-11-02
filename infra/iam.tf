data "aws_partition" "current" {}

data "aws_iam_policy_document" "api_pod_identity_trust" {
  statement {
    sid    = "AllowEksPodIdentity"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }

    actions = [
      "sts:AssumeRole",
      "sts:TagSession",
    ]
  }
}

data "aws_iam_policy_document" "api_s3_access" {
  statement {
    sid       = "ListBatchArchiveObjects"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.batch_archive.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["soil-batches/*"]
    }
  }

  statement {
    sid     = "ArchiveBatchObjects"
    effect  = "Allow"
    actions = ["s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${aws_s3_bucket.batch_archive.arn}/soil-batches/*",
    ]
  }
}

data "aws_iam_policy_document" "api_runtime_boundary" {
  statement {
    sid       = "ListBatchArchiveObjects"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.batch_archive.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["soil-batches/*"]
    }
  }

  statement {
    sid     = "AllowBatchArchiveOnly"
    effect  = "Allow"
    actions = ["s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${aws_s3_bucket.batch_archive.arn}/soil-batches/*",
    ]
  }
}

resource "aws_iam_policy" "api_runtime_boundary" {
  name        = "${var.project_name}-api-runtime-boundary"
  description = "Maximum permissions for the soil-pipeline API workload role."
  policy      = data.aws_iam_policy_document.api_runtime_boundary.json
}

resource "aws_iam_role" "api" {
  name                 = "${var.project_name}-api"
  assume_role_policy   = data.aws_iam_policy_document.api_pod_identity_trust.json
  permissions_boundary = aws_iam_policy.api_runtime_boundary.arn

  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
  }
}

resource "aws_iam_policy" "api_s3_access" {
  name        = "${var.project_name}-api-s3"
  description = "Allows the soil-pipeline API to archive accepted batch files."
  policy      = data.aws_iam_policy_document.api_s3_access.json
}

resource "aws_iam_role_policy_attachment" "api_s3_access" {
  role       = aws_iam_role.api.name
  policy_arn = aws_iam_policy.api_s3_access.arn
}

data "aws_iam_policy_document" "terraform_deployer" {
  statement {
    sid    = "ManageProjectCognito"
    effect = "Allow"
    actions = [
      "cognito-idp:CreateResourceServer",
      "cognito-idp:CreateUserPool",
      "cognito-idp:CreateUserPoolClient",
      "cognito-idp:CreateUserPoolDomain",
      "cognito-idp:DeleteResourceServer",
      "cognito-idp:DeleteUserPool",
      "cognito-idp:DeleteUserPoolClient",
      "cognito-idp:DeleteUserPoolDomain",
      "cognito-idp:DescribeResourceServer",
      "cognito-idp:DescribeUserPool",
      "cognito-idp:DescribeUserPoolClient",
      "cognito-idp:DescribeUserPoolDomain",
      "cognito-idp:GetUserPoolMfaConfig",
      "cognito-idp:ListTagsForResource",
      "cognito-idp:ListUserPools",
      "cognito-idp:ListUserPoolClients",
      "cognito-idp:TagResource",
      "cognito-idp:UntagResource",
      "cognito-idp:UpdateResourceServer",
      "cognito-idp:UpdateUserPool",
      "cognito-idp:UpdateUserPoolClient",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ManageProjectS3"
    effect = "Allow"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:DeleteBucketPolicy",
      "s3:GetBucket*",
      "s3:GetAccelerateConfiguration",
      "s3:GetAnalyticsConfiguration",
      "s3:GetEncryptionConfiguration",
      "s3:GetIntelligentTieringConfiguration",
      "s3:GetInventoryConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:GetMetricsConfiguration",
      "s3:GetPublicAccessBlock",
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
      "s3:PutBucketPolicy",
      "s3:PutBucketTagging",
      "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration",
      "s3:PutPublicAccessBlock",
    ]
    resources = [aws_s3_bucket.batch_archive.arn]
  }

  statement {
    sid       = "ListS3Buckets"
    effect    = "Allow"
    actions   = ["s3:ListAllMyBuckets"]
    resources = ["*"]
  }

  statement {
    sid    = "ManageProjectIam"
    effect = "Allow"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreatePolicy",
      "iam:CreatePolicyVersion",
      "iam:CreateRole",
      "iam:DeletePolicy",
      "iam:DeletePolicyVersion",
      "iam:DeleteRole",
      "iam:DeleteRolePermissionsBoundary",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:GetRole",
      "iam:ListAttachedRolePolicies",
      "iam:ListPolicyVersions",
      "iam:ListRolePolicies",
      "iam:PutRolePermissionsBoundary",
      "iam:PutRolePolicy",
      "iam:TagPolicy",
      "iam:TagRole",
      "iam:UntagPolicy",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-*",
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/${var.project_name}-*",
    ]
  }

  statement {
    sid       = "PassProjectApiRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.api.arn]
  }

  statement {
    sid    = "ManageProjectPodIdentity"
    effect = "Allow"
    actions = [
      "eks:CreatePodIdentityAssociation",
      "eks:DeletePodIdentityAssociation",
      "eks:DescribeCluster",
      "eks:DescribePodIdentityAssociation",
      "eks:ListPodIdentityAssociations",
      "eks:TagResource",
      "eks:UntagResource",
      "eks:UpdatePodIdentityAssociation",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "IdentifyCaller"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "terraform_deployer" {
  name        = "${var.project_name}-deployer"
  description = "Terraform deployment permissions for the soil-pipeline sandbox."
  policy      = data.aws_iam_policy_document.terraform_deployer.json
}

resource "aws_eks_pod_identity_association" "api" {
  count = var.enable_pod_identity ? 1 : 0

  cluster_name    = var.eks_cluster_name
  namespace       = var.kubernetes_namespace
  service_account = var.kubernetes_service_account
  role_arn        = aws_iam_role.api.arn
}
