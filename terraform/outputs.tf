output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "github_actions_role_arn" {
  description = "Set as repo Variable AWS_ROLE_ARN for the CD workflow"
  value       = aws_iam_role.github_actions.arn
}

output "app_runner_service_arn" {
  description = "Set as repo Variable APP_RUNNER_SERVICE_ARN for the CD workflow"
  value       = aws_apprunner_service.app.arn
}

output "app_runner_service_url" {
  value = aws_apprunner_service.app.service_url
}
