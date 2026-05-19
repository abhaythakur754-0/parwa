"""
PARWA Onboarding Jarvis LangGraph — Multi-Agent Graph

Wires the Onboarding Router + Specialist Agents into a LangGraph
StateGraph that processes user messages through the agent pipeline.

Graph Topology:
  START → onboarding_router → [agent_selector] → specialist_agent → END

  agent_selector conditional routing based on router_decision:
    "guide"     → guide_agent_node
    "salesman"  → salesman_agent_node
    "demo"      → demo_agent_node
    "call"      → call_agent_node
    "awareness" → END  (context enrichment only, no direct response)
    "no_action" → END

The graph-based approach is an ALTERNATIVE execution path to the
primary orchestrator (process_onboarding_message). The orchestrator
uses LLM function calling and is the main pipeline. This graph is
for when we want multi-step agent reasoning — each agent node
independently reasons via LLM with its own system prompt and
rule-based fallback.

BC-001: company_id first parameter on all public methods.
BC-008: Every node wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logger import get_logger

logger = get_logger("onboarding_jarvis_graph")

# Singleton graph instance
_graph_instance: Optional[Any] = None


class OnboardingJarvisGraph:
    """Builds and manages the LangGraph StateGraph for Onboarding Jarvis.

    The graph uses OnboardingJarvisState as the state type and wires
    together the router node with specialist agent nodes via conditional
    edges.

    Usage:
        graph = OnboardingJarvisGraph()
        compiled = graph.build()
        result = compiled.invoke(initial_state)
    """

    def __init__(self):
        self._compiled_graph = None

    def build(self) -> Any:
        """Build and compile the Onboarding Jarvis LangGraph.

        Returns:
            Compiled StateGraph ready for .invoke() or .stream().
        """
        if self._compiled_graph is not None:
            return self._compiled_graph

        try:
            from langgraph.graph import StateGraph, END

            from app.services.onboarding_jarvis.onboarding_state import (
                OnboardingJarvisState,
            )
            from app.services.onboarding_jarvis.nodes.onboarding_router import (
                onboarding_router_node,
            )
            from app.services.onboarding_jarvis.nodes.guide_agent import (
                guide_agent_node,
            )
            from app.services.onboarding_jarvis.nodes.salesman_agent import (
                salesman_agent_node,
            )
        except ImportError as e:
            logger.error("onboarding_graph_import_error: %s", str(e)[:200])
            raise

        # Create the state graph
        graph = StateGraph(OnboardingJarvisState)

        # ── Add Nodes ──
        graph.add_node("onboarding_router", onboarding_router_node)
        graph.add_node("guide_agent", guide_agent_node)
        graph.add_node("salesman_agent", salesman_agent_node)

        # Add demo_agent and call_agent if available (created in parallel)
        demo_agent_node = self._try_import_node(
            "app.services.onboarding_jarvis.nodes.demo_agent",
            "demo_agent_node",
        )
        call_agent_node = self._try_import_node(
            "app.services.onboarding_jarvis.nodes.call_agent",
            "call_agent_node",
        )

        if demo_agent_node:
            graph.add_node("demo_agent", demo_agent_node)
        if call_agent_node:
            graph.add_node("call_agent", call_agent_node)

        # ── Add Edges ──
        graph.set_entry_point("onboarding_router")

        # Conditional routing from router to specialist agents
        route_map: Dict[str, str] = {
            "guide": "guide_agent",
            "salesman": "salesman_agent",
        }
        if demo_agent_node:
            route_map["demo"] = "demo_agent"
        if call_agent_node:
            route_map["call"] = "call_agent"

        graph.add_conditional_edges(
            "onboarding_router",
            self._agent_selector,
            {
                **route_map,
                "awareness": END,
                "no_action": END,
                # Fallback for unknown decisions
                "fallback_guide": "guide_agent",
            },
        )

        # All specialist agents flow to END
        graph.add_edge("guide_agent", END)
        graph.add_edge("salesman_agent", END)
        if demo_agent_node:
            graph.add_edge("demo_agent", END)
        if call_agent_node:
            graph.add_edge("call_agent", END)

        # Compile
        self._compiled_graph = graph.compile()

        logger.info(
            "onboarding_graph_built: nodes=onboarding_router,guide_agent,"
            "salesman_agent%s%s",
            ",demo_agent" if demo_agent_node else "",
            ",call_agent" if call_agent_node else "",
        )

        return self._compiled_graph

    @staticmethod
    def _agent_selector(state: Dict[str, Any]) -> str:
        """Determine which specialist agent to route to.

        Reads the router_decision from state and maps it to a graph node.

        Args:
            state: Current OnboardingJarvisState dict.

        Returns:
            Node name string for the next node in the graph.
        """
        try:
            decision = state.get("router_decision", "guide")

            valid_agents = {"guide", "salesman", "demo", "call", "awareness", "no_action"}

            if decision in valid_agents:
                return decision

            # Unknown decision — fallback to guide
            logger.warning(
                "agent_selector_unknown_decision: decision=%s, falling_back_to_guide",
                decision,
            )
            return "fallback_guide"

        except Exception:
            logger.exception("agent_selector_error: falling_back_to_guide")
            return "fallback_guide"

    @staticmethod
    def _try_import_node(module_path: str, attr_name: str) -> Optional[Any]:
        """Try to import a node function, return None if unavailable.

        Used for nodes that may be created in parallel (demo_agent, call_agent).

        Args:
            module_path: Python import path.
            attr_name: Function name to import.

        Returns:
            The imported function or None.
        """
        try:
            module = __import__(module_path, fromlist=[attr_name])
            node_fn = getattr(module, attr_name, None)
            if node_fn:
                logger.info("onboarding_graph_imported_node: %s.%s", module_path, attr_name)
                return node_fn
        except (ImportError, AttributeError) as e:
            logger.info(
                "onboarding_graph_node_not_available: %s.%s (%s)",
                module_path, attr_name, str(e)[:100],
            )
        return None


def get_onboarding_graph() -> Any:
    """Get or create the singleton Onboarding Jarvis graph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    global _graph_instance

    if _graph_instance is not None:
        return _graph_instance

    try:
        builder = OnboardingJarvisGraph()
        _graph_instance = builder.build()
        return _graph_instance
    except Exception:
        logger.exception("get_onboarding_graph_error")
        return None


