from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from sipx.security.redaction import Redactor, default_redactor


class ArtifactKind(StrEnum):
    TIMELINE = "timeline"
    VERDICT = "verdict"
    RECORDING = "recording"
    TRANSCRIPT = "transcript"
    SIP_PCAP = "sip_pcap"
    REPORT = "report"
    OTHER = "other"


@dataclass(slots=True)
class Artifact:
    name: str
    path: Path
    kind: ArtifactKind = ArtifactKind.OTHER
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "kind": self.kind.value,
            "metadata": dict(self.metadata),
        }


class ArtifactStore:
    def __init__(self, root: str | Path, *, redactor: Redactor | None = None) -> None:
        self.root = Path(root)
        self.redactor = default_redactor if redactor is None else redactor
        self._artifacts: list[Artifact] = []

    @property
    def artifacts(self) -> tuple[Artifact, ...]:
        return tuple(self._artifacts)

    def path_for(self, name: str) -> Path:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"artifact name must be relative and safe: {name}")
        return self.root / relative

    def register(
        self,
        name: str,
        *,
        kind: ArtifactKind | str = ArtifactKind.OTHER,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        artifact = Artifact(
            name=name,
            path=self.path_for(name),
            kind=ArtifactKind(kind),
            metadata=dict(metadata or {}),
        )
        self._artifacts.append(artifact)
        return artifact

    def write_text(
        self,
        name: str,
        content: str,
        *,
        kind: ArtifactKind | str = ArtifactKind.OTHER,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        artifact = self.register(name, kind=kind, metadata=metadata)
        artifact.path.parent.mkdir(parents=True, exist_ok=True)
        artifact.path.write_text(self.redactor.redact_text(content), encoding="utf-8")
        return artifact

    def write_json(
        self,
        name: str,
        content: Any,
        *,
        kind: ArtifactKind | str = ArtifactKind.OTHER,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        return self.write_text(
            name,
            json.dumps(
                self.redactor.redact(content),
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            kind=kind,
            metadata=metadata,
        )
