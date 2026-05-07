from langgraph.graph import StateGraph, END
from sentinel.agent.state import AgentState
from sentinel.agent.tools_registry import ToolRegistry
from sentinel.agent.nodes.ingest import ingest_log
from sentinel.agent.nodes.classify import classify_severity, route_severity
from sentinel.agent.nodes.investigate import make_investigate_nodes
from sentinel.agent.nodes.reflect import make_reflect_nodes
from sentinel.agent.nodes.verdict import make_verdict_nodes
from sentinel.agent.nodes.hitl import make_hitl_nodes


def build_graph(registry: ToolRegistry) -> StateGraph:
    workflow = StateGraph(AgentState)

    investigate = make_investigate_nodes(registry)
    reflect = make_reflect_nodes(registry)
    verdict = make_verdict_nodes(registry)
    hitl = make_hitl_nodes(registry)

    workflow.add_node("ingest_log", ingest_log)
    workflow.add_node("classify_severity", classify_severity)
    workflow.add_node("auto_close", investigate["auto_close"])
    workflow.add_node("search_runbook", investigate["search_runbook"])
    workflow.add_node("check_metrics", investigate["check_metrics"])
    workflow.add_node("query_past_incidents", investigate["query_past_incidents"])
    workflow.add_node("reflect", reflect["reflect"])
    workflow.add_node("generate_verdict", verdict["generate_verdict"])
    workflow.add_node("hitl_checkpoint", hitl["hitl_checkpoint"])
    workflow.add_node("write_incident", hitl["write_incident"])
    workflow.add_node("store_rejection", hitl["store_rejection"])
    workflow.add_node("auto_escalate", hitl["auto_escalate"])
    workflow.add_node("close_unreviewed", hitl["close_unreviewed"])

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
        "reflect", reflect["route_reflection"],
        {"search_runbook": "search_runbook", "generate_verdict": "generate_verdict"}
    )
    workflow.add_edge("generate_verdict", "hitl_checkpoint")
    workflow.add_conditional_edges(
        "hitl_checkpoint", hitl["route_hitl"],
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