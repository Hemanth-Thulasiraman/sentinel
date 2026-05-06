CREATE TYPE log_status AS ENUM (
    'PENDING',       -- just ingested, not yet classified
    'CLASSIFIED',    -- classifier has run
    'QUEUED',        -- pushed to Redis for agent investigation  
    'AUTO_CLOSED'    -- classified LOW, closed without agent
);

CREATE TABLE logs (
    log_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_log       TEXT          NOT NULL,                        -- original log line, never modified
    service_name  TEXT          NOT NULL,                        -- parsed source service, used for incident correlation
    error_type    TEXT          NOT NULL,                        -- parsed error category, used for runbook matching
    source        TEXT          NOT NULL,                        -- ingestion source: 'file_watcher' or 'redis_stream'
    status        log_status    NOT NULL DEFAULT 'PENDING',      -- tracks processing state through the pipeline
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()           -- ingestion timestamp, always UTC
);

CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key back to original raw log/event
    log_id UUID NOT NULL REFERENCES logs(log_id) ON DELETE CASCADE,

    -- LangGraph run identifier. Plain UUID because agent_runs may be append-only,
    -- partitioned, or stored separately from the incident lifecycle table.
    run_id UUID NULL,

    service_name TEXT NOT NULL,
    error_type TEXT NULL,
    source_ip INET NULL,

    classifier_severity TEXT NOT NULL CHECK (
        classifier_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    ),
    classifier_confidence NUMERIC(5, 4) NOT NULL,

    final_severity TEXT NOT NULL CHECK (
        final_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNCERTAIN')
    ),

    status TEXT NOT NULL CHECK (
        status IN (
            'AUTO_CLOSED',
            'CONFIRMED',
            'MANUALLY_REJECTED',
            'AUTO_ESCALATED',
            'TIMED_OUT_UNREVIEWED'
        )
    ),

    resolution TEXT NULL CHECK (
        resolution IN (
            'NONE',
            'ESCALATED',
            'REJECTED',
            'AUTO_ESCALATED',
            'FLAGGED_FOR_REVIEW'
        )
    ),

    runbook_found BOOLEAN NOT NULL DEFAULT FALSE,
    runbook_id UUID NULL REFERENCES runbooks(id) ON DELETE SET NULL,
    runbook_title TEXT NULL,

    metrics_snapshot JSONB NULL,

    past_incident_count INT NOT NULL DEFAULT 0,
    last_incident_id UUID NULL REFERENCES incidents(id) ON DELETE SET NULL,
    last_resolution TEXT NULL,
    last_severity TEXT NULL,

    evidence JSONB NULL,
    recommended_action TEXT NULL,
    agent_confidence NUMERIC(5, 4) NULL,
    uncertainty_flagged BOOLEAN NOT NULL DEFAULT FALSE,
    retry_count INT NOT NULL DEFAULT 0,

    reviewed_by TEXT NULL,
    reviewed_at TIMESTAMPTZ NULL,
    rejection_reason TEXT NULL,
    slack_message_ts TEXT NULL,

    log_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER incidents_update_updated_at
BEFORE UPDATE ON incidents
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

CREATE TABLE agent_runs (
    -- Unique identifier for one LangGraph investigation run
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Write sequence:
    -- 1. Create incidents row first with incidents.run_id = NULL
    -- 2. Create agent_runs row with incident_id pointing to incidents.id
    -- 3. After completion, update incidents.run_id = agent_runs.run_id
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,

    log_id UUID NOT NULL REFERENCES logs(log_id) ON DELETE CASCADE,

    service_name TEXT NOT NULL,
    error_type TEXT NULL,

    run_status TEXT NOT NULL CHECK (
        run_status IN (
            'IN_PROGRESS',
            'SUCCEEDED',
            'FAILED',
            'TIMED_OUT'
        )
    ),

    final_severity TEXT NULL CHECK (
        final_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNCERTAIN')
    ),
    final_verdict JSONB NULL,
    recommended_action TEXT NULL,
    uncertainty_flagged BOOLEAN NOT NULL DEFAULT FALSE,

    total_prompt_tokens INT NOT NULL DEFAULT 0,
    total_completion_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT GENERATED ALWAYS AS (
        total_prompt_tokens + total_completion_tokens
    ) STORED,
    total_llm_cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0.000000,

    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL,
    latency_ms INT NULL,

    retry_count INT NOT NULL DEFAULT 0,
    error_message TEXT NULL,

    resolved_status TEXT NULL CHECK (
        resolved_status IN (
            'AUTO_CLOSED',
            'CONFIRMED',
            'MANUALLY_REJECTED',
            'AUTO_ESCALATED',
            'TIMED_OUT_UNREVIEWED'
        )
    ),
    resolution TEXT NULL,
    resolved_at TIMESTAMPTZ NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TRIGGER agent_runs_update_updated_at
BEFORE UPDATE ON agent_runs
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

CREATE TABLE agent_run_steps (
    -- Unique identifier for one tool-call step
    step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent LangGraph investigation run
    run_id UUID NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,

    -- Ordered position of this step within the run
    step_number INT NOT NULL,

    -- LangGraph node that made the tool call
    node_name TEXT NOT NULL,

    -- Tool/function that was called
    tool_name TEXT NOT NULL,

    -- Input sent to the tool
    tool_input JSONB NULL,

    -- Successful tool response
    tool_output JSONB NULL,

    -- Step lifecycle status
    step_status TEXT NOT NULL CHECK (
        step_status IN (
            'STARTED',
            'SUCCEEDED',
            'FAILED',
            'TIMED_OUT'
        )
    ),

    -- Failure/debug details
    error_message TEXT NULL,
    error_type TEXT NULL,

    -- Token usage and cost for this individual tool/model call
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT GENERATED ALWAYS AS (
        prompt_tokens + completion_tokens
    ) STORED,
    cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0.000000,

    -- Per-step latency tracking
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL,
    latency_ms INT NULL,

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Prevent duplicate ordering inside one run
    UNIQUE (run_id, step_number)
);


CREATE TRIGGER agent_run_steps_update_updated_at
BEFORE UPDATE ON agent_run_steps
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE FUNCTION increment_run_totals()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE agent_runs
    SET
        total_prompt_tokens     = total_prompt_tokens + NEW.prompt_tokens,
        total_completion_tokens = total_completion_tokens + NEW.completion_tokens,
        total_llm_cost_usd      = total_llm_cost_usd + NEW.cost_usd
    WHERE run_id = NEW.run_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_run_steps_increment_totals
AFTER INSERT ON agent_run_steps
FOR EACH ROW
EXECUTE FUNCTION increment_run_totals();