async def run_onboarding_from_message(
    session_id: str,
    user_id: str,
    user_message: str,
    company_id: str = "",
    entry_source: str = "direct",
    entry_variant_id: str = "",
    entry_variant_name: str = "",
    industry: str = "",
    detected_stage: str = "welcome",
    message_count_today: int = 0,
    pack_type: str = "free",
    payment_status: str = "none",
    demo_topics: Optional[list] = None,
    concerns_raised: Optional[list] = None,
    selected_variants: Optional[list] = None,
    business_email: str = "",
    email_verified: bool = False,
    channel: str = "chat",
) -> Dict[str, Any]:
    """Convenience function to run the Onboarding Jarvis graph from a message.

    This creates the initial state from the provided parameters,
    invokes the graph, and returns the final state with the
    agent's response.

    IMPORTANT: This is the graph-based execution path. For the primary
    pipeline, use process_onboarding_message from the orchestrator instead.

    Args:
        session_id: Onboarding session ID.
        user_id: User ID for auth/audit.
        user_message: The user's message text.
        company_id: Company ID for BC-001.
        entry_source: Where the user came from.
        entry_variant_id: Variant ID if coming from variant page.
        entry_variant_name: Human-readable variant name.
        industry: Detected/selected industry.
        detected_stage: Current funnel stage.
        message_count_today: Messages sent today (for rate limiting awareness).
        pack_type: 'free' or 'demo'.
        payment_status: Payment status.
        demo_topics: Topics discussed in demo.
        concerns_raised: Objections/concerns detected.
        selected_variants: Variants the client selected.
        business_email: Client's business email.
        email_verified: Whether email is verified.
        channel: 'chat' or 'call'.

    Returns:
        Dict with the final graph state, including:
          - response_text: The conversational response
          - router_decision: Which agent handled it
          - agent_type: The specialist agent type
          - response_card_type: Rich card type (if any)
          - response_card_data: Rich card data (if any)
          - execution_status: 'completed', 'failed', etc.
          - errors: Any accumulated errors
    """
    start_time = time.monotonic()

    try:
        from app.services.onboarding_jarvis.onboarding_state import (
            create_onboarding_state,
        )

        # Create initial state
        initial_state = create_onboarding_state(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            company_id=company_id,
            entry_source=entry_source,
            entry_variant_id=entry_variant_id,
            entry_variant_name=entry_variant_name,
            industry=industry,
            detected_stage=detected_stage,
            message_count_today=message_count_today,
            pack_type=pack_type,
            payment_status=payment_status,
            demo_topics=demo_topics or [],
            concerns_raised=concerns_raised or [],
            selected_variants=selected_variants or [],
            business_email=business_email,
            email_verified=email_verified,
        )

        # Override trigger type if call channel
        if channel == "call":
            initial_state["trigger_type"] = "call_event"

        # Get the compiled graph
        graph = get_onboarding_graph()
        if graph is None:
            logger.error("run_onboarding_graph_not_available")
            return {
                "response_text": (
                    "I'm having trouble processing that right now. "
                    "Could you try again?"
                ),
                "router_decision": "guide",
                "agent_type": "guide",
                "response_card_type": "none",
                "response_card_data": {},
                "execution_status": "failed",
                "execution_error": "Graph not available",
                "errors": ["onboarding_graph_not_available"],
            }

        # Invoke the graph
        final_state = await graph.ainvoke(initial_state)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        # Extract the key response fields from the final state
        result = {
            "response_text": final_state.get("response_text", ""),
            "router_decision": final_state.get("router_decision", ""),
            "router_reasoning": final_state.get("router_reasoning", ""),
            "router_confidence": final_state.get("router_confidence", 0),
            "router_source": final_state.get("router_source", ""),
            "agent_type": final_state.get("agent_type", ""),
            "agent_action": final_state.get("agent_action", ""),
            "agent_reasoning": final_state.get("agent_reasoning", ""),
            "agent_source": final_state.get("agent_source", ""),
            "response_card_type": final_state.get("response_card_type", "none"),
            "response_card_data": final_state.get("response_card_data", {}),
            "execution_status": "completed",
            "execution_time_ms": elapsed_ms,
            "intent_detected": final_state.get("intent_detected", ""),
            "sentiment": final_state.get("sentiment", "neutral"),
            "stage_transition": final_state.get("stage_transition"),
            "new_concerns": final_state.get("new_concerns", []),
            "new_topics": final_state.get("new_topics", []),
            "errors": final_state.get("errors", []),
            "audit_trail": final_state.get("audit_trail", []),
        }

        # If awareness-only routing, no response_text from agent
        if final_state.get("router_decision") == "awareness":
            result["response_text"] = ""
            result["execution_status"] = "completed_no_response"

        # If no action routing
        if final_state.get("router_decision") == "no_action":
            result["response_text"] = ""
            result["execution_status"] = "completed_no_action"

        logger.info(
            "run_onboarding_from_message: session=%s, agent=%s, "
            "intent=%s, status=%s, ms=%.1f",
            session_id,
            final_state.get("agent_type", "unknown"),
            final_state.get("intent_detected", "unknown"),
            result["execution_status"],
            elapsed_ms,
        )

        return result

    except Exception:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception(
            "run_onboarding_from_message_error: session=%s, ms=%.1f",
            session_id, elapsed_ms,
        )
        return {
            "response_text": (
                "I'm having trouble processing that right now. "
                "Could you try again or rephrase your question?"
            ),
            "router_decision": "guide",
            "agent_type": "guide",
            "response_card_type": "none",
            "response_card_data": {},
            "execution_status": "failed",
            "execution_error": "Graph execution error",
            "execution_time_ms": elapsed_ms,
            "errors": ["run_onboarding_from_message: unexpected error"],
        }
