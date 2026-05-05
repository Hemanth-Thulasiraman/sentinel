from typing import TypedDict, Optional

class AgentState(TypedDict):
    run_id: str
    raw_log: str
    parsed_log: dict
    predicted_severity: str
    classifier_confidence: float
    runbook_found: bool
    runbook_match: Optional[dict]
    metrics: dict
    past_incidents: list[dict]
    llm_confidence_score: float
    retry_count: int
    uncertainty_flagged: bool
    verdict: Optional[dict]
    hitl_status: str
    timeout_duration_mins: int