from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sipx_harness.actor import Actor
from sipx_harness.artifacts import ArtifactKind, ArtifactStore
from sipx_harness.capabilities import UnsupportedExpectation
from sipx_harness.expect import ExpectationFailure
from sipx_harness.metrics import Metrics
from sipx_harness.reports import write_report_artifacts
from sipx_harness.timeline import Timeline
from sipx_harness.verdict import Verdict


class Harness:
    def __init__(
        self,
        *,
        run_id: str | None = None,
        artifact_root: str | Path = "artifacts",
        runtimes: dict[str, object] | None = None,
    ) -> None:
        self.run_id = run_id or uuid4().hex
        self.timeline = Timeline(run_id=self.run_id)
        self.artifacts = ArtifactStore(Path(artifact_root) / self.run_id)
        self.metrics = Metrics()
        self._runtimes: dict[str, object] = {}

        if runtimes is None:
            from sipx_harness.mock import MockRuntime

            self.register_runtime("mock", MockRuntime())
        else:
            for name, runtime in runtimes.items():
                self.register_runtime(name, runtime)

    @property
    def runtimes(self) -> dict[str, object]:
        return dict(self._runtimes)

    def register_runtime(self, name: str, runtime: object) -> None:
        if not name:
            raise ValueError("runtime name is required")
        self._runtimes[name] = runtime

    def runtime(self, name: str) -> object:
        try:
            return self._runtimes[name]
        except KeyError as exc:
            raise KeyError(f"unknown runtime: {name}") from exc

    def actor(
        self,
        actor_id: str,
        *,
        runtime: str = "mock",
        kind: str = "actor",
        **metadata: Any,
    ) -> Actor:
        self.runtime(runtime)
        return Actor(
            actor_id=actor_id,
            harness=self,
            runtime_name=runtime,
            kind=kind,
            metadata=dict(metadata),
        )

    async def run(self, scenario: Any) -> Verdict:
        verdict: Verdict
        try:
            result = await scenario.run(self)
            verdict = result if isinstance(result, Verdict) else Verdict.passed()
        except ExpectationFailure as exc:
            verdict = Verdict.failed(
                reason=str(exc),
                failed_expectations=[exc.result],
            )
        except UnsupportedExpectation as exc:
            verdict = Verdict.failed(reason=str(exc))
        except AssertionError as exc:
            verdict = Verdict.failed(reason=str(exc))
        except (
            Exception
        ) as exc:  # pragma: no cover - exact exception is scenario-defined
            verdict = Verdict.error(reason=f"{type(exc).__name__}: {exc}")

        verdict.metrics.update(self.metrics.snapshot())
        timeline_artifact = self.artifacts.write_text(
            "timeline.jsonl",
            self.timeline.to_jsonl(),
            kind=ArtifactKind.TIMELINE,
        )
        verdict.artifacts.append(timeline_artifact)

        verdict_artifact = self.artifacts.register(
            "verdict.json", kind=ArtifactKind.VERDICT
        )
        verdict.artifacts.append(verdict_artifact)
        verdict.artifacts.extend(
            write_report_artifacts(self.artifacts, self.timeline, verdict)
        )

        verdict_artifact.path.parent.mkdir(parents=True, exist_ok=True)
        verdict_artifact.path.write_text(verdict.to_json(), encoding="utf-8")
        return verdict

    async def run_scenario(self, scenario: Any) -> Verdict:
        return await self.run(scenario)
