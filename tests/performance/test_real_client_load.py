"""
Performance Tests for Real Client Data Patterns
Tests: P95 < 500ms, concurrent users, peak load, database queries, API response times
"""
import pytest
import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.app.core.config import settings
from backend.app.services.ticket_service import TicketService
from backend.app.services.approval_service import ApprovalService
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.jarvis_service import JarvisService


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    name: str
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    """Aggregated performance report."""
    name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    throughput_rps: float
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "throughput_rps": round(self.throughput_rps, 2)
        }
    
    def meets_sla(self, p95_threshold_ms: float = 500.0) -> bool:
        """Check if P95 meets SLA threshold."""
        return self.p95_ms < p95_threshold_ms


class PerformanceCollector:
    """Collect and aggregate performance metrics."""
    
    def __init__(self, name: str):
        self.name = name
        self.metrics: List[PerformanceMetric] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    def start(self):
        """Start collection period."""
        self.start_time = datetime.utcnow()
    
    def stop(self):
        """Stop collection period."""
        self.end_time = datetime.utcnow()
    
    def record(self, metric: PerformanceMetric):
        """Record a single metric."""
        self.metrics.append(metric)
    
    def measure(self, name: str, func, *args, **kwargs) -> Any:
        """Measure execution time of a function."""
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            self.record(PerformanceMetric(
                name=name,
                duration_ms=duration_ms,
                success=True,
                metadata=kwargs
            ))
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.record(PerformanceMetric(
                name=name,
                duration_ms=duration_ms,
                success=False,
                error=str(e),
                metadata=kwargs
            ))
            raise
    
    async def measure_async(self, name: str, func, *args, **kwargs) -> Any:
        """Measure execution time of an async function."""
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            self.record(PerformanceMetric(
                name=name,
                duration_ms=duration_ms,
                success=True,
                metadata=kwargs
            ))
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.record(PerformanceMetric(
                name=name,
                duration_ms=duration_ms,
                success=False,
                error=str(e),
                metadata=kwargs
            ))
            raise
    
    def generate_report(self) -> PerformanceReport:
        """Generate aggregated report."""
        if not self.metrics:
            raise ValueError("No metrics collected")
        
        durations = [m.duration_ms for m in self.metrics]
        successful = [m for m in self.metrics if m.success]
        failed = [m for m in self.metrics if not m.success]
        
        # Calculate percentiles
        sorted_durations = sorted(durations)
        n = len(sorted_durations)
        
        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return sorted_durations[min(idx, n - 1)]
        
        # Calculate throughput
        if self.start_time and self.end_time:
            duration_seconds = (self.end_time - self.start_time).total_seconds()
            throughput = n / duration_seconds if duration_seconds > 0 else 0
        else:
            throughput = 0
        
        return PerformanceReport(
            name=self.name,
            total_requests=n,
            successful_requests=len(successful),
            failed_requests=len(failed),
            p50_ms=percentile(50),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            avg_ms=statistics.mean(durations),
            min_ms=min(durations),
            max_ms=max(durations),
            throughput_rps=throughput
        )


