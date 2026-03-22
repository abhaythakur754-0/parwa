#!/usr/bin/env python3
"""
Performance Optimization Script
Analyzes and suggests optimizations for the PARWA platform.
"""
import os
import sys
import time
import json
import argparse
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import subprocess
import re

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.app.core.config import settings
from backend.app.core.database import get_db


@dataclass
class SlowQuery:
    """Represents a slow database query."""
    query: str
    avg_time_ms: float
    max_time_ms: float
    call_count: int
    total_time_ms: float
    suggestions: List[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """Result of an optimization check."""
    category: str
    name: str
    current_value: Any
    recommended_value: Any
    impact: str  # "high", "medium", "low"
    description: str
    applied: bool = False


class PerformanceAnalyzer:
    """Analyzes system performance and suggests optimizations."""
    
    def __init__(self, client_id: Optional[str] = None):
        self.client_id = client_id
        self.slow_queries: List[SlowQuery] = []
        self.optimizations: List[OptimizationResult] = []
        self.start_time = datetime.utcnow()
    
    def analyze_database_queries(self) -> List[SlowQuery]:
        """Analyze slow database queries."""
        print("\n📊 Analyzing database queries...")
        
        db = next(get_db())
        
        # Query pg_stat_statements for slow queries
        try:
            result = db.execute("""
                SELECT 
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    max_exec_time
                FROM pg_stat_statements
                WHERE mean_exec_time > 10  -- Queries averaging > 10ms
                ORDER BY total_exec_time DESC
                LIMIT 20
            """)
            
            for row in result:
                slow_query = SlowQuery(
                    query=row[0],
                    avg_time_ms=row[3],
                    max_time_ms=row[4],
                    call_count=row[1],
                    total_time_ms=row[2],
                    suggestions=self._suggest_query_optimizations(row[0])
                )
                self.slow_queries.append(slow_query)
                
        except Exception as e:
            print(f"  ⚠️  Could not query pg_stat_statements: {e}")
            print("  ℹ️  Using fallback analysis...")
            self._analyze_queries_from_logs()
        
        return self.slow_queries
    
    def _suggest_query_optimizations(self, query: str) -> List[str]:
        """Generate optimization suggestions for a query."""
        suggestions = []
        
        # Check for missing WHERE clauses
        if "WHERE" not in query.upper() and "SELECT" in query.upper():
            suggestions.append("Consider adding WHERE clause to limit results")
        
        # Check for SELECT *
        if "SELECT *" in query.upper():
            suggestions.append("Avoid SELECT * - specify needed columns")
        
        # Check for LIKE with leading wildcard
        if "LIKE '%" in query.upper():
            suggestions.append("LIKE with leading wildcard prevents index usage")
        
        # Check for ORDER BY on non-indexed columns
        if "ORDER BY" in query.upper():
            suggestions.append("Ensure ORDER BY columns are indexed")
        
        # Check for subqueries that could be JOINs
        if "SELECT" in query.upper() and query.upper().count("SELECT") > 1:
            suggestions.append("Consider converting subqueries to JOINs")
        
        # Check for missing LIMIT
        if "LIMIT" not in query.upper() and "SELECT" in query.upper():
            suggestions.append("Consider adding LIMIT clause")
        
        return suggestions
    
    def _analyze_queries_from_logs(self):
        """Fallback: analyze queries from log files."""
        log_path = "/var/log/parwa/postgresql.log"
        if not os.path.exists(log_path):
            return
        
        # Parse log for slow query entries
        with open(log_path, "r") as f:
            for line in f:
                if "duration:" in line.lower():
                    match = re.search(r"duration: ([\d.]+) ms", line)
                    if match and float(match.group(1)) > 100:
                        # Extract query if possible
                        self.slow_queries.append(SlowQuery(
                            query=line[:200],
                            avg_time_ms=float(match.group(1)),
                            max_time_ms=float(match.group(1)),
                            call_count=1,
                            total_time_ms=float(match.group(1)),
                            suggestions=["Review query for optimization"]
                        ))
    
    def suggest_indexes(self) -> List[OptimizationResult]:
        """Suggest missing indexes."""
        print("\n🔍 Analyzing missing indexes...")
        
        db = next(get_db())
        suggestions = []
        
        # Check for tables without indexes
        try:
            result = db.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats
                WHERE schemaname = 'public'
                AND n_distinct > 100
                ORDER BY tablename, attname
            """)
            
            for row in result:
                # High n_distinct with high correlation = good index candidate
                if row[3] > 1000:  # High cardinality
                    optimization = OptimizationResult(
                        category="index",
                        name=f"idx_{row[1]}_{row[2]}",
                        current_value="No index",
                        recommended_value=f"CREATE INDEX idx_{row[1]}_{row[2]} ON {row[1]}({row[2]})",
                        impact="medium" if row[3] < 10000 else "high",
                        description=f"Index on {row[1]}.{row[2]} (cardinality: {row[3]})"
                    )
                    suggestions.append(optimization)
                    self.optimizations.append(optimization)
                    
        except Exception as e:
            print(f"  ⚠️  Could not analyze indexes: {e}")
        
        # Check specific PARWA tables
        critical_indexes = [
            ("tickets", "client_id", "high"),
            ("tickets", "status", "high"),
            ("tickets", "created_at", "medium"),
            ("approvals", "client_id", "high"),
            ("approvals", "status", "high"),
            ("analytics", "client_id", "high"),
            ("analytics", "created_at", "medium"),
            ("users", "email", "high"),
            ("audit_logs", "tenant_id", "high"),
            ("audit_logs", "timestamp", "medium"),
        ]
        
        for table, column, impact in critical_indexes:
            try:
                result = db.execute(f"""
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = '{table}' 
                    AND indexdef LIKE '%{column}%'
                """)
                if not result.fetchone():
                    optimization = OptimizationResult(
                        category="index",
                        name=f"idx_{table}_{column}",
                        current_value="No index",
                        recommended_value=f"CREATE INDEX idx_{table}_{column} ON {table}({column})",
                        impact=impact,
                        description=f"Critical index on {table}.{column}"
                    )
                    suggestions.append(optimization)
                    self.optimizations.append(optimization)
            except Exception:
                pass
        
        return suggestions
    
    def analyze_connection_pool(self) -> List[OptimizationResult]:
        """Analyze database connection pool settings."""
        print("\n🔌 Analyzing connection pool...")
        
        suggestions = []
        db = next(get_db())
        
        try:
            # Get current max connections
            result = db.execute("SHOW max_connections")
            max_conn = int(result.fetchone()[0])
            
            # Get current connection count
            result = db.execute("SELECT count(*) FROM pg_stat_activity")
            current_conn = int(result.fetchone()[0])
            
            utilization = (current_conn / max_conn) * 100
            
            if utilization > 80:
                suggestions.append(OptimizationResult(
                    category="connection_pool",
                    name="max_connections",
                    current_value=max_conn,
                    recommended_value=max_conn * 2,
                    impact="high",
                    description=f"Connection pool {utilization:.1f}% utilized"
                ))
            
            # Check pool size configuration
            pool_size = getattr(settings, 'DB_POOL_SIZE', 20)
            if pool_size < max_conn * 0.5:
                suggestions.append(OptimizationResult(
                    category="connection_pool",
                    name="pool_size",
                    current_value=pool_size,
                    recommended_value=int(max_conn * 0.7),
                    impact="medium",
                    description="Connection pool size can be increased"
                ))
                
        except Exception as e:
            print(f"  ⚠️  Could not analyze connection pool: {e}")
        
        self.optimizations.extend(suggestions)
        return suggestions
    
    def analyze_cache_settings(self) -> List[OptimizationResult]:
        """Analyze Redis cache settings."""
        print("\n💾 Analyzing cache settings...")
        
        suggestions = []
        
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL)
            
            # Get memory info
            info = r.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)
            
            if max_memory > 0:
                utilization = (used_memory / max_memory) * 100
                
                if utilization > 80:
                    suggestions.append(OptimizationResult(
                        category="cache",
                        name="maxmemory",
                        current_value=f"{max_memory / 1024 / 1024:.0f}MB",
                        recommended_value=f"{max_memory * 2 / 1024 / 1024:.0f}MB",
                        impact="high",
                        description=f"Redis memory {utilization:.1f}% utilized"
                    ))
            
            # Check eviction policy
            config = r.config_get("maxmemory-policy")
            eviction_policy = config.get("maxmemory-policy", "noeviction")
            
            if eviction_policy == "noeviction":
                suggestions.append(OptimizationResult(
                    category="cache",
                    name="maxmemory-policy",
                    current_value="noeviction",
                    recommended_value="allkeys-lru",
                    impact="medium",
                    description="LRU eviction provides better cache hit rate"
                ))
            
            # Check key count
            key_count = r.dbsize()
            if key_count > 1000000:
                suggestions.append(OptimizationResult(
                    category="cache",
                    name="key_count",
                    current_value=f"{key_count:,} keys",
                    recommended_value="Consider key expiration",
                    impact="medium",
                    description="Large key count may impact performance"
                ))
                
        except Exception as e:
            print(f"  ⚠️  Could not analyze cache: {e}")
        
        self.optimizations.extend(suggestions)
        return suggestions
    
    def analyze_query_patterns(self) -> List[OptimizationResult]:
        """Analyze query patterns for optimization opportunities."""
        print("\n📝 Analyzing query patterns...")
        
        suggestions = []
        
        # Common optimization patterns
        patterns = [
            {
                "name": "N+1 Query Detection",
                "check": self._check_n1_queries,
                "impact": "high"
            },
            {
                "name": "Missing Pagination",
                "check": self._check_pagination,
                "impact": "medium"
            },
            {
                "name": "Inefficient Joins",
                "check": self._check_join_efficiency,
                "impact": "high"
            },
        ]
        
        for pattern in patterns:
            try:
                result = pattern["check"]()
                if result:
                    suggestions.append(OptimizationResult(
                        category="query_pattern",
                        name=pattern["name"],
                        current_value=result.get("current", "Found"),
                        recommended_value=result.get("recommended", "Optimize"),
                        impact=pattern["impact"],
                        description=result.get("description", "")
                    ))
            except Exception:
                pass
        
        self.optimizations.extend(suggestions)
        return suggestions
    
    def _check_n1_queries(self) -> Optional[Dict]:
        """Check for N+1 query patterns."""
        # This would analyze query logs or APM data
        # For now, return None as placeholder
        return None
    
    def _check_pagination(self) -> Optional[Dict]:
        """Check for queries without pagination."""
        # Would analyze recent queries
        return None
    
    def _check_join_efficiency(self) -> Optional[Dict]:
        """Check for inefficient join patterns."""
        return None
    
    def generate_report(self) -> Dict:
        """Generate comprehensive optimization report."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": self.client_id,
            "analysis_duration_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "slow_queries": [
                {
                    "query": sq.query[:200],
                    "avg_time_ms": sq.avg_time_ms,
                    "max_time_ms": sq.max_time_ms,
                    "call_count": sq.call_count,
                    "suggestions": sq.suggestions
                }
                for sq in self.slow_queries[:10]
            ],
            "optimizations": [
                {
                    "category": opt.category,
                    "name": opt.name,
                    "current_value": str(opt.current_value),
                    "recommended_value": str(opt.recommended_value),
                    "impact": opt.impact,
                    "description": opt.description
                }
                for opt in self.optimizations
            ],
            "summary": {
                "total_optimizations": len(self.optimizations),
                "high_impact": len([o for o in self.optimizations if o.impact == "high"]),
                "medium_impact": len([o for o in self.optimizations if o.impact == "medium"]),
                "low_impact": len([o for o in self.optimizations if o.impact == "low"]),
                "slow_query_count": len(self.slow_queries)
            }
        }
    
    def apply_optimizations(self, dry_run: bool = True) -> List[OptimizationResult]:
        """Apply recommended optimizations."""
        print(f"\n🔧 {'Simulating' if dry_run else 'Applying'} optimizations...")
        
        applied = []
        db = next(get_db())
        
        for opt in self.optimizations:
            if opt.category == "index" and opt.impact == "high":
                try:
                    if not dry_run:
                        db.execute(opt.recommended_value)
                        db.commit()
                    opt.applied = True
                    applied.append(opt)
                    print(f"  ✅ {opt.name}: {'Would apply' if dry_run else 'Applied'}")
                except Exception as e:
                    print(f"  ❌ {opt.name}: Failed - {e}")
        
        return applied


