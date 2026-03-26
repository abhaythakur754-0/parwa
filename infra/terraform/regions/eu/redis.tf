# EU Region Redis Configuration
# ElastiCache with GDPR-compliant encryption
# Region: eu-west-1 (Ireland)

# EU Redis Subnet Group
resource "aws_elasticache_subnet_group" "eu_redis_subnet_group" {
  name        = "${var.project_name}-eu-redis-subnet"
  description = "Redis subnet group for EU region"
  subnet_ids  = aws_subnet.eu_database[*].id

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

# EU Redis Parameter Group
resource "aws_elasticache_parameter_group" "eu_redis_params" {
  family  = "redis7"
  name    = "${var.project_name}-eu-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

# EU Redis Replication Group (Primary + Replicas)
resource "aws_elasticache_replication_group" "eu_redis" {
  replication_group_id       = "${var.project_name}-eu-redis"
  description               = "EU Redis cluster for PARWA (GDPR compliant)"
  replication_group_description = "EU Redis replication group - GDPR compliant"

  # Node configuration
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_nodes
  port                 = 6379

  # Encryption (GDPR requirement)
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                = aws_kms_key.eu_redis_key.arn

  # Network
  subnet_group_name  = aws_elasticache_subnet_group.eu_redis_subnet_group.name
  security_group_ids = [aws_security_group.eu_redis_sg.id]

  # Parameters
  parameter_group_name = aws_elasticache_parameter_group.eu_redis_params.name

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

  # Tags for GDPR compliance
  tags = {
    Name        = "${var.project_name}-eu-redis"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
    Encryption  = "AES-256"
  }
}

# EU KMS Key for Redis Encryption
resource "aws_kms_key" "eu_redis_key" {
  description             = "KMS key for EU Redis encryption (GDPR compliant)"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-eu-redis-key"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

resource "aws_kms_alias" "eu_redis_key_alias" {
  name          = "alias/${var.project_name}-eu-redis-key"
  target_key_id = aws_kms_key.eu_redis_key.key_id
}

# EU CloudWatch Alarms for Redis
resource "aws_cloudwatch_metric_alarm" "eu_redis_cpu" {
  alarm_name          = "${var.project_name}-eu-redis-cpu-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EU Redis CPU utilization > 80%"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-eu-redis"
  }

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

resource "aws_cloudwatch_metric_alarm" "eu_redis_memory" {
  alarm_name          = "${var.project_name}-eu-redis-memory-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeableMemory"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 100000000  # 100MB
  alarm_description   = "EU Redis freeable memory < 100MB"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-eu-redis"
  }

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

resource "aws_cloudwatch_metric_alarm" "eu_redis_connections" {
  alarm_name          = "${var.project_name}-eu-redis-connections-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 10000
  alarm_description   = "EU Redis connections > 10000"
  alarm_actions       = []

  dimensions = {
    CacheClusterId = "${var.project_name}-eu-redis"
  }

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

# EU Redis Event Notification
resource "aws_sns_topic" "eu_redis_notifications" {
  name = "${var.project_name}-eu-redis-notifications"

  tags = {
    Region     = "EU"
    Compliance = "GDPR"
  }
}

# Outputs
output "eu_redis_primary_endpoint" {
  description = "EU Redis primary endpoint"
  value       = aws_elasticache_replication_group.eu_redis.primary_endpoint_address
}

output "eu_redis_reader_endpoint" {
  description = "EU Redis reader endpoint"
  value       = aws_elasticache_replication_group.eu_redis.reader_endpoint_address
}

output "eu_redis_port" {
  description = "EU Redis port"
  value       = aws_elasticache_replication_group.eu_redis.port
}

output "eu_redis_arn" {
  description = "EU Redis ARN"
  value       = aws_elasticache_replication_group.eu_redis.arn
}

output "eu_redis_kms_key_id" {
  description = "EU Redis KMS key ID"
  value       = aws_kms_key.eu_redis_key.key_id
}
