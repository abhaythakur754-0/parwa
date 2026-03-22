#!/usr/bin/env python3
"""
Performance Optimization Script
Identifies slow queries, suggests indexes, cache optimization, connection pooling
"""
import asyncio
import time
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import statistics


@dataclass
class SlowQuery:
    """Represents a slow query."""
    query: str
    avg_time_ms: float
    max_time_ms: float
    count: int
    suggestion: str
    severity: str  # low, medium, high, critical


@dataclass
class IndexSuggestion:
    """Index suggestion."""
    table: str
    columns: List[str]
    reason: str
    estimated_improvement: str


@dataclass
class OptimizationReport:
    """Full optimization report."""
    timestamp: str
    slow_queries: List[SlowQuery] = field(default_factory=list)
    index_suggestions: List[IndexSuggestion] = field(default_factory=list)
    cache_recommendations: List[str] = field(default_factory=list)
    connection_pool_recommendations: List[str] = field(default_factory=list)
    overall_score: float = 0.0


class QueryAnalyzer:
    """Analyzes query performance."""
    
    def __init__(self, slow_threshold_ms: float = 100):
        self.slow_threshold_ms = slow_threshold_ms
        self.query_log: List[Dict] = []
    
    def log_query(self, query: str, duration_ms: float, params: Dict = None):
        """Log a query execution."""
        self.query_log.append({
            'query': query,
            'duration_ms': duration_ms,
            'params': params,
            'timestamp': datetime.now().isoformat()
        })
    
    def analyze_patterns(self) -> List[SlowQuery]:
        """Analyze query patterns for slow queries."""
        query_stats: Dict[str, List[float]] = {}
        
        for entry in self.query_log:
            query = self._normalize_query(entry['query'])
            if query not in query_stats:
                query_stats[query] = []
            query_stats[query].append(entry['duration_ms'])
        
        slow_queries = []
        
        for query, times in query_stats.items():
            avg_time = statistics.mean(times)
            max_time = max(times)
            
            if avg_time > self.slow_threshold_ms:
                severity = self._calculate_severity(avg_time)
                suggestion = self._suggest_optimization(query, avg_time)
                
                slow_queries.append(SlowQuery(
                    query=query[:200],  # Truncate for display
                    avg_time_ms=round(avg_time, 2),
                    max_time_ms=round(max_time, 2),
                    count=len(times),
                    suggestion=suggestion,
                    severity=severity
                ))
        
        return sorted(slow_queries, key=lambda q: q.avg_time_ms, reverse=True)
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching."""
        # Replace specific values with placeholders
        normalized = re.sub(r"'[^']*'", "'?'", query)
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        return normalized.strip()
    
    def _calculate_severity(self, avg_time: float) -> str:
        """Calculate severity level."""
        if avg_time > 1000:
            return 'critical'
        elif avg_time > 500:
            return 'high'
        elif avg_time > 200:
            return 'medium'
        return 'low'
    
    def _suggest_optimization(self, query: str, avg_time: float) -> str:
        """Suggest optimization for slow query."""
        suggestions = []
        
        query_lower = query.lower()
        
        if 'where' not in query_lower and 'limit' not in query_lower:
            suggestions.append("Add WHERE clause to filter data")
        
        if 'select *' in query_lower:
            suggestions.append("Select specific columns instead of *")
        
        if 'order by' in query_lower and 'limit' in query_lower:
            suggestions.append("Consider adding index on ORDER BY column")
        
        if 'like' in query_lower and '%' in query:
            suggestions.append("Leading wildcard prevents index use; consider full-text search")
        
        if 'join' in query_lower:
            suggestions.append("Ensure join columns are indexed")
        
        if not suggestions:
            suggestions.append("Review execution plan and consider index optimization")
        
        return "; ".join(suggestions)


class IndexAdvisor:
    """Advises on index creation."""
    
    def __init__(self):
        self.common_patterns = {
            'tickets': ['status', 'priority', 'customer_id', 'created_at', 'tenant_id'],
            'customers': ['email', 'tenant_id'],
            'approvals': ['status', 'type', 'created_at', 'tenant_id'],
            'audit_logs': ['user_id', 'action', 'timestamp', 'tenant_id'],
        }
    
    def analyze_query(self, query: str) -> List[IndexSuggestion]:
        """Analyze query and suggest indexes."""
        suggestions = []
        query_lower = query.lower()
        
        for table, columns in self.common_patterns.items():
            if table in query_lower:
                # Check for missing indexes
                for col in columns:
                    if col in query_lower and 'where' in query_lower:
                        # Check if already in index suggestions
                        if not any(s.table == table and col in s.columns for s in suggestions):
                            suggestions.append(IndexSuggestion(
                                table=table,
                                columns=[col],
                                reason=f"Column '{col}' frequently used in WHERE clause",
                                estimated_improvement="50-90% query speedup"
                            ))
        
        # Composite indexes for common patterns
        if 'status' in query_lower and 'created_at' in query_lower:
            suggestions.append(IndexSuggestion(
                table='tickets',
                columns=['status', 'created_at'],
                reason="Composite index for status + date filtering",
                estimated_improvement="70-95% for filtered date range queries"
            ))
        
        return suggestions[:10]  # Limit suggestions


class CacheOptimizer:
    """Cache optimization recommendations."""
    
    def __init__(self):
        self.cache_patterns = [
            ('faq_search', 'Frequently searched FAQs', 3600),
            ('product_catalog', 'Product catalog data', 7200),
            ('customer_profile', 'Customer profiles', 1800),
            ('ticket_templates', 'Ticket response templates', 86400),
            ('knowledge_base', 'KB articles', 3600),
        ]
    
    def analyze(self, query_patterns: List[str]) -> List[str]:
        """Analyze and provide cache recommendations."""
        recommendations = []
        
        # Check for repeated queries
        query_counts: Dict[str, int] = {}
        for q in query_patterns:
            normalized = self._normalize(q)
            query_counts[normalized] = query_counts.get(normalized, 0) + 1
        
        for query, count in query_counts.items():
            if count > 10:
                recommendations.append(
                    f"Cache frequently repeated query: {query[:50]}... (called {count} times)"
                )
        
        # Add general recommendations
        recommendations.extend([
            "Enable Redis caching for session data (TTL: 3600s)",
            "Implement query result caching for FAQ lookups",
            "Cache customer profile data with 30-minute TTL",
            "Use Redis pub/sub for cache invalidation on updates",
            "Implement cache warming for top 100 FAQ entries on startup",
            "Enable compression for large cached objects",
            "Monitor cache hit rate; target > 85%",
        ])
        
        return recommendations[:15]
    
    def _normalize(self, query: str) -> str:
        """Normalize query."""
        return re.sub(r"'[^']*'", "'?'", query.lower())[:100]


class ConnectionPoolTuner:
    """Connection pool tuning recommendations."""
    
    def analyze(
        self,
        current_pool_size: int = 20,
        max_connections: int = 100,
        avg_query_time_ms: float = 50,
        peak_concurrent: int = 50
    ) -> List[str]:
        """Analyze and tune connection pool."""
        recommendations = []
        
        # Calculate optimal pool size
        # Formula: connections = (peak_concurrent * avg_query_time) / 1000
        optimal_pool = max(10, min(100, int(peak_concurrent * avg_query_time_ms / 1000 * 2)))
        
        if current_pool_size < optimal_pool:
            recommendations.append(
                f"Increase pool size from {current_pool_size} to {optimal_pool} "
                f"(based on peak concurrent: {peak_concurrent})"
            )
        elif current_pool_size > optimal_pool * 1.5:
            recommendations.append(
                f"Consider reducing pool size from {current_pool_size} to {optimal_pool} "
                f"to save resources"
            )
        
        recommendations.extend([
            f"Set pool min connections to {max(5, optimal_pool // 2)}",
            f"Set pool max connections to {optimal_pool}",
            "Enable connection validation on checkout",
            "Set connection timeout to 30 seconds",
            "Enable connection leak detection in development",
            "Configure idle connection timeout to 600 seconds",
            "Set max lifetime for connections to 1800 seconds",
            f"Max database connections should be at least {optimal_pool + 20} "
            f"(pool + headroom for other clients)",
        ])
        
        return recommendations


class PerformanceOptimizer:
    """Main performance optimization orchestrator."""
    
    def __init__(self):
        self.query_analyzer = QueryAnalyzer()
        self.index_advisor = IndexAdvisor()
        self.cache_optimizer = CacheOptimizer()
        self.pool_tuner = ConnectionPoolTuner()
    
    def simulate_load(self, num_queries: int = 1000):
        """Simulate load for analysis."""
        import random
        
        query_templates = [
            "SELECT * FROM tickets WHERE status = 'open' AND tenant_id = 'client_001'",
            "SELECT * FROM customers WHERE email = 'user@example.com'",
            "SELECT * FROM tickets WHERE customer_id = 123 ORDER BY created_at DESC LIMIT 10",
            "SELECT * FROM approvals WHERE status = 'pending' AND tenant_id = 'client_001'",
            "SELECT COUNT(*) FROM tickets WHERE status = 'open'",
            "SELECT * FROM audit_logs WHERE user_id = 456 ORDER BY timestamp DESC",
            "SELECT * FROM tickets WHERE created_at > '2024-01-01' AND status = 'open'",
            "SELECT * FROM customers WHERE tenant_id = 'client_001' LIMIT 100",
        ]
        
        for _ in range(num_queries):
            query = random.choice(query_templates)
            # Simulate realistic query times (some fast, some slow)
            duration = random.choices(
                [10, 20, 50, 100, 200, 500, 1000],
                weights=[30, 25, 20, 15, 5, 3, 2]
            )[0]
            self.query_analyzer.log_query(query, duration)
    
    def optimize(self) -> OptimizationReport:
        """Run full optimization analysis."""
        print("Running performance optimization analysis...")
        
        # Simulate load if no real data
        if not self.query_analyzer.query_log:
            self.simulate_load(1000)
        
        # Analyze slow queries
        slow_queries = self.query_analyzer.analyze_patterns()
        print(f"Found {len(slow_queries)} slow queries")
        
        # Get index suggestions
        index_suggestions = []
        for sq in slow_queries[:5]:
            suggestions = self.index_advisor.analyze_query(sq.query)
            index_suggestions.extend(suggestions)
        
        # Deduplicate suggestions
        seen = set()
        unique_suggestions = []
        for s in index_suggestions:
            key = (s.table, tuple(s.columns))
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)
        index_suggestions = unique_suggestions
        print(f"Generated {len(index_suggestions)} index suggestions")
        
        # Cache recommendations
        query_patterns = [q['query'] for q in self.query_analyzer.query_log]
        cache_recommendations = self.cache_optimizer.analyze(query_patterns)
        
        # Connection pool recommendations
        pool_recommendations = self.pool_tuner.analyze()
        
        # Calculate overall score (0-100)
        score = 100
        for sq in slow_queries:
            if sq.severity == 'critical':
                score -= 20
            elif sq.severity == 'high':
                score -= 10
            elif sq.severity == 'medium':
                score -= 5
        score = max(0, score)
        
        return OptimizationReport(
            timestamp=datetime.now().isoformat(),
            slow_queries=slow_queries,
            index_suggestions=index_suggestions,
            cache_recommendations=cache_recommendations,
            connection_pool_recommendations=pool_recommendations,
            overall_score=score
        )
    
    def generate_report(self, report: OptimizationReport) -> str:
        """Generate human-readable report."""
        lines = [
            "# Performance Optimization Report",
            f"Generated: {report.timestamp}",
            f"Overall Score: {report.overall_score}/100",
            "",
            "## Slow Queries",
        ]
        
        for sq in report.slow_queries:
            lines.append(f"- [{sq.severity.upper()}] {sq.avg_time_ms}ms avg ({sq.max_time_ms}ms max)")
            lines.append(f"  Query: {sq.query[:100]}...")
            lines.append(f"  Suggestion: {sq.suggestion}")
            lines.append("")
        
        lines.append("## Index Suggestions")
        for idx in report.index_suggestions:
            lines.append(f"- Table: {idx.table}, Columns: {idx.columns}")
            lines.append(f"  Reason: {idx.reason}")
            lines.append(f"  Expected: {idx.estimated_improvement}")
        
        lines.extend([
            "",
            "## Cache Recommendations",
        ])
        for rec in report.cache_recommendations:
            lines.append(f"- {rec}")
        
        lines.extend([
            "",
            "## Connection Pool Recommendations",
        ])
        for rec in report.connection_pool_recommendations:
            lines.append(f"- {rec}")
        
        return "\n".join(lines)


def main():
    """Main entry point."""
    optimizer = PerformanceOptimizer()
    report = optimizer.optimize()
    
    # Print report
    print("\n" + "=" * 60)
    print(optimizer.generate_report(report))
    print("=" * 60)
    
    # Save report
    output_path = "/home/z/my-project/parwa/monitoring/performance_report.md"
    with open(output_path, 'w') as f:
        f.write(optimizer.generate_report(report))
    print(f"\nReport saved to: {output_path}")
    
    return report.overall_score >= 70


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
