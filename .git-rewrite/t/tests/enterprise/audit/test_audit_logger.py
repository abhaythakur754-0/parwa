# Tests for Week 49 Builder 1 - Audit Logger
# Unit tests for audit_logger.py, audit_trail.py, audit_search.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from enterprise.audit.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditConfig,
    AuditEventType,
    AuditSeverity,
    AuditStatus
)

from enterprise.audit.audit_trail import (
    AuditTrailManager,
    AuditTrail,
    AuditTrailEntry,
    TrailStatus
)

from enterprise.audit.audit_search import (
    AuditSearchEngine,
    SearchQuery,
    SearchCondition,
    SearchOperator,
    SortOrder
)


# ============== AUDIT LOGGER TESTS ==============

class TestAuditLogger:
    def test_log_event(self):
        logger = AuditLogger()
        event = logger.log(
            tenant_id="t1",
            user_id="u1",
            event_type=AuditEventType.CREATE,
            resource_type="user",
            resource_id="123",
            action="create_user"
        )
        assert event.tenant_id == "t1"
        assert event.event_type == AuditEventType.CREATE

    def test_log_create(self):
        logger = AuditLogger()
        event = logger.log_create(
            tenant_id="t1",
            user_id="u1",
            resource_type="ticket",
            resource_id="T123",
            new_values={"title": "Test"}
        )
        assert event.event_type == AuditEventType.CREATE

    def test_log_update(self):
        logger = AuditLogger()
        event = logger.log_update(
            tenant_id="t1",
            user_id="u1",
            resource_type="ticket",
            resource_id="T123",
            old_values={"status": "open"},
            new_values={"status": "closed"}
        )
        assert event.event_type == AuditEventType.UPDATE

    def test_log_delete(self):
        logger = AuditLogger()
        event = logger.log_delete(
            tenant_id="t1",
            user_id="u1",
            resource_type="ticket",
            resource_id="T123",
            old_values={"title": "Test"}
        )
        assert event.event_type == AuditEventType.DELETE

    def test_log_read(self):
        logger = AuditLogger()
        event = logger.log_read(
            tenant_id="t1",
            user_id="u1",
            resource_type="report",
            resource_id="R123"
        )
        assert event.event_type == AuditEventType.READ

    def test_log_login_success(self):
        logger = AuditLogger()
        event = logger.log_login(
            tenant_id="t1",
            user_id="u1",
            ip_address="192.168.1.1",
            success=True
        )
        assert event.event_type == AuditEventType.LOGIN
        assert event.status == AuditStatus.SUCCESS

    def test_log_login_failure(self):
        logger = AuditLogger()
        event = logger.log_login(
            tenant_id="t1",
            user_id="u1",
            ip_address="192.168.1.1",
            success=False
        )
        assert event.status == AuditStatus.FAILURE

    def test_log_security_event(self):
        logger = AuditLogger()
        event = logger.log_security_event(
            tenant_id="t1",
            user_id="u1",
            description="Suspicious login attempt"
        )
        assert event.event_type == AuditEventType.SECURITY_EVENT
        assert event.severity == AuditSeverity.HIGH

    def test_sanitize_sensitive_fields(self):
        logger = AuditLogger()
        event = logger.log_create(
            tenant_id="t1",
            user_id="u1",
            resource_type="user",
            resource_id="123",
            new_values={"name": "John", "password": "secret123"}
        )
        assert event.new_values["password"] == "***REDACTED***"

    def test_get_event(self):
        logger = AuditLogger()
        created = logger.log_create("t1", "u1", "ticket", "T1", {})
        event = logger.get_event(created.id)
        assert event.id == created.id

    def test_get_events_by_tenant(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u1", "ticket", "T2", {})
        logger.log_create("t2", "u1", "ticket", "T3", {})

        events = logger.get_events_by_tenant("t1")
        assert len(events) == 2

    def test_get_events_by_user(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u2", "ticket", "T2", {})

        events = logger.get_events_by_user("u1")
        assert len(events) == 1

    def test_get_events_by_resource(self):
        logger = AuditLogger()
        logger.log_update("t1", "u1", "ticket", "T1", {}, {})
        logger.log_update("t1", "u1", "ticket", "T1", {}, {})
        logger.log_update("t1", "u1", "ticket", "T2", {}, {})

        events = logger.get_events_by_resource("ticket", "T1")
        assert len(events) == 2

    def test_get_events_by_correlation(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {}, correlation_id="corr1")
        logger.log_update("t1", "u1", "ticket", "T1", {}, {}, correlation_id="corr1")

        events = logger.get_events_by_correlation("corr1")
        assert len(events) == 2

    def test_get_metrics(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_update("t1", "u1", "ticket", "T1", {}, {})
        metrics = logger.get_metrics()
        assert metrics["total_events"] == 2

    def test_disabled_logging(self):
        config = AuditConfig(enabled=False)
        logger = AuditLogger(config)
        event = logger.log_create("t1", "u1", "ticket", "T1", {})
        assert event is None

    def test_register_hook(self):
        logger = AuditLogger()
        called = []
        def hook(event):
            called.append(event.id)
        
        logger.register_hook(hook)
        event = logger.log_create("t1", "u1", "ticket", "T1", {})
        assert len(called) == 1

    def test_export_events(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t2", "u1", "ticket", "T2", {})

        exported = logger.export_events("t1")
        assert len(exported) == 1
        assert exported[0]["tenant_id"] == "t1"


# ============== AUDIT TRAIL TESTS ==============

class TestAuditTrailManager:
    def test_create_trail(self):
        manager = AuditTrailManager()
        trail = manager.create_trail(
            tenant_id="t1",
            name="Test Trail",
            created_by="u1"
        )
        assert trail.tenant_id == "t1"
        assert trail.status == TrailStatus.ACTIVE

    def test_add_entry(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        entry = manager.add_entry(trail.id, "event1")
        
        assert entry is not None
        assert entry.sequence_number == 1
        assert len(trail.entries) == 1

    def test_multiple_entries(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        manager.add_entry(trail.id, "event1")
        manager.add_entry(trail.id, "event2")
        manager.add_entry(trail.id, "event3")
        
        assert len(trail.entries) == 3
        assert trail.entries[2].sequence_number == 3

    def test_checksum_chain(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        entry1 = manager.add_entry(trail.id, "event1")
        entry2 = manager.add_entry(trail.id, "event2")
        
        assert entry1.previous_checksum == ""
        assert entry2.previous_checksum == entry1.checksum

    def test_close_trail(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        result = manager.close_trail(trail.id)
        
        assert result is True
        assert trail.status == TrailStatus.CLOSED
        assert trail.end_time is not None

    def test_close_nonexistent_trail(self):
        manager = AuditTrailManager()
        result = manager.close_trail("nonexistent")
        assert result is False

    def test_archive_trail(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        manager.close_trail(trail.id)
        result = manager.archive_trail(trail.id)
        
        assert result is True
        assert trail.status == TrailStatus.ARCHIVED

    def test_archive_active_trail_fails(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        result = manager.archive_trail(trail.id)
        assert result is False

    def test_get_trail(self):
        manager = AuditTrailManager()
        created = manager.create_trail("t1", "Test")
        trail = manager.get_trail(created.id)
        assert trail.id == created.id

    def test_get_tenant_trails(self):
        manager = AuditTrailManager()
        manager.create_trail("t1", "Trail1")
        manager.create_trail("t1", "Trail2")
        manager.create_trail("t2", "Trail3")

        trails = manager.get_tenant_trails("t1")
        assert len(trails) == 2

    def test_get_tenant_trails_by_status(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Trail1")
        manager.create_trail("t1", "Trail2")
        manager.close_trail(trail.id)

        active = manager.get_tenant_trails("t1", TrailStatus.ACTIVE)
        assert len(active) == 1

    def test_verify_trail_integrity(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        manager.add_entry(trail.id, "event1")
        manager.add_entry(trail.id, "event2")

        result = manager.verify_trail_integrity(trail.id)
        assert result["valid"] is True

    def test_get_trail_timeline(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        manager.add_entry(trail.id, "event1")
        manager.add_entry(trail.id, "event2")

        timeline = manager.get_trail_timeline(trail.id)
        assert len(timeline) == 2

    def test_get_entry_count(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        manager.add_entry(trail.id, "event1")
        manager.add_entry(trail.id, "event2")

        count = manager.get_entry_count(trail.id)
        assert count == 2

    def test_get_metrics(self):
        manager = AuditTrailManager()
        manager.create_trail("t1", "Trail1")
        manager.create_trail("t1", "Trail2")

        metrics = manager.get_metrics()
        assert metrics["total_trails"] == 2
        assert metrics["active_trails"] == 2

    def test_export_trail(self):
        manager = AuditTrailManager()
        trail = manager.create_trail("t1", "Test")
        manager.add_entry(trail.id, "event1")

        exported = manager.export_trail(trail.id)
        assert exported["trail_id"] == trail.id
        assert len(exported["entries"]) == 1


# ============== AUDIT SEARCH TESTS ==============

class TestAuditSearchEngine:
    def test_search_basic(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u2", "ticket", "T2", {})

        search = AuditSearchEngine(logger)
        query = SearchQuery(limit=10)
        result = search.search(query)

        assert result.total == 2
        assert len(result.items) == 2

    def test_search_with_condition(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u2", "ticket", "T2", {})

        search = AuditSearchEngine(logger)
        query = SearchQuery(
            conditions=[
                SearchCondition("user_id", SearchOperator.EQUALS, "u1")
            ]
        )
        result = search.search(query)

        assert result.total == 1

    def test_search_contains(self):
        logger = AuditLogger()
        logger.log("t1", "u1", AuditEventType.CREATE, "ticket", "T1", "create_test_ticket")
        logger.log("t1", "u1", AuditEventType.CREATE, "ticket", "T2", "create_demo_ticket")

        search = AuditSearchEngine(logger)
        query = SearchQuery(
            conditions=[
                SearchCondition("action", SearchOperator.CONTAINS, "test")
            ]
        )
        result = search.search(query)

        assert result.total == 1

    def test_search_in_operator(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u2", "ticket", "T2", {})
        logger.log_create("t1", "u3", "ticket", "T3", {})

        search = AuditSearchEngine(logger)
        query = SearchQuery(
            conditions=[
                SearchCondition("user_id", SearchOperator.IN, ["u1", "u2"])
            ]
        )
        result = search.search(query)

        assert result.total == 2

    def test_search_sort_asc(self):
        logger = AuditLogger()
        logger.log_create("t1", "u3", "ticket", "T1", {})
        logger.log_create("t1", "u1", "ticket", "T2", {})
        logger.log_create("t1", "u2", "ticket", "T3", {})

        search = AuditSearchEngine(logger)
        query = SearchQuery(
            sort_by="user_id",
            sort_order=SortOrder.ASC
        )
        result = search.search(query)

        assert result.items[0].user_id == "u1"

    def test_search_sort_desc(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u3", "ticket", "T2", {})
        logger.log_create("t1", "u2", "ticket", "T3", {})

        search = AuditSearchEngine(logger)
        query = SearchQuery(
            sort_by="user_id",
            sort_order=SortOrder.DESC
        )
        result = search.search(query)

        assert result.items[0].user_id == "u3"

    def test_search_pagination(self):
        logger = AuditLogger()
        for i in range(25):
            logger.log_create("t1", "u1", "ticket", f"T{i}", {})

        search = AuditSearchEngine(logger)
        query = SearchQuery(limit=10, offset=0)
        result = search.search(query)

        assert len(result.items) == 10
        assert result.has_more is True

    def test_quick_search(self):
        logger = AuditLogger()
        logger.log("t1", "u1", AuditEventType.CREATE, "ticket", "T1", "create_important_ticket")
        logger.log("t1", "u1", AuditEventType.CREATE, "ticket", "T2", "create_normal_ticket")

        search = AuditSearchEngine(logger)
        results = search.quick_search("t1", "important")

        assert len(results) == 1

    def test_search_by_time_range(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})

        search = AuditSearchEngine(logger)
        now = datetime.utcnow()
        results = search.search_by_time_range(
            "t1",
            now - timedelta(hours=1),
            now + timedelta(hours=1)
        )
        assert len(results) >= 1

    def test_search_by_user(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u2", "ticket", "T2", {})

        search = AuditSearchEngine(logger)
        results = search.search_by_user("t1", "u1")
        assert len(results) == 1

    def test_search_by_resource(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})
        logger.log_create("t1", "u1", "report", "R1", {})

        search = AuditSearchEngine(logger)
        results = search.search_by_resource("t1", "ticket")
        assert len(results) == 1

    def test_get_metrics(self):
        logger = AuditLogger()
        logger.log_create("t1", "u1", "ticket", "T1", {})

        search = AuditSearchEngine(logger)
        metrics = search.get_metrics()
        assert "total_searches" in metrics
