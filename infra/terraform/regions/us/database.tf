# US Region Database Configuration
# PostgreSQL with CCPA-compliant encryption and backups
# Region: us-east-1 (N. Virginia)

# US Database Subnet Group
resource "aws_db_subnet_group" "us_db_subnet_group" {
  name       = "${var.project_name}-us-db-subnet"
  subnet_ids = aws_subnet.us_database[*].id

  tags = {
    Name        = "${var.project_name}-us-db-subnet-group"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# US PostgreSQL Instance
resource "aws_db_instance" "us_postgres" {
  identifier     = "${var.project_name}-us-postgres"
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.db_instance_class

  # Storage
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.us_db_key.arn

  # Network
  db_subnet_group_name   = aws_db_subnet_group.us_db_subnet_group.name
  vpc_security_group_ids = [aws_security_group.us_db_sg.id]
  publicly_accessible    = false

  # Credentials (should be from Secrets Manager in production)
  username = var.db_username
  password = var.db_password

  # Database
  database_name = var.db_name

  # Backup Configuration (CCPA requirement: backups in US only)
  backup_retention_period = var.db_backup_retention_days
  backup_window          = "03:00-04:00"
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.project_name}-us-postgres-final"

  # Point-in-time recovery
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true

  # Maintenance
  maintenance_window          = "Mon:04:00-Mon:05:00"
  auto_minor_version_upgrade = true

  # Multi-AZ for high availability
  multi_az = var.db_multi_az

  # Deletion protection
  deletion_protection = true

  # Tags for CCPA compliance
  tags = {
    Name        = "${var.project_name}-us-postgres"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
    Encryption  = "AES-256"
    BackupRegion = "us-east-1"
  }
}

# US Read Replica (stays in US only for CCPA compliance)
resource "aws_db_instance" "us_postgres_replica" {
  count                  = var.enable_read_replica ? 1 : 0
  identifier             = "${var.project_name}-us-postgres-replica"
  replicate_source_db    = aws_db_instance.us_postgres.arn
  instance_class         = var.db_instance_class
  vpc_security_group_ids = [aws_security_group.us_db_sg.id]
  publicly_accessible    = false

  # Storage encryption inherited from source
  storage_encrypted = true

  tags = {
    Name        = "${var.project_name}-us-postgres-replica"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
    Type        = "ReadReplica"
  }
}

# US KMS Key for Database Encryption
resource "aws_kms_key" "us_db_key" {
  description             = "KMS key for US database encryption (CCPA compliant)"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-us-db-key"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

resource "aws_kms_alias" "us_db_key_alias" {
  name          = "alias/${var.project_name}-us-db-key"
  target_key_id = aws_kms_key.us_db_key.key_id
}

# US DB Parameter Group (CCPA optimized)
resource "aws_db_parameter_group" "us_postgres_params" {
  family = "postgres15"
  name   = "${var.project_name}-us-postgres-params"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_duration"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }

  parameter {
    name  = "pgaudit.log"
    value = "all"
  }

  tags = {
    Name        = "${var.project_name}-us-postgres-params"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

# US CloudWatch Alarms for Database
resource "aws_cloudwatch_metric_alarm" "us_db_cpu" {
  alarm_name          = "${var.project_name}-us-db-cpu-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "US database CPU utilization > 80%"
  alarm_actions       = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.us_postgres.id
  }

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

resource "aws_cloudwatch_metric_alarm" "us_db_storage" {
  alarm_name          = "${var.project_name}-us-db-storage-alarm"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5000000000  # 5GB
  alarm_description   = "US database free storage < 5GB"
  alarm_actions       = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.us_postgres.id
  }

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

# Outputs
output "us_db_endpoint" {
  description = "US PostgreSQL endpoint"
  value       = aws_db_instance.us_postgres.endpoint
}

output "us_db_name" {
  description = "US database name"
  value       = aws_db_instance.us_postgres.db_name
}

output "us_db_port" {
  description = "US database port"
  value       = aws_db_instance.us_postgres.port
}

output "us_db_arn" {
  description = "US database ARN"
  value       = aws_db_instance.us_postgres.arn
}

output "us_db_kms_key_id" {
  description = "US database KMS key ID"
  value       = aws_kms_key.us_db_key.key_id
}

output "us_db_replica_endpoint" {
  description = "US read replica endpoint"
  value       = var.enable_read_replica ? aws_db_instance.us_postgres_replica[0].endpoint : null
}
