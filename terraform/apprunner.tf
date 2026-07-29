resource "aws_apprunner_service" "app" {
  service_name = "${var.project_name}-${var.environment}"

  source_configuration {
    # Deploys happen via `aws apprunner start-deployment` from the CD
    # workflow after CI passes — not automatically on every ECR push.
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    image_repository {
      image_repository_type = "ECR"
      image_identifier      = "${aws_ecr_repository.app.repository_url}:latest"

      image_configuration {
        port = "8501"

        runtime_environment_variables = {
          AWS_DEFAULT_REGION   = var.aws_region
          BEDROCK_LLM_MODEL    = var.bedrock_llm_model
          BEDROCK_EMBED_MODEL  = var.bedrock_embed_model
          PINECONE_INDEX_NAME  = var.pinecone_index_name
          PINECONE_ENVIRONMENT = var.pinecone_environment
        }

        runtime_environment_secrets = {
          PINECONE_API_KEY = "${aws_secretsmanager_secret.app_env.arn}:PINECONE_API_KEY::"
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.app_runner_cpu
    memory            = var.app_runner_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/_stcore/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
