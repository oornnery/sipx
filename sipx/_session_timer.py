"""
Session Timers (RFC 4028).

Manages SIP session refresh via re-INVITE or UPDATE to keep
sessions alive. Prevents sessions from being silently dropped
by proxies or firewalls with short timeouts.

Headers:
  - Session-Expires: <delta>;refresher=<uac|uas>
  - Min-SE: <minimum delta>
  - Supported: timer
  - Require: timer (when enforced)

Usage::

    timer = SessionTimer(client, response, interval=1800)
    timer.start()   # auto-sends re-INVITE/UPDATE before expiry
    timer.stop()
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ._client import AsyncClient, Client
    from .models._message import Response


@dataclass
class SessionTimerConfig:
    """Session timer configuration."""

    interval: int = 1800
    """Session-Expires value in seconds (default 30 min)."""

    min_se: int = 90
    """Minimum session expires (Min-SE header, default 90s per RFC 4028)."""

    refresher: str = "uac"
    """Who refreshes: 'uac' (client) or 'uas' (server)."""

    method: str = "UPDATE"
    """Refresh method: 'UPDATE' (preferred) or 'INVITE'."""

    margin: float = 0.5
    """Refresh at interval * margin (default: halfway before expiry)."""


class SessionTimer:
    """Manages session refresh for a SIP dialog.

    Automatically sends re-INVITE or UPDATE before the session expires.

    Args:
        client: SIP client to send refreshes through.
        response: The INVITE 200 OK response (contains dialog info).
        config: Timer configuration (or uses defaults).
        on_refresh: Optional callback after each refresh.
    """

    def __init__(
        self,
        client: Client,
        response: Response,
        config: SessionTimerConfig | None = None,
        on_refresh: Optional[Callable[[Response], None]] = None,
    ):
        self.client = client
        self.response = response
        self.config = config or SessionTimerConfig()
        self.on_refresh = on_refresh

        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._refresh_count = 0

        # Parse Session-Expires from response if present
        self._parse_response_timer()

    def _parse_response_timer(self):
        """Parse Session-Expires and Min-SE from the response."""
        se = self.response.headers.get("Session-Expires")
        if se:
            parts = se.split(";")
            try:
                self.config.interval = int(parts[0].strip())
            except ValueError:
                pass
            for part in parts[1:]:
                kv = part.strip().split("=", 1)
                if len(kv) == 2 and kv[0].strip().lower() == "refresher":
                    self.config.refresher = kv[1].strip().lower()

        min_se = self.response.headers.get("Min-SE")
        if min_se:
            try:
                self.config.min_se = int(min_se.strip().split(";")[0])
            except ValueError:
                pass

        # Enforce minimum
        if self.config.interval < self.config.min_se:
            self.config.interval = self.config.min_se

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def refresh_interval(self) -> float:
        """Actual refresh interval (before expiry)."""
        return self.config.interval * self.config.margin

    def start(self):
        """Start the session timer."""
        if self._running:
            return
        self._running = True
        self._schedule_next()

    def stop(self):
        """Stop the session timer."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self):
        """Schedule the next refresh."""
        if not self._running:
            return
        delay = self.refresh_interval
        self._timer = threading.Timer(delay, self._do_refresh)
        self._timer.daemon = True
        self._timer.start()

    def _do_refresh(self):
        """Send session refresh (re-INVITE or UPDATE)."""
        if not self._running:
            return

        try:
            request = self.response.request
            if not request:
                return

            # Build refresh headers
            headers = {
                "Session-Expires": f"{self.config.interval};refresher={self.config.refresher}",
                "Supported": "timer",
            }

            if self.config.method == "UPDATE":
                refresh_response = self.client.update(
                    uri=request.uri,
                    headers=headers,
                )
            else:
                # re-INVITE
                refresh_response = self.client.invite(
                    to_uri=request.uri,
                    headers=headers,
                )

            self._refresh_count += 1

            if self.on_refresh and refresh_response:
                self.on_refresh(refresh_response)

        except Exception:
            pass  # silently continue — next refresh will retry

        # Schedule next refresh
        self._schedule_next()

    @staticmethod
    def add_supported(request) -> None:
        """Add 'timer' to Supported header of a request."""
        supported = request.headers.get("Supported", "")
        if "timer" not in supported:
            if supported:
                request.headers["Supported"] = f"{supported}, timer"
            else:
                request.headers["Supported"] = "timer"

    @staticmethod
    def add_session_expires(
        request, interval: int = 1800, refresher: str = "uac"
    ) -> None:
        """Add Session-Expires header to a request."""
        request.headers["Session-Expires"] = f"{interval};refresher={refresher}"

    @staticmethod
    def add_min_se(request, min_se: int = 90) -> None:
        """Add Min-SE header to a request."""
        request.headers["Min-SE"] = str(min_se)


