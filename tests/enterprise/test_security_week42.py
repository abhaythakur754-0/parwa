"""
Week 42 Builder 1 - Enterprise Security Tests
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestThreatDetector:
    """Test threat detector"""

    def test_detector_exists(self):
        """Test threat detector exists"""
        from enterprise.security.threat_detector import ThreatDetector
        assert ThreatDetector is not None

    def test_detect_brute_force(self):
        """Test brute force detection"""
        from enterprise.security.threat_detector import ThreatDetector, ThreatLevel, ThreatType

        detector = ThreatDetector("client_001")
        event = detector.detect_brute_force("192.168.1.100", 10)

        assert event is not None
        assert event.level == ThreatLevel.HIGH
        assert event.threat_type == ThreatType.BRUTE_FORCE

    def test_detect_sql_injection(self):
        """Test SQL injection detection"""
        from enterprise.security.threat_detector import ThreatDetector, ThreatLevel

        detector = ThreatDetector("client_001")
        event = detector.detect_sql_injection("SELECT * FROM users WHERE id='1' OR 1=1", "192.168.1.100")

        assert event is not None
        assert event.level == ThreatLevel.CRITICAL


class TestIntrusionPrevention:
    """Test intrusion prevention"""

    def test_ips_exists(self):
        """Test IPS exists"""
        from enterprise.security.intrusion_prevention import IntrusionPrevention
        assert IntrusionPrevention is not None

    def test_block_ip(self):
        """Test blocking IP"""
        from enterprise.security.intrusion_prevention import IntrusionPrevention, BlockReason

        ips = IntrusionPrevention()
        action = ips.block_ip("192.168.1.100", BlockReason.BRUTE_FORCE)

        assert ips.is_blocked("192.168.1.100") is True
        assert action.reason == BlockReason.BRUTE_FORCE

    def test_whitelist(self):
        """Test whitelist"""
        from enterprise.security.intrusion_prevention import IntrusionPrevention, BlockReason

        ips = IntrusionPrevention()
        ips.add_to_whitelist("192.168.1.1")
        ips.block_ip("192.168.1.1", BlockReason.MANUAL)

        assert ips.is_blocked("192.168.1.1") is False


class TestVulnerabilityScanner:
    """Test vulnerability scanner"""

    def test_scanner_exists(self):
        """Test scanner exists"""
        from enterprise.security.vulnerability_scanner import VulnerabilityScanner
        assert VulnerabilityScanner is not None

    def test_start_scan(self):
        """Test starting scan"""
        from enterprise.security.vulnerability_scanner import VulnerabilityScanner

        scanner = VulnerabilityScanner("client_001")
        scan = scanner.start_scan("full")

        assert scan.client_id == "client_001"
        assert scan.status == "running"

    def test_complete_scan(self):
        """Test completing scan"""
        from enterprise.security.vulnerability_scanner import VulnerabilityScanner

        scanner = VulnerabilityScanner("client_001")
        scan = scanner.start_scan()
        result = scanner.complete_scan(scan.scan_id, [
            {"name": "SQL Injection", "severity": "critical", "affected_component": "api"}
        ])

        assert result.vulnerabilities_found == 1
        assert result.critical == 1
