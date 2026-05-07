# sentinel/core/config.py
import os

REFLECTION_CONFIDENCE_THRESHOLD = float(
    os.getenv("REFLECTION_CONFIDENCE_THRESHOLD", "0.75")
)
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "2"))

DATABASE_URL = os.getenv("DATABASE_URL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
METRICS_BASE_URL = os.getenv("METRICS_BASE_URL", "http://localhost:8001")
METRICS_API_KEY = os.getenv("METRICS_API_KEY", "")