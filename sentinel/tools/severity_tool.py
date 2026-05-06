# sentinel/tools/severity_tool.py

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal

from anthropic import APIConnectionError, APIError, APITimeoutError, RateLimitError
from pydantic import BaseModel, Field, ValidationError

from sentinel.tools.base import BaseTool, ToolResult


SeverityLabel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNCERTAIN"]


class SeverityVerdict(BaseModel):
    severity: SeverityLabel
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]
    recommended_action: str
    uncertainty_flagged: bool = False


class SeverityTool(BaseTool):
    name = "severity_tool"

    def __init__(self, anthropic_client, model: str = "claude-sonnet-4-6"):
        self.anthropic_client = anthropic_client
        self.model = model

    async def run(
        self,
        evidence: dict[str, Any],
        _retry: bool = True,
        _strict: bool = False,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            prompt = self._build_prompt(evidence)
            system = (
                self._strict_system_prompt()
                if _strict
                else self._system_prompt()
            )

            response = await self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=800,
                temperature=0,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_text = response.content[0].text
            verdict = self._parse_and_validate(raw_text)

            return self._success(
                data={
                    "severity": verdict.severity,
                    "confidence": verdict.confidence,
                    "evidence": verdict.evidence,
                    "recommended_action": verdict.recommended_action,
                    "uncertainty_flagged": verdict.uncertainty_flagged,
                    "raw_response": raw_text,
                },
                duration_ms=self._duration_ms(start),
            )

        except (json.JSONDecodeError, ValidationError):
            if _retry:
                await asyncio.sleep(1)
                return await self.run(
                    evidence=evidence,
                    _retry=False,
                    _strict=True,
                )

            return self._success(
                data=self._fallback_to_classifier(evidence),
                duration_ms=self._duration_ms(start),
            )

        except RateLimitError as exc:
            return self._failure(
                error=str(exc),
                error_type="rate_limit",
                duration_ms=self._duration_ms(start),
            )

        except (APITimeoutError, APIConnectionError) as exc:
            if _retry:
                await asyncio.sleep(2)
                return await self.run(
                    evidence=evidence,
                    _retry=False,
                    _strict=_strict,
                )

            return self._failure(
                error=str(exc),
                error_type="model_error",
                duration_ms=self._duration_ms(start),
            )

        except APIError as exc:
            return self._failure(
                error=str(exc),
                error_type="model_error",
                duration_ms=self._duration_ms(start),
            )

    def _system_prompt(self) -> str:
        return """
You are SENTINEL's severity scoring tool.

Return only valid JSON matching this schema:
{
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNCERTAIN",
  "confidence": number between 0 and 1,
  "evidence": ["short evidence string"],
  "recommended_action": "short action string",
  "uncertainty_flagged": boolean
}

Rules:
- Do not invent evidence.
- A runbook match is evidence, not a conclusion.
- Metrics and past incidents should corroborate severity.
- If evidence is weak or conflicting, use UNCERTAIN and set uncertainty_flagged=true.
""".strip()

    def _strict_system_prompt(self) -> str:
        return """
You are SENTINEL's severity scoring tool.
Your previous response could not be parsed.

Return ONLY this JSON object with NO other text:
{
  "severity": "LOW",
  "confidence": 0.5,
  "evidence": ["one evidence string"],
  "recommended_action": "one action string",
  "uncertainty_flagged": false
}

Replace the values. Do not add any text before or after the JSON.
""".strip()

    def _build_prompt(self, evidence: dict[str, Any]) -> str:
        return f"""
Score the incident severity using this evidence:

{json.dumps(evidence, indent=2, default=str)}

Return only JSON.
""".strip()

    def _parse_and_validate(self, raw_text: str) -> SeverityVerdict:
        cleaned = raw_text.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)
        return SeverityVerdict.model_validate(payload)

    def _fallback_to_classifier(self, evidence: dict[str, Any]) -> dict[str, Any]:
        classifier_severity = evidence.get("classifier_severity", "UNCERTAIN")
        classifier_confidence = evidence.get("classifier_confidence", 0.0)

        if classifier_severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            classifier_severity = "UNCERTAIN"

        return {
            "severity": classifier_severity,
            "confidence": float(classifier_confidence),
            "evidence": [
                "Severity scorer returned malformed output twice.",
                "Fallback used original classifier severity.",
            ],
            "recommended_action": "Send to human review with uncertainty flag.",
            "uncertainty_flagged": True,
            "fallback_used": True,
        }

    def _duration_ms(self, start: float) -> int:
        return int((time.perf_counter() - start) * 1000)