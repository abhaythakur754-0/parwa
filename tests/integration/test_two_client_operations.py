"""
Two Client Parallel Operations Tests.
Tests simultaneous operations across Client 001 and Client 002.
"""
import concurrent.futures
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class Ticket:
    ticket_id: str
    client_id: str
    subject: str
    body: str
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Approval:
    approval_id: str
    client_id: str
    ticket_id: str
    action: str
    approved: bool = False


class MockClientSystem:
    def __init__(self):
        self.lock = threading.Lock()
        self.tickets: Dict[str, List[Ticket]] = {"client_001": [], "client_002": []}
        self.approvals: Dict[str, List[Approval]] = {"client_001": [], "client_002": []}
        self.knowledge_bases: Dict[str, Dict] = {
            "client_001": {"entries": 25, "categories": ["orders", "shipping"]},
            "client_002": {"entries": 30, "categories": ["billing", "api"]},
        }
        self.dashboards: Dict[str, Dict] = {
            "client_001": {"widgets": 6, "theme": "light"},
            "client_002": {"widgets": 8, "theme": "dark"},
        }
    
    def create_ticket(self, client_id: str, subject: str, body: str) -> Ticket:
        with self.lock:
            ticket = Ticket(ticket_id=f"t_{uuid.uuid4().hex[:8]}", client_id=client_id, subject=subject, body=body)
            self.tickets[client_id].append(ticket)
            return ticket
    
    def get_tickets(self, client_id: str) -> List[Ticket]:
        with self.lock:
            return self.tickets.get(client_id, []).copy()
    
    def create_approval(self, client_id: str, ticket_id: str, action: str) -> Approval:
        with self.lock:
            approval = Approval(approval_id=f"a_{uuid.uuid4().hex[:8]}", client_id=client_id, ticket_id=ticket_id, action=action)
            self.approvals[client_id].append(approval)
            return approval
    
    def get_approvals(self, client_id: str) -> List[Approval]:
        with self.lock:
            return self.approvals.get(client_id, []).copy()
    
    def get_knowledge_base(self, client_id: str) -> Dict:
        with self.lock:
            return self.knowledge_bases.get(client_id, {}).copy()
    
    def get_dashboard(self, client_id: str) -> Dict:
        with self.lock:
            return self.dashboards.get(client_id, {}).copy()


@pytest.fixture
def system():
    return MockClientSystem()


class TestSimultaneousTicketCreation:
    def test_simultaneous_ticket_creation(self, system):
        def create_c1():
            for i in range(10):
                system.create_ticket("client_001", f"Client 001 Ticket {i}", f"Body {i}")
        def create_c2():
            for i in range(10):
                system.create_ticket("client_002", f"Client 002 Ticket {i}", f"Body {i}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1, f2 = executor.submit(create_c1), executor.submit(create_c2)
            f1.result()
            f2.result()
        c1_tickets, c2_tickets = system.get_tickets("client_001"), system.get_tickets("client_002")
        assert len(c1_tickets) == 10
        assert len(c2_tickets) == 10
        for t in c1_tickets:
            assert t.client_id == "client_001"
        for t in c2_tickets:
            assert t.client_id == "client_002"
    
    def test_ticket_creation_isolation(self, system):
        threads = []
        def create_tickets(cid, count):
            for i in range(count):
                system.create_ticket(cid, f"Ticket {i}", f"Body {i}")
        for _ in range(5):
            threads.append(threading.Thread(target=create_tickets, args=("client_001", 5)))
            threads.append(threading.Thread(target=create_tickets, args=("client_002", 5)))
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(system.get_tickets("client_001")) == 25
        assert len(system.get_tickets("client_002")) == 25


class TestSimultaneousApprovalProcessing:
    def test_simultaneous_approvals(self, system):
        for i in range(5):
            system.create_ticket("client_001", f"C1 Ticket {i}", f"Body {i}")
            system.create_ticket("client_002", f"C2 Ticket {i}", f"Body {i}")
        c1_tickets, c2_tickets = system.get_tickets("client_001"), system.get_tickets("client_002")
        def process_c1():
            for t in c1_tickets:
                system.create_approval("client_001", t.ticket_id, "approve")
        def process_c2():
            for t in c2_tickets:
                system.create_approval("client_002", t.ticket_id, "approve")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(process_c1).result()
            executor.submit(process_c2).result()
        assert len(system.get_approvals("client_001")) == 5
        assert len(system.get_approvals("client_002")) == 5


class TestKnowledgeBaseIsolation:
    def test_knowledge_base_isolation(self, system):
        def access_c1():
            return system.get_knowledge_base("client_001")
        def access_c2():
            return system.get_knowledge_base("client_002")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            c1_kb = executor.submit(access_c1).result()
            c2_kb = executor.submit(access_c2).result()
        assert c1_kb["entries"] == 25
        assert c2_kb["entries"] == 30
        assert c1_kb["categories"] != c2_kb["categories"]


class TestVariantIsolation:
    def test_variant_isolation(self, system):
        c1_kb = system.get_knowledge_base("client_001")
        c2_kb = system.get_knowledge_base("client_002")
        assert c1_kb != c2_kb
    
    def test_variant_features_isolated(self, system):
        c1_dash = system.get_dashboard("client_001")
        c2_dash = system.get_dashboard("client_002")
        assert c1_dash["widgets"] == 6
        assert c2_dash["widgets"] == 8


class TestDashboardSeparation:
    def test_dashboard_separation(self, system):
        c1_dash = system.get_dashboard("client_001")
        c2_dash = system.get_dashboard("client_002")
        assert c1_dash["theme"] == "light"
        assert c2_dash["theme"] == "dark"
    
    def test_concurrent_dashboard_access(self, system):
        results = []
        lock = threading.Lock()
        def access_dashboard(cid):
            dash = system.get_dashboard(cid)
            with lock:
                results.append((cid, dash))
        threads = []
        for _ in range(20):
            threads.append(threading.Thread(target=access_dashboard, args=("client_001",)))
            threads.append(threading.Thread(target=access_dashboard, args=("client_002",)))
        for t in threads: t.start()
        for t in threads: t.join()
        for cid, dash in results:
            if cid == "client_001":
                assert dash["theme"] == "light"
            else:
                assert dash["theme"] == "dark"


class TestParallelOperationsIntegrity:
    def test_data_integrity_under_parallel_load(self, system):
        def client_ops(cid):
            for i in range(5):
                system.create_ticket(cid, f"Ticket {i}", f"Body {i}")
            tickets = system.get_tickets(cid)
            for t in tickets[:3]:
                system.create_approval(cid, t.ticket_id, "approve")
            return len(tickets)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            c1_count = executor.submit(client_ops, "client_001").result()
            c2_count = executor.submit(client_ops, "client_002").result()
        assert c1_count == 5
        assert c2_count == 5
        assert len(system.get_approvals("client_001")) == 3
        assert len(system.get_approvals("client_002")) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
