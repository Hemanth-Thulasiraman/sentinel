TOOL_SCHEMAS = [
    # Tool 1 — SQL Tool
    {
        "name": "query_past_incidents",
        "description": (
            "Queries the incidents database for historical incidents "
            "matching a service and error type. Use this to understand "
            "if this pattern has occurred before and how it was resolved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "The name of the service that generated the log"
                },
                "error_type": {
                    "type": "string",
                    "description": "The error category to search for"
                },
                "time_window": {
                    "type": "string",
                    "description": "How far back to search. Examples: 24h, 7d, 15min"
                }
            },
            "required": ["service_name", "error_type"]
        }
    },

    # Tool 2 — Runbook Tool
    {
        "name": "search_runbook",
        "description": (
            "Searches the runbook knowledge base for known solutions or patterns "
            "related to an error. Use this when you want remediation steps or "
            "to check if this issue has a documented fix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "error_type": {
                    "type": "string",
                    "description": "The category of the error being investigated"
                },
                "log_message": {
                    "type": "string",
                    "description": "The raw log message for additional context"
                }
            },
            "required": ["error_type", "log_message"]
        }
    },

    # Tool 3 — Metrics Tool
    {
        "name": "check_metrics",
        "description": (
            "Fetches system metrics such as CPU usage, error rate, and latency "
            "around a given timestamp. Use this to validate whether an issue "
            "correlates with system anomalies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "The name of the service being investigated"
                },
                "timestamp": {
                    "type": "string",
                    "description": "The timestamp of the log event"
                },
                "time_window": {
                    "type": "string",
                    "description": "Window around the timestamp to analyze, e.g. 15min"
                }
            },
            "required": ["service_name", "timestamp"]
        }
    },

    # Tool 4 — Severity Tool
    {
        "name": "score_severity",
        "description": (
            "Analyzes all collected evidence and assigns a severity level with "
            "confidence, supporting evidence, and recommended action. Use this "
            "after gathering runbook, metrics, and historical context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "evidence": {
                    "type": "object",
                    "description": (
                        "All collected evidence including classifier output, "
                        "runbook match, metrics signals, and past incidents"
                    )
                }
            },
            "required": ["evidence"]
        }
    },

    # Tool 5 — Escalation Tool
    {
        "name": "send_for_review",
        "description": (
            "Sends the final verdict to a human reviewer via Slack. "
            "Use this when the investigation is complete and requires "
            "approval, rejection, or escalation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "object",
                    "description": "Final decision including severity, evidence, and recommendation"
                },
                "run_id": {
                    "type": "string",
                    "description": "Unique identifier of the agent run"
                },
                "incident_id": {
                    "type": "string",
                    "description": "Unique identifier of the incident"
                },
                "service_name": {
                    "type": "string",
                    "description": "The service associated with the incident"
                }
            },
            "required": ["verdict", "run_id", "incident_id", "service_name"]
        }
    }
]