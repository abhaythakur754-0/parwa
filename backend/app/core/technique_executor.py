"""
TechniqueExecutor — Central orchestrator that wires all technique
infrastructure together (BC-013, SG-02, SG-14, SG-16).

Execution flow for each query:
  1. TechniqueRouter determines which techniques activate
  2. TechniqueTierAccessChecker filters by variant tier
  3. For each technique: cache check -> execute -> metrics -> cache store
  4. Fallback applied if T3 technique fails
  5. Returns updated ConversationState + PipelineResult

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from app.core.technique_router import (
    FALLBACK_MAP,
    TechniqueActivation,
    TechniqueID,
    TechniqueRouter,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
)
from app.core.technique_caching import TechniqueCache
from app.core.technique_metrics import TechniqueMetricsCollector
from app.core.technique_tier_access import TechniqueTierAccessChecker
from app.core.techniques.base import (
    ConversationState,
    TECHNIQUE_NODES,
)
from app.logger import get_logger

logger = get_logger("technique_executor")


# ── Data Structures ──────────────────────────────────────────────────


@dataclass
class ExecutionDetail:
    """Details of a single technique execution."""

    technique_id: str = ""
    tier: str = ""
    status: str = "pending"
    tokens_used: int = 0
    exec_time_ms: float = 0.0
    cached: bool = False
    fallback_applied: bool = False
    error: Optional[str] = None
    executed_at: str = ""


@dataclass
class PipelineResult:
    """Result of executing the full technique pipeline."""

    techniques_executed: int = 0
    techniques_cached: int = 0
    techniques_skipped: int = 0
    techniques_failed: int = 0
    total_tokens_used: int = 0
    total_exec_time_ms: float = 0.0
    details: List[ExecutionDetail] = field(default_factory=list)
    fallback_count: int = 0


# ── Technique Executor ──────────────────────────────────────────────


class TechniqueExecutor:
    """
    Central orchestrator for technique execution.

    Wires TechniqueRouter + TechniqueTierAccessChecker +
    TechniqueCache + TechniqueMetricsCollector + TECHNIQUE_NODES.
    """

    def __init__(
        self,
        model_tier: str = "medium",
        variant_type: str = "parwa",
        company_id: str = "",
    ) -> None:
        self.model_tier = model_tier
        self.variant_type = variant_type
        self.company_id = company_id

        self.router = TechniqueRouter(model_tier=model_tier)
        self.tier_checker = TechniqueTierAccessChecker()
        self.cache = TechniqueCache()
        self.metrics = TechniqueMetricsCollector()

    # ── Main Pipeline ──────────────────────────────────────────────

    async def execute_pipeline(
        self,
        state: ConversationState,
    ) -> tuple[ConversationState, PipelineResult]:
        """
        Execute the full technique pipeline on the given state.

        Flow: route -> filter by variant -> sort by tier -> execute.

        Returns:
            Tuple of (updated state, pipeline result with counters).
        """
        pipeline_result = PipelineResult()

        try:
            # 1. Route — determine which techniques activate
            router_result = self.router.route(state.signals)
        except Exception as exc:
            logger.error(
                "executor_routing_error",
                error=str(exc),
                company_id=self.company_id,
            )
            return state, pipeline_result

        # 2. Filter by variant tier access
        filtered = self._filter_by_tier_access(
            router_result.activated_techniques,
        )

        # 3. Sort by tier (T1 -> T2 -> T3) for execution order
        sorted_activations = self._sort_by_tier(filtered)

        # 4. Execute each technique
        for activation in sorted_activations:
            detail = await self._execute_with_infrastructure(
                activation,
                state,
            )
            pipeline_result.details.append(detail)

            if detail.status == "success":
                pipeline_result.techniques_executed += 1
                pipeline_result.total_tokens_used += detail.tokens_used
                pipeline_result.total_exec_time_ms += detail.exec_time_ms
                if detail.cached:
                    pipeline_result.techniques_cached += 1
            elif detail.status == "skipped_budget":
                pipeline_result.techniques_skipped += 1
            else:
                pipeline_result.techniques_failed += 1

            if detail.fallback_applied:
                pipeline_result.fallback_count += 1

        logger.info(
            "executor_pipeline_complete",
            company_id=self.company_id,
            variant=self.variant_type,
            executed=pipeline_result.techniques_executed,
            cached=pipeline_result.techniques_cached,
            skipped=pipeline_result.techniques_skipped,
            failed=pipeline_result.techniques_failed,
            total_tokens=pipeline_result.total_tokens_used,
            total_ms=round(pipeline_result.total_exec_time_ms, 2),
        )

        return state, pipeline_result

    async def execute_single(
        self,
        technique_id: TechniqueID,
        state: ConversationState,
    ) -> ConversationState:
        """Execute a single technique with caching and metrics."""
        activation = TechniqueActivation(
            technique_id=technique_id,
            triggered_by=["manual_single"],
            tier=TECHNIQUE_REGISTRY[technique_id].tier,
        )
        await self._execute_with_infrastructure(activation, state)
        return state

    # ── Infrastructure-Aware Execution ─────────────────────────────

    async def _execute_with_infrastructure(
        self,
        activation: TechniqueActivation,
        state: ConversationState,
    ) -> ExecutionDetail:
        """Execute a technique with cache, metrics, and fallback."""
        tid = activation.technique_id
        tid_str = tid.value if isinstance(tid, TechniqueID) else str(tid)
        tier_str = activation.tier.value
        now = datetime.now(timezone.utc).isoformat()
        start_ms = time.monotonic() * 1000

        detail = ExecutionDetail(
            technique_id=tid_str,
            tier=tier_str,
            executed_at=now,
        )

        # Get node from registry
        node = TECHNIQUE_NODES.get(tid)
        if node is None:
            detail.status = "error"
            detail.error = f"technique_node_not_found:{tid_str}"
            self.metrics.record_execution(
                technique_id=tid_str,
                variant=self.variant_type,
                company_id=self.company_id,
                status="error",
                exec_time_ms=0.0,
            )
            return detail

        # Check budget
        info = TECHNIQUE_REGISTRY.get(tid)
        if info and not node.check_token_budget(state):
            detail.status = "skipped_budget"
            node.record_skip(state, reason="budget_exceeded")
            logger.info(
                "executor_budget_skip",
                technique=tid_str,
                company_id=self.company_id,
            )
            return detail

        # Check cache
        query_hash = hashlib.sha256(
            state.query.encode(),
        ).hexdigest()
        signals_hash = hashlib.sha256(
            str(state.signals).encode(),
        ).hexdigest()

        try:
            cached_result = self.cache.get(
                technique_id=tid_str,
                query_hash=query_hash,
                signals_hash=signals_hash,
                company_id=self.company_id,
            )
        except Exception:
            cached_result = None

        if cached_result is not None:
            # Cache hit
            detail.status = "success"
            detail.cached = True
            detail.tokens_used = (
                cached_result.get("tokens_used", 0)
                if isinstance(cached_result, dict)
                else info.estimated_tokens if info else 0
            )
            detail.exec_time_ms = time.monotonic() * 1000 - start_ms

            # Record in state
            node.record_result(
                state,
                cached_result,
                tokens_used=detail.tokens_used,
            )

            self.metrics.record_execution(
                technique_id=tid_str,
                variant=self.variant_type,
                company_id=self.company_id,
                status="success",
                tokens_used=detail.tokens_used,
                exec_time_ms=detail.exec_time_ms,
            )
            logger.debug(
                "executor_cache_hit",
                technique=tid_str,
                company_id=self.company_id,
            )
            return detail

        # Execute technique
        try:
            exec_start = time.monotonic()
            state = await node.execute(state)
            exec_time = (time.monotonic() - exec_start) * 1000

            detail.status = "success"
            detail.tokens_used = info.estimated_tokens if info else 0
            detail.exec_time_ms = exec_time

            # Store in cache
            try:
                result_data = state.technique_results.get(tid_str, {})
                self.cache.set(
                    technique_id=tid_str,
                    query_hash=query_hash,
                    signals_hash=signals_hash,
                    company_id=self.company_id,
                    result=result_data,
                )
            except Exception as cache_err:
                logger.warning(
                    "executor_cache_store_error",
                    technique=tid_str,
                    error=str(cache_err),
                )

            self.metrics.record_execution(
                technique_id=tid_str,
                variant=self.variant_type,
                company_id=self.company_id,
                status="success",
                tokens_used=detail.tokens_used,
                exec_time_ms=detail.exec_time_ms,
            )

        except Exception as exc:
            detail.status = "error"
            detail.error = str(exc)
            detail.exec_time_ms = time.monotonic() * 1000 - start_ms

            logger.warning(
                "executor_technique_error",
                technique=tid_str,
                error=str(exc),
                company_id=self.company_id,
            )

            self.metrics.record_execution(
                technique_id=tid_str,
                variant=self.variant_type,
                company_id=self.company_id,
                status="error",
                exec_time_ms=detail.exec_time_ms,
            )

            # Apply fallback for T3 -> T2
            await self._apply_fallback(tid, state, exc, detail)

        return detail

    async def _apply_fallback(
        self,
        technique_id: TechniqueID,
        state: ConversationState,
        error: Exception,
        detail: ExecutionDetail,
    ) -> None:
        """Apply fallback technique when a technique fails."""
        tier = TECHNIQUE_REGISTRY.get(technique_id)
        if tier is None or tier.tier != TechniqueTier.TIER_3:
            return

        fallbacks = FALLBACK_MAP.get(technique_id, [])
        if not fallbacks:
            return

        for fb_id in fallbacks:
            fb_node = TECHNIQUE_NODES.get(fb_id)
            if fb_node is None:
                continue

            try:
                fb_start = time.monotonic()
                state = await fb_node.execute(state)
                fb_time = (time.monotonic() - fb_start) * 1000

                detail.fallback_applied = True
                detail.status = "success"
                detail.error = f"fallback_from_{
                    technique_id.value}_to_{
                    fb_id.value}"

                fb_info = TECHNIQUE_REGISTRY.get(fb_id)
                detail.tokens_used = fb_info.estimated_tokens if fb_info else 0

                logger.info(
                    "executor_fallback_applied",
                    original=technique_id.value,
                    fallback=fb_id.value,
                    company_id=self.company_id,
                )

                self.metrics.record_execution(
                    technique_id=fb_id.value,
                    variant=self.variant_type,
                    company_id=self.company_id,
                    status="success",
                    tokens_used=detail.tokens_used,
                    exec_time_ms=fb_time,
                )
                break  # first successful fallback wins

            except Exception as fb_err:
                logger.warning(
                    "executor_fallback_error",
                    original=technique_id.value,
                    fallback=fb_id.value,
                    error=str(fb_err),
                )

    # ── Variant Filtering ──────────────────────────────────────────

    def _filter_by_tier_access(
        self,
        activations: List[TechniqueActivation],
    ) -> List[TechniqueActivation]:
        """Filter techniques by variant tier access (SG-02)."""
        if not self.company_id:
            # No company context — allow all
            return list(activations)

        filtered: List[TechniqueActivation] = []
        for act in activations:
            tid_str = (
                act.technique_id.value
                if isinstance(act.technique_id, TechniqueID)
                else str(act.technique_id)
            )
            result = self.tier_checker.check_access(
                technique_id=tid_str,
                variant_type=self.variant_type,
                company_id=self.company_id,
            )

            if (
                result.decision.value == "allowed"
                or result.decision.value == "downgraded"
            ):
                filtered.append(act)
            # Blocked with no fallback — silently dropped

        return filtered

    # ── Tier Sorting ───────────────────────────────────────────────

    @staticmethod
    def _sort_by_tier(
        activations: List[TechniqueActivation],
    ) -> List[TechniqueActivation]:
        """Sort activations by tier: T1 -> T2 -> T3."""
        tier_order = {
            TechniqueTier.TIER_1: 0,
            TechniqueTier.TIER_2: 1,
            TechniqueTier.TIER_3: 2,
        }
        return sorted(
            activations,
            key=lambda a: tier_order.get(a.tier, 99),
        )

    # ── Utility ───────────────────────────────────────────────────

    def get_cache_key(
        self,
        technique_id: str,
        query: str,
        company_id: str = "",
    ) -> str:
        """Generate SHA-256 cache key."""
        raw = f"{technique_id}:{query}:{company_id}"
        return hashlib.sha256(raw.encode()).hexdigest()
