from pydantic import BaseModel
from typing import Optional
import time


class ToolResult(BaseModel):
    success: bool
    data: Optional[dict]
    error: Optional[str]
    error_type: Optional[str]  # timeout, empty_result, rate_limit, parse_error, db_error
    tool_name: str
    duration_ms: int


class BaseTool:
    name: str

    def run(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    def _success(self, data: dict, duration_ms: int) -> ToolResult:
        return ToolResult(
            success=True,
            data=data,
            error=None,
            error_type=None,
            tool_name=self.name,
            duration_ms=duration_ms
        )

    def _failure(self, error: str, error_type: str, duration_ms: int) -> ToolResult:
        return ToolResult(
            success=False,
            data=None,
            error=error,
            error_type=error_type,
            tool_name=self.name,
            duration_ms=duration_ms
        )