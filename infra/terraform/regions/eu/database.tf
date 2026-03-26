# EU Region Database Configuration
# PostgreSQL with GDPR-compliant encryption and backups
# Region: eu-west-1 (Ireland)

# EU Database Subnet Group
resource "aws_db_subnet_group" "eu_db_subnet_group" {
  name       = "${var.project_name}-eu-db-subnet"
  subnet_ids = aws_subnet.eu_database[*].id

  tags = {
    Name        = "${var.project_name}-eu-db-subnet-group"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# EU PostgreSQL Instance
resource "aws_db_instance" "eu_postgres" {
  identifier     = "${var.project_name}-eu-postgres"
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.db_instance_class

  # Storage
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.eu_db_key.arn

  # Network
  db_subnet_group_name   = aws_db_subnet_group.eu_db_subnet_group.name
  vpc_security_group_ids = [aws_security_group.eu_db_sg.id]
  publicly_accessible    = false

  # Credentials (should be from Secrets Manager in production)
  username = var.db_username
  password = var.db_password

  # Database
  database_name = var.db_name

  # Backup Configuration (GDPR requirement: backups in EU only)
  backup_retention_period = var.db_backup_retention_days
  backup_window          = "03:00-04:00"
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.project_name}-eu-postgres-final"

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

  # Tags for GDPR compliance
  tags = {
    Name        = "${var.project_name}-eu-postgres"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
    Encryption  = "AES-256"
    BackupRegion = "eu-west-1"
  }
}

# EU Read Replica (stays in EU only for GDPR compliance)
resource "aws_db_instance" "eu_postgres_replica" {
  count                  = var.enable_read_replica ? 1 : 0
  identifier             = "${var.project_name}-eu-postgres-replica"
  replicate_source_db    = aws_db_instance.eu_postgres.arn
  instance_class         = var.db_instance_class
  vpc_security_group_ids = [aws_security_group.eu_db_sg.id]
  publicly_accessible    = false

  # Storage encryption inherited from source
  storage_encrypted = true

  tags = {
    Name        = "${var.project_name}-eu-postgres-replica"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
    Type        = "ReadReplica"
  }
}

# EU KMS Key for Database Encryption
resource "aws_kms_key" "eu_db_key" {
  description             = "KMS key for EU database encryption (GDPR compliant)"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-eu-db-key"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

resource "aws_kms_alias" "eu_db_key_alias" {
  name          = "alias/${var.project_name}-eu-db-key"
  target_key_id = aws_kms_key.eu_db_key.key_id
}

# EU DB Parameter Group (GDPR optimized)
resource "aws_db_parameter_group" "eu_postgres_params" {
  family = "postgres15"
  name   = "${var.project_name}-eu-postgres-params"

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
    Name        = "${var.project_name}-eu-postgres-params"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

# EU CloudWatch Alarms for Database
resource "aws_cloudwatch_metric_alarm" "eu_db_cpu" {
  alarm_name          = "${var.project_name}-eu-db-cpu-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EU database CPU utilization > 80%"
  alarm_actions       = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.eu_postgres.id
  }

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

resource "aws_cloudwatch_metric_alarm" "eu_db_storage" {
  alarm_name          = "${var.project_name}-eu-db-storage-alarm"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5000000000  # 5GB
  alarm_description   = "EU database free storage < 5GB"
  alarm_actions       = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.eu_postgres.id
  }

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

# Outputs
output "eu_db_endpoint" {
  description = "EU PostgreSQL endpoint"
  value       = aws_db_instance.eu_postgres.endpoint
}

output "eu_db_name" {
  description = "EU database name"
  value       = aws_db_instance.eu_postgres.db_name
}

output "eu_db_port" {
  description = "EU database port"
  value       = aws_db_instance.eu_postgres.port
}

output "eu_db_arn" {
  description = "EU database ARN"
  value       = aws_db_instance.eu_postgres.arn
}

output "eu_db_kms_key_id" {
  description = "EU database KMS key ID"
  value       = aws_kms_key.eu_db_key.key_id
}

output "eu_db_replica_endpoint" {
  description = "EU read replica endpoint"
  value       = var.enable_read_replica ? aws_db_instance.eu_postgres_replica[0].endpoint : null
}
