# sentinel/agent/nodes/hitl.py
from typing import Literal
from langgraph.types import interrupt
from sentinel.agent.state import AgentState
from sentinel.agent.tools_registry import ToolRegistry

def make_hitl_nodes(registry: ToolRegistry):

    async def hitl_checkpoint(state: AgentState) -> AgentState:
        """Sends verdict to Slack, suspends graph waiting for human response."""
        verdict = state["verdict"]
        parsed = state["parsed_log"]

        result = await registry.escalation.run(
            verdict=verdict,
            run_id=state["run_id"],
            incident_id=state.get("incident_id", "unknown"),
            service_name=parsed["service_name"],
        )

        # suspend graph here — resumes when POST /hitl/{run_id}/respond fires
        human_response = interrupt("waiting_for_human_review")

        return {
            "hitl_status": human_response.get("hitl_status", "TIMED_OUT"),
        }

    def route_hitl(
        state: AgentState,
    ) -> Literal["write_incident", "store_rejection", "auto_escalate", "close_unreviewed"]:
        status = state["hitl_status"]
        severity = state["verdict"]["severity"] if state.get("verdict") else "MEDIUM"

        if status == "APPROVED":
            return "write_incident"
        elif status == "REJECTED":
            return "store_rejection"
        elif status == "TIMED_OUT" and severity == "CRITICAL":
            return "auto_escalate"
        else:
            return "close_unreviewed"

    def write_incident(state: AgentState) -> AgentState:
        """Records confirmed incident. DB write happens via API layer."""
        return {"hitl_status": "CONFIRMED"}

    def store_rejection(state: AgentState) -> AgentState:
        """Records rejected verdict as training signal."""
        return {"hitl_status": "MANUALLY_REJECTED"}

    def auto_escalate(state: AgentState) -> AgentState:
        """Auto-escalates CRITICAL incidents on HITL timeout."""
        return {"hitl_status": "AUTO_ESCALATED"}

    def close_unreviewed(state: AgentState) -> AgentState:
        """Parks MEDIUM incidents on HITL timeout for next shift."""
        return {"hitl_status": "TIMED_OUT_UNREVIEWED"}

    return {
        "hitl_checkpoint": hitl_checkpoint,
        "route_hitl": route_hitl,
        "write_incident": write_incident,
        "store_rejection": store_rejection,
        "auto_escalate": auto_escalate,
        "close_unreviewed": close_unreviewed,
    }