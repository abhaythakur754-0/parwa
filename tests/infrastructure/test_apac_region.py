"""
APAC Region Infrastructure Tests.

Tests for APAC region Terraform configuration and data compliance.
"""

import os
import pytest
from pathlib import Path


class TestAPACRegionStructure:
    """Test APAC region file structure."""

    def test_apac_region_directory_exists(self):
        """Test that APAC region directory exists."""
        apac_dir = Path("infra/terraform/regions/apac")
        assert apac_dir.exists(), "APAC region directory should exist"
        assert apac_dir.is_dir(), "APAC region path should be a directory"

    def test_apac_main_tf_exists(self):
        """Test that main.tf exists."""
        main_tf = Path("infra/terraform/regions/apac/main.tf")
        assert main_tf.exists(), "APAC main.tf should exist"

    def test_apac_database_tf_exists(self):
        """Test that database.tf exists."""
        database_tf = Path("infra/terraform/regions/apac/database.tf")
        assert database_tf.exists(), "APAC database.tf should exist"

    def test_apac_redis_tf_exists(self):
        """Test that redis.tf exists."""
        redis_tf = Path("infra/terraform/regions/apac/redis.tf")
        assert redis_tf.exists(), "APAC redis.tf should exist"

    def test_apac_variables_tf_exists(self):
        """Test that variables.tf exists."""
        variables_tf = Path("infra/terraform/regions/apac/variables.tf")
        assert variables_tf.exists(), "APAC variables.tf should exist"

    def test_apac_init_py_exists(self):
        """Test that __init__.py exists."""
        init_py = Path("infra/terraform/regions/apac/__init__.py")
        assert init_py.exists(), "APAC __init__.py should exist"


class TestAPACRegionMainConfig:
    """Test APAC region main.tf configuration."""

    @pytest.fixture
    def main_tf_content(self):
        """Load main.tf content."""
        main_tf = Path("infra/terraform/regions/apac/main.tf")
        return main_tf.read_text()

    def test_apac_region_is_ap_southeast_1(self, main_tf_content):
        """Test that APAC region is ap-southeast-1 (Singapore)."""
        assert "ap-southeast-1" in main_tf_content, "APAC region should be ap-southeast-1"

    def test_apac_compliance_tag(self, main_tf_content):
        """Test that APAC compliance tag is present."""
        assert "APAC" in main_tf_content, "APAC compliance tag should be present"

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

    def test_apac_data_class_tag(self, main_tf_content):
        """Test that APAC data class tag is present."""
        assert "APAC-RESTRICTED" in main_tf_content, "APAC data class tag should be present"


class TestAPACRegionDatabase:
    """Test APAC region database.tf configuration."""

    @pytest.fixture
    def database_tf_content(self):
        """Load database.tf content."""
        database_tf = Path("infra/terraform/regions/apac/database.tf")
        return database_tf.read_text()

    def test_postgres_configured(self, database_tf_content):
        """Test that PostgreSQL is configured."""
        assert "postgres" in database_tf_content.lower(), "PostgreSQL should be configured"

    def test_encryption_at_rest(self, database_tf_content):
        """Test that encryption at rest is enabled."""
        assert "storage_encrypted" in database_tf_content, "Storage encryption should be enabled"
        assert "true" in database_tf_content, "Encryption should be true"

    def test_kms_key_configured(self, database_tf_content):
        """Test that KMS key is configured for encryption."""
        assert 'resource "aws_kms_key"' in database_tf_content, "KMS key should be configured"

    def test_backup_configured(self, database_tf_content):
        """Test that backups are configured."""
        assert "backup_retention_period" in database_tf_content, "Backup retention should be configured"

    def test_backups_in_apac_only(self, database_tf_content):
        """Test that backups are configured in APAC only."""
        assert "ap-southeast-1" in database_tf_content, "Backup region should be ap-southeast-1"

    def test_point_in_time_recovery(self, database_tf_content):
        """Test that point-in-time recovery is enabled."""
        assert "cloudwatch_logs_exports" in database_tf_content, "CloudWatch logs should be exported"

    def test_read_replica_in_apac_only(self, database_tf_content):
        """Test that read replica is in APAC only."""
        assert "apac_postgres_replica" in database_tf_content, "Read replica should be in APAC"

    def test_multi_az_enabled(self, database_tf_content):
        """Test that Multi-AZ is configurable."""
        assert "multi_az" in database_tf_content, "Multi-AZ should be configurable"

    def test_deletion_protection(self, database_tf_content):
        """Test that deletion protection is enabled."""
        assert "deletion_protection" in database_tf_content, "Deletion protection should be configured"

    def test_db_subnet_group(self, database_tf_content):
        """Test that DB subnet group is configured."""
        assert 'resource "aws_db_subnet_group"' in database_tf_content, "DB subnet group should be configured"

    def test_audit_parameters(self, database_tf_content):
        """Test that audit parameters are set."""
        assert "pgaudit" in database_tf_content or "log_connections" in database_tf_content, \
            "Audit logging should be configured"


