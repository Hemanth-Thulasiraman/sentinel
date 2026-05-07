# sentinel/api/routes.py
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from langgraph.types import Command
from sentinel.api.schemas import (
    IngestRequest, IngestResponse, IngestedLog,
    IncidentResponse, HitlRespondRequest, HitlRespondResponse,
    IncidentStatus,
)
from sentinel.core.database import get_pool
from sentinel.classifier.model import predict
from sentinel.classifier.features import extract_features

router = APIRouter()


async def _run_pipeline(log_id: str, log: dict) -> None:
    """Background task: classify log, create incident, queue for agent if needed."""
    pool = await get_pool()
    
    severity, confidence = predict(log)

    async with pool.acquire() as conn:
        incident_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO incidents (
                id, log_id, service_name, error_type,
                classifier_severity, classifier_confidence,
                final_severity, status, log_timestamp
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())
            """,
            incident_id, log_id,
            log["service_name"], log.get("error_type", "unknown"),
            severity, confidence,
            severity,
            "AUTO_CLOSED" if severity == "LOW" else "IN_PROGRESS",
        )

        await conn.execute(
            "UPDATE logs SET status = $1 WHERE log_id = $2",
            "AUTO_CLOSED" if severity == "LOW" else "QUEUED",
            log_id,
        )

    if severity != "LOW":
        from sentinel.api.main import agent_app
        await agent_app.ainvoke(
            {"raw_log": log["raw_log"]},
            config={"configurable": {"thread_id": incident_id}}
        )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_logs(request: IngestRequest, background_tasks: BackgroundTasks):
    pool = await get_pool()
    ingested = []

    for log in request.logs:
        log_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO logs (log_id, raw_log, service_name, error_type, source, status)
                VALUES ($1, $2, $3, $4, $5, 'PENDING')
                """,
                log_id, log.raw_log, log.service_name,
                log.error_type, "api",
            )

        background_tasks.add_task(
            _run_pipeline,
            log_id,
            log.model_dump(),
        )
        ingested.append(IngestedLog(log_id=log_id, status="QUEUED"))

    return IngestResponse(
        accepted=len(ingested),
        logs=ingested,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    return IncidentResponse(**dict(row), agent_trace=None)


@router.post("/hitl/{run_id}/respond", response_model=HitlRespondResponse)
async def hitl_respond(run_id: str, request: HitlRespondRequest):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status FROM incidents WHERE run_id = $1", run_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    incident_id = str(row["id"])
    new_status = (
        IncidentStatus.CONFIRMED if request.decision.value == "APPROVED"
        else IncidentStatus.MANUALLY_REJECTED
    )

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE incidents SET
                status = $1,
                reviewed_by = $2,
                reviewed_at = NOW(),
                rejection_reason = $3
            WHERE id = $4
            """,
            new_status.value,
            request.reviewer_id,
            request.rejection_reason,
            incident_id,
        )

    from sentinel.api.main import agent_app
    await agent_app.ainvoke(
        Command(resume={
            "hitl_status": request.decision.value,
            "reviewer_id": request.reviewer_id,
        }),
        config={"configurable": {"thread_id": run_id}}
    )

    return HitlRespondResponse(
        run_id=run_id,
        incident_id=incident_id,
        decision=request.decision,
        status=new_status,
        message=f"Incident {new_status.value.lower().replace('_', ' ')}.",
    )