# US Region Variables
# Region: us-east-1 (N. Virginia)
# Compliance: CCPA

# Project Variables
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "parwa"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region for US deployment"
  type        = string
  default     = "us-east-1"
}

# VPC Variables
variable "vpc_cidr" {
  description = "CIDR block for US VPC"
  type        = string
  default     = "10.2.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for US public subnets"
  type        = list(string)
  default     = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for US private subnets"
  type        = list(string)
  default     = ["10.2.11.0/24", "10.2.12.0/24", "10.2.13.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for US database subnets"
  type        = list(string)
  default     = ["10.2.21.0/24", "10.2.22.0/24", "10.2.23.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT gateway for US VPC"
  type        = bool
  default     = true
}

# Database Variables
variable "postgres_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "db_instance_class" {
  description = "Database instance class"
  type        = string
  default     = "db.r6g.xlarge"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage in GB"
  type        = number
  default     = 500
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "parwa_admin"
  sensitive   = true
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "parwa_us"
}

variable "db_backup_retention_days" {
  description = "Backup retention period in days"
  type        = number
  default     = 35
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for database"
  type        = bool
  default     = true
}

variable "enable_read_replica" {
  description = "Enable read replica (in US only for CCPA)"
  type        = bool
  default     = true
}

# Redis Variables
variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_num_nodes" {
  description = "Number of Redis cache clusters"
  type        = number
  default     = 2
}

# Compliance Variables
variable "data_retention_days" {
  description = "Data retention period for CCPA compliance"
  type        = number
  default     = 90
}

variable "enable_audit_logging" {
  description = "Enable audit logging for CCPA compliance"
  type        = bool
  default     = true
}

# Validation
variable "allowed_regions" {
  description = "Allowed regions for US data (CCPA compliance)"
  type        = list(string)
  default     = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]
}

# Variable Validation
variable "backup_region" {
  description = "Backup region (must be in US for CCPA)"
  type        = string
  default     = "us-east-1"

  validation {
    condition     = contains(["us-east-1", "us-east-2", "us-west-1", "us-west-2"], var.backup_region)
    error_message = "Backup region must be in US for CCPA compliance."
  }
}

# Tags
variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project    = "PARWA"
    Region     = "US"
    Compliance = "CCPA"
    ManagedBy  = "Terraform"
  }
}
