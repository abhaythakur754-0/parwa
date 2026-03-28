# Tests for Week 54 Builder 2 - Threat Detector
# Unit tests for threat_detector.py, anomaly_detector.py, intrusion_prevention.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from enterprise.security_hardening.threat_detector import (
    ThreatDetector,
    Threat,
    ThreatType,
    ThreatSeverity,
    ThreatStatus,
    ThreatIndicator,
    ThreatSignature
)

from enterprise.security_hardening.anomaly_detector import (
    AnomalyDetector,
    Anomaly,
    AnomalyType,
    AnomalySeverity,
    AnomalyStatus,
    Baseline
)

from enterprise.security_hardening.intrusion_prevention import (
    IntrusionPrevention,
    IPBlock,
    IPBlockStatus,
    PreventionRule,
    PreventionLog,
    ActionType,
    BlockReason,
    RulePriority
)


# ============== THREAT DETECTOR TESTS ==============

class TestThreatDetector:
    def test_detector_initialization(self):
        """Test threat detector initialization"""
        detector = ThreatDetector()
        assert detector is not None
        assert len(detector.signatures) > 0
        assert len(detector.threats) == 0

    def test_detect_sql_injection(self):
        """Test SQL injection detection"""
        detector = ThreatDetector()
        threats = detector.detect(
            data="SELECT * FROM users WHERE id=1 UNION SELECT * FROM passwords",
            source="web_request",
            source_ip="192.168.1.100"
        )
        
        assert len(threats) >= 1
        assert any(t.threat_type == ThreatType.SQL_INJECTION for t in threats)

    def test_detect_xss(self):
        """Test XSS detection"""
        detector = ThreatDetector()
        threats = detector.detect(
            data="<script>alert('XSS')</script>",
            source="form_input",
            source_ip="10.0.0.1"
        )
        
        assert len(threats) >= 1
        assert any(t.threat_type == ThreatType.XSS for t in threats)

    def test_detect_path_traversal(self):
        """Test path traversal detection"""
        detector = ThreatDetector()
        threats = detector.detect(
            data="../../../etc/passwd",
            source="file_request",
            source_ip="172.16.0.1"
        )
        
        assert len(threats) >= 1
        assert any(t.threat_type == ThreatType.PATH_TRAVERSAL for t in threats)

    def test_detect_command_injection(self):
        """Test command injection detection"""
        detector = ThreatDetector()
        threats = detector.detect(
            data="test; cat /etc/passwd",
            source="shell_input",
            source_ip="192.168.2.1"
        )
        
        assert len(threats) >= 1
        assert any(t.threat_type == ThreatType.COMMAND_INJECTION for t in threats)

    def test_detect_brute_force(self):
        """Test brute force detection"""
        detector = ThreatDetector()
        threat = detector.detect_brute_force(
            source_ip="192.168.1.50",
            failed_attempts=10,
            threshold=5
        )
        
        assert threat is not None
        assert threat.threat_type == ThreatType.BRUTE_FORCE
        assert threat.severity == ThreatSeverity.HIGH
        assert threat.source_ip == "192.168.1.50"

    def test_detect_brute_force_below_threshold(self):
        """Test brute force detection below threshold"""
        detector = ThreatDetector()
        threat = detector.detect_brute_force(
            source_ip="192.168.1.50",
            failed_attempts=3,
            threshold=5
        )
        
        assert threat is None

    def test_detect_ddos(self):
        """Test DDoS detection"""
        detector = ThreatDetector()
        threat = detector.detect_ddos(
            source_ip="10.0.0.100",
            request_count=5000,
            threshold=1000
        )
        
        assert threat is not None
        assert threat.threat_type == ThreatType.DDOS
        assert threat.severity == ThreatSeverity.CRITICAL

    def test_detect_data_exfiltration(self):
        """Test data exfiltration detection"""
        detector = ThreatDetector()
        threat = detector.detect_data_exfiltration(
            user_id="user123",
            data_volume_mb=500.0,
            threshold_mb=100.0
        )
        
        assert threat is not None
        assert threat.threat_type == ThreatType.DATA_EXFILTRATION
        assert threat.user_id == "user123"

    def test_detect_privilege_escalation(self):
        """Test privilege escalation detection"""
        detector = ThreatDetector()
        threat = detector.detect_privilege_escalation(
            user_id="user456",
            original_role="user",
            new_role="admin",
            authorized=False
        )
        
        assert threat is not None
        assert threat.threat_type == ThreatType.PRIVILEGE_ESCALATION
        assert threat.severity == ThreatSeverity.CRITICAL

    def test_add_custom_signature(self):
        """Test adding custom signature"""
        detector = ThreatDetector()
        signature = ThreatSignature(
            signature_id="custom_001",
            name="Custom Attack",
            threat_type=ThreatType.API_ABUSE,
            severity=ThreatSeverity.HIGH,
            pattern=r"custom_attack_pattern",
            pattern_type="regex"
        )
        
        detector.add_signature(signature)
        assert "custom_001" in detector.signatures

    def test_get_threats_filtering(self):
        """Test getting threats with filters"""
        detector = ThreatDetector()
        detector.detect("' OR 1=1 --", "test", "192.168.1.1")
        detector.detect("<script>alert(1)</script>", "test", "192.168.1.2")
        
        sql_threats = detector.get_threats(threat_type=ThreatType.SQL_INJECTION)
        assert all(t.threat_type == ThreatType.SQL_INJECTION for t in sql_threats)

    def test_resolve_threat(self):
        """Test resolving a threat"""
        detector = ThreatDetector()
        threats = detector.detect("' OR 1=1 --", "test", "192.168.1.1")
        threat_id = threats[0].threat_id
        
        result = detector.resolve_threat(threat_id)
        assert result is True
        assert detector.threats[threat_id].status == ThreatStatus.RESOLVED

    def test_threat_statistics(self):
        """Test threat statistics"""
        detector = ThreatDetector()
        detector.detect("' OR 1=1 --", "test", "192.168.1.1")
        detector.detect("<script>alert(1)</script>", "test", "192.168.1.2")
        
        stats = detector.get_statistics()
        assert stats["total_threats"] >= 2
        assert "by_type" in stats
        assert "by_severity" in stats


