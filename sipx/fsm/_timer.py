"""Timer managers for SIP transaction retransmissions."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Dict, List


class TimerManager:
    """
    Manages active retransmission timers for SIP transactions.

    Tracks timers by name and ensures only one timer per name is active.
    Thread-safe: timers run in background threads via threading.Timer.
    """

    def __init__(self) -> None:
        """Initialize timer manager."""
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def start_timer(
        self, name: str, delay: float, callback: Callable[[], None]
    ) -> None:
        """
        Start a named timer. Cancels any existing timer with the same name.

        Args:
            name: Unique timer name (e.g. "Timer G", "Timer H")
            delay: Delay in seconds before callback fires
            callback: Function to call when timer expires
        """
        with self._lock:
            # Cancel existing timer with this name
            if name in self._timers:
                self._timers[name].cancel()
            timer = threading.Timer(delay, callback)
            timer.daemon = True
            timer.name = f"SIP-{name}"
            self._timers[name] = timer
            timer.start()

    def cancel_timer(self, name: str) -> None:
        """
        Cancel a specific timer by name.

        Args:
            name: Timer name to cancel
        """
        with self._lock:
            timer = self._timers.pop(name, None)
            if timer is not None:
                timer.cancel()

    def cancel_all(self) -> None:
        """Cancel all active timers."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()

    @property
    def active_timers(self) -> List[str]:
        """Return list of active timer names."""
        with self._lock:
            return list(self._timers.keys())

    def __repr__(self) -> str:
        return f"<TimerManager({len(self._timers)} active)>"


class AsyncTimerManager:
    """Async timer manager using asyncio tasks instead of threading.Timer.

    Drop-in async replacement for TimerManager. Callbacks can be sync or async.
    """

    def __init__(self) -> None:
        """Initialize async timer manager."""
        self._tasks: dict[str, asyncio.Task] = {}

    def start_timer(
        self, name: str, delay: float, callback: Callable[[], None]
    ) -> None:
        """Schedule an async timer.

        Args:
            name: Unique timer name (e.g. "Timer G", "Timer H")
            delay: Delay in seconds before callback fires
            callback: Sync or async callable to invoke when timer expires
        """
        self.cancel_timer(name)
        self._tasks[name] = asyncio.ensure_future(self._run(name, delay, callback))

    async def _run(self, name: str, delay: float, callback: Callable) -> None:
        """Internal coroutine that sleeps then invokes callback."""
        try:
            await asyncio.sleep(delay)
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()
        except asyncio.CancelledError:
            pass
        finally:
            self._tasks.pop(name, None)

    def cancel_timer(self, name: str) -> None:
        """Cancel a specific timer by name.

        Args:
            name: Timer name to cancel
        """
        task = self._tasks.pop(name, None)
        if task and not task.done():
            task.cancel()

    def cancel_all(self) -> None:
        """Cancel all active timers."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()

    @property
    def active_timers(self) -> list[str]:
        """Return list of active timer names."""
        return [n for n, t in self._tasks.items() if not t.done()]

    def __repr__(self) -> str:
        return f"<AsyncTimerManager({len(self._tasks)} active)>"
