# BigQuery to Redshift Migration Infrastructure
# Terraform configuration for cross-cloud networking and security

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "datamiq-terraform-state"
    key    = "bq-redshift-migration/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
  }
}

# Variables
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "datamiq-bq-redshift"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "vpc_cidr" {
  description = "CIDR block for AWS VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "gcp_vpc_cidr" {
  description = "CIDR block for GCP VPC"
  type        = string
  default     = "10.1.0.0/16"
}

# Providers
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Outputs
output "aws_vpc_id" {
  description = "AWS VPC ID"
  value       = module.aws_networking.vpc_id
}

output "gcp_vpc_name" {
  description = "GCP VPC name"
  value       = module.gcp_networking.vpc_name
}

output "vpn_tunnel_status" {
  description = "VPN tunnel status"
  value       = module.vpn.tunnel_status
}

output "iam_roles" {
  description = "Created IAM roles"
  value = {
    aws_migration_role = module.iam_roles.aws_migration_role_arn
    gcp_service_account = module.iam_roles.gcp_service_account_email
  }
}

# Modules
module "aws_networking" {
  source = "./modules/aws_networking"
  
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

module "gcp_networking" {
  source = "./modules/gcp_networking"
  
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.gcp_vpc_cidr
  project_id   = var.gcp_project_id
}

module "vpn" {
  source = "./modules/vpn"
  
  project_name    = var.project_name
  environment     = var.environment
  aws_vpc_id      = module.aws_networking.vpc_id
  aws_subnet_id   = module.aws_networking.private_subnet_ids[0]
  gcp_vpc_name    = module.gcp_networking.vpc_name
  gcp_project_id  = var.gcp_project_id
}

module "iam_roles" {
  source = "./modules/iam_roles"
  
  project_name   = var.project_name
  environment    = var.environment
  gcp_project_id = var.gcp_project_id
}

module "security_groups" {
  source = "./modules/security_groups"
  
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.aws_networking.vpc_id
  gcp_vpc_cidr = var.gcp_vpc_cidr
}

module "kms" {
  source = "./modules/kms"
  
  project_name = var.project_name
  environment  = var.environment
}