class AsyncSessionTimer:
    """Async session timer using asyncio instead of threading.

    Drop-in async replacement for SessionTimer. Uses ``asyncio.create_task``
    and ``asyncio.sleep`` for non-blocking refresh scheduling.

    Args:
        client: Async SIP client to send refreshes through.
        response: The INVITE 200 OK response (contains dialog info).
        config: Timer configuration (or uses defaults).
        on_refresh: Optional async/sync callback after each refresh.
    """

    def __init__(
        self,
        client: AsyncClient,
        response: Response,
        config: SessionTimerConfig | None = None,
        on_refresh: Optional[Callable[[Response], None]] = None,
    ):
        self.client = client
        self.response = response
        self.config = config or SessionTimerConfig()
        self.on_refresh = on_refresh

        self._task: asyncio.Task | None = None
        self._running = False
        self._refresh_count = 0

        # Parse Session-Expires from response if present
        self._parse_response_timer()

    def _parse_response_timer(self) -> None:
        """Parse Session-Expires and Min-SE from the response."""
        se = self.response.headers.get("Session-Expires")
        if se:
            parts = se.split(";")
            try:
                self.config.interval = int(parts[0].strip())
            except ValueError:
                pass
            for part in parts[1:]:
                kv = part.strip().split("=", 1)
                if len(kv) == 2 and kv[0].strip().lower() == "refresher":
                    self.config.refresher = kv[1].strip().lower()

        min_se = self.response.headers.get("Min-SE")
        if min_se:
            try:
                self.config.min_se = int(min_se.strip().split(";")[0])
            except ValueError:
                pass

        # Enforce minimum
        if self.config.interval < self.config.min_se:
            self.config.interval = self.config.min_se

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def refresh_interval(self) -> float:
        """Actual refresh interval (before expiry)."""
        return self.config.interval * self.config.margin

    async def start(self) -> None:
        """Start the async session timer."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        """Stop the async session timer."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _refresh_loop(self) -> None:
        """Periodically send session refreshes until stopped."""
        while self._running:
            await asyncio.sleep(self.refresh_interval)
            if not self._running:
                break
            try:
                request = self.response.request
                if not request:
                    continue

                headers = {
                    "Session-Expires": f"{self.config.interval};refresher={self.config.refresher}",
                    "Supported": "timer",
                }

                if self.config.method == "UPDATE":
                    refresh_response = await self.client.update(
                        uri=request.uri,
                        headers=headers,
                    )
                else:
                    refresh_response = await self.client.invite(
                        to_uri=request.uri,
                        headers=headers,
                    )

                self._refresh_count += 1

                if self.on_refresh and refresh_response:
                    if asyncio.iscoroutinefunction(self.on_refresh):
                        await self.on_refresh(refresh_response)
                    else:
                        self.on_refresh(refresh_response)

            except asyncio.CancelledError:
                break
            except Exception:
                # Back off on error, then retry on next cycle
                await asyncio.sleep(30)

    @staticmethod
    def add_supported(request) -> None:
        """Add 'timer' to Supported header of a request."""
        SessionTimer.add_supported(request)

    @staticmethod
    def add_session_expires(
        request, interval: int = 1800, refresher: str = "uac"
    ) -> None:
        """Add Session-Expires header to a request."""
        SessionTimer.add_session_expires(request, interval, refresher)

    @staticmethod
    def add_min_se(request, min_se: int = 90) -> None:
        """Add Min-SE header to a request."""
        SessionTimer.add_min_se(request, min_se)


__all__ = ["AsyncSessionTimer", "SessionTimer", "SessionTimerConfig"]
