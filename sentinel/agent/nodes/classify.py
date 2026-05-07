# sentinel/agent/nodes/classify.py
from typing import Literal
from sentinel.agent.state import AgentState
from sentinel.classifier.model import predict

def classify_severity(state: AgentState) -> AgentState:
    """Runs XGBoost classifier on parsed_log. Writes predicted_severity and confidence."""
    parsed_log = state["parsed_log"]
    predicted_severity, confidence = predict(parsed_log)
    return {
        "predicted_severity": predicted_severity,
        "classifier_confidence": confidence,
    }

def route_severity(state: AgentState) -> Literal["auto_close", "search_runbook"]:
    """Routes LOW to auto_close, everything else to investigation."""
    predicted_severity = state["predicted_severity"]
    if predicted_severity == "LOW":
        return "auto_close"
    else:
        return "search_runbook"
