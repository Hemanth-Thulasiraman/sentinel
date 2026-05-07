# sentinel/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sentinel.core.database import get_pool, close_pool
from sentinel.core.config import (
    ANTHROPIC_API_KEY, OPENAI_API_KEY,
    SLACK_WEBHOOK_URL, METRICS_BASE_URL, METRICS_API_KEY
)
from sentinel.agent.tools_registry import ToolRegistry
from sentinel.agent.graph import build_graph
from sentinel.api.routes import router

# global registry and app instance
registry: ToolRegistry | None = None
agent_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global registry, agent_app

    # STARTUP
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI
    import cohere

    pool = await get_pool()

    registry = ToolRegistry(
        pool=pool,
        openai_client=AsyncOpenAI(api_key=OPENAI_API_KEY),
        anthropic_client=AsyncAnthropic(api_key=ANTHROPIC_API_KEY),
        cohere_client=cohere.Client(),
        metrics_base_url=METRICS_BASE_URL,
        metrics_api_key=METRICS_API_KEY,
        slack_webhook_url=SLACK_WEBHOOK_URL,
    )

    agent_app = build_graph(registry).compile()

    yield

    # SHUTDOWN
    await close_pool()

app = FastAPI(title="SENTINEL", lifespan=lifespan)
app.include_router(router)