def run_analysis(client_id: Optional[str] = None, apply: bool = False) -> Dict:
    """Run complete performance analysis."""
    analyzer = PerformanceAnalyzer(client_id)
    
    print("=" * 60)
    print("PARWA Performance Optimization Analysis")
    print("=" * 60)
    
    # Run all analyses
    analyzer.analyze_database_queries()
    analyzer.suggest_indexes()
    analyzer.analyze_connection_pool()
    analyzer.analyze_cache_settings()
    analyzer.analyze_query_patterns()
    
    # Apply optimizations if requested
    if apply:
        analyzer.apply_optimizations(dry_run=False)
    else:
        analyzer.apply_optimizations(dry_run=True)
    
    # Generate report
    report = analyzer.generate_report()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total optimizations found: {report['summary']['total_optimizations']}")
    print(f"  🔴 High impact: {report['summary']['high_impact']}")
    print(f"  🟡 Medium impact: {report['summary']['medium_impact']}")
    print(f"  🟢 Low impact: {report['summary']['low_impact']}")
    print(f"Slow queries identified: {report['summary']['slow_query_count']}")
    
    return report


def main():
    parser = argparse.ArgumentParser(description="PARWA Performance Optimization")
    parser.add_argument("--client", "-c", help="Client ID to analyze")
    parser.add_argument("--apply", "-a", action="store_true", help="Apply optimizations")
    parser.add_argument("--output", "-o", help="Output file for report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    report = run_analysis(client_id=args.client, apply=args.apply)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Report saved to: {args.output}")
    
    if args.json:
        print(json.dumps(report, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
