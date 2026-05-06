# sentinel/tools/escalation_tool.py

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import asyncpg
import httpx

from sentinel.tools.base import BaseTool, ToolResult


class EscalationTool(BaseTool):
    name = "escalation_tool"

    def __init__(self, slack_webhook_url: str, pool: asyncpg.Pool):
        self.webhook_url = slack_webhook_url
        self.pool = pool

    async def run(
        self,
        verdict: dict[str, Any],
        run_id: str,
        incident_id: str,
        service_name: str,
        _retry: bool = True,
    ) -> ToolResult:
        start = time.perf_counter()
        payload = self._build_payload(verdict, run_id, incident_id, service_name)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=5.0,
                )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "2"))

                if _retry:
                    await asyncio.sleep(retry_after)
                    return await self.run(
                        verdict=verdict,
                        run_id=run_id,
                        incident_id=incident_id,
                        service_name=service_name,
                        _retry=False,
                    )

                await self._write_dead_letter(
                    run_id=run_id,
                    incident_id=incident_id,
                    payload=payload,
                    error_type="rate_limit",
                    error_message=response.text,
                )

                return self._failure(
                    error=response.text,
                    error_type="rate_limit",
                    duration_ms=self._duration_ms(start),
                )

            if response.status_code >= 500:
                await self._write_dead_letter(
                    run_id=run_id,
                    incident_id=incident_id,
                    payload=payload,
                    error_type="slack_down",
                    error_message=response.text,
                )

                return self._failure(
                    error=response.text,
                    error_type="slack_down",
                    duration_ms=self._duration_ms(start),
                )

            if response.status_code >= 400:
                await self._write_dead_letter(
                    run_id=run_id,
                    incident_id=incident_id,
                    payload=payload,
                    error_type="slack_error",
                    error_message=response.text,
                )

                return self._failure(
                    error=response.text,
                    error_type="slack_error",
                    duration_ms=self._duration_ms(start),
                )

            return self._success(
                data={
                    # Slack Incoming Webhooks return plain text "ok", not JSON.
                    # ts is not available via webhook. TODO v2: use chat.postMessage
                    # with a bot token if thread updates require message_ts.
                    "slack_message_ts": None,
                    "notification_sent": True,
                    "correlation_key": incident_id,
                },
                duration_ms=self._duration_ms(start),
            )

        except httpx.TimeoutException as exc:
            if _retry:
                await asyncio.sleep(2)
                return await self.run(
                    verdict=verdict,
                    run_id=run_id,
                    incident_id=incident_id,
                    service_name=service_name,
                    _retry=False,
                )

            await self._write_dead_letter(
                run_id=run_id,
                incident_id=incident_id,
                payload=payload,
                error_type="timeout",
                error_message=str(exc),
            )

            return self._failure(
                error=str(exc),
                error_type="timeout",
                duration_ms=self._duration_ms(start),
            )

        except httpx.HTTPError as exc:
            await self._write_dead_letter(
                run_id=run_id,
                incident_id=incident_id,
                payload=payload,
                error_type="slack_error",
                error_message=str(exc),
            )

            return self._failure(
                error=str(exc),
                error_type="slack_error",
                duration_ms=self._duration_ms(start),
            )

        except asyncpg.PostgresError as db_exc:
            return self._failure(
                error=(
                    f"Dead letter write failed: {db_exc}. "
                    "Original Slack error occurred before dead letter persistence."
                ),
                error_type="dead_letter_write_failed",
                duration_ms=self._duration_ms(start),
            )

    def _build_payload(
        self,
        verdict: dict[str, Any],
        run_id: str,
        incident_id: str,
        service_name: str,
    ) -> dict[str, Any]:
        severity = verdict.get("severity", "UNKNOWN")
        recommended_action = verdict.get("recommended_action", "No action provided.")
        confidence = verdict.get("confidence", "unknown")
        uncertainty_flagged = verdict.get("uncertainty_flagged", False)

        evidence_items = verdict.get("evidence", [])
        if isinstance(evidence_items, list):
            evidence_text = "\n".join(f"• {item}" for item in evidence_items)
        else:
            evidence_text = str(evidence_items)

        uncertainty_text = (
            "\n*Uncertainty:* Flagged for reviewer attention"
            if uncertainty_flagged
            else ""
        )

        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 SENTINEL Alert: {severity}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Service:* {service_name}\n"
                            f"*Incident ID:* `{incident_id}`\n"
                            f"*Run ID:* `{run_id}`\n"
                            f"*Confidence:* {confidence}\n"
                            f"{uncertainty_text}"
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Evidence:*\n{evidence_text}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommended Action:*\n{recommended_action}",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve"},
                            "style": "primary",
                            "value": run_id,
                            "action_id": "hitl_approve",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject"},
                            "style": "danger",
                            "value": run_id,
                            "action_id": "hitl_reject",
                        },
                    ],
                },
            ]
        }

    async def _write_dead_letter(
        self,
        run_id: str,
        incident_id: str,
        payload: dict[str, Any],
        error_type: str,
        error_message: str,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO dead_letter_notifications (
                    run_id,
                    incident_id,
                    payload,
                    error_type,
                    error_message,
                    created_at
                )
                VALUES ($1, $2, $3::jsonb, $4, $5, NOW());
                """,
                run_id,
                incident_id,
                json.dumps(payload),
                error_type,
                error_message,
            )

    def _duration_ms(self, start: float) -> int:
        return int((time.perf_counter() - start) * 1000)