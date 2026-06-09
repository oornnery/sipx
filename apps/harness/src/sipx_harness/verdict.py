from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from sipx_harness.artifacts import Artifact


VerdictStatus = Literal["passed", "failed", "error", "skipped"]


@dataclass(slots=True)
class ExpectationResult:
    name: str
    status: str
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(slots=True)
class Verdict:
    status: VerdictStatus
    reason: str | None = None
    failed_expectations: list[ExpectationResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def passed(cls, *, reason: str | None = None) -> Verdict:
        return cls(status="passed", reason=reason)

    @classmethod
    def failed(
        cls,
        *,
        reason: str | None = None,
        failed_expectations: list[ExpectationResult] | None = None,
    ) -> Verdict:
        return cls(
            status="failed",
            reason=reason,
            failed_expectations=list(failed_expectations or []),
        )

    @classmethod
    def error(cls, *, reason: str | None = None) -> Verdict:
        return cls(status="error", reason=reason)

    @classmethod
    def skipped(cls, *, reason: str | None = None) -> Verdict:
        return cls(status="skipped", reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "failed_expectations": [
                expectation.to_dict() for expectation in self.failed_expectations
            ],
            "warnings": list(self.warnings),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metrics": dict(self.metrics),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str) + "\n"
