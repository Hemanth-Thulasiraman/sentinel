# sentinel/tools/runbook_tool.py

from __future__ import annotations

import asyncio
import time

import asyncpg
from cohere.errors import CohereAPIError, CohereConnectionError, TooManyRequestsError
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from sentinel.tools.base import BaseTool, ToolResult


class RunbookTool(BaseTool):
    name = "runbook_tool"

    def __init__(self, pool: asyncpg.Pool, openai_client, cohere_client):
        self.pool = pool
        self.openai_client = openai_client
        self.cohere_client = cohere_client

    async def run(
        self,
        error_type: str,
        log_message: str,
        _retry: bool = True,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            query_string = self._build_query(error_type, log_message)

            embedding_response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query_string,
            )

            query_embedding = embedding_response.data[0].embedding
            query_vector = "[" + ",".join(str(x) for x in query_embedding) + "]"

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        title,
                        content,
                        1 - (embedding <=> $1::vector) AS similarity
                    FROM runbooks
                    WHERE 1 - (embedding <=> $1::vector) > 0.75
                    ORDER BY embedding <=> $1::vector
                    LIMIT 5;
                    """,
                    query_vector,
                    timeout=5,
                )

            if not rows:
                if _retry:
                    return await self.run(
                        error_type=error_type,
                        log_message="",
                        _retry=False,
                    )

                return self._success(
                    data={
                        "runbook_found": False,
                        "runbook_match": None,
                        "empty": True,
                    },
                    duration_ms=self._duration_ms(start),
                )

            results = [dict(row) for row in rows]
            loop = asyncio.get_running_loop()
            rerank_response = await loop.run_in_executor(
                None,
                lambda: self.cohere_client.rerank(
                    model="rerank-english-v3.0",
                    query=query_string,
                    documents=[r["content"] for r in results],
                    top_n=1,
                ),
            )

            best_index = rerank_response.results[0].index
            best = results[best_index]

            return self._success(
                data={
                    "runbook_found": True,
                    "runbook_match": {
                        "id": str(best["id"]),
                        "title": best["title"],
                        "content": best["content"],
                        "similarity": float(best["similarity"]),
                        "rerank_score": float(
                            rerank_response.results[0].relevance_score
                        ),
                    },
                    "empty": False,
                },
                duration_ms=self._duration_ms(start),
            )

        except asyncpg.exceptions.QueryCanceledError as exc:
            if _retry:
                await asyncio.sleep(2)
                return await self.run(
                    error_type=error_type,
                    log_message=log_message,
                    _retry=False,
                )

            return self._failure(
                error=str(exc),
                error_type="timeout",
                duration_ms=self._duration_ms(start),
            )

        except (APITimeoutError, APIConnectionError) as exc:
            if _retry:
                await asyncio.sleep(2)
                return await self.run(
                    error_type=error_type,
                    log_message=log_message,
                    _retry=False,
                )

            return self._failure(
                error=str(exc),
                error_type="embedding_error",
                duration_ms=self._duration_ms(start),
            )

        except RateLimitError as exc:
            return self._failure(
                error=str(exc),
                error_type="rate_limit",
                duration_ms=self._duration_ms(start),
            )

        except APIError as exc:
            return self._failure(
                error=str(exc),
                error_type="embedding_error",
                duration_ms=self._duration_ms(start),
            )

        except asyncpg.PostgresError as exc:
            return self._failure(
                error=str(exc),
                error_type="store_error",
                duration_ms=self._duration_ms(start),
            )

        except TooManyRequestsError as exc:
            return self._failure(
                error=str(exc),
                error_type="rate_limit",
                duration_ms=self._duration_ms(start),
            )

        except CohereConnectionError as exc:
            return self._failure(
                error=str(exc),
                error_type="rerank_error",
                duration_ms=self._duration_ms(start),
            )

        except CohereAPIError as exc:
            return self._failure(
                error=str(exc),
                error_type="rerank_error",
                duration_ms=self._duration_ms(start),
            )

    def _build_query(self, error_type: str, log_message: str) -> str:
        return f"{error_type}: {log_message}".strip()

    def _duration_ms(self, start: float) -> int:
        return int((time.perf_counter() - start) * 1000)