┌─────────────────────────────┬──────────────────────────┬────────────────────────────────────────┬─────────────────────────────┐
│ From                        │ To                       │ What travels                           │ How                         │
├─────────────────────────────┼──────────────────────────┼────────────────────────────────────────┼─────────────────────────────┤
│ Log file / Redis            │ Ingestion worker         │ Raw log string                         │ File read / XREADGROUP      │
│ Ingestion worker            │ logs table               │ Parsed log record                      │ SQL INSERT via asyncpg      │
│ Ingestion worker            │ XGBoost classifier       │ Feature vector                         │ Direct Python function call │
│ XGBoost classifier          │ incidents table          │ predicted_severity, confidence         │ SQL INSERT via asyncpg      │
│ XGBoost classifier          │ Redis stream             │ log_id, incident_id, parsed_log,       │ Redis XADD                  │
│                             │                          │ predicted_severity, confidence         │ sentinel:triage stream      │
│ Redis stream                │ Agent worker             │ Same payload                           │ Redis XREADGROUP            │
│                             │                          │                                        │ consumer group agent-workers│
│ Agent worker                │ agent_runs table         │ run_id, incident_id, log_id,           │ SQL INSERT via asyncpg      │
│                             │                          │ run_status=IN_PROGRESS                 │                             │
│ Agent → SQL tool            │ incidents table          │ IN: service_name, error_type,          │ SQL SELECT via asyncpg      │
│                             │                          │ time_window=24h                        │                             │
│                             │                          │ OUT: count, last_resolution,           │                             │
│                             │                          │ last_severity, last_incident_id        │                             │
│ Agent → RAG tool            │ pgvector                 │ IN: embedded query string              │ pgvector cosine similarity  │
│                             │                          │ OUT: runbook_found, runbook_match      │ + Cohere rerank             │
│ Agent → metrics tool        │ Metrics API              │ IN: service_name, timestamp,           │ HTTP GET                    │
│                             │                          │ time_window=±15min                     │                             │
│                             │                          │ OUT: cpu_spike, error_rate,            │                             │
│                             │                          │ latency_p99, anomaly_detected          │                             │
│ Agent → HITL tool           │ Slack API                │ IN: verdict, evidence,                 │ HTTP POST                   │
│                             │                          │ recommended_action, run_id             │ Slack Incoming Webhook      │
│                             │                          │ OUT: slack_message_ts                  │                             │
│ Human                       │ FastAPI                  │ hitl_status, rejection_reason,         │ HTTP POST                   │
│                             │                          │ reviewed_by                            │ /hitl/{run_id}/respond      │
│ FastAPI                     │ Agent worker             │ hitl_status, rejection_reason,         │ LangGraph Command(resume)   │
│                             │                          │ reviewed_by                            │ thread_id=run_id            │
│ Agent worker                │ agent_run_steps          │ Full step record per tool call         │ SQL INSERT via asyncpg      │
│                             │                          │                                        │ triggers run total update   │
│ Agent worker                │ LangSmith                │ node traces, tokens, cost,             │ Automatic via SDK           │
│                             │                          │ latency, run_id                        │ LANGCHAIN_TRACING_V2=true   │
└─────────────────────────────┴──────────────────────────┴────────────────────────────────────────┴─────────────────────────────┘