from app.agents.state import AgentState
from app.agents.router import route_by_intent
from app.agents.nodes.intent_node import input_node, intent_node
from app.agents.nodes.contact_node import contact_node
from app.agents.nodes.reminder_node import reminder_node
from app.agents.nodes.security_node import security_node
from app.agents.nodes.order_node import order_node
from app.agents.nodes.response_node import (
    validation_node,
    confirmation_node,
    response_node,
)

try:
    from langgraph.graph import StateGraph, END

    HAS_LANGGRAPH = True
except ImportError:  # pragma: no cover
    HAS_LANGGRAPH = False


class _FallbackCompiledGraph:
    """Deterministic fallback runner executing the exact same node graph if langgraph is not installed."""

    def invoke(self, initial_state: AgentState) -> AgentState:
        state = input_node(initial_state)
        state = intent_node(state)
        next_node = route_by_intent(state)
        if next_node == "contact_node":
            state = contact_node(state)
        elif next_node == "reminder_node":
            state = reminder_node(state)
        elif next_node == "security_node":
            state = security_node(state)
        elif next_node == "order_node":
            state = order_node(state)
        state = validation_node(state)
        state = confirmation_node(state)
        state = response_node(state)
        return state


def build_agent_graph():
    """Build and compile the YAXIN AI LangGraph workflow (Section 9.1 & 9.6)."""
    if not HAS_LANGGRAPH:
        return _FallbackCompiledGraph()

    workflow = StateGraph(AgentState)

    workflow.add_node("input_node", input_node)
    workflow.add_node("intent_node", intent_node)
    workflow.add_node("contact_node", contact_node)
    workflow.add_node("reminder_node", reminder_node)
    workflow.add_node("security_node", security_node)
    workflow.add_node("order_node", order_node)
    workflow.add_node("validation_node", validation_node)
    workflow.add_node("confirmation_node", confirmation_node)
    workflow.add_node("response_node", response_node)

    workflow.set_entry_point("input_node")
    workflow.add_edge("input_node", "intent_node")

    workflow.add_conditional_edges(
        "intent_node",
        route_by_intent,
        {
            "contact_node": "contact_node",
            "reminder_node": "reminder_node",
            "security_node": "security_node",
            "order_node": "order_node",
            "validation_node": "validation_node",
        },
    )

    workflow.add_edge("contact_node", "validation_node")
    workflow.add_edge("reminder_node", "validation_node")
    workflow.add_edge("security_node", "validation_node")
    workflow.add_edge("order_node", "validation_node")
    workflow.add_edge("validation_node", "confirmation_node")
    workflow.add_edge("confirmation_node", "response_node")
    workflow.add_edge("response_node", END)

    return workflow.compile()


agent_graph = build_agent_graph()


def run_agent_workflow(user_id: str, user_message: str) -> AgentState:
    """Execute the full YAXIN AI agent workflow for a user message."""
    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": user_message,
        "intent": None,
        "confidence": None,
        "action_data": {},
        "requires_confirmation": False,
        "confirmation_status": None,
        "response": None,
        "status": None,
    }
    return agent_graph.invoke(initial_state)

