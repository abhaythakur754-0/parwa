"""PARWA Subgraph Architecture — Specialized mini-pipelines for each intent domain.

Instead of routing ALL tickets through the same 22-node flat pipeline,
subgraphs provide specialized, shorter pipelines for each intent type:

  refund_request  → Refund Subgraph (8 nodes, refund-specialized techniques)
  technical_support → Tech Subgraph (10 nodes, diagnostic techniques)
  billing_issue   → Billing Subgraph (9 nodes, billing-specialized techniques)
  everything else → General Subgraph (11 nodes, general techniques)

Benefits over the flat pipeline:
  - Specialized system prompts → more focused LLM responses
  - Domain-specific technique priorities → right techniques fire first
  - Shorter paths → fewer tokens, faster responses
  - Subgraph-specific KB search → more relevant documents
  - Easier to tune per domain → isolate failures and optimize
"""

from parwa.subgraphs.router import SubgraphRouter, route_to_subgraph
from parwa.subgraphs.refund_graph import build_refund_graph, RefundGraph
from parwa.subgraphs.tech_graph import build_tech_graph, TechGraph
from parwa.subgraphs.billing_graph import build_billing_graph, BillingGraph
from parwa.subgraphs.general_graph import build_general_graph, GeneralGraph

__all__ = [
    "SubgraphRouter",
    "route_to_subgraph",
    "build_refund_graph",
    "RefundGraph",
    "build_tech_graph",
    "TechGraph",
    "build_billing_graph",
    "BillingGraph",
    "build_general_graph",
    "GeneralGraph",
]
