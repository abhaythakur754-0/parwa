"""
Week 60 - Builder 3 Tests: Release Manager Module
Unit tests for Release Manager, Version Manager, and Release Validator
"""

import pytest
from parwa_final_release.release_manager import (
    ReleaseManager, Release, ReleaseStatus,
    VersionManager, VersionInfo, VersionBump,
    ReleaseValidator
)


class TestReleaseManager:
    """Tests for ReleaseManager class"""

    @pytest.fixture
    def manager(self):
        """Create release manager"""
        return ReleaseManager()

    def test_create_release(self, manager):
        """Test release creation"""
        release = manager.create_release(
            version="1.0.0",
            changelog=["Initial release"],
            notes="First stable release"
        )

        assert release.version == "1.0.0"
        assert release.status == ReleaseStatus.DRAFT

    def test_promote_release(self, manager):
        """Test release promotion"""
        release = manager.create_release("1.0.0")
        result = manager.promote_release("1.0.0", ReleaseStatus.RELEASED)

        assert result is True
        assert manager.get_release("1.0.0").status == ReleaseStatus.RELEASED
        assert manager.get_current_version() == "1.0.0"

    def test_withdraw_release(self, manager):
        """Test release withdrawal"""
        release = manager.create_release("1.0.0")
        manager.promote_release("1.0.0", ReleaseStatus.RELEASED)
        result = manager.withdraw_release("1.0.0", "Critical bug found")

        assert result is True
        assert manager.get_release("1.0.0").status == ReleaseStatus.WITHDRAWN

    def test_get_release(self, manager):
        """Test get release"""
        manager.create_release("1.0.0")
        release = manager.get_release("1.0.0")

        assert release.version == "1.0.0"

    def test_get_current_version(self, manager):
        """Test get current version"""
        manager.create_release("1.0.0")
        manager.promote_release("1.0.0", ReleaseStatus.RELEASED)

        version = manager.get_current_version()
        assert version == "1.0.0"

    def test_list_releases(self, manager):
        """Test list releases"""
        manager.create_release("1.0.0")
        manager.create_release("2.0.0")

        releases = manager.list_releases()
        assert len(releases) == 2

    def test_add_changelog_entry(self, manager):
        """Test adding changelog entry"""
        manager.create_release("1.0.0")
        result = manager.add_changelog_entry("1.0.0", "Fixed bug")

        assert result is True
        assert "Fixed bug" in manager.get_release("1.0.0").changelog


class TestVersionManager:
    """Tests for VersionManager class"""

    @pytest.fixture
    def manager(self):
        """Create version manager"""
        return VersionManager()

    def test_parse_version(self, manager):
        """Test version parsing"""
        version = manager.parse_version("1.2.3")

        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3

    def test_parse_version_with_prerelease(self, manager):
        """Test parsing version with prerelease"""
        version = manager.parse_version("1.0.0-alpha")

        assert version.major == 1
        assert version.prerelease == "alpha"

    def test_bump_major(self, manager):
        """Test major version bump"""
        new_version = manager.bump_version("1.2.3", VersionBump.MAJOR)

        assert new_version == "2.0.0"

    def test_bump_minor(self, manager):
        """Test minor version bump"""
        new_version = manager.bump_version("1.2.3", VersionBump.MINOR)

        assert new_version == "1.3.0"

    def test_bump_patch(self, manager):
        """Test patch version bump"""
        new_version = manager.bump_version("1.2.3", VersionBump.PATCH)

        assert new_version == "1.2.4"

    def test_compare_versions(self, manager):
        """Test version comparison"""
        assert manager.compare_versions("1.0.0", "2.0.0") == -1
        assert manager.compare_versions("2.0.0", "1.0.0") == 1
        assert manager.compare_versions("1.0.0", "1.0.0") == 0

    def test_register_version(self, manager):
        """Test version registration"""
        result = manager.register_version("1.0.0")

        assert result is True
        assert "1.0.0" in manager.versions

    def test_create_tag(self, manager):
        """Test tag creation"""
        manager.register_version("1.0.0")
        result = manager.create_tag("v1.0.0", "1.0.0")

        assert result is True
        assert manager.get_tag_version("v1.0.0") == "1.0.0"

    def test_get_version(self, manager):
        """Test get version"""
        manager.register_version("1.0.0")
        version = manager.get_version("1.0.0")

        assert version.major == 1

    def test_list_versions(self, manager):
        """Test list versions"""
        manager.register_version("1.0.0")
        manager.register_version("2.0.0")

        versions = manager.list_versions()
        assert len(versions) == 2


class TestReleaseValidator:
    """Tests for ReleaseValidator class"""

    @pytest.fixture
    def validator(self):
        """Create release validator"""
        return ReleaseValidator()

    def test_register_check(self, validator):
        """Test check registration"""
        validator.register_check("test_check", lambda v: True)

        assert len(validator.checks) == 1

    def test_run_checks(self, validator):
        """Test running checks"""
        validator.register_check("test", lambda v: True)
        results = validator.run_checks("1.0.0")

        assert results["version"] == "1.0.0"
        assert results["passed"] is True

    def test_failed_check(self, validator):
        """Test failed check"""
        validator.register_check("failing", lambda v: False, required=True)
        results = validator.run_checks("1.0.0")

        assert results["passed"] is False

    def test_request_signoff(self, validator):
        """Test signoff request"""
        validator.request_signoff("1.0.0", "alice")

        signoffs = validator.get_signoffs("1.0.0")
        assert len(signoffs) == 1
        assert signoffs[0]["approver"] == "alice"

    def test_provide_signoff(self, validator):
        """Test providing signoff"""
        validator.request_signoff("1.0.0", "alice")
        result = validator.provide_signoff("1.0.0", "alice", True, "Looks good")

        assert result is True
        signoffs = validator.get_signoffs("1.0.0")
        assert signoffs[0]["status"] == "approved"

    def test_is_approved(self, validator):
        """Test approval check"""
        validator.request_signoff("1.0.0", "alice")
        assert validator.is_approved("1.0.0") is False

        validator.provide_signoff("1.0.0", "alice", True)
        assert validator.is_approved("1.0.0") is True

    def test_get_result(self, validator):
        """Test get validation result"""
        validator.register_check("test", lambda v: True)
        validator.run_checks("1.0.0")

        result = validator.get_result("1.0.0")
        assert result is not None
