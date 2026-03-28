# Cost Estimation Terraform Configuration
# Provides cost estimates for infrastructure resources
# Uses Terraform cost estimation features

# Provider configuration with cost estimation tags
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "PARWA"
      Environment = var.environment
      CostCenter  = var.cost_center
      ManagedBy   = "Terraform"
    }
  }
}

# Variables for cost tracking
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "cost_center" {
  description = "Cost center for billing"
  type        = string
  default     = "parwa-platform"
}

# Budget configuration
resource "aws_budgets_budget" "parwa_monthly" {
  name              = "parwa-monthly-budget"
  budget_type       = "COST"
  limit_amount      = "5000"
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["finance@parwa.com"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["finance@parwa.com", "ops@parwa.com"]
  }

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_support            = true
    include_tax                = true
    include_upfront            = true
    usage                     = true
  }
}

# Budget for EC2 compute costs
resource "aws_budgets_budget" "parwa_compute" {
  name              = "parwa-compute-budget"
  budget_type       = "COST"
  limit_amount      = "2000"
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  cost_filter {
    name = "Service"
    values = ["Amazon Elastic Compute Cloud - Compute"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 90
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["ops@parwa.com"]
  }
}

# Budget for RDS database costs
resource "aws_budgets_budget" "parwa_database" {
  name              = "parwa-database-budget"
  budget_type       = "COST"
  limit_amount      = "1500"
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  cost_filter {
    name = "Service"
    values = ["Amazon Relational Database Service"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 90
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["ops@parwa.com"]
  }
}

# Cost allocation tags
resource "aws_ce_cost_allocation_tag" "parwa_project" {
  tag_key = "Project"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "parwa_environment" {
  tag_key = "Environment"
  status  = "Active"
}

# Cost anomaly detection
resource "aws_ce_anomaly_monitor" "parwa_total_cost" {
  name              = "PARWA Total Cost Monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"

  specification_value = jsonencode({
    Dimension = "SERVICE"
    MatchOptions = ["EQUALS"]
    Values = ["Amazon Elastic Compute Cloud - Compute", "Amazon Relational Database Service"]
  })
}

# Anomaly subscription for alerts
resource "aws_ce_anomaly_subscription" "parwa_anomaly_alert" {
  name      = "PARWA Cost Anomaly Alert"
  frequency = "IMMEDIATE"

  monitor_arn_list = [
    aws_ce_anomaly_monitor.parwa_total_cost.arn
  ]

  subscriber {
    type    = "EMAIL"
    address = "finance@parwa.com"
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["100"]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}

# Outputs for cost tracking
output "monthly_budget_id" {
  description = "Monthly budget ID"
  value       = aws_budgets_budget.parwa_monthly.id
}

output "compute_budget_id" {
  description = "Compute budget ID"
  value       = aws_budgets_budget.parwa_compute.id
}

output "database_budget_id" {
  description = "Database budget ID"
  value       = aws_budgets_budget.parwa_database.id
}

output "cost_tags" {
  description = "Cost allocation tags"
  value = {
    Project     = "PARWA"
    Environment = var.environment
    CostCenter  = var.cost_center
  }
}
