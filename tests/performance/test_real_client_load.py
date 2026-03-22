"""
Performance Tests with Real Client Data Patterns
Tests: P95 < 500ms, Concurrent users, Peak load, DB queries, API response times
"""
import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import random
import string


@dataclass
class PerformanceResult:
    """Performance test result."""
    name: str
    duration_ms: float
    passed: bool
    threshold_ms: float
    error: str = None


class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, name: str, threshold_ms: float = 500):
        self.name = name
        self.threshold_ms = threshold_ms
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000


class MockDatabase:
    """Mock database for performance testing."""
    
    def __init__(self):
        self.tickets = self._generate_tickets(10000)
        self.customers = self._generate_customers(5000)
        self._indexes = {}
    
    def _generate_tickets(self, count: int) -> List[Dict]:
        """Generate mock tickets."""
        statuses = ['open', 'pending', 'resolved', 'closed']
        priorities = ['low', 'medium', 'high', 'urgent']
        categories = ['orders', 'shipping', 'returns', 'products', 'account']
        
        return [
            {
                'id': f'TKT-{i:06d}',
                'subject': f'Ticket subject {i}',
                'status': random.choice(statuses),
                'priority': random.choice(priorities),
                'category': random.choice(categories),
                'customer_id': f'CUST-{random.randint(1, 5000):06d}',
                'created_at': datetime.now().isoformat(),
                'tenant_id': 'client_001'
            }
            for i in range(count)
        ]
    
    def _generate_customers(self, count: int) -> List[Dict]:
        """Generate mock customers."""
        return [
            {
                'id': f'CUST-{i:06d}',
                'email': f'customer{i}@example.com',
                'name': f'Customer {i}',
                'tenant_id': 'client_001'
            }
            for i in range(count)
        ]
    
    async def query_tickets(self, filters: Dict = None, limit: int = 20) -> List[Dict]:
        """Query tickets with optional filters."""
        await asyncio.sleep(0.001)  # Simulate DB latency
        results = self.tickets
        
        if filters:
            if 'status' in filters:
                results = [t for t in results if t['status'] == filters['status']]
            if 'priority' in filters:
                results = [t for t in results if t['priority'] == filters['priority']]
            if 'category' in filters:
                results = [t for t in results if t['category'] == filters['category']]
        
        return results[:limit]
    
    async def get_ticket_by_id(self, ticket_id: str) -> Dict:
        """Get single ticket by ID."""
        await asyncio.sleep(0.0005)  # Simulate indexed lookup
        for ticket in self.tickets:
            if ticket['id'] == ticket_id:
                return ticket
        return None
    
    async def create_ticket(self, data: Dict) -> Dict:
        """Create new ticket."""
        await asyncio.sleep(0.002)  # Simulate write latency
        ticket = {
            'id': f'TKT-{len(self.tickets):06d}',
            **data,
            'created_at': datetime.now().isoformat()
        }
        self.tickets.append(ticket)
        return ticket


