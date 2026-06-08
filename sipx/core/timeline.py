from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from sipx.core.event import TimelineEvent


class Timeline:
    def __init__(
        self,
        *,
        run_id: str | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.run_id = run_id or uuid4().hex
        self._clock_ns = clock_ns
        self._events: list[TimelineEvent] = []
        self._last_ts_ns = -1

    @property
    def events(self) -> tuple[TimelineEvent, ...]:
        return tuple(self._events)

    def __iter__(self) -> Iterator[TimelineEvent]:
        return iter(self.events)

    def record(
        self,
        category: str,
        name: str,
        *,
        actor_id: str | None = None,
        call_id: str | None = None,
        leg_id: str | None = None,
        data: dict[str, Any] | None = None,
        ts_ns: int | None = None,
    ) -> TimelineEvent:
        timestamp = self._next_ts(ts_ns)
        event = TimelineEvent(
            ts_ns=timestamp,
            run_id=self.run_id,
            actor_id=actor_id,
            call_id=call_id,
            leg_id=leg_id,
            category=category,
            name=name,
            data=dict(data or {}),
        )
        self._events.append(event)
        return event

    def extend(self, events: Iterable[TimelineEvent]) -> None:
        for event in events:
            self.record(
                event.category,
                event.name,
                actor_id=event.actor_id,
                call_id=event.call_id,
                leg_id=event.leg_id,
                data=event.data,
                ts_ns=event.ts_ns,
            )

    def to_jsonl(self) -> str:
        return "".join(
            json.dumps(event.to_dict(), sort_keys=True, default=str) + "\n"
            for event in self._events
        )

    def write_jsonl(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(self.to_jsonl(), encoding="utf-8")

    @classmethod
    def from_jsonl(cls, content: str) -> Timeline:
        events = [
            TimelineEvent.from_dict(json.loads(line))
            for line in content.splitlines()
            if line.strip()
        ]
        run_id = events[0].run_id if events else None
        timeline = cls(run_id=run_id)
        timeline.extend(events)
        return timeline

    @classmethod
    def read_jsonl(cls, path: str | Path) -> Timeline:
        return cls.from_jsonl(Path(path).read_text(encoding="utf-8"))

    def _next_ts(self, ts_ns: int | None) -> int:
        timestamp = self._clock_ns() if ts_ns is None else ts_ns
        if timestamp <= self._last_ts_ns:
            timestamp = self._last_ts_ns + 1
        self._last_ts_ns = timestamp
        return timestamp
