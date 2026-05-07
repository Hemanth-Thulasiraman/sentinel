# sentinel/agent/nodes/ingest.py
import uuid
from sentinel.agent.state import AgentState
import re

def ingest_log(state: AgentState) -> AgentState:
    """Parses raw log string into normalized fields. Generates run_id."""
    raw_log = state["raw_log"]

    pattern = r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<severity>\w+) (?P<service_name>[\w-]+) (?P<source_ip>[\d.]+) - (?P<message>.*)$"

    match = re.match(pattern, raw_log)
    if not match:
        raise ValueError(f"Invalid log format: {raw_log}")

    parsed = {
        "timestamp": match.group("timestamp"),
        "severity_label": match.group("severity"),
        "service_name": match.group("service_name"),
        "source_ip": match.group("source_ip"),
        "message": match.group("message"),
    }

    return {
        "run_id": str(uuid.uuid4()),
        "parsed_log": parsed,
    }