# Graph Report - parwa  (2026-06-10)

## Corpus Check
- 34 files · ~11,896 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 411 nodes · 697 edges · 27 communities (24 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c000db1f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]

## God Nodes (most connected - your core abstractions)
1. `get_mock_llm()` - 21 edges
2. `get_llm()` - 20 edges
3. `intent_classifier()` - 14 edges
4. `action_executor()` - 13 edges
5. `ActionType` - 13 edges
6. `Any` - 12 edges
7. `ingest()` - 12 edges
8. `sentiment_analyzer()` - 12 edges
9. `escalation_decision()` - 11 edges
10. `pii_compliance_guard()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `Any` --uses--> `TicketChannel`  [INFERRED]
  parwa/nodes/ingest.py → parwa/state.py
- `Any` --uses--> `SentimentType`  [INFERRED]
  parwa/nodes/sentiment_analyzer.py → parwa/state.py
- `parwa_graph()` --calls--> `build_parwa_graph()`  [EXTRACTED]
  tests/test_graph.py → parwa/graph.py
- `Any` --uses--> `ActionType`  [INFERRED]
  parwa/nodes/action_executor.py → parwa/state.py
- `Any` --uses--> `ExecutionMode`  [INFERRED]
  parwa/nodes/action_executor.py → parwa/state.py

## Import Cycles
- None detected.

## Communities (27 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (42): ActionType, Enum, ExecutionMode, Node 8: ACTION_EXECUTOR — Executes planned actions or creates recommendations., action_planner(), _plan_actions_rule_based(), Node 7: ACTION_PLANNER — Decides what actions should be taken.  Action Agent nod, Create action plans based on intent and strategy. (+34 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (41): _after_action_verifier(), _after_escalation(), _after_faq_matcher(), _after_quality_scorer(), _after_reasoning(), _after_reverse_thinker(), _after_sentiment(), _after_strategy_planner() (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (28): BaseChatModel, Determine escalation using LLM. Returns (should_escalate, reason)., _should_escalate_llm(), _classify_intent_llm(), Classify intent using LLM. Returns (intent, confidence)., Node 6: REASONING_ENGINE — Thinks through the problem using Chain of Thought.  R, Reason through the problem using Chain of Thought.      Reads: raw_message, inte, Reason using rule-based chain of thought. Returns (chain, conclusion). (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (23): audit_logger(), Node 16: AUDIT_LOGGER — Logs every action and decision for compliance and debugg, Log all actions and decisions for audit trail.      Reads: ticket_id, intent, ac, feedback_loop(), _generate_feedback_signal(), Node 22: FEEDBACK_LOOP — Captures customer reaction for continuous improvement., Generate a feedback signal from the ticket resolution., Capture feedback signal for continuous improvement.      Reads: intent, quality_ (+15 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (22): KnowledgeResult, faq_matcher(), _match_faq_llm(), _match_faq_rule_based(), Node 3: FAQ_MATCHER — Checks if this is a known frequently asked question.  Know, Match against FAQs using keyword matching., Match against FAQs using LLM., Match the ticket against known FAQs.      Reads: raw_message, intent     Writes: (+14 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (18): _predict_issues_rule_based(), prediction_engine(), Node 14: PREDICTION_ENGINE — Forecasts future issues or follow-up needs.  Proact, Predict future issues based on current interaction., Forecast future issues or follow-up needs.      Reads: intent, integration_data,, _check_proactive_rule_based(), proactive_checker(), Node 13: PROACTIVE_CHECKER — Anticipates what the customer might ask next.  Proa (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (13): BaseModel, _explore_paths_rule_based(), Node 12: TREE_OF_THOUGHTS — Explores multiple solution paths and picks the best., Generate multiple solution paths based on intent. Returns list of ReasoningPath, Explore multiple solution paths and select the best one.      Reads: intent, rea, tree_of_thoughts(), Any, Central state object that flows through all 22 nodes.      This is the single so (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.19
Nodes (10): _detect_pii(), pii_compliance_guard(), Node 15: PII_COMPLIANCE_GUARD — Redacts PII and enforces compliance rules.  Comp, Detect PII in text. Returns (has_pii, found_items)., Redact PII from text, replacing with placeholders., Detect and redact PII from the response.      Reads: final_response (or raw_mess, _redact_pii(), Any (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.19
Nodes (10): action_verifier(), Node 9: ACTION_VERIFIER — Verifies the action was successful or recommendation i, Verify that all executed actions completed successfully., Verify that a recommendation has all required fields., Verify that actions were executed or recommendations are complete.      Reads: e, _verify_execution(), _verify_recommendation(), Any (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.21
Nodes (8): _classify_intent_rule_based(), _determine_complexity(), intent_classifier(), Classify intent using keyword matching. Returns (intent, confidence)., Determine ticket complexity based on intent confidence., Classify the intent of the customer's message.      Reads: raw_message     Write, Node 2: INTENT_CLASSIFIER, TestIntentClassifier

### Community 10 - "Community 10"
Cohesion: 0.23
Nodes (9): action_executor(), _create_recommendation(), _execute_action(), Execute an action directly. Returns execution result., Create a recommendation for human approval (Mini PARWA)., Execute or recommend actions based on variant permissions.      Reads: action_pl, Any, Node 8: ACTION_EXECUTOR — KEY VARIANT DIFFERENTIATION NODE (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (10): 22-Node Architecture (in pipeline order), 6 Agents (node ownership), Architecture: Same Brain, Different Capacity, Key Rules, PARWA - AI Customer Service Platform, Project Overview, Project Structure, Tech Stack (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (8): quality_scorer(), Node 21: QUALITY_SCORER — Scores the response before sending.  Compliance Agent, Score response quality using rules. Returns (score, issues)., Score the quality of the response before sending.      Reads: intent, reasoning_, _score_quality_rule_based(), Any, Node 21: QUALITY_SCORER, TestQualityScorer

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (8): _format_response_rule_based(), Node 17: RESPONSE_FORMATTER — Crafts the final customer-facing response.  Compli, Format the final response using rules., Craft the final customer-facing response.      Reads: intent, reasoning_conclusi, response_formatter(), Any, Node 17: RESPONSE_FORMATTER, TestResponseFormatter

### Community 14 - "Community 14"
Cohesion: 0.24
Nodes (8): Node 10: REVERSE_THINKER — Works backwards from the goal to validate the solutio, Validate conclusion by tracing backwards. Returns validation dict., Validate the reasoning conclusion by working backwards.      Reads: reasoning_co, _reverse_think_rule_based(), reverse_thinker(), Any, Node 10: REVERSE_THINKER, TestReverseThinker

### Community 15 - "Community 15"
Cohesion: 0.24
Nodes (7): _analyze_sentiment_rule_based(), Analyze sentiment using keyword matching. Returns (sentiment, urgency)., Analyze customer sentiment and urgency.      Reads: raw_message     Writes: sent, sentiment_analyzer(), Any, Node 18: SENTIMENT_ANALYZER, TestSentimentAnalyzer

### Community 16 - "Community 16"
Cohesion: 0.22
Nodes (8): _plan_strategy_rule_based(), Node 11: STRATEGY_PLANNER — Creates a multi-step plan before executing.  Reasoni, Create a strategy plan based on intent and selected path., Create a multi-step execution plan.      Reads: intent, reasoning_conclusion, se, strategy_planner(), Any, Node 11: STRATEGY_PLANNER, TestStrategyPlanner

### Community 17 - "Community 17"
Cohesion: 0.24
Nodes (6): context_manager(), Node 19: CONTEXT_MANAGER — Manages conversation history and unresolved issues., Manage conversation context and history.      Reads: customer_id, raw_message, Any, Node 19: CONTEXT_MANAGER, TestContextManager

### Community 18 - "Community 18"
Cohesion: 0.20
Nodes (6): PARWA High should EXECUTE refund directly., All variants should have identical thinking (intent, sentiment, reasoning)., Test that variants think identically but act differently., Mini PARWA should RECOMMEND refund, not execute., PARWA should EXECUTE refund directly., TestVariantDifferentiation

### Community 19 - "Community 19"
Cohesion: 0.28
Nodes (6): escalation_decision(), Determine escalation using rules. Returns (should_escalate, reason)., Decide whether to escalate this ticket to a human.      Reads: raw_message, sent, _should_escalate_rule_based(), Node 20: ESCALATION_DECISION, TestEscalationDecision

### Community 20 - "Community 20"
Cohesion: 0.33
Nodes (4): ingest(), Receive and validate a raw ticket.      Reads: raw_message, customer_id, channel, Any, TestIngest

### Community 21 - "Community 21"
Cohesion: 0.25
Nodes (5): Test complete ticket processing through the full graph., Test a refund ticket on PARWA variant — should execute refund., Test a simple order status inquiry., Test a cancellation request., TestFullPipeline

### Community 22 - "Community 22"
Cohesion: 0.33
Nodes (4): Test that quality scoring loop-back works., Every response should have a quality score., Every response should have an audit log., TestQualityLoopBack

### Community 23 - "Community 23"
Cohesion: 0.50
Nodes (3): Agent, PARWA Agent definitions.  6 Agents, each owning specific nodes. All 6 agents wor, A PARWA agent that owns a set of nodes.

## Knowledge Gaps
- **19 isolated node(s):** `Any`, `Any`, `Any`, `Any`, `Any` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `action_executor()` connect `Community 10` to `Community 0`, `Community 1`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `intent_classifier()` connect `Community 9` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `get_mock_llm()` connect `Community 2` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 12`, `Community 13`, `Community 14`, `Community 16`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `ActionType` (e.g. with `ActionType` and `ExecutionMode`) actually correct?**
  _`ActionType` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PARWA - AI Customer Service Platform  Same Brain, Different Capacity. All 22 nod`, `PARWA Agent definitions.  6 Agents, each owning specific nodes. All 6 agents wor`, `A PARWA agent that owns a set of nodes.` to the rest of the system?**
  _174 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.0783673469387755 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06183574879227053 - nodes in this community are weakly interconnected._