terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
provider "aws" {
  region = var.aws_region
}
variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "bucket_name" {
  type        = string
  description = "Globally unique private backup bucket name."
}
variable "retention_days" {
  type    = number
  default = 30
  validation {
    condition     = var.retention_days >= 7 && floor(var.retention_days) == var.retention_days
    error_message = "Keep backups for at least seven whole days."
  }
}
resource "aws_s3_bucket" "backups" {
  bucket        = var.bucket_name
  force_destroy = false
  tags          = { Project = "cloud-health-recovery", ManagedBy = "Terraform" }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.backups.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.backups.arn, "${aws_s3_bucket.backups.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}
resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket     = aws_s3_bucket.backups.id
  depends_on = [aws_s3_bucket_versioning.backups]
  rule {
    id     = "recovery-retention"
    status = "Enabled"
    filter {
      prefix = "recovery/"
    }
    expiration {
      days = var.retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = 7
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
  rule {
    id     = "expired-markers"
    status = "Enabled"
    filter {
      prefix = "recovery/"
    }
    expiration {
      expired_object_delete_marker = true
    }
  }
}
output "bucket_name" {
  value = aws_s3_bucket.backups.id
}
# These are reviewable policy documents, not attached permissions or new identities.
output "writer_policy" {
  value = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["s3:PutObject"]
      Resource = "${aws_s3_bucket.backups.arn}/recovery/*"
    }]
  })
}
output "reader_policy" {
  value = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.backups.arn,
      Condition = { StringLike = { "s3:prefix" = ["recovery/*"] } } },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.backups.arn}/recovery/*" }
    ]
  })
}
