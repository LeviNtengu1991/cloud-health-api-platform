variable "aws_region" {
  description = "AWS region used for the portfolio infrastructure."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Base name for provisioned resources."
  type        = string
  default     = "cloud-health-api"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "Environment must be dev, stage, or prod."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 14
}
