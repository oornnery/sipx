from __future__ import annotations

import json
from dataclasses import dataclass, field
from pprint import pformat
from typing import Any

from sipx_harness.artifacts import Artifact, ArtifactKind, ArtifactStore
from sipx_harness.event import TimelineEvent
from sipx_harness.timeline import Timeline


@dataclass(frozen=True, slots=True)
class ScenarioAction:
    name: str
    category: str = "user_action"
    actor_id: str | None = None
    call_id: str | None = None
    leg_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_event(cls, event: TimelineEvent) -> ScenarioAction:
        return cls(
            name=event.name,
            category=event.category,
            actor_id=event.actor_id,
            call_id=event.call_id,
            leg_id=event.leg_id,
            data=dict(event.data),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "actor_id": self.actor_id,
            "call_id": self.call_id,
            "leg_id": self.leg_id,
            "data": dict(self.data),
        }


class ScenarioRecorder:
    def __init__(self, *, name: str = "recorded_scenario") -> None:
        if not name:
            raise ValueError("scenario name is required")
        self.name = name
        self.actions: list[ScenarioAction] = []

    @classmethod
    def from_timeline(
        cls,
        timeline: Timeline,
        *,
        name: str = "recorded_scenario",
    ) -> ScenarioRecorder:
        recorder = cls(name=name)
        for event in timeline.events:
            if event.category == "scenario" and event.name in {"started", "ended"}:
                continue
            recorder.actions.append(ScenarioAction.from_event(event))
        return recorder

    def record_action(
        self,
        timeline: Timeline,
        name: str,
        *,
        actor_id: str | None = None,
        call_id: str | None = None,
        leg_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> ScenarioAction:
        event = timeline.record(
            "user_action",
            name,
            actor_id=actor_id,
            call_id=call_id,
            leg_id=leg_id,
            data=data,
        )
        action = ScenarioAction.from_event(event)
        self.actions.append(action)
        return action

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "actions": [action.to_dict() for action in self.actions],
        }

    def export_yaml(self) -> str:
        lines = [f"name: {self.name}", "actions:"]
        if not self.actions:
            lines.append("  []")
            return "\n".join(lines) + "\n"
        for action in self.actions:
            lines.append(f"  - category: {action.category}")
            lines.append(f"    name: {action.name}")
            _append_optional_yaml(lines, "actor_id", action.actor_id)
            _append_optional_yaml(lines, "call_id", action.call_id)
            _append_optional_yaml(lines, "leg_id", action.leg_id)
            lines.append(f"    data: {json.dumps(action.data, sort_keys=True)}")
        return "\n".join(lines) + "\n"

    def export_python(self) -> str:
        actions = pformat(
            [action.to_dict() for action in self.actions], sort_dicts=True
        )
        return (
            "from sipx_harness import scenario\n\n"
            f"ACTIONS = {actions}\n\n"
            f"@scenario({self.name!r})\n"
            "async def recorded(h):\n"
            "    for action in ACTIONS:\n"
            "        h.timeline.record(\n"
            "            action['category'],\n"
            "            action['name'],\n"
            "            actor_id=action.get('actor_id'),\n"
            "            call_id=action.get('call_id'),\n"
            "            leg_id=action.get('leg_id'),\n"
            "            data=action.get('data'),\n"
            "        )\n"
        )

    def write_exports(
        self,
        store: ArtifactStore,
        *,
        basename: str = "scenario",
    ) -> tuple[Artifact, Artifact]:
        yaml_artifact = store.write_text(
            f"{basename}.yaml",
            self.export_yaml(),
            kind=ArtifactKind.OTHER,
            metadata={"format": "yaml", "source": "scenario_recorder"},
        )
        python_artifact = store.write_text(
            f"{basename}.py",
            self.export_python(),
            kind=ArtifactKind.OTHER,
            metadata={"format": "python", "source": "scenario_recorder"},
        )
        return yaml_artifact, python_artifact


def _append_optional_yaml(lines: list[str], key: str, value: str | None) -> None:
    if value is not None:
        lines.append(f"    {key}: {value}")
