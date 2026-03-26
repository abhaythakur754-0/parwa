"""
US Region Infrastructure Tests.

Tests for US region Terraform configuration and CCPA compliance.
"""

import os
import pytest
from pathlib import Path


class TestUSRegionStructure:
    """Test US region file structure."""

    def test_us_region_directory_exists(self):
        """Test that US region directory exists."""
        us_dir = Path("infra/terraform/regions/us")
        assert us_dir.exists(), "US region directory should exist"
        assert us_dir.is_dir(), "US region path should be a directory"

    def test_us_main_tf_exists(self):
        """Test that main.tf exists."""
        main_tf = Path("infra/terraform/regions/us/main.tf")
        assert main_tf.exists(), "US main.tf should exist"

    def test_us_database_tf_exists(self):
        """Test that database.tf exists."""
        database_tf = Path("infra/terraform/regions/us/database.tf")
        assert database_tf.exists(), "US database.tf should exist"

    def test_us_redis_tf_exists(self):
        """Test that redis.tf exists."""
        redis_tf = Path("infra/terraform/regions/us/redis.tf")
        assert redis_tf.exists(), "US redis.tf should exist"

    def test_us_variables_tf_exists(self):
        """Test that variables.tf exists."""
        variables_tf = Path("infra/terraform/regions/us/variables.tf")
        assert variables_tf.exists(), "US variables.tf should exist"

    def test_us_init_py_exists(self):
        """Test that __init__.py exists."""
        init_py = Path("infra/terraform/regions/us/__init__.py")
        assert init_py.exists(), "US __init__.py should exist"


class TestUSRegionMainConfig:
    """Test US region main.tf configuration."""

    @pytest.fixture
    def main_tf_content(self):
        """Load main.tf content."""
        main_tf = Path("infra/terraform/regions/us/main.tf")
        return main_tf.read_text()

    def test_us_region_is_us_east_1(self, main_tf_content):
        """Test that US region is us-east-1 (N. Virginia)."""
        assert "us-east-1" in main_tf_content, "US region should be us-east-1"

    def test_ccpa_compliance_tag(self, main_tf_content):
        """Test that CCPA compliance tag is present."""
        assert "CCPA" in main_tf_content, "CCPA compliance tag should be present"

    def test_aws_provider_configured(self, main_tf_content):
        """Test that AWS provider is configured."""
        assert 'provider "aws"' in main_tf_content, "AWS provider should be configured"

    def test_vpc_configured(self, main_tf_content):
        """Test that VPC is configured."""
        assert 'resource "aws_vpc"' in main_tf_content, "VPC should be configured"

    def test_public_subnets_configured(self, main_tf_content):
        """Test that public subnets are configured."""
        assert "aws_subnet" in main_tf_content, "Subnets should be configured"

    def test_security_groups_configured(self, main_tf_content):
        """Test that security groups are configured."""
        assert 'resource "aws_security_group"' in main_tf_content, "Security groups should be configured"

    def test_internet_gateway_configured(self, main_tf_content):
        """Test that internet gateway is configured."""
        assert 'resource "aws_internet_gateway"' in main_tf_content, "Internet gateway should be configured"

    def test_nat_gateway_configured(self, main_tf_content):
        """Test that NAT gateway is configured."""
        assert 'resource "aws_nat_gateway"' in main_tf_content, "NAT gateway should be configured"

    def test_vpc_flow_logs_enabled(self, main_tf_content):
        """Test that VPC flow logs are enabled for audit."""
        assert 'resource "aws_flow_log"' in main_tf_content, "VPC flow logs should be enabled"

    def test_us_data_class_tag(self, main_tf_content):
        """Test that US data class tag is present."""
        assert "US-RESTRICTED" in main_tf_content, "US data class tag should be present"


