# Tests for Builder 2 - CDN Integration
# Week 51: cdn_manager.py, cache_edge.py, content_distributor.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.global_infra.cdn_manager import (
    CDNManager, CDNConfig, CacheRule, CDNProvider, CacheBehavior
)
from enterprise.global_infra.cache_edge import (
    EdgeCache, EdgeCacheEntry, CachePolicy, EdgeLocation, CacheStatus
)
from enterprise.global_infra.content_distributor import (
    ContentDistributor, DistributionTarget, DistributionJob,
    DistributionStatus, ContentType
)


# =============================================================================
# CDN MANAGER TESTS
# =============================================================================

class TestCDNManager:
    """Tests for CDNManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = CDNManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_configs"] == 0

    def test_create_config(self):
        """Test creating CDN configuration"""
        manager = CDNManager()
        config = manager.create_config(
            name="main-cdn",
            provider=CDNProvider.CLOUDFRONT,
            domain="cdn.example.com",
            origin="origin.example.com"
        )
        assert config.name == "main-cdn"
        assert config.provider == CDNProvider.CLOUDFRONT

    def test_update_config(self):
        """Test updating CDN configuration"""
        manager = CDNManager()
        config = manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        result = manager.update_config(config.id, ttl_seconds=7200)
        assert result is True
        assert config.ttl_seconds == 7200

    def test_delete_config(self):
        """Test deleting CDN configuration"""
        manager = CDNManager()
        config = manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        result = manager.delete_config(config.id)
        assert result is True
        assert manager.get_config(config.id) is None

    def test_add_cache_rule(self):
        """Test adding cache rule"""
        manager = CDNManager()
        config = manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        rule = manager.add_cache_rule(config_id=config.id, path_pattern="/images/*", ttl_seconds=86400)
        assert rule is not None
        assert rule.path_pattern == "/images/*"

    def test_remove_cache_rule(self):
        """Test removing cache rule"""
        manager = CDNManager()
        config = manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        rule = manager.add_cache_rule(config.id, "/images/*")
        result = manager.remove_cache_rule(rule.id)
        assert result is True

    def test_get_config_by_domain(self):
        """Test getting config by domain"""
        manager = CDNManager()
        manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        config = manager.get_config_by_domain("cdn.example.com")
        assert config is not None

    def test_purge_cache(self):
        """Test cache purge"""
        manager = CDNManager()
        config = manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        result = manager.purge_cache(config.id, ["/images/*"])
        assert result is True
        metrics = manager.get_metrics()
        assert metrics["purge_requests"] == 1

    def test_cache_hit_miss_recording(self):
        """Test cache hit/miss recording"""
        manager = CDNManager()
        manager.record_cache_hit()
        manager.record_cache_hit()
        manager.record_cache_miss()
        hit_rate = manager.get_cache_hit_rate()
        assert hit_rate == pytest.approx(66.67, rel=0.01)

    def test_enable_disable_config(self):
        """Test enabling and disabling config"""
        manager = CDNManager()
        config = manager.create_config("test", CDNProvider.CLOUDFRONT, "cdn.example.com", "origin.example.com")
        manager.disable_config(config.id)
        assert config.enabled is False
        manager.enable_config(config.id)
        assert config.enabled is True

    def test_get_configs_by_provider(self):
        """Test getting configs by provider"""
        manager = CDNManager()
        manager.create_config("cf", CDNProvider.CLOUDFRONT, "cdn1.example.com", "origin.example.com")
        manager.create_config("cf2", CDNProvider.CLOUDFRONT, "cdn2.example.com", "origin.example.com")
        manager.create_config("ff", CDNProvider.FASTLY, "cdn3.example.com", "origin.example.com")
        cf_configs = manager.get_configs_by_provider(CDNProvider.CLOUDFRONT)
        assert len(cf_configs) == 2


# =============================================================================
# EDGE CACHE TESTS
# =============================================================================

class TestEdgeCache:
    """Tests for EdgeCache class"""

    def test_init(self):
        """Test cache initialization"""
        cache = EdgeCache()
        assert cache is not None
        metrics = cache.get_metrics()
        assert metrics["total_entries"] == 0

    def test_set_and_get(self):
        """Test setting and getting cache values"""
        cache = EdgeCache()
        entry = cache.set("key1", "value1", ttl_seconds=3600)
        assert entry.key == "key1"
        result = cache.get("key1")
        assert result == "value1"

    def test_get_nonexistent_key(self):
        """Test getting nonexistent key"""
        cache = EdgeCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_get_expired_entry(self):
        """Test getting expired entry"""
        cache = EdgeCache()
        cache.set("key1", "value1", ttl_seconds=1)
        time.sleep(1.1)
        result = cache.get("key1")
        assert result is None

    def test_get_status_hit(self):
        """Test cache status for hit"""
        cache = EdgeCache()
        cache.set("key1", "value1")
        status = cache.get_status("key1")
        assert status == CacheStatus.HIT

    def test_get_status_miss(self):
        """Test cache status for miss"""
        cache = EdgeCache()
        status = cache.get_status("nonexistent")
        assert status == CacheStatus.MISS

    def test_get_status_stale(self):
        """Test cache status for stale entry"""
        cache = EdgeCache()
        cache.set("key1", "value1", ttl_seconds=1)
        time.sleep(1.1)
        status = cache.get_status("key1")
        assert status == CacheStatus.STALE

    def test_invalidate(self):
        """Test invalidating entry"""
        cache = EdgeCache()
        cache.set("key1", "value1")
        result = cache.invalidate("key1")
        assert result is True
        assert cache.get("key1") is None

    def test_invalidate_by_location(self):
        """Test invalidating by location"""
        cache = EdgeCache()
        cache.set("key1", "value1", location=EdgeLocation.US_EAST)
        cache.set("key2", "value2", location=EdgeLocation.US_WEST)
        count = cache.invalidate_by_location(EdgeLocation.US_EAST)
        assert count == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_by_pattern(self):
        """Test invalidating by pattern"""
        cache = EdgeCache()
        cache.set("/images/img1.jpg", "data1")
        cache.set("/images/img2.jpg", "data2")
        cache.set("/videos/vid1.mp4", "data3")
        count = cache.invalidate_by_pattern("/images/*")
        assert count == 2

    def test_create_policy(self):
        """Test creating cache policy"""
        cache = EdgeCache()
        policy = cache.create_policy("default", default_ttl=3600, max_ttl=86400)
        assert policy.name == "default"
        assert policy.default_ttl == 3600

    def test_get_entries_by_location(self):
        """Test getting entries by location"""
        cache = EdgeCache()
        cache.set("key1", "value1", location=EdgeLocation.US_EAST)
        cache.set("key2", "value2", location=EdgeLocation.US_EAST)
        cache.set("key3", "value3", location=EdgeLocation.EU_WEST)
        entries = cache.get_entries_by_location(EdgeLocation.US_EAST)
        assert len(entries) == 2

    def test_cleanup_expired(self):
        """Test cleanup of expired entries"""
        cache = EdgeCache()
        cache.set("key1", "value1", ttl_seconds=1)
        time.sleep(1.1)
        count = cache.cleanup_expired()
        assert count == 1

    def test_clear_all(self):
        """Test clearing all entries"""
        cache = EdgeCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.clear_all()
        assert count == 2


# =============================================================================
# CONTENT DISTRIBUTOR TESTS
# =============================================================================

class TestContentDistributor:
    """Tests for ContentDistributor class"""

    def test_init(self):
        """Test distributor initialization"""
        distributor = ContentDistributor()
        assert distributor is not None
        metrics = distributor.get_metrics()
        assert metrics["total_jobs"] == 0

    def test_add_target(self):
        """Test adding distribution target"""
        distributor = ContentDistributor()
        target = distributor.add_target(region="us-east-1", endpoint="https://us-east.example.com")
        assert target.region == "us-east-1"
        assert target.endpoint == "https://us-east.example.com"

    def test_remove_target(self):
        """Test removing distribution target"""
        distributor = ContentDistributor()
        target = distributor.add_target("us-east-1", "https://us-east.example.com")
        result = distributor.remove_target(target.id)
        assert result is True
        assert distributor.get_target(target.id) is None

    def test_create_job(self):
        """Test creating distribution job"""
        distributor = ContentDistributor()
        distributor.add_target("us-east-1", "https://us-east.example.com")
        job = distributor.create_job(content_type=ContentType.STATIC, source_path="/content/assets", target_regions=["us-east-1"])
        assert job.content_type == ContentType.STATIC
        assert job.status == DistributionStatus.PENDING
        assert len(job.targets) == 1

    def test_start_job(self):
        """Test starting a job"""
        distributor = ContentDistributor()
        job = distributor.create_job(ContentType.STATIC, "/content")
        result = distributor.start_job(job.id)
        assert result is True
        assert job.status == DistributionStatus.IN_PROGRESS

    def test_update_progress(self):
        """Test updating job progress"""
        distributor = ContentDistributor()
        job = distributor.create_job(ContentType.STATIC, "/content")
        distributor.start_job(job.id)
        result = distributor.update_progress(job.id, 50, 100)
        assert result is True
        assert job.progress_percent == 50

    def test_complete_job(self):
        """Test completing a job"""
        distributor = ContentDistributor()
        distributor.add_target("us-east-1", "https://us-east.example.com")
        job = distributor.create_job(ContentType.STATIC, "/content")
        distributor.start_job(job.id)
        distributor.update_progress(job.id, 100, 100)
        result = distributor.complete_job(job.id)
        assert result is True
        assert job.status == DistributionStatus.COMPLETED

    def test_fail_job(self):
        """Test failing a job"""
        distributor = ContentDistributor()
        job = distributor.create_job(ContentType.STATIC, "/content")
        result = distributor.fail_job(job.id, "Connection refused")
        assert result is True
        assert job.status == DistributionStatus.FAILED

    def test_get_jobs_by_status(self):
        """Test getting jobs by status"""
        distributor = ContentDistributor()
        j1 = distributor.create_job(ContentType.STATIC, "/content1")
        j2 = distributor.create_job(ContentType.STATIC, "/content2")
        distributor.start_job(j1.id)
        distributor.complete_job(j1.id)
        completed = distributor.get_jobs_by_status(DistributionStatus.COMPLETED)
        pending = distributor.get_jobs_by_status(DistributionStatus.PENDING)
        assert len(completed) == 1
        assert len(pending) == 1

    def test_enable_disable_target(self):
        """Test enabling and disabling targets"""
        distributor = ContentDistributor()
        target = distributor.add_target("us-east-1", "https://us-east.example.com")
        distributor.disable_target(target.id)
        assert target.enabled is False
        distributor.enable_target(target.id)
        assert target.enabled is True

    def test_cancel_job(self):
        """Test cancelling a job"""
        distributor = ContentDistributor()
        job = distributor.create_job(ContentType.STATIC, "/content")
        result = distributor.cancel_job(job.id)
        assert result is True
        assert job.status == DistributionStatus.FAILED

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        distributor = ContentDistributor()
        distributor.add_target("us-east-1", "https://us-east.example.com")
        job = distributor.create_job(ContentType.STATIC, "/content")
        distributor.start_job(job.id)
        distributor.update_progress(job.id, 10, 10)
        distributor.complete_job(job.id)
        metrics = distributor.get_metrics()
        assert metrics["total_jobs"] == 1
