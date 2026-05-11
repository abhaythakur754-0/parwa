---
Task ID: 2-b
Agent: FAKE Voting Agent
Task: Create FAKE Voting Sub-System with multi-evaluator consensus

File Created:
- /home/z/my-project/parwa/backend/app/core/fake_voting.py (458 lines)

Dependencies Read (for context):
- /home/z/my-project/parwa/backend/app/core/langgraph/nodes/11_maker_validator.py — existing MAKER validator (685 lines)
- /home/z/my-project/parwa/backend/app/core/smart_router.py — SmartRouter, AtomicStepType.FAKE_VOTING
- /home/z/my-project/parwa/backend/app/core/langgraph/config.py — MAKER_CONFIG per tier
- /home/z/my-project/parwa/backend/app/logger.py — structlog get_logger

Components Built:
1. FakeVotingConfig (dataclass) — num_candidates, evaluators list, evaluator_weights dict, consensus_threshold, min_evaluators_agree, auto weight normalization in __post_init__
2. get_fake_voting_config(variant_type) — factory function with 3 presets:
   - mini_parwa: 3 candidates, 3 evaluators (fluency/relevance/safety), threshold 0.50, min_agree 2
   - parwa: 5 candidates, 4 evaluators (+accuracy), threshold 0.60, min_agree 3
   - parwa_high: 7 candidates, 5 evaluators (+empathy), threshold 0.75, min_agree 4
3. RedFlagEngine — 5 async check methods:
   - _check_hallucination_risk: speculative language patterns (I think, probably, might be, etc.)
   - _check_pii_leakage: regex for email, phone, SSN, credit card
   - _check_off_topic: keyword Jaccard similarity < 0.05
   - _check_policy_violation: guarantees, promises, legal advice patterns
   - _check_confidence_mismatch: low score + confident language, or high score + uncertain language
4. FakeVotingEngine — main voting engine:
   - vote(): evaluates all candidates, computes weighted consensus, selects winner
   - evaluate_fluency(): LLM scoring + sentence variance/repetition heuristic fallback
   - evaluate_relevance(): LLM scoring + keyword Jaccard similarity fallback
   - evaluate_accuracy(): LLM scoring + neutral 0.5 fallback
   - evaluate_safety(): keyword blocklist first, then LLM; takes minimum of both
   - evaluate_empathy(): LLM scoring + empathy keyword detection fallback
   - _llm_score(): SmartRouter integration via AtomicStepType.FAKE_VOTING
   - _parse_score(): handles 0.85, 75%, Score: 0.9, integer 0-100

Testing Results:
- All imports validated OK
- get_fake_voting_config returns correct presets for all 3 variants + unknown fallback
- Weight normalization: all presets sum to 1.0000
- RedFlagEngine correctly flags: hallucination_risk (medium) with 3 speculative phrases, pii_leakage (medium) with email+phone
- _parse_score handles: 0.85→0.85, 75%→0.75, Score: 0.9→0.9, ''→None, 'no number'→None
- Full vote pipeline: 3 candidates scored, winner selected (score 0.5595), 2 red flags raised
- BC-008 verified: system gracefully handles SmartRouter failures and falls back to heuristic evaluators

Integration Points:
- Designed as drop-in enhancement for 11_maker_validator.py's _score_solution/_score_all_solutions
- vote() returns same shape: {winner, consensus_score, all_scores, red_flags, voting_summary}
- Red flags integrate with Loophole Registry pattern
- SmartRouter integration via AtomicStepType.FAKE_VOTING (LIGHT tier)
