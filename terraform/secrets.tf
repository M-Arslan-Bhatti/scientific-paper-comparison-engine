# Only genuinely secret values live here (Pinecone API key). AWS credentials
# are intentionally NOT stored anywhere — the App Runner instance role
# (bedrock_iam.tf) supplies Bedrock access via boto3's default credential
# chain instead of static keys.
resource "aws_secretsmanager_secret" "app_env" {
  name = "${var.project_name}/${var.environment}/app-env"
}

resource "aws_secretsmanager_secret_version" "app_env" {
  secret_id = aws_secretsmanager_secret.app_env.id
  secret_string = jsonencode({
    PINECONE_API_KEY = var.pinecone_api_key
  })
}
