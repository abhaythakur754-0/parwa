# APAC Region Variables
# Region: ap-southeast-1 (Singapore)
# Compliance: Asian Data Laws

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
  description = "AWS region for APAC deployment"
  type        = string
  default     = "ap-southeast-1"
}

# VPC Variables
variable "vpc_cidr" {
  description = "CIDR block for APAC VPC"
  type        = string
  default     = "10.3.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for APAC public subnets"
  type        = list(string)
  default     = ["10.3.1.0/24", "10.3.2.0/24", "10.3.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for APAC private subnets"
  type        = list(string)
  default     = ["10.3.11.0/24", "10.3.12.0/24", "10.3.13.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for APAC database subnets"
  type        = list(string)
  default     = ["10.3.21.0/24", "10.3.22.0/24", "10.3.23.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT gateway for APAC VPC"
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
  default     = "parwa_apac"
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
  description = "Enable read replica (in APAC only)"
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
  description = "Data retention period for compliance"
  type        = number
  default     = 90
}

variable "enable_audit_logging" {
  description = "Enable audit logging for compliance"
  type        = bool
  default     = true
}

# Validation
variable "allowed_regions" {
  description = "Allowed regions for APAC data"
  type        = list(string)
  default     = ["ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2"]
}

# Variable Validation
variable "backup_region" {
  description = "Backup region (must be in APAC)"
  type        = string
  default     = "ap-southeast-1"

  validation {
    condition     = contains(["ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2"], var.backup_region)
    error_message = "Backup region must be in APAC for data compliance."
  }
}

# Tags
variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project    = "PARWA"
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
    ManagedBy  = "Terraform"
  }
}
