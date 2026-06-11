"""Event hooks system for SIP protocol interception.

Follows the httpx-style event_hooks pattern: a dict mapping event names
to lists of callables. Hooks are side-effect only; return values are ignored.

Supported events:
    - "request": called before a request is sent
    - "response": called after a response is received
    - "provisional": called after a 1xx provisional response is received

Hook order is not guaranteed when multiple hooks are registered for the
same event; they run in registration order but callers should not rely on it.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

EventHooks = dict[str, list[Callable[..., None]]]


async def run_hooks(hooks: EventHooks, event: str, *args: Any) -> None:
    """Run all hooks registered for *event*, passing *args* to each.

    Both sync and async hooks are supported. Hook exceptions are caught
    and suppressed so that one failing hook does not prevent others from
    running and does not break the caller's flow.
    """
    for hook in hooks.get(event, []):
        try:
            if inspect.iscoroutinefunction(hook):
                await hook(*args)
            else:
                hook(*args)
        except Exception:
            continue
