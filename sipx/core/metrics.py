from __future__ import annotations

from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        self._validate_name(name)
        self._values[name] = value

    def increment(self, name: str, amount: int | float = 1) -> int | float:
        self._validate_name(name)
        current = self._values.get(name, 0)
        if not isinstance(current, int | float):
            raise TypeError(f"metric is not numeric: {name}")
        next_value = current + amount
        self._values[name] = next_value
        return next_value

    def snapshot(self) -> dict[str, Any]:
        return dict(self._values)

    def _validate_name(self, name: str) -> None:
        if not name:
            raise ValueError("metric name is required")
