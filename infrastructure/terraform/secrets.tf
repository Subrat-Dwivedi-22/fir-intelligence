# -----------------------------------------------------------------------------
# SSM Parameter Store
#
# Values are intentionally supplied outside Terraform.
# Terraform creates the parameter names, but does not contain the secrets.
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "mongodb_uri" {
  name = "/fir-intelligence/MONGODB_URI"
  type = "SecureString"

  # Placeholder only. We will replace this manually after infrastructure exists.
  value = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "fir-intelligence-mongodb-uri"
  }
}

resource "aws_ssm_parameter" "person_id_hmac_secret" {
  name = "/fir-intelligence/PERSON_ID_HMAC_SECRET"
  type = "SecureString"

  value = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "fir-intelligence-person-id-secret"
  }
}

resource "aws_ssm_parameter" "gemini_api_key" {
  name = "/fir-intelligence/GEMINI_API_KEY"
  type = "SecureString"

  value = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "fir-intelligence-gemini-api-key"
  }
}