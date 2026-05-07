# sentinel/agent/nodes/investigate.py
from sentinel.agent.state import AgentState
from sentinel.agent.tools_registry import ToolRegistry

def make_investigate_nodes(registry: ToolRegistry):
    """
    Returns node functions with tools injected via closure.
    Called once at startup when building the graph.
    """

    async def search_runbook(state: AgentState) -> AgentState:
        parsed = state["parsed_log"]
        result = await registry.runbook.run(
            error_type=parsed["error_type"],
            log_message=parsed["message"],
        )
        return {
            "runbook_found": result.data.get("runbook_found", False) if result.success else False,
            "runbook_match": result.data.get("runbook_match") if result.success else None,
        }

    async def check_metrics(state: AgentState) -> AgentState:
        parsed = state["parsed_log"]
        result = await registry.metrics.run(
            service_name=parsed["service_name"],
            timestamp=parsed["timestamp"],
        )
        return {
            "metrics": result.data if result.success else {},
        }

    async def query_past_incidents(state: AgentState) -> AgentState:
        parsed = state["parsed_log"]
        result = await registry.sql.run(
            service_name=parsed["service_name"],
            error_type=parsed["error_type"],
        )
        return {
            "past_incidents": [result.data] if result.success and not result.data.get("empty") else [],
        }

    def auto_close(state: AgentState) -> AgentState:
        return {
            "verdict": {
                "severity": "LOW",
                "confidence": state["classifier_confidence"],
                "evidence": ["Classified as LOW severity by XGBoost classifier"],
                "recommended_action": "No action required",
                "uncertainty_flagged": False,
            }
        }

    return {
        "auto_close": auto_close,
        "search_runbook": search_runbook,
        "check_metrics": check_metrics,
        "query_past_incidents": query_past_incidents,
    }