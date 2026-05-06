from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

import asyncpg

from sentinel.tools.base import BaseTool, ToolResult


class SQLTool(BaseTool):
    name = "sql_tool"

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def run(
        self,
        service_name: str,
        error_type: str,
        time_window: str = "24h",
        _retry: bool = True,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            start_time = self._calculate_start_time(time_window)

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        final_severity,
                        resolution,
                        status,
                        created_at
                    FROM incidents
                    WHERE service_name = $1
                      AND error_type = $2
                      AND created_at >= $3
                    ORDER BY created_at DESC
                    LIMIT 50;
                    """,
                    service_name,
                    error_type,
                    start_time,
                    timeout=5,
                )

            duration_ms = self._duration_ms(start)

            if not rows:
                return self._success(
                    data={
                        "count": 0,
                        "last_resolution": None,
                        "last_severity": None,
                        "last_incident_id": None,
                        "empty": True,
                    },
                    duration_ms=duration_ms,
                )

            latest = rows[0]

            return self._success(
                data={
                    "count": len(rows),
                    "last_resolution": latest["resolution"],
                    "last_severity": latest["final_severity"],
                    "last_incident_id": str(latest["id"]),
                    "last_status": latest["status"],
                    "last_seen_at": latest["created_at"].isoformat(),
                    "empty": False,
                },
                duration_ms=duration_ms,
            )

        except asyncpg.exceptions.QueryCanceledError as exc:
            if _retry:
                await asyncio.sleep(2)
                return await self.run(
                    service_name=service_name,
                    error_type=error_type,
                    time_window=time_window,
                    _retry=False,
                )

            return self._failure(
                error=str(exc),
                error_type="timeout",
                duration_ms=self._duration_ms(start),
            )

        except asyncpg.PostgresError as exc:
            return self._failure(
                error=str(exc),
                error_type="db_error",
                duration_ms=self._duration_ms(start),
            )

        except ValueError as exc:
            return self._failure(
                error=str(exc),
                error_type="invalid_time_window",
                duration_ms=self._duration_ms(start),
            )

    def _calculate_start_time(self, time_window: str) -> datetime:
        now = datetime.now(timezone.utc)

        if time_window.endswith("min"):
            minutes = int(time_window[:-3])
            return now - timedelta(minutes=minutes)

        if time_window.endswith("h"):
            hours = int(time_window[:-1])
            return now - timedelta(hours=hours)

        if time_window.endswith("d"):
            days = int(time_window[:-1])
            return now - timedelta(days=days)

        raise ValueError(
            f"Unsupported time_window format: {time_window}. "
            "Use formats like '15min', '24h', or '7d'."
        )

    def _duration_ms(self, start: float) -> int:
        return int((time.perf_counter() - start) * 1000)