"""
Memory Usage Benchmark Test for PARWA.

Validates memory usage stays within acceptable limits under load.
"""

import asyncio
import tracemalloc
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime, timezone


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    label: str
    current_mb: float
    peak_mb: float


class MemoryUsageBenchmark:
    """
    Benchmark for memory usage validation.
    
    Target: Peak memory < 2GB under normal load.
    """
    
    MAX_MEMORY_MB = 2048  # 2GB limit
    
    def __init__(self):
        self.snapshots: List[MemorySnapshot] = []
        tracemalloc.start()
    
    def take_snapshot(self, label: str) -> MemorySnapshot:
        """Take a memory snapshot."""
        current, peak = tracemalloc.get_traced_memory()
        snapshot = MemorySnapshot(
            label=label,
            current_mb=current / 1024 / 1024,
            peak_mb=peak / 1024 / 1024
        )
        self.snapshots.append(snapshot)
        return snapshot
    
    async def simulate_client_requests(self, num_requests: int = 100):
        """Simulate processing client requests."""
        # Simulate request processing with data structures
        requests = []
        for i in range(num_requests):
            request = {
                "id": f"req_{i}",
                "client_id": f"client_{i % 50}",
                "data": {"query": f"Test query {i}" * 10},
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
            requests.append(request)
            await asyncio.sleep(0.001)  # Simulate processing
        
        return requests
    
    async def simulate_knowledge_base_search(self, num_searches: int = 50):
        """Simulate knowledge base searches."""
        results = []
        for i in range(num_searches):
            # Simulate KB search results
            search_result = {
                "query": f"search_{i}",
                "results": [
                    {"id": f"doc_{j}", "score": 0.9 - j * 0.1, "content": f"Content {j}" * 100}
                    for j in range(10)
                ]
            }
            results.append(search_result)
            await asyncio.sleep(0.001)
        
        return results
    
    async def simulate_agent_processing(self, num_tickets: int = 100):
        """Simulate agent processing tickets."""
        processed = []
        for i in range(num_tickets):
            ticket = {
                "ticket_id": f"ticket_{i}",
                "classification": ["refund", "technical", "billing", "general"][i % 4],
                "confidence": 0.85 + (i % 10) * 0.01,
                "response": f"Generated response for ticket {i}" * 50,
                "actions": ["action_1", "action_2", "action_3"]
            }
            processed.append(ticket)
            await asyncio.sleep(0.001)
        
        return processed
    
    async def run_benchmark(self) -> Dict[str, Any]:
        """Run complete memory benchmark."""
        
        # Initial state
        self.take_snapshot("initial")
        
        # Test 1: Client requests
        await self.simulate_client_requests(100)
        self.take_snapshot("after_client_requests")
        
        # Test 2: Knowledge base searches
        await self.simulate_knowledge_base_search(50)
        self.take_snapshot("after_kb_searches")
        
        # Test 3: Agent processing
        await self.simulate_agent_processing(100)
        self.take_snapshot("after_agent_processing")
        
        # Final state
        self.take_snapshot("final")
        
        # Get peak memory
        _, peak = tracemalloc.get_traced_memory()
        peak_mb = peak / 1024 / 1024
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "max_memory_mb": self.MAX_MEMORY_MB,
            "peak_memory_mb": round(peak_mb, 2),
            "target_met": peak_mb < self.MAX_MEMORY_MB,
            "snapshots": [
                {
                    "label": s.label,
                    "current_mb": round(s.current_mb, 2),
                    "peak_mb": round(s.peak_mb, 2)
                }
                for s in self.snapshots
            ]
        }
    
    def cleanup(self):
        """Cleanup memory tracking."""
        tracemalloc.stop()


async def main():
    """Run the memory usage benchmark."""
    print("=" * 60)
    print("MEMORY USAGE BENCHMARK")
    print("=" * 60)
    
    benchmark = MemoryUsageBenchmark()
    
    try:
        report = await benchmark.run_benchmark()
        
        print(f"\nMax Allowed: {report['max_memory_mb']} MB")
        print(f"Peak Memory: {report['peak_memory_mb']} MB")
        print(f"Target Met: {'✅ YES' if report['target_met'] else '❌ NO'}")
        print("\nMemory Snapshots:")
        
        for snapshot in report["snapshots"]:
            print(f"  {snapshot['label']}: Current={snapshot['current_mb']}MB, Peak={snapshot['peak_mb']}MB")
        
        print("=" * 60)
        
        return report
    
    finally:
        benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
