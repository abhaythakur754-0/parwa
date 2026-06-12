"""Agent definition tests — CLAUDE.md required.

Tests that all 6 agents are properly defined with correct
node ownership and that each node belongs to exactly one agent.
"""

from __future__ import annotations

import pytest

from parwa.agents import (
    ROUTER_AGENT, KNOWLEDGE_AGENT, REASONING_AGENT,
    ACTION_AGENT, COMPLIANCE_AGENT, PROACTIVE_AGENT,
    ALL_AGENTS, NODE_TO_AGENT, Agent,
)


class TestAgentDefinitions:
    """Test that all 6 agents are properly defined."""

    def test_six_agents_exist(self):
        assert len(ALL_AGENTS) == 6

    def test_router_agent(self):
        assert ROUTER_AGENT.name == "Router Agent"
        assert ROUTER_AGENT.node_ids == [1, 2, 18, 20]
        assert "INGEST" in ROUTER_AGENT.node_names
        assert "INTENT_CLASSIFIER" in ROUTER_AGENT.node_names
        assert "SENTIMENT_ANALYZER" in ROUTER_AGENT.node_names
        assert "ESCALATION_DECISION" in ROUTER_AGENT.node_names

    def test_knowledge_agent(self):
        assert KNOWLEDGE_AGENT.name == "Knowledge Agent"
        assert KNOWLEDGE_AGENT.node_ids == [3, 4, 19, 5]
        assert "FAQ_MATCHER" in KNOWLEDGE_AGENT.node_names
        assert "KB_RETRIEVER" in KNOWLEDGE_AGENT.node_names
        assert "CONTEXT_MANAGER" in KNOWLEDGE_AGENT.node_names
        assert "INTEGRATION_LOOKUP" in KNOWLEDGE_AGENT.node_names

    def test_reasoning_agent(self):
        assert REASONING_AGENT.name == "Reasoning Agent"
        assert REASONING_AGENT.node_ids == [6, 10, 12, 11]
        assert "REASONING_ENGINE" in REASONING_AGENT.node_names
        assert "REVERSE_THINKER" in REASONING_AGENT.node_names
        assert "TREE_OF_THOUGHTS" in REASONING_AGENT.node_names
        assert "STRATEGY_PLANNER" in REASONING_AGENT.node_names

    def test_action_agent(self):
        assert ACTION_AGENT.name == "Action Agent"
        assert ACTION_AGENT.node_ids == [7, 8, 9]
        assert "ACTION_PLANNER" in ACTION_AGENT.node_names
        assert "ACTION_EXECUTOR" in ACTION_AGENT.node_names
        assert "ACTION_VERIFIER" in ACTION_AGENT.node_names

    def test_compliance_agent(self):
        assert COMPLIANCE_AGENT.name == "Compliance Agent"
        assert COMPLIANCE_AGENT.node_ids == [15, 16, 21, 17]
        assert "PII_COMPLIANCE_GUARD" in COMPLIANCE_AGENT.node_names
        assert "AUDIT_LOGGER" in COMPLIANCE_AGENT.node_names
        assert "QUALITY_SCORER" in COMPLIANCE_AGENT.node_names
        assert "RESPONSE_FORMATTER" in COMPLIANCE_AGENT.node_names

    def test_proactive_agent(self):
        assert PROACTIVE_AGENT.name == "Proactive Agent"
        assert PROACTIVE_AGENT.node_ids == [13, 14, 22]
        assert "PROACTIVE_CHECKER" in PROACTIVE_AGENT.node_names
        assert "PREDICTION_ENGINE" in PROACTIVE_AGENT.node_names
        assert "FEEDBACK_LOOP" in PROACTIVE_AGENT.node_names


class TestAgentNodeCoverage:
    """Test that all 22 nodes are covered by agents."""

    def test_all_22_nodes_covered(self):
        """Every node should belong to exactly one agent."""
        all_node_ids = set()
        for agent in ALL_AGENTS:
            for nid in agent.node_ids:
                assert nid not in all_node_ids, f"Node {nid} belongs to multiple agents!"
                all_node_ids.add(nid)

        # 22 nodes total
        assert len(all_node_ids) == 22

    def test_node_to_agent_mapping(self):
        """NODE_TO_AGENT mapping should be complete."""
        assert len(NODE_TO_AGENT) == 22

    def test_every_node_id_mapped(self):
        """Every node ID should map to an agent."""
        for agent in ALL_AGENTS:
            for nid in agent.node_ids:
                assert nid in NODE_TO_AGENT
                assert NODE_TO_AGENT[nid] == agent


class TestAgentRoles:
    """Test that each agent has a meaningful role description."""

    def test_router_has_role(self):
        assert len(ROUTER_AGENT.primary_role) > 10

    def test_knowledge_has_role(self):
        assert len(KNOWLEDGE_AGENT.primary_role) > 10

    def test_reasoning_has_role(self):
        assert len(REASONING_AGENT.primary_role) > 10

    def test_action_has_role(self):
        assert len(ACTION_AGENT.primary_role) > 10

    def test_compliance_has_role(self):
        assert len(COMPLIANCE_AGENT.primary_role) > 10

    def test_proactive_has_role(self):
        assert len(PROACTIVE_AGENT.primary_role) > 10


class TestAgentEmojis:
    """Test that agents have emojis for identification."""

    def test_all_agents_have_emojis(self):
        for agent in ALL_AGENTS:
            assert len(agent.emoji) > 0
            # Emoji should be a unicode character (not ASCII)
            assert ord(agent.emoji[0]) > 127
