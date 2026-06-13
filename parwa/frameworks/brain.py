"""FrameworkBrain — Decision engine that selects and runs AI techniques.

The FrameworkBrain is the core of Phase 2. It sits inside each node and:
  1. Looks at the ticket complexity and node name
  2. Selects which technique(s) to activate
  3. Runs the selected techniques (in parallel where possible)
  4. Combines results using ENSEMBLE VOTING (P1 upgrade)
  5. Tracks which frameworks were activated in state

P0 UPGRADES:
  - MAX_TECHNIQUES_PER_NODE raised to 3 (from 1)
  - Smart technique selection: picks complementary techniques per node
  - Evidence-weighted merge: highest-confidence technique's output wins,
    but ALL chains and evidence are preserved
  - Structured evidence chain: each technique result carries (claim, source, confidence)
  - Variant-aware budget: mini gets 1 technique, parwa gets 2, high gets 3

P1 UPGRADES:
  - ENSEMBLE VOTING: When 2+ techniques produce outputs, they VOTE on the
    best answer. Techniques that agree get boosted; outliers get penalized.
    This is much more robust than just picking the highest-confidence output.
  - Agreement detection: If all techniques agree, confidence gets a major boost.
  - Disagreement detection: If techniques disagree, confidence drops and
    the disagreement is flagged in metadata for downstream nodes to handle.
  - Weighted voting: Each technique's vote is weighted by its reliability
    score (based on historical accuracy per node type).

Usage inside a node:
    brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
    result = await brain.think(
        prompt="Reason about this ticket",
        techniques=["cot", "react", "uot"],  # candidates, not all will activate
    )
    # result.chain, result.output, result.frameworks_used, result.evidence_chain, etc.

Complexity-based activation:
    Simple   → CoT only
    Medium   → CoT + one complementary technique
    Complex  → CoT + 2 complementary techniques
    Critical → Up to 3 techniques (best coverage)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from parwa.frameworks.base import TechniqueResult
from parwa.frameworks.registry import get_registry

logger = logging.getLogger("parwa.frameworks.brain")


# ─── P1: Technique reliability scores for weighted voting ─────────────────────
# Historical reliability of each technique per node category.
# These weights determine how much each technique's vote counts in ensemble
# voting. Higher = more reliable. These are starting estimates that will
# be tuned based on actual production performance.
_TECHNIQUE_RELIABILITY: dict[str, float] = {
    # Reasoning techniques — generally high reliability
    "chain_of_thought": 0.85,
    "react": 0.80,
    "tree_of_thoughts": 0.75,
    "reverse_thinking": 0.82,
    "uncertainty_of_thought": 0.78,
    "graph_strategic_thought": 0.73,
    "least_to_most": 0.77,
    # RAG techniques — moderate reliability (depends on KB quality)
    "clara": 0.72,
    "hyde": 0.68,
    "multi_query": 0.70,
    "step_back": 0.71,
    # Quality techniques — variable reliability
    "reflexion": 0.75,
    "self_consistency": 0.80,
    "crp": 0.70,
    "zero_shot_validator": 0.73,
    # Memory techniques — moderate
    "thread_of_thought": 0.65,
    "dynamic_context": 0.67,
    "contextual_compression": 0.60,
    # Proprietary techniques — variable (newer, less proven)
    "gsd": 0.70,
    "smart_router": 0.65,
    "maker": 0.60,
    "adaptive_budget": 0.55,
    "turbo_compress": 0.58,
    "federated_reasoning": 0.62,
    "meta_learner": 0.57,
}


# ─── Variant-aware technique budgets ──────────────────────────────────────────
# How many techniques each variant is allowed to run per node.
# Mini = cheaper (1), PARWA = balanced (2), High = thorough (3)
_VARIANT_TECHNIQUE_BUDGET = {
    "mini": 1,
    "parwa": 2,
    "high": 3,
}

# ─── Smart technique pairing rules ────────────────────────────────────────────
# For each node, define which techniques complement each other.
# The brain picks techniques in priority order, skipping those that
# overlap in function. This ensures diversity of reasoning.
_NODE_TECHNIQUE_PRIORITY: dict[str, list[str]] = {
    "REASONING_ENGINE": [
        "chain_of_thought",   # Always start with CoT (baseline reasoning)
        "react",              # Action-oriented reasoning (complements CoT)
        "uncertainty_of_thought",  # Doubt-checking (complements CoT+ReAct)
        "graph_strategic_thought",  # Multi-path strategic reasoning
    ],
    "REVERSE_THINKER": [
        "reverse_thinking",   # Primary: validates by working backwards
        "chain_of_thought",   # Complementary: forward reasoning for comparison
        "zero_shot_validator",  # Quick validation check
    ],
    "TREE_OF_THOUGHTS": [
        "tree_of_thoughts",   # Primary: explores multiple paths
        "graph_strategic_thought",  # Strategic analysis of paths
    ],
    "STRATEGY_PLANNER": [
        "graph_strategic_thought",  # Primary: strategic planning
        "chain_of_thought",   # Structured reasoning for strategy
        "least_to_most",      # Decomposition for complex strategy
    ],
    "ACTION_PLANNER": [
        "chain_of_thought",   # Reason about what actions to take
        "least_to_most",      # Decompose complex multi-step actions
        "react",              # Action-oriented planning
    ],
    "INTENT_CLASSIFIER": [
        "chain_of_thought",   # Step-by-step classification
        "react",              # Classify + verify
    ],
    "CONTEXT_MANAGER": [
        "clara",              # Context-aware retrieval
        "hyde",               # Hypothetical document embedding
        "dynamic_context",    # Dynamic context window
    ],
    "KB_RETRIEVER": [
        "react",              # Action-oriented retrieval reasoning
    ],
    "QUALITY_SCORER": [
        "reflexion",          # Self-critique scoring
        "self_consistency",   # Consistency check
        "crp",                # Constrained evaluation
    ],
    "RESPONSE_FORMATTER": [
        "crp",                # Constrained response protocol
        "chain_of_thought",   # Reasoned response generation
    ],
    "FAQ_MATCHER": [
        "chain_of_thought",   # Reason about FAQ match
    ],
    "SENTIMENT_ANALYZER": [
        "chain_of_thought",   # Reasoned sentiment analysis
    ],
    "ESCALATION_DECISION": [
        "uncertainty_of_thought",  # Doubt-checking before escalating
        "chain_of_thought",   # Step-by-step escalation reasoning
    ],
    "ACTION_VERIFIER": [
        "chain_of_thought",   # Verify actions step by step
        "zero_shot_validator",  # Quick validation
    ],
    "PROACTIVE_CHECKER": [
        "chain_of_thought",   # Reason about proactive follow-ups
    ],
    "PREDICTION_ENGINE": [
        "chain_of_thought",   # Reasoned predictions
    ],
    "PII_COMPLIANCE_GUARD": [
        "chain_of_thought",   # Step-by-step PII detection
    ],
    "SITUATION_MODEL": [
        "chain_of_thought",   # Structured context analysis
        "react",              # Action-oriented context reasoning
    ],
    "POLICY_GUARD": [
        "chain_of_thought",   # Structured policy analysis
    ],
    "META_REASONER": [
        "reflexion",          # Self-critique of reasoning structure
        "self_consistency",   # Check pipeline coherence
    ],
    "CONVERSATIONAL_REPAIR": [
        "crp",                # Constrained response repair
        "chain_of_thought",   # Step-by-step repair reasoning
    ],
}

# ─── Technique category groups (for diversity enforcement) ────────────────────
# Techniques in the same group are considered overlapping.
# The brain will prefer techniques from DIFFERENT groups when selecting multiple.
_TECHNIQUE_GROUPS: dict[str, str] = {
    # Reasoning group
    "chain_of_thought": "reasoning",
    "react": "reasoning_action",
    "tree_of_thoughts": "reasoning_explore",
    "reverse_thinking": "reasoning_validate",
    "uncertainty_of_thought": "reasoning_doubt",
    "graph_strategic_thought": "reasoning_strategy",
    "least_to_most": "reasoning_decompose",
    # RAG group
    "clara": "rag_context",
    "hyde": "rag_query",
    "multi_query": "rag_query",
    "step_back": "rag_query",
    # Quality group
    "reflexion": "quality_critique",
    "self_consistency": "quality_consistency",
    "crp": "quality_constrain",
    "zero_shot_validator": "quality_validate",
    # Memory group
    "thread_of_thought": "memory_thread",
    "dynamic_context": "memory_context",
    "contextual_compression": "memory_compress",
    # Proprietary group
    "gsd": "proprietary_compress",
    "smart_router": "proprietary_route",
    "maker": "proprietary_maker",
    "adaptive_budget": "proprietary_budget",
    "turbo_compress": "proprietary_compress",
    "federated_reasoning": "proprietary_federate",
    "meta_learner": "proprietary_meta",
}


class FrameworkBrain:
    """Decision engine that selects and runs AI techniques inside a node.

    The brain does NOT replace the node. It makes the node smarter by
    selecting the right technique(s) based on ticket complexity and
    running them with the production-hardened LLM client.

    P0 UPDATES:
      - Techniques run in parallel (asyncio.gather) for speed
      - Results merged with evidence-weighted merge (not last-wins)
      - Evidence chain: structured (claim, source, confidence) tuples
      - Variant-aware: mini=1, parwa=2, high=3 techniques per node

    Args:
        node: The node name (e.g. "REASONING_ENGINE").
        state: The current ticket state dict.
    """

    def __init__(self, node: str, state: dict[str, Any]) -> None:
        self.node = node
        self.state = state
        self._registry = get_registry()

    def _get_max_techniques(self, variant: str, complexity: str) -> int:
        """Get the maximum number of techniques for this variant + complexity.

        Variant budget is the hard cap. Complexity can reduce it further:
        - Simple: 1 technique (don't overthink simple tickets)
        - Medium: up to variant budget
        - Complex/Critical: up to variant budget

        This saves tokens on simple tickets while allowing full power on hard ones.
        """
        variant_budget = _VARIANT_TECHNIQUE_BUDGET.get(variant, 2)

        if complexity == "simple":
            return min(1, variant_budget)  # Simple = 1 technique max
        elif complexity == "medium":
            return min(2, variant_budget)  # Medium = up to 2
        else:
            return variant_budget  # Complex/Critical = full variant budget

    def _select_techniques(
        self,
        candidate_names: list[str],
        max_techniques: int,
        complexity: str,
    ) -> list[Any]:
        """Select the best diverse set of techniques from candidates.

        Selection strategy:
        1. Start with node-priority techniques (if available)
        2. Fill remaining slots with registry candidates, preferring
           techniques from different groups (diversity)
        3. Activate techniques for ALL complexity levels — the budget
           (max_techniques) controls quantity, not the complexity gate:
           - SIMPLE: 1 technique (CoT or most relevant)
           - MEDIUM: 2 techniques (CoT + one complementary)
           - COMPLEX: 2-3 techniques (CoT + ReAct/UoT)
           - CRITICAL: 3 techniques (CoT + ReAct + UoT)

        FIX (Bug #4): Previously, technique.can_apply() filtered out
        most techniques at SIMPLE complexity because many have
        _min_complexity >= "medium". This meant 24 techniques never
        activated for the majority of tickets (which default to SIMPLE).
        Now, the complexity gate is bypassed — node applicability is
        still checked, but the technique budget alone controls how
        many techniques run.

        Returns a list of technique instances (up to max_techniques).
        """
        # Get priority list for this node
        priority_names = _NODE_TECHNIQUE_PRIORITY.get(self.node, [])

        # Build pool of valid candidates
        # BUG #4 FIX: Check node applicability but bypass the complexity
        # gate. The budget (max_techniques) already limits how many
        # techniques run per complexity level, so the _min_complexity
        # check in can_apply() is redundant and was preventing SIMPLE
        # tickets from getting any techniques at all.
        candidates: list[Any] = []
        for name in candidate_names:
            technique = self._registry.get(name)
            if technique is None:
                logger.warning("brain: technique '%s' not found in registry, skipping", name)
                continue
            # Check node applicability only (not complexity — budget handles that)
            if technique.applicable_nodes and self.node not in technique.applicable_nodes:
                continue
            candidates.append(technique)

        if not candidates:
            return []

        if max_techniques <= 0:
            return []

        # If only 1 technique allowed, pick the highest-priority one
        if max_techniques == 1:
            # Prefer priority-list techniques
            for pname in priority_names:
                for t in candidates:
                    if t.name == pname:
                        return [t]
            # Fall back to first candidate
            return [candidates[0]]

        # Multiple techniques: select with diversity
        selected: list[Any] = []
        selected_groups: set[str] = set()

        # First pass: pick from priority list in order
        for pname in priority_names:
            if len(selected) >= max_techniques:
                break
            for t in candidates:
                if t.name == pname and t not in selected:
                    group = _TECHNIQUE_GROUPS.get(t.name, "unknown")
                    selected.append(t)
                    selected_groups.add(group)
                    break

        # Second pass: fill remaining slots with diverse candidates
        for t in candidates:
            if len(selected) >= max_techniques:
                break
            if t in selected:
                continue
            group = _TECHNIQUE_GROUPS.get(t.name, "unknown")
            # Prefer techniques from a different group
            if group not in selected_groups:
                selected.append(t)
                selected_groups.add(group)

        # Third pass: if still not full, just add remaining
        for t in candidates:
            if len(selected) >= max_techniques:
                break
            if t not in selected:
                selected.append(t)

        return selected

    @staticmethod
    def _compute_output_similarity(text_a: str, text_b: str) -> float:
        """Compute rough semantic similarity between two outputs.

        Uses keyword overlap (Jaccard similarity) as a fast approximation.
        This is NOT a full embedding-based similarity — it's a lightweight
        heuristic that works well enough for ensemble voting.

        Returns:
            Similarity score between 0.0 (no overlap) and 1.0 (identical keywords).
        """
        if not text_a or not text_b:
            return 0.0

        # Normalize and extract keywords (lowercase, strip punctuation)
        import re
        def _keywords(text: str) -> set[str]:
            words = re.findall(r'\b[a-z]{3,}\b', text.lower())
            # Remove common stop words
            stops = {"the", "and", "for", "that", "this", "with", "from", "are", "was",
                     "were", "been", "have", "has", "had", "will", "would", "could",
                     "should", "may", "might", "shall", "can", "not", "but", "our",
                     "your", "their", "what", "which", "when", "where", "who", "how",
                     "all", "each", "every", "both", "few", "more", "most", "other",
                     "some", "such", "than", "too", "very", "just", "also", "into"}
            return set(words) - stops

        kw_a = _keywords(text_a)
        kw_b = _keywords(text_b)

        if not kw_a or not kw_b:
            return 0.0

        # Jaccard similarity
        intersection = kw_a & kw_b
        union = kw_a | kw_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _ensemble_vote(
        results: list[tuple[Any, TechniqueResult]],
    ) -> tuple[str, float, dict[str, Any]]:
        """P1 ENSEMBLE VOTING: Techniques vote on the best answer.

        Instead of just picking the highest-confidence output, this method:
        1. Clusters outputs by semantic similarity
        2. Each technique's vote is weighted by its reliability score
        3. The cluster with the highest weighted vote count wins
        4. Agreement = confidence boost, Disagreement = confidence penalty

        This is significantly more robust than just picking max confidence
        because it catches cases where one technique hallucinates with
        high confidence while others disagree.

        Returns:
            (winning_output, final_confidence, vote_metadata)
        """
        if not results:
            return "", 0.0, {}

        if len(results) == 1:
            technique, result = results[0]
            reliability = _TECHNIQUE_RELIABILITY.get(technique.name, 0.5)
            # Single technique: confidence = result confidence * reliability
            adj_conf = result.confidence * reliability
            return (
                result.output,
                adj_conf,
                {
                    "vote_type": "single",
                    "technique": technique.name,
                    "reliability": reliability,
                    "raw_confidence": result.confidence,
                },
            )

        # Step 1: Build clusters of similar outputs
        # Each cluster = (representative_output, [list of (technique, result, weight)])
        SIMILARITY_THRESHOLD = 0.35  # Outputs with >35% keyword overlap are "similar"
        clusters: list[tuple[str, list[tuple[Any, TechniqueResult, float]]]] = []

        for technique, result in results:
            if not result.output:
                continue

            reliability = _TECHNIQUE_RELIABILITY.get(technique.name, 0.5)
            vote_weight = reliability * max(result.confidence, 0.1)

            # Find the best matching cluster
            best_cluster_idx = -1
            best_sim = 0.0
            for idx, (rep_output, _) in enumerate(clusters):
                sim = FrameworkBrain._compute_output_similarity(result.output, rep_output)
                if sim > best_sim:
                    best_sim = sim
                    best_cluster_idx = idx

            if best_sim >= SIMILARITY_THRESHOLD and best_cluster_idx >= 0:
                # Add to existing cluster
                clusters[best_cluster_idx][1].append((technique, result, vote_weight))
            else:
                # Create new cluster
                clusters.append((result.output, [(technique, result, vote_weight)]))

        if not clusters:
            # All outputs were empty — fall back to first result
            technique, result = results[0]
            return result.output or "", 0.0, {"vote_type": "fallback_empty"}

        # Step 2: Count weighted votes per cluster
        cluster_scores: list[tuple[str, float, int, list[str]]] = []
        for rep_output, members in clusters:
            total_weight = sum(w for _, _, w in members)
            member_names = [t.name for t, _, _ in members]
            cluster_scores.append((rep_output, total_weight, len(members), member_names))

        # Sort by total weight (highest wins)
        cluster_scores.sort(key=lambda x: x[1], reverse=True)

        winner_output = cluster_scores[0][0]
        winner_weight = cluster_scores[0][1]
        winner_count = cluster_scores[0][2]
        winner_members = cluster_scores[0][3]

        # Step 3: Compute final confidence based on agreement level
        total_techniques = len(results)
        agreement_ratio = winner_count / total_techniques  # 1.0 = unanimous

        # Find the winner's raw confidence (highest among winning cluster)
        winner_raw_conf = 0.0
        for technique, result, _ in clusters[0][1] if clusters else []:
            if result.confidence > winner_raw_conf:
                winner_raw_conf = result.confidence

        # Final confidence calculation:
        # - Base: winner's raw confidence
        # - Agreement bonus: if multiple techniques agree, boost by up to 20%
        # - Disagreement penalty: if there's a strong dissenting cluster, penalize
        if total_techniques == 1:
            final_confidence = winner_raw_conf * _TECHNIQUE_RELIABILITY.get(results[0][0].name, 0.5)
        elif agreement_ratio >= 1.0:
            # Unanimous agreement — strong confidence boost
            final_confidence = min(1.0, winner_raw_conf * 1.20)
        elif agreement_ratio >= 0.66:
            # Majority agreement — moderate confidence
            final_confidence = winner_raw_conf * 1.05
        else:
            # Split decision — lower confidence, flag disagreement
            final_confidence = winner_raw_conf * 0.80

        # If there's a strong dissenting cluster, apply additional penalty
        if len(cluster_scores) > 1:
            second_weight = cluster_scores[1][1]
            if second_weight > winner_weight * 0.5:
                # Strong dissent — significant confidence penalty
                final_confidence *= 0.85

        final_confidence = max(0.0, min(1.0, final_confidence))

        # Step 4: Build vote metadata for transparency
        vote_meta = {
            "vote_type": "ensemble",
            "cluster_count": len(clusters),
            "agreement_ratio": round(agreement_ratio, 2),
            "winner_cluster_size": winner_count,
            "winner_members": winner_members,
            "winner_weight": round(winner_weight, 3),
            "unanimous": agreement_ratio >= 1.0,
            "has_dissent": len(cluster_scores) > 1,
            "all_clusters": [
                {
                    "representative": rep[:100],
                    "weight": round(w, 3),
                    "members": names,
                    "size": sz,
                }
                for rep, w, sz, names in cluster_scores
            ],
        }

        return winner_output, final_confidence, vote_meta

    @staticmethod
    def _merge_technique_results(
        results: list[tuple[Any, TechniqueResult]],
    ) -> TechniqueResult:
        """Merge results from multiple techniques using ENSEMBLE VOTING (P1).

        P1 UPGRADE: Replaces P0's "highest confidence wins" with ensemble voting:
        - OUTPUT: Determined by weighted VOTE across techniques (not just max confidence)
        - CHAIN: Concatenate ALL chains (preserves full reasoning trace)
        - EVIDENCE CHAIN: Build structured (claim, source, confidence) entries
        - CONFIDENCE: Based on agreement level (unanimous = boost, split = penalty)
        - METADATA: Full voting details for debugging and transparency

        Why this is better:
        - Catches hallucinations: if one technique hallucinates with high confidence
          but others disagree, voting will override it
        - Agreement detection: unanimous agreement → high confidence
        - Disagreement detection: split vote → confidence penalty + flagged metadata
        - Weighted by reliability: proven techniques get more voting power

        Args:
            results: List of (technique, result) tuples.

        Returns:
            Single merged TechniqueResult.
        """
        if not results:
            return TechniqueResult(
                output="",
                chain=[],
                confidence=0.0,
                frameworks_used=[],
                metadata={"activated_count": 0},
            )

        if len(results) == 1:
            technique, result = results[0]
            evidence_chain = FrameworkBrain._build_evidence_chain(results)
            return TechniqueResult(
                output=result.output,
                chain=result.chain,
                confidence=result.confidence,
                frameworks_used=result.frameworks_used,
                metadata={
                    **result.metadata,
                    "activated_count": 1,
                    "evidence_chain": evidence_chain,
                    "vote_type": "single",
                },
                token_estimate=result.token_estimate,
                error=result.error,
            )

        # Multiple results: use ENSEMBLE VOTING (P1)
        combined_chain: list[str] = []
        combined_frameworks: list[str] = []
        combined_metadata: dict[str, Any] = {"activated_count": len(results)}
        total_tokens = 0
        all_errors: list[str] = []

        for technique, result in results:
            # Accumulate chains (ALL reasoning preserved)
            if result.chain:
                prefixed = [f"[{technique.name}] {step}" for step in result.chain]
                combined_chain.extend(prefixed)

            # Track frameworks
            if result.frameworks_used:
                combined_frameworks.extend(result.frameworks_used)

            # Token tracking
            total_tokens += result.token_estimate

            # Per-technique metadata
            combined_metadata[f"technique_{technique.name}"] = {
                "output_length": len(result.output),
                "chain_length": len(result.chain),
                "confidence": result.confidence,
                "reliability": _TECHNIQUE_RELIABILITY.get(technique.name, 0.5),
                "token_estimate": result.token_estimate,
                "error": result.error,
            }

            if result.error:
                all_errors.append(f"{technique.name}: {result.error}")

        # P1: Use ensemble voting to determine best output and confidence
        winner_output, vote_confidence, vote_meta = FrameworkBrain._ensemble_vote(results)

        # Build evidence chain
        evidence_chain = FrameworkBrain._build_evidence_chain(results)
        combined_metadata["evidence_chain"] = evidence_chain
        combined_metadata["vote"] = vote_meta

        # If voting produced no output, fall back to last chain entry
        if not winner_output and combined_chain:
            winner_output = combined_chain[-1].replace("[", "").split("]", 1)[-1].strip()

        return TechniqueResult(
            output=winner_output,
            chain=combined_chain,
            confidence=vote_confidence,
            frameworks_used=list(dict.fromkeys(combined_frameworks)),  # dedupe, preserve order
            metadata=combined_metadata,
            token_estimate=total_tokens,
            error="; ".join(all_errors) if all_errors else None,
        )

    @staticmethod
    def _build_evidence_chain(
        results: list[tuple[Any, TechniqueResult]],
    ) -> list[dict[str, Any]]:
        """Build a structured evidence chain from technique results.

        Each entry: {claim, source, confidence, technique}
        This is the P0 EVIDENCE CHAIN that flows between nodes.

        Instead of passing just "Customer is eligible for refund" as a
        conclusion string, the evidence chain passes:
        - claim: "Customer is eligible for refund"
        - source: "CRM shows duplicate charge of $49.99"
        - confidence: 0.95
        - technique: "chain_of_thought"

        Downstream nodes can then verify, cross-reference, and build
        upon this structured evidence instead of trusting a bare string.
        """
        chain: list[dict[str, Any]] = []

        for technique, result in results:
            # The main claim = the technique's output/conclusion
            claim = result.output.strip() if result.output else ""
            if not claim and result.chain:
                # If no explicit output, use the last chain step as the claim
                claim = result.chain[-1]

            # Evidence sources = the chain steps that support the claim
            sources = []
            if result.chain:
                # Take the first N steps as evidence (skip the conclusion step)
                evidence_steps = result.chain[:-1] if len(result.chain) > 1 else result.chain
                sources = [step.strip() for step in evidence_steps if step.strip()]

            if claim:
                chain.append({
                    "claim": claim,
                    "sources": sources,
                    "confidence": result.confidence,
                    "technique": technique.name,
                    "category": technique.category.value,
                })

        return chain

    async def think(
        self,
        prompt: str,
        techniques: list[str] | None = None,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Select and run techniques based on ticket complexity.

        P0 UPDATES:
        - Techniques run in PARALLEL (asyncio.gather) for speed
        - Smart selection with diversity enforcement
        - Evidence-weighted merge instead of "last wins"
        - Variant-aware technique budget

        Args:
            prompt: The reasoning prompt for the technique.
            techniques: Optional list of candidate technique names.
                       If None, uses all techniques applicable to this node.
            ticket_id: Current ticket ID for tracking.
            variant: Current variant for budget allocation.

        Returns:
            Combined TechniqueResult from all activated techniques.
        """
        complexity = self.state.get("complexity", "simple")
        candidate_names = techniques or self._registry.get_technique_names_for_node(self.node)

        # Get variant-aware technique budget
        max_techniques = self._get_max_techniques(variant, complexity)

        # Smart selection with diversity
        activated = self._select_techniques(candidate_names, max_techniques, complexity)

        if not activated:
            logger.debug("brain: no techniques activated for node=%s complexity=%s", self.node, complexity)
            return TechniqueResult(
                output="",
                chain=[],
                confidence=0.0,
                frameworks_used=[],
                metadata={"activated_count": 0, "complexity": complexity},
            )

        logger.debug(
            "brain: activated %d techniques for node=%s complexity=%s variant=%s: %s",
            len(activated), self.node, complexity, variant,
            [t.name for t in activated],
        )

        # Run ALL techniques in parallel (P0: was sequential before)
        # Each technique is independent, so they can run concurrently
        async def _safe_run(technique: Any) -> tuple[Any, TechniqueResult]:
            """Run a single technique, catching any exception."""
            try:
                result = await technique.think(
                    prompt,
                    self.state,
                    ticket_id=ticket_id,
                    variant=variant,
                )
                return technique, result
            except Exception as exc:
                logger.warning(
                    "brain: technique=%s FAILED on node=%s: %s",
                    technique.name, self.node, exc,
                )
                # Return a failure result instead of crashing
                failed_result = TechniqueResult(
                    output="",
                    chain=[f"[{technique.name}] FAILED: {exc}"],
                    confidence=0.0,
                    frameworks_used=[technique.name],
                    metadata={"error": str(exc), "failed": True},
                    token_estimate=0,
                    error=str(exc),
                )
                return technique, failed_result

        # Execute all techniques in parallel
        results_list = await asyncio.gather(
            *[_safe_run(t) for t in activated],
            return_exceptions=False,  # We handle exceptions in _safe_run
        )

        # Filter out completely failed techniques (confidence=0 and no output)
        valid_results = []
        for technique, result in results_list:
            if result.output or result.chain:
                valid_results.append((technique, result))
            else:
                logger.debug(
                    "brain: technique=%s produced no output on node=%s, skipping from merge",
                    technique.name, self.node,
                )

        if not valid_results:
            # All techniques failed — return the first failure as the result
            if results_list:
                technique, result = results_list[0]
                return TechniqueResult(
                    output=result.output,
                    chain=result.chain,
                    confidence=0.0,
                    frameworks_used=result.frameworks_used,
                    metadata={
                        **result.metadata,
                        "activated_count": len(activated),
                        "all_failed": True,
                        "complexity": complexity,
                        "node": self.node,
                    },
                    token_estimate=0,
                    error=result.error or "All techniques produced no output",
                )
            return TechniqueResult(
                output="",
                chain=[],
                confidence=0.0,
                frameworks_used=[],
                metadata={"activated_count": 0, "complexity": complexity},
            )

        # Merge results using evidence-weighted merge (P0: was last-wins)
        merged = self._merge_technique_results(valid_results)

        # Add pipeline-level metadata
        merged.metadata["complexity"] = complexity
        merged.metadata["node"] = self.node
        merged.metadata["variant"] = variant

        logger.debug(
            "brain: merged %d techniques for node=%s confidence=%.2f frameworks=%s",
            len(valid_results), self.node, merged.confidence,
            merged.frameworks_used,
        )

        return merged

    async def think_single(
        self,
        technique_name: str,
        prompt: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Run a single specific technique by name.

        Useful when a node knows exactly which technique it needs
        (e.g. reverse_thinker always uses Reverse Thinking).

        Args:
            technique_name: The technique to run.
            prompt: The reasoning prompt.
            ticket_id: Current ticket ID.
            variant: Current variant.

        Returns:
            TechniqueResult from the single technique.

        Raises:
            ValueError: If the technique name is not found in registry.
        """
        technique = self._registry.get(technique_name)
        if technique is None:
            raise ValueError(f"Technique '{technique_name}' not found in registry")

        result = await technique.think(
            prompt,
            self.state,
            ticket_id=ticket_id,
            variant=variant,
        )

        # Add evidence chain even for single technique
        evidence_chain = self._build_evidence_chain([(technique, result)])
        result.metadata["evidence_chain"] = evidence_chain

        return result
