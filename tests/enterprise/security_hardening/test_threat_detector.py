"""Tests for Threat Detector Module - Week 54, Builder 2"""
import pytest
from datetime import datetime, timedelta

from enterprise.security_hardening.threat_detector import (
    ThreatDetector, Threat, ThreatSignature, ThreatType, ThreatSeverity
)
from enterprise.security_hardening.anomaly_detector import (
    AnomalyDetector, Anomaly, Baseline, AnomalyType
)
from enterprise.security_hardening.intrusion_prevention import (
    IntrusionPrevention, BlockEntry, PreventionRule, ActionType
)


class TestThreatDetector:
    def test_init(self):
        detector = ThreatDetector()
        assert len(detector.signatures) > 0
        assert len(detector.threats) == 0

    def test_detect_sql_injection(self):
        detector = ThreatDetector()
        threats = detector.detect("SELECT * FROM users WHERE id='1' OR '1'='1'", "test")
        assert len(threats) > 0
        assert any(t.threat_type == ThreatType.SQL_INJECTION for t in threats)

    def test_detect_xss(self):
        detector = ThreatDetector()
        threats = detector.detect("<script>alert('xss')</script>", "test")
        assert len(threats) > 0
        assert any(t.threat_type == ThreatType.XSS for t in threats)

    def test_detect_path_traversal(self):
        detector = ThreatDetector()
        threats = detector.detect("../../../etc/passwd", "test")
        assert len(threats) > 0
        assert any(t.threat_type == ThreatType.PATH_TRAVERSAL for t in threats)

    def test_no_threat_detected(self):
        detector = ThreatDetector()
        threats = detector.detect("Hello, world!", "test")
        assert len(threats) == 0

    def test_add_signature(self):
        detector = ThreatDetector()
        sig = ThreatSignature("custom", "custom_pattern", ThreatType.MALWARE, ThreatSeverity.HIGH)
        detector.add_signature(sig)
        assert any(s.name == "custom" for s in detector.signatures)

    def test_get_threats(self):
        detector = ThreatDetector()
        detector.detect("SELECT * FROM users WHERE id='1'", "test")
        threats = detector.get_threats()
        assert len(threats) > 0

    def test_resolve_threat(self):
        detector = ThreatDetector()
        detector.detect("SELECT * FROM users WHERE id='1'", "test")
        threats = detector.get_threats()
        if threats:
            threat_id = list(detector.threats.keys())[0]
            assert detector.resolve_threat(threat_id)
            assert detector.threats[threat_id].resolved


class TestAnomalyDetector:
    def test_init(self):
        detector = AnomalyDetector()
        assert detector.default_threshold == 3.0
        assert len(detector.anomalies) == 0

    def test_baseline_mean(self):
        baseline = Baseline()
        for v in [1, 2, 3, 4, 5]:
            baseline.add(v)
        assert baseline.mean == 3.0

    def test_baseline_std(self):
        baseline = Baseline()
        for v in [2, 4, 4, 4, 5, 5, 7, 9]:
            baseline.add(v)
        assert abs(baseline.std - 2.0) < 0.1

    def test_detect_anomaly_insufficient_data(self):
        detector = AnomalyDetector()
        result = detector.detect_anomalies("test", 100.0)
        assert result is None

    def test_detect_anomaly_normal(self):
        detector = AnomalyDetector()
        for v in [10, 10, 10, 10, 10]:
            detector.detect_anomalies("test", v)
        result = detector.detect_anomalies("test", 10.5)
        assert result is None or not result.is_anomaly

    def test_detect_anomaly_outlier(self):
        detector = AnomalyDetector(default_threshold=2.0)
        for v in [10, 10, 10, 10, 10]:
            detector.detect_anomalies("test", v)
        result = detector.detect_anomalies("test", 100.0)
        assert result is not None
        assert result.is_anomaly

    def test_get_anomalies(self):
        detector = AnomalyDetector(default_threshold=1.0)
        for v in [10, 10, 10, 10, 10]:
            detector.detect_anomalies("test", v)
        detector.detect_anomalies("test", 100.0)
        anomalies = detector.get_anomalies()
        assert len(anomalies) > 0

    def test_clear_anomalies(self):
        detector = AnomalyDetector(default_threshold=1.0)
        for v in [10, 10, 10, 10, 10]:
            detector.detect_anomalies("test", v)
        detector.detect_anomalies("test", 100.0)
        detector.clear_anomalies()
        assert len(detector.anomalies) == 0


class TestIntrusionPrevention:
    def test_init(self):
        ips = IntrusionPrevention()
        assert len(ips.rules) > 0
        assert len(ips.blocked_ips) == 0

    def test_block_ip(self):
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", "test block")
        assert ips.is_blocked("192.168.1.100")

    def test_unblock_ip(self):
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", "test block")
        assert ips.unblock("192.168.1.100")
        assert not ips.is_blocked("192.168.1.100")

    def test_block_expiration(self):
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", "test block", duration_seconds=-1)
        assert not ips.is_blocked("192.168.1.100")

    def test_add_rule(self):
        ips = IntrusionPrevention()
        rule = PreventionRule("test_rule", "test_condition", ActionType.ALERT)
        ips.add_rule(rule)
        assert any(r.name == "test_rule" for r in ips.rules)

    def test_remove_rule(self):
        ips = IntrusionPrevention()
        rule = PreventionRule("test_rule", "test_condition", ActionType.ALERT)
        ips.add_rule(rule)
        assert ips.remove_rule("test_rule")
        assert not any(r.name == "test_rule" for r in ips.rules)

    def test_evaluate_block(self):
        ips = IntrusionPrevention()
        action = ips.evaluate("192.168.1.100", "sql_injection")
        assert action == ActionType.BLOCK
        assert ips.is_blocked("192.168.1.100")

    def test_get_blocked_ips(self):
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", "test")
        blocked = ips.get_blocked_ips()
        assert len(blocked) == 1
        assert blocked[0].ip == "192.168.1.100"

    def test_get_stats(self):
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", "test")
        stats = ips.get_stats()
        assert stats.total_blocks == 1

    def test_clear_expired(self):
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", "test", duration_seconds=-1)
        cleared = ips.clear_expired()
        assert cleared == 1
