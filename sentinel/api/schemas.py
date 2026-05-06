# sentinel/api/schemas.py

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNCERTAIN = "UNCERTAIN"


class IncidentStatus(str, Enum):
    AUTO_CLOSED = "AUTO_CLOSED"
    CONFIRMED = "CONFIRMED"
    MANUALLY_REJECTED = "MANUALLY_REJECTED"
    AUTO_ESCALATED = "AUTO_ESCALATED"
    TIMED_OUT_UNREVIEWED = "TIMED_OUT_UNREVIEWED"


class RunStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class HitlDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LogEvent(BaseModel):
    raw_log: str
    timestamp: datetime
    service_name: str
    error_type: str
    severity_label: str
    message: str
    source_ip: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    logs: list[LogEvent]


class IngestedLog(BaseModel):
    log_id: UUID
    status: str = "QUEUED"


class IngestResponse(BaseModel):
    accepted: int
    logs: list[IngestedLog]
    message: str = "Logs accepted. Ingestion pipeline started asynchronously."


class AgentRunStepResponse(BaseModel):
    step_id: UUID
    step_number: int
    node_name: str
    tool_name: str
    step_status: str
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class AgentTraceResponse(BaseModel):
    run_id: UUID
    run_status: RunStatus
    final_severity: Optional[Severity] = None
    final_verdict: Optional[dict[str, Any]] = None
    recommended_action: Optional[str] = None
    uncertainty_flagged: bool
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_llm_cost_usd: float
    latency_ms: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: list[AgentRunStepResponse]


class IncidentResponse(BaseModel):
    incident_id: UUID
    log_id: UUID
    run_id: Optional[UUID] = None

    service_name: str
    error_type: Optional[str] = None
    source_ip: Optional[str] = None

    classifier_severity: Severity
    classifier_confidence: float
    final_severity: Severity
    status: IncidentStatus
    resolution: Optional[str] = None

    runbook_found: bool
    runbook_id: Optional[UUID] = None
    runbook_title: Optional[str] = None

    metrics_snapshot: Optional[dict[str, Any]] = None
    past_incident_count: int
    evidence: Optional[dict[str, Any]] = None
    recommended_action: Optional[str] = None
    agent_confidence: Optional[float] = None
    uncertainty_flagged: bool
    retry_count: int

    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    log_timestamp: datetime
    created_at: datetime
    updated_at: datetime

    agent_trace: Optional[AgentTraceResponse] = None


class HitlRespondRequest(BaseModel):
    decision: HitlDecision
    reviewer_id: str
    rejection_reason: Optional[str] = None


class HitlRespondResponse(BaseModel):
    run_id: UUID
    incident_id: UUID
    decision: HitlDecision
    status: IncidentStatus
    message: str  # e.g. "Incident confirmed and escalated" or "Incident rejected and stored for retraining"