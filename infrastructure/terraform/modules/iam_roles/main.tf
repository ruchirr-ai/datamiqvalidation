# IAM Roles Module - Cross-Cloud Authentication
# Creates IAM roles and service accounts for secure cross-cloud access

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "gcp_project_id" {
  type = string
}

# AWS IAM Role for Migration Service
resource "aws_iam_role" "migration_service" {
  name = "${var.project_name}-${var.environment}-migration-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "ec2.amazonaws.com",
            "ecs-tasks.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
      }
    ]
  })
  
  tags = {
    Name = "${var.project_name}-${var.environment}-migration-role"
  }
}

# AWS IAM Policy for S3 Access
resource "aws_iam_policy" "s3_access" {
  name        = "${var.project_name}-${var.environment}-s3-access"
  description = "S3 access for migration data"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-${var.environment}-migration-*",
          "arn:aws:s3:::${var.project_name}-${var.environment}-migration-*/*"
        ]
      }
    ]
  })
}

# AWS IAM Policy for Redshift Access
resource "aws_iam_policy" "redshift_access" {
  name        = "${var.project_name}-${var.environment}-redshift-access"
  description = "Redshift access for data loading"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "redshift:DescribeClusters",
          "redshift:GetClusterCredentials",
          "redshift-data:ExecuteStatement",
          "redshift-data:DescribeStatement",
          "redshift-data:GetStatementResult"
        ]
        Resource = "*"
      }
    ]
  })
}

# AWS IAM Policy for DMS Access (Path B)
resource "aws_iam_policy" "dms_access" {
  name        = "${var.project_name}-${var.environment}-dms-access"
  description = "DMS access for migration"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dms:CreateReplicationInstance",
          "dms:CreateEndpoint",
          "dms:CreateReplicationTask",
          "dms:StartReplicationTask",
          "dms:StopReplicationTask",
          "dms:DescribeReplicationTasks",
          "dms:DescribeReplicationInstances",
          "dms:DescribeEndpoints"
        ]
        Resource = "*"
      }
    ]
  })
}

# AWS IAM Policy for DataSync Access (Path C)
resource "aws_iam_policy" "datasync_access" {
  name        = "${var.project_name}-${var.environment}-datasync-access"
  description = "DataSync access for cross-cloud transfer"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "datasync:CreateLocation*",
          "datasync:CreateTask",
          "datasync:StartTaskExecution",
          "datasync:DescribeTask*",
          "datasync:ListTasks"
        ]
        Resource = "*"
      }
    ]
  })
}

# AWS IAM Policy for KMS Access
resource "aws_iam_policy" "kms_access" {
  name        = "${var.project_name}-${var.environment}-kms-access"
  description = "KMS access for encryption"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

# AWS IAM Policy for Secrets Manager Access
resource "aws_iam_policy" "secrets_access" {
  name        = "${var.project_name}-${var.environment}-secrets-access"
  description = "Secrets Manager access for credentials"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.project_name}/${var.environment}/*"
      }
    ]
  })
}

# Attach policies to role
resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.migration_service.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_role_policy_attachment" "redshift_access" {
  role       = aws_iam_role.migration_service.name
  policy_arn = aws_iam_policy.redshift_access.arn
}

resource "aws_iam_role_policy_attachment" "dms_access" {
  role       = aws_iam_role.migration_service.name
  policy_arn = aws_iam_policy.dms_access.arn
}

resource "aws_iam_role_policy_attachment" "datasync_access" {
  role       = aws_iam_role.migration_service.name
  policy_arn = aws_iam_policy.datasync_access.arn
}

resource "aws_iam_role_policy_attachment" "kms_access" {
  role       = aws_iam_role.migration_service.name
  policy_arn = aws_iam_policy.kms_access.arn
}

resource "aws_iam_role_policy_attachment" "secrets_access" {
  role       = aws_iam_role.migration_service.name
  policy_arn = aws_iam_policy.secrets_access.arn
}

# GCP Service Account for Migration
resource "google_service_account" "migration_service" {
  account_id   = "${var.project_name}-${var.environment}-migration"
  display_name = "Migration Service Account"
  description  = "Service account for BigQuery to Redshift migrations"
  project      = var.gcp_project_id
}

# GCP IAM Roles for BigQuery Access
resource "google_project_iam_member" "bigquery_data_viewer" {
  project = var.gcp_project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.migration_service.email}"
}

resource "google_project_iam_member" "bigquery_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.migration_service.email}"
}

# GCP IAM Roles for GCS Access
resource "google_project_iam_member" "storage_object_admin" {
  project = var.gcp_project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.migration_service.email}"
}

# GCP IAM Roles for Storage Transfer Service (Path A)
resource "google_project_iam_member" "storage_transfer_admin" {
  project = var.gcp_project_id
  role    = "roles/storagetransfer.admin"
  member  = "serviceAccount:${google_service_account.migration_service.email}"
}

# Create service account key
resource "google_service_account_key" "migration_key" {
  service_account_id = google_service_account.migration_service.name
}

# Store GCP service account key in AWS Secrets Manager
resource "aws_secretsmanager_secret" "gcp_service_account_key" {
  name        = "${var.project_name}/${var.environment}/gcp-service-account-key"
  description = "GCP service account key for cross-cloud authentication"
  
  tags = {
    Name = "${var.project_name}-${var.environment}-gcp-key"
  }
}

resource "aws_secretsmanager_secret_version" "gcp_service_account_key" {
  secret_id     = aws_secretsmanager_secret.gcp_service_account_key.id
  secret_string = base64decode(google_service_account_key.migration_key.private_key)
}

# Outputs
output "aws_migration_role_arn" {
  description = "AWS IAM role ARN for migration service"
  value       = aws_iam_role.migration_service.arn
}

output "gcp_service_account_email" {
  description = "GCP service account email"
  value       = google_service_account.migration_service.email
}

output "gcp_service_account_key_secret_arn" {
  description = "AWS Secrets Manager ARN for GCP service account key"
  value       = aws_secretsmanager_secret.gcp_service_account_key.arn
  sensitive   = true
}
