output "ecr_repository_url" {
  description = "URL of the ECR repository."
  value       = aws_ecr_repository.service.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.service.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group used by the service."
  value       = aws_cloudwatch_log_group.service.name
}