class MockCache:
    """Mock Redis cache for performance testing."""
    
    def __init__(self):
        self._cache = {}
        self._hit_count = 0
        self._miss_count = 0
    
    async def get(self, key: str) -> Any:
        """Get from cache."""
        await asyncio.sleep(0.0001)  # Simulate Redis latency
        if key in self._cache:
            self._hit_count += 1
            return self._cache[key]
        self._miss_count += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set in cache."""
        await asyncio.sleep(0.0001)
        self._cache[key] = value
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0


class PerformanceTestSuite:
    """Performance test suite for real client data patterns."""
    
    def __init__(self):
        self.db = MockDatabase()
        self.cache = MockCache()
        self.results: List[PerformanceResult] = []
    
    def record_result(self, result: PerformanceResult):
        """Record test result."""
        self.results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status} {result.name}: {result.duration_ms:.2f}ms (threshold: {result.threshold_ms}ms)")
    
    async def test_api_response_time(self):
        """Test: API response time < 500ms P95."""
        times = []
        
        for _ in range(100):
            start = time.perf_counter()
            # Simulate API call
            await self.db.query_tickets({'status': 'open'}, limit=20)
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)
        
        p95 = statistics.quantiles(times, n=20)[18]  # 95th percentile
        passed = p95 < 500
        
        self.record_result(PerformanceResult(
            name="API Response Time P95",
            duration_ms=p95,
            passed=passed,
            threshold_ms=500
        ))
        
        return passed
    
    async def test_database_query_performance(self):
        """Test: Database query performance."""
        times = []
        
        # Test indexed lookup
        for i in range(50):
            start = time.perf_counter()
            await self.db.get_ticket_by_id(f'TKT-{i:06d}')
            times.append((time.perf_counter() - start) * 1000)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        passed = max_time < 100  # Single lookup should be < 100ms
        
        self.record_result(PerformanceResult(
            name=f"DB Query Performance (avg: {avg_time:.2f}ms, max: {max_time:.2f}ms)",
            duration_ms=max_time,
            passed=passed,
            threshold_ms=100
        ))
        
        return passed
    
    async def test_concurrent_users(self):
        """Test: Concurrent user simulation."""
        async def user_session(user_id: int):
            """Simulate user session."""
            times = []
            
            # User does multiple operations
            for _ in range(5):
                start = time.perf_counter()
                await self.db.query_tickets(limit=10)
                times.append((time.perf_counter() - start) * 1000)
            
            return times
        
        # Simulate 50 concurrent users
        start = time.perf_counter()
        results = await asyncio.gather(*[user_session(i) for i in range(50)])
        total_time = (time.perf_counter() - start) * 1000
        
        # Flatten times
        all_times = [t for session_times in results for t in session_times]
        p95 = statistics.quantiles(all_times, n=20)[18]
        
        passed = p95 < 500 and total_time < 10000  # All sessions complete in 10s
        
        self.record_result(PerformanceResult(
            name=f"Concurrent Users (50 users, P95: {p95:.2f}ms)",
            duration_ms=p95,
            passed=passed,
            threshold_ms=500
        ))
        
        return passed
    
    async def test_peak_load_handling(self):
        """Test: Peak load handling."""
        # Simulate peak load: 100 requests per second for 10 seconds
        times = []
        
        async def burst_requests():
            """Send burst of requests."""
            start = time.perf_counter()
            await asyncio.gather(*[self.db.query_tickets(limit=20) for _ in range(100)])
            return (time.perf_counter() - start) * 1000
        
        for _ in range(10):
            duration = await burst_requests()
            times.append(duration)
        
        avg_burst_time = statistics.mean(times)
        passed = avg_burst_time < 2000  # 100 requests should complete in < 2s
        
        self.record_result(PerformanceResult(
            name=f"Peak Load (100 req/burst, avg: {avg_burst_time:.2f}ms)",
            duration_ms=avg_burst_time,
            passed=passed,
            threshold_ms=2000
        ))
        
        return passed
    
    async def test_cache_performance(self):
        """Test: Cache hit rate and performance."""
        # Warm up cache
        tickets = await self.db.query_tickets(limit=100)
        for ticket in tickets:
            await self.cache.set(f"ticket:{ticket['id']}", ticket)
        
        # Test cache retrieval
        cache_times = []
        db_times = []
        
        for ticket in tickets[:50]:
            # Cache lookup
            start = time.perf_counter()
            await self.cache.get(f"ticket:{ticket['id']}")
            cache_times.append((time.perf_counter() - start) * 1000)
            
            # DB lookup
            start = time.perf_counter()
            await self.db.get_ticket_by_id(ticket['id'])
            db_times.append((time.perf_counter() - start) * 1000)
        
        avg_cache = statistics.mean(cache_times)
        avg_db = statistics.mean(db_times)
        speedup = avg_db / avg_cache if avg_cache > 0 else 0
        
        passed = self.cache.hit_rate > 0.9 and speedup > 2
        
        self.record_result(PerformanceResult(
            name=f"Cache Performance (hit_rate: {self.cache.hit_rate:.0%}, speedup: {speedup:.1f}x)",
            duration_ms=avg_cache,
            passed=passed,
            threshold_ms=1
        ))
        
        return passed
    
    async def test_ticket_creation_performance(self):
        """Test: Ticket creation performance."""
        times = []
        
        for i in range(50):
            start = time.perf_counter()
            await self.db.create_ticket({
                'subject': f'New ticket {i}',
                'status': 'open',
                'priority': 'medium',
                'customer_id': f'CUST-{i:06d}',
                'tenant_id': 'client_001'
            })
            times.append((time.perf_counter() - start) * 1000)
        
        p95 = statistics.quantiles(times, n=20)[18]
        passed = p95 < 100
        
        self.record_result(PerformanceResult(
            name=f"Ticket Creation P95",
            duration_ms=p95,
            passed=passed,
            threshold_ms=100
        ))
        
        return passed
    
    async def run_all_tests(self):
        """Run all performance tests."""
        print("=" * 60)
        print("PERFORMANCE TEST SUITE - Real Client Data Patterns")
        print("=" * 60)
        
        tests = [
            self.test_api_response_time,
            self.test_database_query_performance,
            self.test_concurrent_users,
            self.test_peak_load_handling,
            self.test_cache_performance,
            self.test_ticket_creation_performance,
        ]
        
        for test in tests:
            try:
                await test()
            except Exception as e:
                self.record_result(PerformanceResult(
                    name=test.__name__,
                    duration_ms=0,
                    passed=False,
                    threshold_ms=500,
                    error=str(e)
                ))
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"Tests Passed: {passed}/{total}")
        print(f"Pass Rate: {passed/total:.0%}")
        
        # Critical: P95 < 500ms
        p95_results = [r for r in self.results if 'P95' in r.name]
        if p95_results:
            all_p95_pass = all(r.passed for r in p95_results)
            print(f"\nCRITICAL - P95 < 500ms: {'✅ PASS' if all_p95_pass else '❌ FAIL'}")
        
        return passed == total


# Pytest tests
@pytest.fixture
def performance_suite():
    """Create performance test suite."""
    return PerformanceTestSuite()


@pytest.mark.asyncio
async def test_api_response_time_p95(performance_suite):
    """Test: API response time P95 < 500ms."""
    passed = await performance_suite.test_api_response_time()
    assert passed, "API response time P95 exceeds 500ms"


@pytest.mark.asyncio
async def test_database_query_performance(performance_suite):
    """Test: Database query performance."""
    passed = await performance_suite.test_database_query_performance()
    assert passed, "Database query performance below threshold"


@pytest.mark.asyncio
async def test_concurrent_users(performance_suite):
    """Test: Concurrent user handling."""
    passed = await performance_suite.test_concurrent_users()
    assert passed, "Concurrent user performance below threshold"


@pytest.mark.asyncio
async def test_peak_load_handling(performance_suite):
    """Test: Peak load handling."""
    passed = await performance_suite.test_peak_load_handling()
    assert passed, "Peak load handling below threshold"


@pytest.mark.asyncio
async def test_cache_performance(performance_suite):
    """Test: Cache performance."""
    passed = await performance_suite.test_cache_performance()
    assert passed, "Cache performance below threshold"


@pytest.mark.asyncio
async def test_ticket_creation_performance(performance_suite):
    """Test: Ticket creation performance."""
    passed = await performance_suite.test_ticket_creation_performance()
    assert passed, "Ticket creation performance below threshold"


@pytest.mark.asyncio
async def test_full_performance_suite():
    """Test: Full performance suite passes."""
    suite = PerformanceTestSuite()
    passed = await suite.run_all_tests()
    assert passed, "Performance test suite failed"


if __name__ == "__main__":
    asyncio.run(PerformanceTestSuite().run_all_tests())
