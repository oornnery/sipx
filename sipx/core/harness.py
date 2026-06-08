from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sipx.core.actor import Actor
from sipx.core.artifacts import ArtifactKind, ArtifactStore
from sipx.core.capabilities import UnsupportedExpectation
from sipx.core.expect import ExpectationFailure
from sipx.core.metrics import Metrics
from sipx.core.timeline import Timeline
from sipx.core.verdict import Verdict


class Harness:
    def __init__(
        self,
        *,
        run_id: str | None = None,
        artifact_root: str | Path = "artifacts",
        backends: dict[str, object] | None = None,
    ) -> None:
        self.run_id = run_id or uuid4().hex
        self.timeline = Timeline(run_id=self.run_id)
        self.artifacts = ArtifactStore(Path(artifact_root) / self.run_id)
        self.metrics = Metrics()
        self._backends: dict[str, object] = {}

        if backends is None:
            from sipx.backends.mock import MockBackend

            self.register_backend("mock", MockBackend())
        else:
            for name, backend in backends.items():
                self.register_backend(name, backend)

    @property
    def backends(self) -> dict[str, object]:
        return dict(self._backends)

    def register_backend(self, name: str, backend: object) -> None:
        if not name:
            raise ValueError("backend name is required")
        self._backends[name] = backend

    def backend(self, name: str) -> object:
        try:
            return self._backends[name]
        except KeyError as exc:
            raise KeyError(f"unknown backend: {name}") from exc

    def actor(
        self,
        actor_id: str,
        *,
        backend: str = "mock",
        kind: str = "actor",
        **metadata: Any,
    ) -> Actor:
        self.backend(backend)
        return Actor(
            actor_id=actor_id,
            harness=self,
            backend_name=backend,
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
        verdict_artifact.path.parent.mkdir(parents=True, exist_ok=True)
        verdict_artifact.path.write_text(
            verdict.to_json(),
            encoding="utf-8",
        )
        return verdict

    async def run_scenario(self, scenario: Any) -> Verdict:
        return await self.run(scenario)
