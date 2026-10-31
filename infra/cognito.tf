resource "aws_cognito_user_pool" "soil_pipeline" {
  name                = "${var.project_name}-users"
  username_attributes = ["email"]

  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = true
  }

  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
  }
}

resource "aws_cognito_user_pool_domain" "soil_pipeline" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.soil_pipeline.id
}

resource "aws_cognito_resource_server" "soil_pipeline" {
  identifier   = "https://soil-pipeline.local"
  name         = var.project_name
  user_pool_id = aws_cognito_user_pool.soil_pipeline.id

  scope {
    scope_name        = "soil:read"
    scope_description = "Read soil samples, reports, and map data."
  }

  scope {
    scope_name        = "soil:write"
    scope_description = "Create soil samples, parties, and provenance records."
  }

  scope {
    scope_name        = "batch:upload"
    scope_description = "Upload soil sample CSV batches."
  }
}

resource "aws_cognito_user_pool_client" "soil_pipeline" {
  name         = "${var.project_name}-web"
  user_pool_id = aws_cognito_user_pool.soil_pipeline.id

  generate_secret = false

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes = [
    "openid",
    "email",
    "${aws_cognito_resource_server.soil_pipeline.identifier}/soil:read",
    "${aws_cognito_resource_server.soil_pipeline.identifier}/soil:write",
    "${aws_cognito_resource_server.soil_pipeline.identifier}/batch:upload",
  ]
  callback_urls                = var.cognito_callback_urls
  logout_urls                  = var.cognito_logout_urls
  supported_identity_providers = ["COGNITO"]

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