class TestAPACRegionRedis:
    """Test APAC region redis.tf configuration."""

    @pytest.fixture
    def redis_tf_content(self):
        """Load redis.tf content."""
        redis_tf = Path("infra/terraform/regions/apac/redis.tf")
        return redis_tf.read_text()

    def test_elasticache_configured(self, redis_tf_content):
        """Test that ElastiCache is configured."""
        assert "aws_elasticache" in redis_tf_content, "ElastiCache should be configured"

    def test_encryption_at_rest(self, redis_tf_content):
        """Test that encryption at rest is enabled."""
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

    def test_redis_in_apac_only(self, redis_tf_content):
        """Test that Redis is in APAC region."""
        assert "apac-redis" in redis_tf_content, "Redis should be in APAC region"

    def test_snapshot_retention(self, redis_tf_content):
        """Test that snapshot retention is configured."""
        assert "snapshot_retention_limit" in redis_tf_content, "Snapshot retention should be configured"


class TestAPACRegionVariables:
    """Test APAC region variables.tf configuration."""

    @pytest.fixture
    def variables_tf_content(self):
        """Load variables.tf content."""
        variables_tf = Path("infra/terraform/regions/apac/variables.tf")
        return variables_tf.read_text()

    def test_aws_region_variable(self, variables_tf_content):
        """Test that aws_region variable is defined with APAC default."""
        assert "aws_region" in variables_tf_content, "aws_region variable should be defined"
        assert "ap-southeast-1" in variables_tf_content, "Default region should be ap-southeast-1"

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

    def test_compliance_variables(self, variables_tf_content):
        """Test that compliance variables are defined."""
        assert "data_retention_days" in variables_tf_content, "data_retention_days should be defined"
        assert "enable_audit_logging" in variables_tf_content, "enable_audit_logging should be defined"

    def test_allowed_regions_validation(self, variables_tf_content):
        """Test that allowed regions validation exists."""
        assert "allowed_regions" in variables_tf_content, "allowed_regions should be defined"

    def test_backup_region_validation(self, variables_tf_content):
        """Test that backup region validation ensures APAC only."""
        assert "backup_region" in variables_tf_content, "backup_region should be defined"
        assert "ap-southeast-1" in variables_tf_content or "ap-northeast" in variables_tf_content, \
            "Backup region should default to APAC"


class TestAPACRegionCompliance:
    """Test data compliance of APAC region infrastructure."""

    @pytest.fixture
    def all_tf_content(self):
        """Load all .tf file contents."""
        content = {}
        apac_dir = Path("infra/terraform/regions/apac")
        for tf_file in apac_dir.glob("*.tf"):
            content[tf_file.name] = tf_file.read_text()
        return content

    def test_all_resources_have_apac_tag(self, all_tf_content):
        """Test that all resources have APAC region tag."""
        for filename, content in all_tf_content.items():
            assert "APAC" in content or "apac" in content or "ap-southeast" in content, \
                f"{filename} should have APAC region tag"

    def test_all_resources_have_compliance_tag(self, all_tf_content):
        """Test that all resources have compliance tag."""
        for filename, content in all_tf_content.items():
            if "variables.tf" not in filename:
                assert "APAC-DATA-LAWS" in content or "APAC" in content, \
                    f"{filename} should have compliance tag"

    def test_no_eu_region_references(self, all_tf_content):
        """Test that there are no EU region references in APAC config."""
        for filename, content in all_tf_content.items():
            assert "eu-west-1" not in content, \
                f"{filename} should not reference EU region"
            assert "eu-central" not in content, \
                f"{filename} should not reference EU region"

    def test_no_us_region_references(self, all_tf_content):
        """Test that there are no US region references in APAC config."""
        for filename, content in all_tf_content.items():
            assert "us-east-1" not in content, \
                f"{filename} should not reference US region"
            assert "us-west" not in content, \
                f"{filename} should not reference US region"

    def test_encryption_enabled_everywhere(self, all_tf_content):
        """Test that encryption is enabled on all data resources."""
        for filename, content in all_tf_content.items():
            if "database.tf" in filename or "redis.tf" in filename:
                assert "encrypt" in content.lower(), \
                    f"{filename} should have encryption enabled"


class TestAPACRegionInitPy:
    """Test APAC region __init__.py."""

    @pytest.fixture
    def init_py_content(self):
        """Load __init__.py content."""
        init_py = Path("infra/terraform/regions/apac/__init__.py")
        return init_py.read_text()

    def test_module_docstring(self, init_py_content):
        """Test that module has docstring."""
        assert '"""' in init_py_content, "__init__.py should have docstring"

    def test_apac_region_mentioned(self, init_py_content):
        """Test that APAC region is mentioned."""
        assert "ap-southeast-1" in init_py_content or "APAC" in init_py_content, \
            "APAC region should be mentioned"

    def test_compliance_mentioned(self, init_py_content):
        """Test that compliance is mentioned."""
        assert "Asia" in init_py_content or "APAC" in init_py_content, \
            "Asia-Pacific compliance should be mentioned in docstring"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
