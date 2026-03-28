# US Region Redis Configuration
# ElastiCache with CCPA-compliant encryption
# Region: us-east-1 (N. Virginia)

# US Redis Subnet Group
resource "aws_elasticache_subnet_group" "us_redis_subnet_group" {
  name        = "${var.project_name}-us-redis-subnet"
  description = "Redis subnet group for US region"
  subnet_ids  = aws_subnet.us_database[*].id

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

# US Redis Parameter Group
resource "aws_elasticache_parameter_group" "us_redis_params" {
  family  = "redis7"
  name    = "${var.project_name}-us-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

# US Redis Replication Group (Primary + Replicas)
resource "aws_elasticache_replication_group" "us_redis" {
  replication_group_id       = "${var.project_name}-us-redis"
  description               = "US Redis cluster for PARWA (CCPA compliant)"
  replication_group_description = "US Redis replication group - CCPA compliant"

  # Node configuration
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_nodes
  port                 = 6379

  # Encryption (CCPA requirement)
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                = aws_kms_key.us_redis_key.arn

  # Network
  subnet_group_name  = aws_elasticache_subnet_group.us_redis_subnet_group.name
  security_group_ids = [aws_security_group.us_redis_sg.id]

  # Parameters
  parameter_group_name = aws_elasticache_parameter_group.us_redis_params.name

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

  # Tags for CCPA compliance
  tags = {
    Name        = "${var.project_name}-us-redis"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
    Encryption  = "AES-256"
  }
}

# US KMS Key for Redis Encryption
resource "aws_kms_key" "us_redis_key" {
  description             = "KMS key for US Redis encryption (CCPA compliant)"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-us-redis-key"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

resource "aws_kms_alias" "us_redis_key_alias" {
  name          = "alias/${var.project_name}-us-redis-key"
  target_key_id = aws_kms_key.us_redis_key.key_id
}

# US CloudWatch Alarms for Redis
resource "aws_cloudwatch_metric_alarm" "us_redis_cpu" {
  alarm_name          = "${var.project_name}-us-redis-cpu-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "US Redis CPU utilization > 80%"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-us-redis"
  }

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

resource "aws_cloudwatch_metric_alarm" "us_redis_memory" {
  alarm_name          = "${var.project_name}-us-redis-memory-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeableMemory"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 100000000  # 100MB
  alarm_description   = "US Redis freeable memory < 100MB"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-us-redis"
  }

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

resource "aws_cloudwatch_metric_alarm" "us_redis_connections" {
  alarm_name          = "${var.project_name}-us-redis-connections-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 10000
  alarm_description   = "US Redis connections > 10000"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-us-redis"
  }

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

# US Redis Event Notification
resource "aws_sns_topic" "us_redis_notifications" {
  name = "${var.project_name}-us-redis-notifications"

  tags = {
    Region     = "US"
    Compliance = "CCPA"
  }
}

# Outputs
output "us_redis_primary_endpoint" {
  description = "US Redis primary endpoint"
  value       = aws_elasticache_replication_group.us_redis.primary_endpoint_address
}

output "us_redis_reader_endpoint" {
  description = "US Redis reader endpoint"
  value       = aws_elasticache_replication_group.us_redis.reader_endpoint_address
}

output "us_redis_port" {
  description = "US Redis port"
  value       = aws_elasticache_replication_group.us_redis.port
}

output "us_redis_arn" {
  description = "US Redis ARN"
  value       = aws_elasticache_replication_group.us_redis.arn
}

output "us_redis_kms_key_id" {
  description = "US Redis KMS key ID"
  value       = aws_kms_key.us_redis_key.key_id
}
