# sentinel/agent/nodes/reflect.py
import json
from typing import Literal
from sentinel.agent.state import AgentState
from sentinel.agent.tools_registry import ToolRegistry
from sentinel.core.config import REFLECTION_CONFIDENCE_THRESHOLD, MAX_RETRY_COUNT


def make_reflect_nodes(registry: ToolRegistry):

    async def reflect(state: AgentState) -> AgentState:
        """Calls Claude to synthesize evidence and assign confidence score."""
        
        evidence = {
            "parsed_log": state["parsed_log"],
            "predicted_severity": state["predicted_severity"],
            "runbook_match": state["runbook_match"],
            "metrics": state["metrics"],
            "past_incidents": state["past_incidents"],
            "retry_count": state["retry_count"],
        }

        prompt = f"""
You are a security analyst. Based on the following evidence, assess how confident 
you are that this is a genuine security incident requiring escalation.

Evidence:
{json.dumps(evidence, indent=2, default=str)}

Respond with ONLY valid JSON:
{{
    "confidence_score": <float between 0.0 and 1.0>,
    "reasoning": "<one sentence explaining your confidence level>",
    "uncertainty_flagged": <true if confidence below 0.75, false otherwise>
}}
""".strip()

        response = await registry.severity.anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        
        # strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        parsed = json.loads(raw)
        confidence = float(parsed["confidence_score"])
        current_retry = state.get("retry_count", 0)

        return {
            "llm_confidence_score": confidence,
            "uncertainty_flagged": confidence < REFLECTION_CONFIDENCE_THRESHOLD,
            "retry_count": current_retry + 1 if confidence < REFLECTION_CONFIDENCE_THRESHOLD else current_retry,
        }

    def route_reflection(
        state: AgentState,
    ) -> Literal["search_runbook", "generate_verdict"]:
        """Routes based on confidence score and retry count."""
        if (
            state["llm_confidence_score"] < REFLECTION_CONFIDENCE_THRESHOLD
            and state["retry_count"] < MAX_RETRY_COUNT
        ):
            return "search_runbook"
        return "generate_verdict"

    return {"reflect": reflect, "route_reflection": route_reflection}