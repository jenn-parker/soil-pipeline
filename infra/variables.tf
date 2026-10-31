variable "aws_region" {
  description = "AWS region for soil-pipeline resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for project resources and IAM names."
  type        = string
  default     = "soil-pipeline"
}

variable "s3_bucket_prefix" {
  description = "Globally unique prefix for the private soil batch archive bucket."
  type        = string
  default     = "soil-pipeline-batches-"
}

variable "cognito_domain_prefix" {
  description = "Globally unique prefix for the Cognito managed-login domain."
  type        = string
}

variable "cognito_callback_urls" {
  description = "Allowed OAuth callback URLs for the Cognito app client."
  type        = list(string)
  default     = ["http://localhost:8000/auth/callback"]
}

variable "cognito_logout_urls" {
  description = "Allowed OAuth logout URLs for the Cognito app client."
  type        = list(string)
  default     = ["http://localhost:8000/"]
}

variable "enable_pod_identity" {
  description = "Whether to create the EKS Pod Identity association."
  type        = bool
  default     = false
}

variable "eks_cluster_name" {
  description = "Existing EKS cluster name used by the optional Pod Identity association."
  type        = string
  default     = null
  nullable    = true
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace for the API service account."
  type        = string
  default     = "default"
}

variable "kubernetes_service_account" {
  description = "Kubernetes service account used by the API workload."
  type        = string
  default     = "soil-pipeline"
}
