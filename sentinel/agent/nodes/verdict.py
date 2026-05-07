# sentinel/agent/nodes/verdict.py
from sentinel.agent.state import AgentState
from sentinel.agent.tools_registry import ToolRegistry

def make_verdict_nodes(registry: ToolRegistry):

    async def generate_verdict(state: AgentState) -> AgentState:
        """Calls SeverityTool with all evidence. Writes final verdict to state."""
        evidence = {
            "parsed_log": state["parsed_log"],
            "predicted_severity": state["predicted_severity"],
            "classifier_confidence": state["classifier_confidence"],
            "runbook_match": state["runbook_match"],
            "metrics": state["metrics"],
            "past_incidents": state["past_incidents"],
            "llm_confidence_score": state["llm_confidence_score"],
        }

        result = await registry.severity.run(evidence=evidence)

        return {
            "verdict": result.data if result.success else {
                "severity": state["predicted_severity"],
                "confidence": state["classifier_confidence"],
                "evidence": ["Severity tool failed, using classifier output"],
                "recommended_action": "Manual review required",
                "uncertainty_flagged": True,
            }
        }

    return {"generate_verdict": generate_verdict}