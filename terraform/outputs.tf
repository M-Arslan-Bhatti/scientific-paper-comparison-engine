output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "github_actions_role_arn" {
  description = "Set as repo Variable AWS_ROLE_ARN for the CD workflow"
  value       = aws_iam_role.github_actions.arn
}

output "ecs_cluster_name" {
  description = "Set as repo Variable ECS_CLUSTER for the CD workflow"
  value       = aws_ecs_cluster.app.name
}

output "ecs_service_name" {
  description = "Set as repo Variable ECS_SERVICE for the CD workflow"
  value       = aws_ecs_service.app.name
}

output "ecs_task_family" {
  description = "Set as repo Variable ECS_TASK_FAMILY for the CD workflow"
  value       = aws_ecs_task_definition.app.family
}

output "ecs_execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}

output "app_url" {
  description = "Public URL of the deployed app (once a task is running and healthy)"
  value       = "http://${aws_lb.app.dns_name}"
}
