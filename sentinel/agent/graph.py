from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from sentinel.agent.state import AgentState
from sentinel.agent.tools_registry import ToolRegistry
from sentinel.agent.nodes.ingest import ingest_log
from sentinel.agent.nodes.classify import classify_severity, route_severity
from sentinel.agent.nodes.investigate import make_investigate_nodes
from sentinel.agent.nodes.reflect import reflect, route_reflection
from sentinel.agent.nodes.verdict import generate_verdict
from sentinel.agent.nodes.hitl import (
    hitl_checkpoint, route_hitl,
    write_incident, store_rejection,
    auto_escalate, close_unreviewed
)


def build_graph(registry: ToolRegistry) -> StateGraph:
    workflow = StateGraph(AgentState)
    nodes = make_investigate_nodes(registry)

    workflow.add_node("ingest_log", ingest_log)
    workflow.add_node("classify_severity", classify_severity)
    workflow.add_node("auto_close", nodes["auto_close"])
    workflow.add_node("search_runbook", nodes["search_runbook"])
    workflow.add_node("check_metrics", nodes["check_metrics"])
    workflow.add_node("query_past_incidents", nodes["query_past_incidents"])
    workflow.add_node("reflect", reflect)
    workflow.add_node("generate_verdict", generate_verdict)
    workflow.add_node("hitl_checkpoint", hitl_checkpoint)
    workflow.add_node("write_incident", write_incident)
    workflow.add_node("store_rejection", store_rejection)
    workflow.add_node("auto_escalate", auto_escalate)
    workflow.add_node("close_unreviewed", close_unreviewed)

    workflow.set_entry_point("ingest_log")
    workflow.add_edge("ingest_log", "classify_severity")
    workflow.add_conditional_edges(
        "classify_severity", route_severity,
        {"auto_close": "auto_close", "search_runbook": "search_runbook"}
    )
    workflow.add_edge("auto_close", "write_incident")
    workflow.add_edge("search_runbook", "check_metrics")
    workflow.add_edge("check_metrics", "query_past_incidents")
    workflow.add_edge("query_past_incidents", "reflect")
    workflow.add_conditional_edges(
        "reflect", route_reflection,
        {"search_runbook": "search_runbook", "generate_verdict": "generate_verdict"}
    )
    workflow.add_edge("generate_verdict", "hitl_checkpoint")
    workflow.add_conditional_edges(
        "hitl_checkpoint", route_hitl,
        {
            "write_incident": "write_incident",
            "store_rejection": "store_rejection",
            "auto_escalate": "auto_escalate",
            "close_unreviewed": "close_unreviewed",
        }
    )
    workflow.add_edge("write_incident", END)
    workflow.add_edge("store_rejection", END)
    workflow.add_edge("auto_escalate", END)
    workflow.add_edge("close_unreviewed", END)

    return workflow

# app instantiated at startup in core/config.py
# checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
# app = build_graph(registry).compile(checkpointer=checkpointer)