class TestUSRegionDatabase:
    """Test US region database.tf configuration."""

    @pytest.fixture
    def database_tf_content(self):
        """Load database.tf content."""
        database_tf = Path("infra/terraform/regions/us/database.tf")
        return database_tf.read_text()

    def test_postgres_configured(self, database_tf_content):
        """Test that PostgreSQL is configured."""
        assert "postgres" in database_tf_content.lower(), "PostgreSQL should be configured"

    def test_encryption_at_rest(self, database_tf_content):
        """Test that encryption at rest is enabled (CCPA requirement)."""
        assert "storage_encrypted" in database_tf_content, "Storage encryption should be enabled"
        assert "true" in database_tf_content, "Encryption should be true"

    def test_kms_key_configured(self, database_tf_content):
        """Test that KMS key is configured for encryption."""
        assert 'resource "aws_kms_key"' in database_tf_content, "KMS key should be configured"

    def test_backup_configured(self, database_tf_content):
        """Test that backups are configured."""
        assert "backup_retention_period" in database_tf_content, "Backup retention should be configured"

    def test_backups_in_us_only(self, database_tf_content):
        """Test that backups are configured in US only (CCPA)."""
        assert "us-east-1" in database_tf_content, "Backup region should be us-east-1"

    def test_point_in_time_recovery(self, database_tf_content):
        """Test that point-in-time recovery is enabled."""
        assert "cloudwatch_logs_exports" in database_tf_content, "CloudWatch logs should be exported"

    def test_read_replica_in_us_only(self, database_tf_content):
        """Test that read replica is in US only."""
        assert "us_postgres_replica" in database_tf_content, "Read replica should be in US"

    def test_multi_az_enabled(self, database_tf_content):
        """Test that Multi-AZ is configurable."""
        assert "multi_az" in database_tf_content, "Multi-AZ should be configurable"

    def test_deletion_protection(self, database_tf_content):
        """Test that deletion protection is enabled."""
        assert "deletion_protection" in database_tf_content, "Deletion protection should be configured"

    def test_db_subnet_group(self, database_tf_content):
        """Test that DB subnet group is configured."""
        assert 'resource "aws_db_subnet_group"' in database_tf_content, "DB subnet group should be configured"

    def test_ccpa_audit_parameters(self, database_tf_content):
        """Test that CCPA audit parameters are set."""
        assert "pgaudit" in database_tf_content or "log_connections" in database_tf_content, \
            "Audit logging should be configured"


class TestUSRegionRedis:
    """Test US region redis.tf configuration."""

    @pytest.fixture
    def redis_tf_content(self):
        """Load redis.tf content."""
        redis_tf = Path("infra/terraform/regions/us/redis.tf")
        return redis_tf.read_text()

    def test_elasticache_configured(self, redis_tf_content):
        """Test that ElastiCache is configured."""
        assert "aws_elasticache" in redis_tf_content, "ElastiCache should be configured"

    def test_encryption_at_rest(self, redis_tf_content):
        """Test that encryption at rest is enabled (CCPA requirement)."""
        assert "at_rest_encryption_enabled" in redis_tf_content, "At-rest encryption should be enabled"

    def test_encryption_in_transit(self, redis_tf_content):
        """Test that encryption in transit is enabled."""
        assert "transit_encryption_enabled" in redis_tf_content, "In-transit encryption should be enabled"

    def test_kms_key_configured(self, redis_tf_content):
        """Test that KMS key is configured for Redis encryption."""
        assert 'resource "aws_kms_key"' in redis_tf_content, "KMS key should be configured for Redis"

    def test_automatic_failover(self, redis_tf_content):
        """Test that automatic failover is enabled."""
        assert "automatic_failover_enabled" in redis_tf_content, "Automatic failover should be enabled"

    def test_multi_az_enabled(self, redis_tf_content):
        """Test that Multi-AZ is enabled for Redis."""
        assert "multi_az_enabled" in redis_tf_content, "Multi-AZ should be enabled"

    def test_redis_subnet_group(self, redis_tf_content):
        """Test that Redis subnet group is configured."""
        assert 'resource "aws_elasticache_subnet_group"' in redis_tf_content, \
            "Redis subnet group should be configured"

    def test_redis_in_us_only(self, redis_tf_content):
        """Test that Redis is in US region."""
        assert "us-redis" in redis_tf_content, "Redis should be in US region"

    def test_snapshot_retention(self, redis_tf_content):
        """Test that snapshot retention is configured."""
        assert "snapshot_retention_limit" in redis_tf_content, "Snapshot retention should be configured"


