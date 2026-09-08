from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


Severity = Literal["critical", "high", "medium", "low", "info"]
Status = Literal["pass", "fail", "error", "skipped", "inconclusive"]


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckResult(ReportModel):
    engine: str
    check: str
    status: Status
    severity: Severity
    details: str
    duration_ms: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    remediation: list[str] = Field(default_factory=list)
    raw_ref: str | None = None


class TargetSummary(ReportModel):
    name: str
    type: Literal["ml", "llm"]
    format: str | None = None
    provider: str | None = None
    access_mode: str | None = None


class Summary(ReportModel):
    total_checks: int
    passed: int
    failed: int
    errors: int
    skipped: int
    severity_breakdown: dict[str, int]


class ScanReport(ReportModel):
    schema_version: Literal["1.0"] = "1.0"
    scan_id: str
    target: TargetSummary
    suite: str
    started_at: datetime
    finished_at: datetime
    summary: Summary
    results: list[CheckResult]
    tool: dict[str, str]


def build_report(
    config: Any,
    suite: Any,
    results: list[CheckResult],
    started_at: datetime | None = None,
) -> ScanReport:
    from llminator import __version__

    started_at = started_at or datetime.now(timezone.utc)
    statuses = Counter(result.status for result in results)
    severities = Counter(
        result.severity for result in results if result.status == "fail"
    )
    target = TargetSummary(
        name=config.name,
        type=config.type,
        format=getattr(config, "format", None),
        provider=getattr(config, "provider", None),
        access_mode=getattr(config, "access_mode", None),
    )
    return ScanReport(
        scan_id=str(uuid4()),
        target=target,
        suite=suite.name,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        summary=Summary(
            total_checks=len(results),
            passed=statuses["pass"],
            failed=statuses["fail"],
            errors=statuses["error"],
            skipped=statuses["skipped"],
            severity_breakdown={
                level: severities[level]
                for level in ("critical", "high", "medium", "low")
            },
        ),
        results=results,
        tool={"name": "llminator", "version": __version__},
    )
