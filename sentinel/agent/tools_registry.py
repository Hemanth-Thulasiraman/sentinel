# sentinel/agent/tools_registry.py
import asyncpg
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import cohere

from sentinel.tools.sql_tool import SQLTool
from sentinel.tools.runbook_tool import RunbookTool
from sentinel.tools.metrics_tool import MetricsTool
from sentinel.tools.severity_tool import SeverityTool
from sentinel.tools.escalation_tool import EscalationTool

class ToolRegistry:
    """
    Created once at application startup.
    Holds all tool instances with shared clients and pools.
    Injected into node functions via closure.
    """
    def __init__(
        self,
        pool: asyncpg.Pool,
        openai_client: AsyncOpenAI,
        anthropic_client: AsyncAnthropic,
        cohere_client: cohere.Client,
        metrics_base_url: str,
        metrics_api_key: str,
        slack_webhook_url: str,
    ):
        self.sql = SQLTool(pool=pool)
        self.runbook = RunbookTool(
            pool=pool,
            openai_client=openai_client,
            cohere_client=cohere_client,
        )
        self.metrics = MetricsTool(
            base_url=metrics_base_url,
            api_key=metrics_api_key,
        )
        self.severity = SeverityTool(anthropic_client=anthropic_client)
        self.escalation = EscalationTool(
            slack_webhook_url=slack_webhook_url,
            pool=pool,
        )