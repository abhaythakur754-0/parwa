# APAC Region Database Configuration
# PostgreSQL with encryption and backups in APAC only
# Region: ap-southeast-1 (Singapore)

# APAC Database Subnet Group
resource "aws_db_subnet_group" "apac_db_subnet_group" {
  name       = "${var.project_name}-apac-db-subnet"
  subnet_ids = aws_subnet.apac_database[*].id

  tags = {
    Name        = "${var.project_name}-apac-db-subnet-group"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# APAC PostgreSQL Instance
resource "aws_db_instance" "apac_postgres" {
  identifier     = "${var.project_name}-apac-postgres"
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.db_instance_class

  # Storage
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.apac_db_key.arn

  # Network
  db_subnet_group_name   = aws_db_subnet_group.apac_db_subnet_group.name
  vpc_security_group_ids = [aws_security_group.apac_db_sg.id]
  publicly_accessible    = false

  # Credentials (should be from Secrets Manager in production)
  username = var.db_username
  password = var.db_password

  # Database
  database_name = var.db_name

  # Backup Configuration (backups in APAC only)
  backup_retention_period = var.db_backup_retention_days
  backup_window          = "03:00-04:00"
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.project_name}-apac-postgres-final"

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

  # Tags for compliance
  tags = {
    Name        = "${var.project_name}-apac-postgres"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
    Encryption  = "AES-256"
    BackupRegion = "ap-southeast-1"
  }
}

# APAC Read Replica (stays in APAC only)
resource "aws_db_instance" "apac_postgres_replica" {
  count                  = var.enable_read_replica ? 1 : 0
  identifier             = "${var.project_name}-apac-postgres-replica"
  replicate_source_db    = aws_db_instance.apac_postgres.arn
  instance_class         = var.db_instance_class
  vpc_security_group_ids = [aws_security_group.apac_db_sg.id]
  publicly_accessible    = false

  # Storage encryption inherited from source
  storage_encrypted = true

  tags = {
    Name        = "${var.project_name}-apac-postgres-replica"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
    Type        = "ReadReplica"
  }
}

# APAC KMS Key for Database Encryption
resource "aws_kms_key" "apac_db_key" {
  description             = "KMS key for APAC database encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-apac-db-key"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

resource "aws_kms_alias" "apac_db_key_alias" {
  name          = "alias/${var.project_name}-apac-db-key"
  target_key_id = aws_kms_key.apac_db_key.key_id
}

# APAC DB Parameter Group
resource "aws_db_parameter_group" "apac_postgres_params" {
  family = "postgres15"
  name   = "${var.project_name}-apac-postgres-params"

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
    Name        = "${var.project_name}-apac-postgres-params"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

# APAC CloudWatch Alarms for Database
resource "aws_cloudwatch_metric_alarm" "apac_db_cpu" {
  alarm_name          = "${var.project_name}-apac-db-cpu-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "APAC database CPU utilization > 80%"
  alarm_actions       = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.apac_postgres.id
  }

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

resource "aws_cloudwatch_metric_alarm" "apac_db_storage" {
  alarm_name          = "${var.project_name}-apac-db-storage-alarm"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5000000000  # 5GB
  alarm_description   = "APAC database free storage < 5GB"
  alarm_actions       = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.apac_postgres.id
  }

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

# Outputs
output "apac_db_endpoint" {
  description = "APAC PostgreSQL endpoint"
  value       = aws_db_instance.apac_postgres.endpoint
}

output "apac_db_name" {
  description = "APAC database name"
  value       = aws_db_instance.apac_postgres.db_name
}

output "apac_db_port" {
  description = "APAC database port"
  value       = aws_db_instance.apac_postgres.port
}

output "apac_db_arn" {
  description = "APAC database ARN"
  value       = aws_db_instance.apac_postgres.arn
}

output "apac_db_kms_key_id" {
  description = "APAC database KMS key ID"
  value       = aws_kms_key.apac_db_key.key_id
}

output "apac_db_replica_endpoint" {
  description = "APAC read replica endpoint"
  value       = var.enable_read_replica ? aws_db_instance.apac_postgres_replica[0].endpoint : null
}
