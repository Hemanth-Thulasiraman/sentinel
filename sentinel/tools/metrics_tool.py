# sentinel/tools/metrics_tool.py

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from sentinel.tools.base import BaseTool, ToolResult


class MetricsTool(BaseTool):
    name = "metrics_tool"

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def run(
        self,
        service_name: str,
        timestamp: str,
        time_window: str = "15min",
        _retry: bool = True,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            url = f"{self.base_url}/metrics"

            params = {
                "service_name": service_name,
                "timestamp": timestamp,
                "time_window": time_window,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }

            # TODO v2: inject shared httpx.AsyncClient for connection reuse.
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=5.0,
                )

            if response.status_code >= 500:
                return self._failure(
                    error=f"Metrics API server error: {response.status_code}",
                    error_type="api_error",
                    duration_ms=self._duration_ms(start),
                )

            if response.status_code >= 400:
                return self._failure(
                    error=f"Metrics API client error: {response.status_code}",
                    error_type="api_error",
                    duration_ms=self._duration_ms(start),
                )

            payload: dict[str, Any] = response.json()

            if not payload or payload.get("data_available") is False:
                return self._success(
                    data={
                        "cpu_spike": False,
                        "error_rate": None,
                        "latency_p99": None,
                        "anomaly_detected": False,
                        "data_available": False,
                        "empty": True,
                    },
                    duration_ms=self._duration_ms(start),
                )

            return self._success(
                data={
                    "cpu_spike": bool(payload.get("cpu_spike", False)),
                    "error_rate": payload.get("error_rate"),
                    "latency_p99": payload.get("latency_p99"),
                    "anomaly_detected": bool(payload.get("anomaly_detected", False)),
                    "data_available": True,
                    "empty": False,
                },
                duration_ms=self._duration_ms(start),
            )

        except httpx.TimeoutException as exc:
            if _retry:
                await asyncio.sleep(2)
                return await self.run(
                    service_name=service_name,
                    timestamp=timestamp,
                    time_window="5min",
                    _retry=False,
                )

            return self._failure(
                error=str(exc),
                error_type="timeout",
                duration_ms=self._duration_ms(start),
            )

        except httpx.HTTPError as exc:
            return self._failure(
                error=str(exc),
                error_type="api_error",
                duration_ms=self._duration_ms(start),
            )

        except ValueError as exc:
            return self._failure(
                error=str(exc),
                error_type="malformed_response",
                duration_ms=self._duration_ms(start),
            )

    def _duration_ms(self, start: float) -> int:
        return int((time.perf_counter() - start) * 1000)