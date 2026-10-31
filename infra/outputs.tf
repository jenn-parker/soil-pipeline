output "aws_account_id" {
  description = "AWS account used by this Terraform configuration."
  value       = data.aws_caller_identity.current.account_id
}

output "batch_archive_bucket_name" {
  description = "Private S3 bucket used to archive uploaded CSV batches."
  value       = aws_s3_bucket.batch_archive.bucket
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for application authentication."
  value       = aws_cognito_user_pool.soil_pipeline.id
}

output "cognito_issuer" {
  description = "Cognito issuer URL used to validate access tokens."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.soil_pipeline.id}"
}

output "cognito_app_client_id" {
  description = "Public Cognito app client ID for the web application."
  value       = aws_cognito_user_pool_client.soil_pipeline.id
}

output "cognito_login_domain" {
  description = "Cognito managed-login domain."
  value       = "https://${var.cognito_domain_prefix}.auth.${var.aws_region}.amazoncognito.com"
}

output "api_role_arn" {
  description = "IAM role intended for the soil-pipeline API workload."
  value       = aws_iam_role.api.arn
}

output "terraform_deployer_policy_arn" {
  description = "Attach this customer-managed policy to the SoilPipelineTerraform permission set."
  value       = aws_iam_policy.terraform_deployer.arn
}
