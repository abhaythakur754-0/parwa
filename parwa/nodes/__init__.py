"""PARWA LangGraph pipeline nodes.

Each node is a pure function: dict -> dict.
Nodes are organized by agent:
  - Router Agent: Nodes 1, 2, 18, 20
  - Knowledge Agent: Nodes 3, 4, 19, 5
  - Reasoning Agent: Nodes 6, 10, 12, 11
  - Action Agent: Nodes 7, 8, 9
  - Proactive Agent: Nodes 13, 14, 22
  - Compliance Agent: Nodes 15, 16, 21, 17
"""
