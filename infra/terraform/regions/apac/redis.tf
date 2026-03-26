# APAC Region Redis Configuration
# ElastiCache with encryption in APAC only
# Region: ap-southeast-1 (Singapore)

# APAC Redis Subnet Group
resource "aws_elasticache_subnet_group" "apac_redis_subnet_group" {
  name        = "${var.project_name}-apac-redis-subnet"
  description = "Redis subnet group for APAC region"
  subnet_ids  = aws_subnet.apac_database[*].id

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

# APAC Redis Parameter Group
resource "aws_elasticache_parameter_group" "apac_redis_params" {
  family  = "redis7"
  name    = "${var.project_name}-apac-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

# APAC Redis Replication Group (Primary + Replicas)
resource "aws_elasticache_replication_group" "apac_redis" {
  replication_group_id       = "${var.project_name}-apac-redis"
  description               = "APAC Redis cluster for PARWA"
  replication_group_description = "APAC Redis replication group"

  # Node configuration
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_nodes
  port                 = 6379

  # Encryption enabled
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                = aws_kms_key.apac_redis_key.arn

  # Network
  subnet_group_name  = aws_elasticache_subnet_group.apac_redis_subnet_group.name
  security_group_ids = [aws_security_group.apac_redis_sg.id]

  # Parameters
  parameter_group_name = aws_elasticache_parameter_group.apac_redis_params.name

  # Automatic failover
  automatic_failover_enabled = true
  multi_az_enabled          = true

  # Cluster mode (disabled for simplicity, can enable for larger scale)
  cluster_enabled = false

  # Maintenance
  maintenance_window = "sun:04:00-sun:05:00"

  # Snapshot configuration
  snapshot_window            = "02:00-03:00"
  snapshot_retention_limit   = 7

  # Tags for compliance
  tags = {
    Name        = "${var.project_name}-apac-redis"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
    Encryption  = "AES-256"
  }
}

# APAC KMS Key for Redis Encryption
resource "aws_kms_key" "apac_redis_key" {
  description             = "KMS key for APAC Redis encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-apac-redis-key"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

resource "aws_kms_alias" "apac_redis_key_alias" {
  name          = "alias/${var.project_name}-apac-redis-key"
  target_key_id = aws_kms_key.apac_redis_key.key_id
}

# APAC CloudWatch Alarms for Redis
resource "aws_cloudwatch_metric_alarm" "apac_redis_cpu" {
  alarm_name          = "${var.project_name}-apac-redis-cpu-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "APAC Redis CPU utilization > 80%"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-apac-redis"
  }

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

resource "aws_cloudwatch_metric_alarm" "apac_redis_memory" {
  alarm_name          = "${var.project_name}-apac-redis-memory-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeableMemory"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 100000000  # 100MB
  alarm_description   = "APAC Redis freeable memory < 100MB"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-apac-redis"
  }

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

resource "aws_cloudwatch_metric_alarm" "apac_redis_connections" {
  alarm_name          = "${var.project_name}-apac-redis-connections-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 10000
  alarm_description   = "APAC Redis connections > 10000"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-apac-redis"
  }

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

# APAC Redis Event Notification
resource "aws_sns_topic" "apac_redis_notifications" {
  name = "${var.project_name}-apac-redis-notifications"

  tags = {
    Region     = "APAC"
    Compliance = "APAC-DATA-LAWS"
  }
}

# Outputs
output "apac_redis_primary_endpoint" {
  description = "APAC Redis primary endpoint"
  value       = aws_elasticache_replication_group.apac_redis.primary_endpoint_address
}

output "apac_redis_reader_endpoint" {
  description = "APAC Redis reader endpoint"
  value       = aws_elasticache_replication_group.apac_redis.reader_endpoint_address
}

output "apac_redis_port" {
  description = "APAC Redis port"
  value       = aws_elasticache_replication_group.apac_redis.port
}

output "apac_redis_arn" {
  description = "APAC Redis ARN"
  value       = aws_elasticache_replication_group.apac_redis.arn
}

output "apac_redis_kms_key_id" {
  description = "APAC Redis KMS key ID"
  value       = aws_kms_key.apac_redis_key.key_id
}