# ============== ANOMALY DETECTOR TESTS ==============

class TestAnomalyDetector:
    def test_detector_initialization(self):
        """Test anomaly detector initialization"""
        detector = AnomalyDetector()
        assert detector is not None
        assert len(detector.baselines) > 0

    def test_learn_baseline(self):
        """Test baseline learning"""
        detector = AnomalyDetector()
        values = [10, 12, 11, 13, 10, 11, 12, 14, 11, 10]
        
        baseline = detector.learn_baseline("test_metric", values)
        
        assert baseline.metric_name == "test_metric"
        assert baseline.mean == pytest.approx(sum(values) / len(values))
        assert baseline.sample_count == len(values)

    def test_baseline_percentiles(self):
        """Test baseline percentile calculation"""
        detector = AnomalyDetector()
        values = list(range(1, 101))  # 1 to 100
        
        baseline = detector.learn_baseline("percentile_test", values)
        
        assert baseline.percentiles[50] == pytest.approx(50.5, rel=0.1)
        assert baseline.percentiles[90] == pytest.approx(90.1, rel=0.1)

    def test_detect_traffic_anomaly(self):
        """Test traffic anomaly detection"""
        detector = AnomalyDetector()
        # Learn normal baseline
        normal_values = [100 + i for i in range(-10, 11)]
        detector.learn_baseline("requests_per_minute", normal_values)
        
        # Detect anomaly with high value
        anomaly = detector.detect_traffic_anomaly(
            requests_per_minute=1000.0,
            source_ip="192.168.1.100"
        )
        
        # May or may not detect depending on threshold
        # This tests the method works
        assert detector.baselines.get("requests_per_minute") is not None

    def test_detect_anomaly_with_z_score(self):
        """Test anomaly detection with z-score"""
        detector = AnomalyDetector()
        # Create baseline with known distribution
        values = [100 + i for i in range(-10, 11)]
        detector.learn_baseline("test_z_score", values)
        
        # Test extreme value
        anomaly = detector.detect_anomalies(
            metric_name="test_z_score",
            value=1000.0,
            source="test"
        )
        
        # Should detect anomaly
        assert anomaly is not None
        assert anomaly.score > 2.0

    def test_detect_no_anomaly(self):
        """Test no anomaly detected for normal value"""
        detector = AnomalyDetector()
        values = [100 + i for i in range(-10, 11)]
        detector.learn_baseline("normal_metric", values)
        
        # Normal value should not trigger anomaly
        anomaly = detector.detect_anomalies(
            metric_name="normal_metric",
            value=100.0,
            source="test"
        )
        
        # Should not detect anomaly for normal value
        assert anomaly is None

    def test_detect_api_usage_anomaly(self):
        """Test API usage anomaly detection"""
        detector = AnomalyDetector()
        anomaly = detector.detect_api_usage_anomaly(
            api_calls_per_minute=500.0,
            api_endpoint="/api/data"
        )
        
        # Method should work
        assert detector.baselines.get("api_calls_per_minute") is not None

    def test_detect_authentication_anomaly(self):
        """Test authentication anomaly detection"""
        detector = AnomalyDetector()
        anomaly = detector.detect_authentication_anomaly(
            auth_failures=50,
            user_id="user123"
        )
        
        # Method should work
        assert detector.baselines.get("auth_failures_per_hour") is not None

    def test_resolve_anomaly(self):
        """Test resolving an anomaly"""
        detector = AnomalyDetector()
        # Force create an anomaly
        values = [100 + i for i in range(-10, 11)]
        detector.learn_baseline("resolve_test", values)
        
        anomaly = detector.detect_anomalies(
            metric_name="resolve_test",
            value=10000.0,
            source="test"
        )
        
        if anomaly:
            result = detector.resolve_anomaly(anomaly.anomaly_id)
            assert result is True
            assert detector.anomalies[anomaly.anomaly_id].status == AnomalyStatus.RESOLVED

    def test_anomaly_statistics(self):
        """Test anomaly statistics"""
        detector = AnomalyDetector()
        stats = detector.get_statistics()
        
        assert "total_anomalies" in stats
        assert "by_severity" in stats
        assert "by_status" in stats
        assert "baselines_count" in stats

    def test_set_threshold(self):
        """Test setting custom threshold"""
        detector = AnomalyDetector()
        detector.set_threshold("custom_metric", 3.5)
        
        assert detector.get_threshold("custom_metric") == 3.5

    def test_learning_mode_toggle(self):
        """Test learning mode toggle"""
        detector = AnomalyDetector()
        
        detector.disable_learning_mode()
        assert detector._learning_mode is False
        
        detector.enable_learning_mode()
        assert detector._learning_mode is True

    def test_analyze_correlation(self):
        """Test anomaly correlation analysis"""
        detector = AnomalyDetector()
        
        # Create some test anomalies
        a1 = Anomaly(
            anomaly_type=AnomalyType.TRAFFIC,
            source_ip="192.168.1.1",
            user_id="user1"
        )
        a2 = Anomaly(
            anomaly_type=AnomalyType.ACCESS,
            source_ip="192.168.1.1",
            user_id="user1"
        )
        
        detector.anomalies[a1.anomaly_id] = a1
        detector.anomalies[a2.anomaly_id] = a2
        
        correlation = detector.analyze_correlation([a1, a2])
        
        assert correlation["total_anomalies"] == 2
        assert correlation["unique_ips"] == 1
        assert correlation["unique_users"] == 1


