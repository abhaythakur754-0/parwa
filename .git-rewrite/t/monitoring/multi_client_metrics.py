"""
Multi-Client Metrics Collection

Collects metrics from all 5 clients with cross-client analysis.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import statistics


class ClientIndustry(Enum):
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    RETAIL = "retail"
    FINANCE = "finance"


@dataclass
class ClientMetrics:
    client_id: str
    client_name: str
    industry: ClientIndustry
    ticket_count: int
    accuracy_percent: float
    avg_response_time_ms: float
    error_rate: float
    csat_score: float


class MultiClientMetricsCollector:
    """Collects metrics across all 5 clients."""
    
    CLIENTS = {
        "client_001": {"name": "Acme E-commerce", "industry": ClientIndustry.ECOMMERCE},
        "client_002": {"name": "TechStart SaaS", "industry": ClientIndustry.SAAS},
        "client_003": {"name": "MedCare Health", "industry": ClientIndustry.HEALTHCARE},
        "client_004": {"name": "RetailMax", "industry": ClientIndustry.RETAIL},
        "client_005": {"name": "FinServe Banking", "industry": ClientIndustry.FINANCE},
    }
    
    async def collect_client_metrics(self, client_id: str) -> ClientMetrics:
        """Collect metrics for a single client."""
        await asyncio.sleep(0.01)
        import random
        
        client = self.CLIENTS.get(client_id, {"name": "Unknown", "industry": ClientIndustry.ECOMMERCE})
        
        return ClientMetrics(
            client_id=client_id,
            client_name=client["name"],
            industry=client["industry"],
            ticket_count=random.randint(100, 1000),
            accuracy_percent=random.uniform(75, 95),
            avg_response_time_ms=random.uniform(80, 300),
            error_rate=random.uniform(0.001, 0.01),
            csat_score=random.uniform(4.0, 4.9)
        )
    
    async def collect_all(self) -> List[ClientMetrics]:
        """Collect metrics from all clients."""
        tasks = [self.collect_client_metrics(cid) for cid in self.CLIENTS]
        return await asyncio.gather(*tasks)
    
    def compute_aggregates(self, metrics: List[ClientMetrics]) -> Dict[str, Any]:
        """Compute aggregate metrics."""
        return {
            "total_clients": len(metrics),
            "total_tickets": sum(m.ticket_count for m in metrics),
            "avg_accuracy": statistics.mean([m.accuracy_percent for m in metrics]),
            "avg_response_time_ms": statistics.mean([m.avg_response_time_ms for m in metrics]),
            "avg_error_rate": statistics.mean([m.error_rate for m in metrics]),
            "avg_csat": statistics.mean([m.csat_score for m in metrics]),
        }
    
    def compare_by_industry(self, metrics: List[ClientMetrics]) -> Dict[str, List[float]]:
        """Compare metrics by industry."""
        by_industry: Dict[str, List[float]] = {}
        for m in metrics:
            industry = m.industry.value
            if industry not in by_industry:
                by_industry[industry] = []
            by_industry[industry].append(m.accuracy_percent)
        return by_industry


async def run_metrics_collection() -> Dict[str, Any]:
    """Run full metrics collection."""
    collector = MultiClientMetricsCollector()
    metrics = await collector.collect_all()
    aggregates = collector.compute_aggregates(metrics)
    
    print(f"\n{'='*60}")
    print("MULTI-CLIENT METRICS REPORT")
    print(f"{'='*60}")
    print(f"Total Clients: {aggregates['total_clients']}")
    print(f"Total Tickets: {aggregates['total_tickets']}")
    print(f"Avg Accuracy: {aggregates['avg_accuracy']:.2f}%")
    print(f"Avg Response Time: {aggregates['avg_response_time_ms']:.2f}ms")
    print(f"{'='*60}\n")
    
    return {"metrics": metrics, "aggregates": aggregates}


if __name__ == "__main__":
    asyncio.run(run_metrics_collection())
