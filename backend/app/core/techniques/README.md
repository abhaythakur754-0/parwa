# AI Technique Nodes

Day 6 Security Audit (I6): Audit of technique node implementations.

## Architecture

Each technique is a LangGraph-style node in the PARWA AI pipeline (F-060).
All nodes inherit from `BaseTechniqueNode` defined in `base.py`.

## Files

| File | Technique | Tier | Status |
|------|-----------|------|--------|
| `base.py` | BaseTechniqueNode, ConversationState, GSDState | Core | Production |
| `chain_of_thought.py` | Chain of Thought | Tier 1 | Production |
| `react.py` | ReAct (Reason + Act) | Tier 2 | Production |
| `react_tools.py` | ReAct with Tool Use | Tier 2 | Production |
| `thread_of_thought.py` | Thread of Thought | Tier 1 | Production |
| `gst.py` | Generative Skill Tree | Tier 2 | Production |
| `reverse_thinking.py` | Reverse Thinking | Tier 1 | Production |
| `step_back.py` | Step-Back Prompting | Tier 1 | Production |
| `tree_of_thoughts.py` | Tree of Thoughts | Tier 3 | Production |
| `least_to_most.py` | Least-to-Most | Tier 3 | Production |
| `self_consistency.py` | Self-Consistency | Tier 3 | Production |
| `reflexion.py` | Reflexion | Tier 3 | Production |
| `universe_of_thoughts.py` | Universe of Thoughts | Tier 3 | Production |
| `crp.py` | CRP (Custom Response Pattern) | Stub | Placeholder |
| `stub_nodes.py` | Placeholder nodes for all techniques | Stub | Fallback |

## Security Notes

- All techniques are scoped to a single conversation/request context.
- No direct database access from technique nodes.
- Tenant isolation is enforced at the pipeline level (BC-001), not inside
  individual technique nodes.
- Technique nodes receive `ConversationState` which already contains the
  validated `company_id` from the upstream pipeline.

## Building Codes

- BC-001: Multi-tenant isolation (pipeline-level, not node-level)
- BC-007: All AI interaction through Smart Router
- BC-008: Graceful degradation — stub nodes as fallback