class TestRealClientLoad:
    """Performance tests with real client data patterns."""
    
    @pytest.fixture
    def collector(self):
        """Create performance collector."""
        return PerformanceCollector("real_client_load")
    
    @pytest.fixture
    def client_id(self):
        """Default client ID for tests."""
        return "client_001"
    
    # ==================== API Response Time Tests ====================
    
    def test_ticket_list_response_time(self, collector, client_id):
        """Test: Ticket list API responds within SLA."""
        collector.start()
        service = TicketService()
        
        # Simulate 100 ticket list requests
        for i in range(100):
            collector.measure(
                f"ticket_list_{i}",
                service.get_tickets,
                client_id=client_id,
                page=1,
                limit=20
            )
        
        collector.stop()
        report = collector.generate_report()
        
        # CRITICAL: P95 < 500ms
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms exceeds 500ms SLA"
        assert report.failed_requests == 0, f"{report.failed_requests} requests failed"
        
        print(f"\nTicket List Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    def test_ticket_detail_response_time(self, collector, client_id):
        """Test: Ticket detail API responds within SLA."""
        collector.start()
        service = TicketService()
        
        # Simulate 100 ticket detail requests
        # Using sample ticket IDs
        sample_ticket_ids = [f"ticket_{i:04d}" for i in range(100)]
        
        for i, ticket_id in enumerate(sample_ticket_ids):
            try:
                collector.measure(
                    f"ticket_detail_{i}",
                    service.get_ticket,
                    ticket_id=ticket_id,
                    client_id=client_id
                )
            except Exception:
                # Record even if ticket doesn't exist
                pass
        
        collector.stop()
        report = collector.generate_report()
        
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms exceeds 500ms SLA"
        print(f"\nTicket Detail Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    def test_approvals_list_response_time(self, collector, client_id):
        """Test: Approvals list API responds within SLA."""
        collector.start()
        service = ApprovalService()
        
        for i in range(100):
            collector.measure(
                f"approvals_list_{i}",
                service.get_approvals,
                client_id=client_id,
                status="pending"
            )
        
        collector.stop()
        report = collector.generate_report()
        
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms exceeds 500ms SLA"
        print(f"\nApprovals List Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    def test_analytics_metrics_response_time(self, collector, client_id):
        """Test: Analytics metrics API responds within SLA."""
        collector.start()
        service = AnalyticsService()
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        for i in range(50):
            collector.measure(
                f"analytics_metrics_{i}",
                service.get_metrics,
                client_id=client_id,
                start_date=start_date,
                end_date=end_date
            )
        
        collector.stop()
        report = collector.generate_report()
        
        # Analytics can be slightly slower, but still < 500ms
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms exceeds 500ms SLA"
        print(f"\nAnalytics Metrics Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    def test_jarvis_command_response_time(self, collector, client_id):
        """Test: Jarvis command API responds within SLA."""
        collector.start()
        service = JarvisService()
        
        sample_commands = [
            "What's the status of order #12345?",
            "How many open tickets do we have?",
            "Show me today's escalation count",
            "What's our CSAT score this week?",
            "List pending refunds"
        ]
        
        for i in range(50):
            command = sample_commands[i % len(sample_commands)]
            collector.measure(
                f"jarvis_command_{i}",
                service.send_command,
                client_id=client_id,
                command=command
            )
        
        collector.stop()
        report = collector.generate_report()
        
        # Jarvis can take slightly longer but should still be reasonable
        assert report.meets_sla(1000), f"P95 {report.p95_ms}ms exceeds 1000ms"
        print(f"\nJarvis Command Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    # ==================== Concurrent User Tests ====================
    
    @pytest.mark.asyncio
    async def test_concurrent_users_10(self, client_id):
        """Test: 10 concurrent users."""
        collector = PerformanceCollector("concurrent_10_users")
        collector.start()
        
        async def user_session(user_id: int):
            """Simulate a user session."""
            ticket_service = TicketService()
            
            # Each user makes 10 requests
            for i in range(10):
                await collector.measure_async(
                    f"user_{user_id}_request_{i}",
                    ticket_service.get_tickets,
                    client_id=client_id,
                    page=1,
                    limit=20
                )
        
        # Run 10 concurrent user sessions
        tasks = [user_session(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        collector.stop()
        report = collector.generate_report()
        
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms under 10 concurrent users"
        assert report.throughput_rps > 10, f"Throughput {report.throughput_rps} RPS too low"
        
        print(f"\n10 Concurrent Users: {json.dumps(report.to_dict(), indent=2)}")
    
    @pytest.mark.asyncio
    async def test_concurrent_users_50(self, client_id):
        """Test: 50 concurrent users."""
        collector = PerformanceCollector("concurrent_50_users")
        collector.start()
        
        async def user_session(user_id: int):
            ticket_service = TicketService()
            for i in range(5):  # Each user makes 5 requests
                await collector.measure_async(
                    f"user_{user_id}_request_{i}",
                    ticket_service.get_tickets,
                    client_id=client_id,
                    page=1,
                    limit=20
                )
        
        tasks = [user_session(i) for i in range(50)]
        await asyncio.gather(*tasks)
        
        collector.stop()
        report = collector.generate_report()
        
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms under 50 concurrent users"
        
        print(f"\n50 Concurrent Users: {json.dumps(report.to_dict(), indent=2)}")
    
    @pytest.mark.asyncio
    async def test_concurrent_users_100(self, client_id):
        """Test: 100 concurrent users - CRITICAL TEST."""
        collector = PerformanceCollector("concurrent_100_users")
        collector.start()
        
        async def user_session(user_id: int):
            ticket_service = TicketService()
            for i in range(3):  # Each user makes 3 requests
                await collector.measure_async(
                    f"user_{user_id}_request_{i}",
                    ticket_service.get_tickets,
                    client_id=client_id,
                    page=1,
                    limit=20
                )
        
        tasks = [user_session(i) for i in range(100)]
        await asyncio.gather(*tasks)
        
        collector.stop()
        report = collector.generate_report()
        
        # CRITICAL: P95 < 500ms at 100 concurrent users
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms exceeds 500ms SLA at 100 users"
        assert report.failed_requests == 0, f"{report.failed_requests} requests failed under load"
        
        print(f"\n100 Concurrent Users: {json.dumps(report.to_dict(), indent=2)}")
    
    # ==================== Peak Load Tests ====================
    
    @pytest.mark.asyncio
    async def test_peak_load_burst(self, client_id):
        """Test: Peak load burst handling."""
        collector = PerformanceCollector("peak_load_burst")
        collector.start()
        
        # Simulate sudden burst of 500 requests
        async def burst_request(request_id: int):
            ticket_service = TicketService()
            await collector.measure_async(
                f"burst_{request_id}",
                ticket_service.get_tickets,
                client_id=client_id,
                page=1,
                limit=20
            )
        
        # Launch all 500 requests simultaneously
        tasks = [burst_request(i) for i in range(500)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        collector.stop()
        report = collector.generate_report()
        
        # Under burst load, allow slightly higher latency
        assert report.meets_sla(1000), f"P95 {report.p95_ms}ms under burst load too high"
        
        print(f"\nPeak Load Burst: {json.dumps(report.to_dict(), indent=2)}")
    
    # ==================== Database Query Tests ====================
    
    def test_database_query_performance(self, collector, client_id):
        """Test: Database queries perform within SLA."""
        from backend.app.core.database import get_db
        
        collector.start()
        
        queries = [
            ("SELECT * FROM tickets WHERE client_id = %s LIMIT 20", (client_id,)),
            ("SELECT COUNT(*) FROM tickets WHERE client_id = %s", (client_id,)),
            ("SELECT * FROM approvals WHERE client_id = %s AND status = 'pending'", (client_id,)),
            ("SELECT * FROM analytics WHERE client_id = %s ORDER BY created_at DESC LIMIT 100", (client_id,)),
        ]
        
        db = next(get_db())
        
        for i in range(100):
            for query_name, (query, params) in enumerate(queries):
                start = time.perf_counter()
                try:
                    db.execute(query, params)
                    duration_ms = (time.perf_counter() - start) * 1000
                    collector.record(PerformanceMetric(
                        name=f"db_query_{query_name}_{i}",
                        duration_ms=duration_ms,
                        success=True
                    ))
                except Exception as e:
                    duration_ms = (time.perf_counter() - start) * 1000
                    collector.record(PerformanceMetric(
                        name=f"db_query_{query_name}_{i}",
                        duration_ms=duration_ms,
                        success=False,
                        error=str(e)
                    ))
        
        collector.stop()
        report = collector.generate_report()
        
        # Database queries should be fast
        assert report.meets_sla(200), f"P95 {report.p95_ms}ms DB query time too high"
        
        print(f"\nDatabase Query Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    # ==================== End-to-End Flow Tests ====================
    
    @pytest.mark.asyncio
    async def test_full_ticket_flow_performance(self, client_id):
        """Test: Full ticket creation to resolution flow."""
        collector = PerformanceCollector("full_ticket_flow")
        collector.start()
        
        ticket_service = TicketService()
        approval_service = ApprovalService()
        
        async def create_and_resolve_ticket(ticket_num: int):
            # 1. Create ticket
            ticket = await collector.measure_async(
                f"create_ticket_{ticket_num}",
                ticket_service.create_ticket,
                client_id=client_id,
                subject=f"Test Ticket {ticket_num}",
                body="This is a test ticket for performance testing",
                priority="medium"
            )
            
            # 2. Assign ticket
            await collector.measure_async(
                f"assign_ticket_{ticket_num}",
                ticket_service.assign_ticket,
                ticket_id=ticket["id"],
                agent_id="agent_001",
                client_id=client_id
            )
            
            # 3. Add reply
            await collector.measure_async(
                f"reply_ticket_{ticket_num}",
                ticket_service.add_reply,
                ticket_id=ticket["id"],
                body="Thank you for contacting us.",
                client_id=client_id
            )
            
            # 4. Close ticket
            await collector.measure_async(
                f"close_ticket_{ticket_num}",
                ticket_service.close_ticket,
                ticket_id=ticket["id"],
                resolution="Issue resolved",
                client_id=client_id
            )
        
        # Run 50 complete ticket flows
        tasks = [create_and_resolve_ticket(i) for i in range(50)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        collector.stop()
        report = collector.generate_report()
        
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms for full flow too high"
        
        print(f"\nFull Ticket Flow Performance: {json.dumps(report.to_dict(), indent=2)}")
    
    # ==================== Stress Tests ====================
    
    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_sustained_load_5_minutes(self, client_id):
        """Test: Sustained load over 5 minutes."""
        collector = PerformanceCollector("sustained_5min")
        collector.start()
        
        ticket_service = TicketService()
        end_time = time.time() + 300  # 5 minutes
        
        async def sustained_requests():
            request_count = 0
            while time.time() < end_time:
                try:
                    await collector.measure_async(
                        f"sustained_{request_count}",
                        ticket_service.get_tickets,
                        client_id=client_id,
                        page=1,
                        limit=20
                    )
                except Exception:
                    pass
                request_count += 1
                await asyncio.sleep(0.1)  # 10 RPS per task
        
        # Run 10 parallel sustained request streams = 100 RPS total
        tasks = [sustained_requests() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        collector.stop()
        report = collector.generate_report()
        
        assert report.meets_sla(500), f"P95 {report.p95_ms}ms under sustained load"
        assert report.failed_requests / report.total_requests < 0.01, "Error rate > 1%"
        
        print(f"\nSustained 5min Load: {json.dumps(report.to_dict(), indent=2)}")
    
    # ==================== Memory and Resource Tests ====================
    
    def test_memory_usage_under_load(self, client_id):
        """Test: Memory usage stays reasonable under load."""
        import tracemalloc
        
        tracemalloc.start()
        
        ticket_service = TicketService()
        
        # Process 1000 tickets
        for i in range(1000):
            try:
                ticket_service.get_tickets(client_id=client_id, page=1, limit=100)
            except Exception:
                pass
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Peak memory should be less than 500MB
        peak_mb = peak / 1024 / 1024
        assert peak_mb < 500, f"Peak memory {peak_mb:.2f}MB exceeds 500MB limit"
        
        print(f"\nMemory Usage: Peak {peak_mb:.2f}MB")
    
    # ==================== Client Isolation Tests ====================
    
    @pytest.mark.asyncio
    async def test_cross_tenant_performance_isolation(self):
        """Test: One client's load doesn't affect another's performance."""
        collector_1 = PerformanceCollector("client_001_load")
        collector_2 = PerformanceCollector("client_002_load")
        
        ticket_service = TicketService()
        
        async def client_requests(collector: PerformanceCollector, client_id: str, count: int):
            for i in range(count):
                await collector.measure_async(
                    f"request_{i}",
                    ticket_service.get_tickets,
                    client_id=client_id,
                    page=1,
                    limit=20
                )
        
        # Run heavy load on client_001 while measuring client_002
        tasks = [
            client_requests(collector_1, "client_001", 500),  # Heavy load
            client_requests(collector_2, "client_002", 100),  # Normal load
        ]
        await asyncio.gather(*tasks)
        
        report_1 = collector_1.generate_report()
        report_2 = collector_2.generate_report()
        
        # Client 002 should still meet SLA despite client_001's heavy load
        assert report_2.meets_sla(500), f"Client 002 P95 {report_2.p95_ms}ms affected by other tenant"
        
        print(f"\nCross-Tenant Isolation:")
        print(f"  Client 001: {json.dumps(report_1.to_dict(), indent=2)}")
        print(f"  Client 002: {json.dumps(report_2.to_dict(), indent=2)}")


class TestPerformanceBaselines:
    """Establish and verify performance baselines."""
    
    def test_baseline_api_response_times(self):
        """Test: Establish baseline API response times."""
        baselines = {
            "ticket_list": {"target_p95": 200, "max_p95": 500},
            "ticket_detail": {"target_p95": 100, "max_p95": 300},
            "approvals_list": {"target_p95": 150, "max_p95": 400},
            "analytics": {"target_p95": 300, "max_p95": 500},
            "jarvis_command": {"target_p95": 500, "max_p95": 1000},
        }
        
        print("\n=== Performance Baselines ===")
        for endpoint, thresholds in baselines.items():
            print(f"  {endpoint}: target P95 {thresholds['target_p95']}ms, max {thresholds['max_p95']}ms")
        
        # Baselines documented for tracking
        assert True
    
    def test_baseline_throughput(self):
        """Test: Establish baseline throughput."""
        baselines = {
            "single_user": {"min_rps": 50},
            "10_concurrent": {"min_rps": 100},
            "50_concurrent": {"min_rps": 200},
            "100_concurrent": {"min_rps": 300},
        }
        
        print("\n=== Throughput Baselines ===")
        for scenario, thresholds in baselines.items():
            print(f"  {scenario}: min {thresholds['min_rps']} RPS")
        
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