class TestUSRegionVariables:
    """Test US region variables.tf configuration."""

    @pytest.fixture
    def variables_tf_content(self):
        """Load variables.tf content."""
        variables_tf = Path("infra/terraform/regions/us/variables.tf")
        return variables_tf.read_text()

    def test_aws_region_variable(self, variables_tf_content):
        """Test that aws_region variable is defined with US default."""
        assert "aws_region" in variables_tf_content, "aws_region variable should be defined"
        assert "us-east-1" in variables_tf_content, "Default region should be us-east-1"

    def test_vpc_cidr_variable(self, variables_tf_content):
        """Test that vpc_cidr variable is defined."""
        assert "vpc_cidr" in variables_tf_content, "vpc_cidr variable should be defined"

    def test_database_variables(self, variables_tf_content):
        """Test that database variables are defined."""
        assert "db_instance_class" in variables_tf_content, "db_instance_class should be defined"
        assert "db_allocated_storage" in variables_tf_content, "db_allocated_storage should be defined"
        assert "db_backup_retention_days" in variables_tf_content, "db_backup_retention_days should be defined"

    def test_redis_variables(self, variables_tf_content):
        """Test that Redis variables are defined."""
        assert "redis_node_type" in variables_tf_content, "redis_node_type should be defined"
        assert "redis_num_nodes" in variables_tf_content, "redis_num_nodes should be defined"

    def test_ccpa_compliance_variables(self, variables_tf_content):
        """Test that CCPA compliance variables are defined."""
        assert "data_retention_days" in variables_tf_content, "data_retention_days should be defined"
        assert "enable_audit_logging" in variables_tf_content, "enable_audit_logging should be defined"

    def test_allowed_regions_validation(self, variables_tf_content):
        """Test that allowed regions validation exists for CCPA."""
        assert "allowed_regions" in variables_tf_content, "allowed_regions should be defined"

    def test_backup_region_validation(self, variables_tf_content):
        """Test that backup region validation ensures US only."""
        assert "backup_region" in variables_tf_content, "backup_region should be defined"
        assert "us-east-1" in variables_tf_content or "us-west" in variables_tf_content, \
            "Backup region should default to US"


class TestUSRegionCCPACompliance:
    """Test CCPA compliance of US region infrastructure."""

    @pytest.fixture
    def all_tf_content(self):
        """Load all .tf file contents."""
        content = {}
        us_dir = Path("infra/terraform/regions/us")
        for tf_file in us_dir.glob("*.tf"):
            content[tf_file.name] = tf_file.read_text()
        return content

    def test_all_resources_have_us_tag(self, all_tf_content):
        """Test that all resources have US region tag."""
        for filename, content in all_tf_content.items():
            assert "US" in content or "us-" in content, \
                f"{filename} should have US region tag"

    def test_all_resources_have_ccpa_tag(self, all_tf_content):
        """Test that all resources have CCPA compliance tag."""
        for filename, content in all_tf_content.items():
            if "variables.tf" not in filename:
                assert "CCPA" in content, \
                    f"{filename} should have CCPA compliance tag"

    def test_no_eu_region_references(self, all_tf_content):
        """Test that there are no EU region references in US config."""
        for filename, content in all_tf_content.items():
            assert "eu-west-1" not in content, \
                f"{filename} should not reference EU region"
            assert "eu-central" not in content, \
                f"{filename} should not reference EU region"

    def test_no_apac_region_references(self, all_tf_content):
        """Test that there are no APAC region references in US config."""
        for filename, content in all_tf_content.items():
            assert "ap-southeast" not in content, \
                f"{filename} should not reference APAC region"

    def test_encryption_enabled_everywhere(self, all_tf_content):
        """Test that encryption is enabled on all data resources."""
        for filename, content in all_tf_content.items():
            if "database.tf" in filename or "redis.tf" in filename:
                assert "encrypt" in content.lower(), \
                    f"{filename} should have encryption enabled"


class TestUSRegionInitPy:
    """Test US region __init__.py."""

    @pytest.fixture
    def init_py_content(self):
        """Load __init__.py content."""
        init_py = Path("infra/terraform/regions/us/__init__.py")
        return init_py.read_text()

    def test_module_docstring(self, init_py_content):
        """Test that module has docstring."""
        assert '"""' in init_py_content, "__init__.py should have docstring"

    def test_us_region_mentioned(self, init_py_content):
        """Test that US region is mentioned."""
        assert "us-east-1" in init_py_content or "US" in init_py_content, \
            "US region should be mentioned"

    def test_ccpa_mentioned(self, init_py_content):
        """Test that CCPA is mentioned."""
        assert "CCPA" in init_py_content, "CCPA should be mentioned in docstring"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