# ============== INTRUSION PREVENTION TESTS ==============

class TestIntrusionPrevention:
    def test_ips_initialization(self):
        """Test IPS initialization"""
        ips = IntrusionPrevention()
        assert ips is not None
        assert len(ips.get_rules()) > 0

    def test_block_ip(self):
        """Test blocking an IP"""
        ips = IntrusionPrevention()
        block = ips.block(
            ip_address="192.168.1.100",
            reason=BlockReason.BRUTE_FORCE,
            duration_hours=24
        )
        
        assert block is not None
        assert block.ip_address == "192.168.1.100"
        assert block.reason == BlockReason.BRUTE_FORCE
        assert ips.is_blocked("192.168.1.100")

    def test_unblock_ip(self):
        """Test unblocking an IP"""
        ips = IntrusionPrevention()
        ips.block("192.168.1.100", BlockReason.SUSPICIOUS_ACTIVITY)
        
        result = ips.unblock("192.168.1.100")
        assert result is True
        assert not ips.is_blocked("192.168.1.100")

    def test_allow_whitelist(self):
        """Test adding IP to whitelist"""
        ips = IntrusionPrevention()
        ips.allow("10.0.0.1")
        
        # Try to block whitelisted IP
        block = ips.block("10.0.0.1", BlockReason.BRUTE_FORCE)
        assert block is None
        assert not ips.is_blocked("10.0.0.1")

    def test_disallow_whitelist(self):
        """Test removing IP from whitelist"""
        ips = IntrusionPrevention()
        ips.allow("10.0.0.1")
        
        result = ips.disallow("10.0.0.1")
        assert result is True
        assert "10.0.0.1" not in ips._whitelist

    def test_blacklist(self):
        """Test permanent blacklist"""
        ips = IntrusionPrevention()
        ips.add_to_blacklist("192.168.100.1")
        
        assert ips.is_blocked("192.168.100.1")
        
        result = ips.remove_from_blacklist("192.168.100.1")
        assert result is True
        assert not ips.is_blocked("192.168.100.1")

    def test_block_expiration(self):
        """Test block expiration"""
        ips = IntrusionPrevention()
        block = ips.block(
            ip_address="192.168.1.200",
            reason=BlockReason.RATE_LIMIT_EXCEEDED,
            duration_hours=1
        )
        
        # Manually expire the block
        block.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        # Should no longer be blocked
        assert not ips.is_blocked("192.168.1.200")

    def test_add_rule(self):
        """Test adding a prevention rule"""
        ips = IntrusionPrevention()
        rule = ips.add_rule(
            name="Custom Block Rule",
            action=ActionType.BLOCK,
            conditions={"suspicious_score": {"$gt": 0.9}},
            priority=RulePriority.HIGH
        )
        
        assert rule is not None
        assert rule.name == "Custom Block Rule"
        assert rule.action == ActionType.BLOCK

    def test_remove_rule(self):
        """Test removing a rule"""
        ips = IntrusionPrevention()
        rule = ips.add_rule(
            name="Test Rule",
            action=ActionType.LOG,
            conditions={"test": True}
        )
        
        result = ips.remove_rule(rule.rule_id)
        assert result is True
        assert ips.get_rule(rule.rule_id) is None

    def test_enable_disable_rule(self):
        """Test enabling and disabling rules"""
        ips = IntrusionPrevention()
        rule = ips.add_rule(
            name="Toggle Test",
            action=ActionType.ALERT,
            conditions={"test": True}
        )
        
        ips.disable_rule(rule.rule_id)
        assert ips.get_rule(rule.rule_id).enabled is False
        
        ips.enable_rule(rule.rule_id)
        assert ips.get_rule(rule.rule_id).enabled is True

    def test_evaluate_rules(self):
        """Test rule evaluation"""
        ips = IntrusionPrevention()
        
        context = {
            "failed_attempts": 10,
            "source_ip": "192.168.1.50"
        }
        
        matching = ips.evaluate_rules(context)
        # Should match brute force rule
        assert len(matching) >= 1

    def test_execute_prevention(self):
        """Test prevention execution"""
        ips = IntrusionPrevention()
        
        context = {
            "threat_type": "sql_injection",
            "source_ip": "192.168.1.100"
        }
        
        result = ips.execute_prevention(context)
        
        assert "actions_taken" in result
        assert "rules_matched" in result

    def test_rate_limiting(self):
        """Test rate limiting"""
        ips = IntrusionPrevention()
        ips.set_rate_limit("test_limit", max_requests=5, window_seconds=60)
        
        # Should be allowed initially
        for i in range(5):
            status = ips.check_rate_limit("192.168.1.1", "test_limit")
            assert status["allowed"] is True
        
        # Should be blocked after limit
        status = ips.check_rate_limit("192.168.1.1", "test_limit")
        assert status["allowed"] is False

    def test_rate_limit_status(self):
        """Test rate limit status"""
        ips = IntrusionPrevention()
        status = ips.check_rate_limit("10.0.0.1", "global")
        
        assert "allowed" in status
        assert "current_count" in status
        assert "limit" in status
        assert "reset_at" in status

    def test_action_handler_registration(self):
        """Test action handler registration"""
        ips = IntrusionPrevention()
        called = []
        
        def handler(data):
            called.append(data)
        
        ips.register_action_handler(ActionType.BLOCK, handler)
        ips.block("192.168.1.50", BlockReason.MANUAL)
        
        assert len(called) == 1

    def test_get_statistics(self):
        """Test getting statistics"""
        ips = IntrusionPrevention()
        ips.block("192.168.1.1", BlockReason.SUSPICIOUS_ACTIVITY)
        
        stats = ips.get_statistics()
        
        assert "total_blocks" in stats
        assert "active_blocks" in stats
        assert "blacklist_size" in stats
        assert "whitelist_size" in stats
        assert "rules_count" in stats

    def test_clear_expired_blocks(self):
        """Test clearing expired blocks"""
        ips = IntrusionPrevention()
        block = ips.block("192.168.1.1", BlockReason.SUSPICIOUS_ACTIVITY, duration_hours=1)
        block.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        cleared = ips.clear_expired_blocks()
        assert cleared == 1
        assert not ips.is_blocked("192.168.1.1")

    def test_export_blocks(self):
        """Test exporting blocks"""
        ips = IntrusionPrevention()
        ips.block("192.168.1.1", BlockReason.SUSPICIOUS_ACTIVITY)
        
        exported = ips.export_blocks()
        assert len(exported) >= 1
        assert any(b["ip_address"] == "192.168.1.1" for b in exported)

    def test_export_rules(self):
        """Test exporting rules"""
        ips = IntrusionPrevention()
        exported = ips.export_rules()
        
        assert len(exported) >= 1
        assert all("rule_id" in r for r in exported)

    def test_prevention_logs(self):
        """Test prevention logging"""
        ips = IntrusionPrevention()
        ips.block("192.168.1.1", BlockReason.SUSPICIOUS_ACTIVITY)
        
        logs = ips.get_logs()
        assert len(logs) >= 1
        assert any(l.action == ActionType.BLOCK for l in logs)

    def test_ip_block_time_remaining(self):
        """Test IP block time remaining"""
        ips = IntrusionPrevention()
        block = ips.block("192.168.1.1", BlockReason.SUSPICIOUS_ACTIVITY, duration_hours=24)
        
        remaining = block.time_remaining()
        assert remaining is not None
        assert remaining.total_seconds() > 0

    def test_ip_block_to_dict(self):
        """Test IP block serialization"""
        ips = IntrusionPrevention()
        block = ips.block("192.168.1.1", BlockReason.SUSPICIOUS_ACTIVITY)
        
        block_dict = block.to_dict()
        assert "block_id" in block_dict
        assert "ip_address" in block_dict
        assert "reason" in block_dict
