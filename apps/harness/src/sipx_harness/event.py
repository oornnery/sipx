from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TimelineEvent:
    ts_ns: int
    run_id: str
    category: str
    name: str
    actor_id: str | None = None
    call_id: str | None = None
    leg_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ts_ns < 0:
            raise ValueError("ts_ns must be non-negative")
        if not self.run_id:
            raise ValueError("run_id is required")
        if not self.category:
            raise ValueError("category is required")
        if not self.name:
            raise ValueError("name is required")
        self.data = dict(self.data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts_ns": self.ts_ns,
            "run_id": self.run_id,
            "actor_id": self.actor_id,
            "call_id": self.call_id,
            "leg_id": self.leg_id,
            "category": self.category,
            "name": self.name,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        return cls(
            ts_ns=int(data["ts_ns"]),
            run_id=str(data["run_id"]),
            actor_id=data.get("actor_id"),
            call_id=data.get("call_id"),
            leg_id=data.get("leg_id"),
            category=str(data["category"]),
            name=str(data["name"]),
            data=dict(data.get("data") or {}),
        )
