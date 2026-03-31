"""
SIP SUBSCRIBE/NOTIFY (RFC 6665 / RFC 3265).

Manages subscription lifecycle: subscribe, refresh, notify, unsubscribe.

Usage::

    sub = Subscription(client, "sip:alice@pbx.com", event="presence")
    sub.subscribe(expires=3600)
    print(sub.state)       # "active"
    print(sub.last_notify)  # last NOTIFY body
    sub.unsubscribe()
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ..client import AsyncClient, Client
    from ..models._message import Response


class SubscriptionState(Enum):
    """Subscription states per RFC 6665."""

    INIT = auto()
    PENDING = auto()
    ACTIVE = auto()
    TERMINATED = auto()


@dataclass
class Subscription:
    """Manages a SIP event subscription.

    Handles SUBSCRIBE requests, auto-refresh before expiry,
    and tracks NOTIFY state.
    """

    client: Client
    uri: str
    event: str = "presence"
    expires: int = 3600
    state: SubscriptionState = field(default=SubscriptionState.INIT)
    last_notify_body: str | None = None
    on_notify: Optional[Callable[[str], None]] = None

    _timer: Optional[threading.Timer] = field(default=None, repr=False)
    _refresh_count: int = field(default=0, repr=False)

    def subscribe(self, expires: int | None = None) -> Response | None:
        """Send SUBSCRIBE request.

        Args:
            expires: Subscription duration in seconds (default: self.expires).

        Returns:
            Response from server.
        """
        if expires is not None:
            self.expires = expires

        r = self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=self.expires,
        )

        if r and r.status_code == 200:
            self.state = SubscriptionState.ACTIVE
            self._schedule_refresh()
        elif r and r.status_code == 202:
            self.state = SubscriptionState.PENDING
            self._schedule_refresh()
        else:
            self.state = SubscriptionState.TERMINATED

        return r

    def unsubscribe(self) -> Response | None:
        """Send SUBSCRIBE with Expires: 0 to unsubscribe."""
        self._cancel_refresh()
        r = self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=0,
        )
        self.state = SubscriptionState.TERMINATED
        return r

    def refresh(self) -> Response | None:
        """Manually refresh the subscription."""
        r = self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=self.expires,
        )

        if r and r.status_code in (200, 202):
            self._refresh_count += 1
            self._schedule_refresh()
        else:
            self.state = SubscriptionState.TERMINATED

        return r

    def handle_notify(self, body: str, subscription_state: str = "") -> None:
        """Process an incoming NOTIFY.

        Args:
            body: NOTIFY body content (e.g. PIDF XML for presence).
            subscription_state: Subscription-State header value.
        """
        self.last_notify_body = body

        if "terminated" in subscription_state.lower():
            self.state = SubscriptionState.TERMINATED
            self._cancel_refresh()
        elif "active" in subscription_state.lower():
            self.state = SubscriptionState.ACTIVE
        elif "pending" in subscription_state.lower():
            self.state = SubscriptionState.PENDING

        if self.on_notify:
            self.on_notify(body)

    @property
    def is_active(self) -> bool:
        return self.state in (SubscriptionState.ACTIVE, SubscriptionState.PENDING)

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    def _schedule_refresh(self):
        """Schedule auto-refresh at 80% of expires."""
        self._cancel_refresh()
        if self.expires <= 0:
            return
        delay = self.expires * 0.8
        self._timer = threading.Timer(delay, self._do_refresh)
        self._timer.daemon = True
        self._timer.start()

    def _do_refresh(self):
        """Execute auto-refresh."""
        if self.state == SubscriptionState.TERMINATED:
            return
        self.refresh()

    def _cancel_refresh(self):
        """Cancel pending refresh timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None


@dataclass
class AsyncSubscription:
    """Async subscription manager using asyncio.

    Drop-in async replacement for Subscription. Uses ``asyncio.create_task``
    and ``asyncio.sleep`` for non-blocking refresh scheduling.
    """

    client: AsyncClient
    uri: str
    event: str = "presence"
    expires: int = 3600
    state: SubscriptionState = field(default=SubscriptionState.INIT)
    last_notify_body: str | None = None
    on_notify: Optional[Callable[[str], None]] = None

    _task: asyncio.Task | None = field(default=None, repr=False)
    _refresh_count: int = field(default=0, repr=False)

    async def subscribe(self, expires: int | None = None) -> Response | None:
        """Send SUBSCRIBE request.

        Args:
            expires: Subscription duration in seconds (default: self.expires).

        Returns:
            Response from server.
        """
        if expires is not None:
            self.expires = expires

        r = await self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=self.expires,
        )

        if r and r.status_code == 200:
            self.state = SubscriptionState.ACTIVE
            self._schedule_refresh()
        elif r and r.status_code == 202:
            self.state = SubscriptionState.PENDING
            self._schedule_refresh()
        else:
            self.state = SubscriptionState.TERMINATED

        return r

    async def unsubscribe(self) -> Response | None:
        """Send SUBSCRIBE with Expires: 0 to unsubscribe."""
        self._cancel_refresh()
        r = await self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=0,
        )
        self.state = SubscriptionState.TERMINATED
        return r

    async def refresh(self) -> Response | None:
        """Manually refresh the subscription."""
        r = await self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=self.expires,
        )

        if r and r.status_code in (200, 202):
            self._refresh_count += 1
            self._schedule_refresh()
        else:
            self.state = SubscriptionState.TERMINATED

        return r

    def handle_notify(self, body: str, subscription_state: str = "") -> None:
        """Process an incoming NOTIFY.

        Args:
            body: NOTIFY body content (e.g. PIDF XML for presence).
            subscription_state: Subscription-State header value.
        """
        self.last_notify_body = body

        if "terminated" in subscription_state.lower():
            self.state = SubscriptionState.TERMINATED
            self._cancel_refresh()
        elif "active" in subscription_state.lower():
            self.state = SubscriptionState.ACTIVE
        elif "pending" in subscription_state.lower():
            self.state = SubscriptionState.PENDING

        if self.on_notify:
            self.on_notify(body)

    @property
    def is_active(self) -> bool:
        return self.state in (SubscriptionState.ACTIVE, SubscriptionState.PENDING)

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    def _schedule_refresh(self) -> None:
        """Schedule auto-refresh at 80% of expires."""
        self._cancel_refresh()
        if self.expires <= 0:
            return
        self._task = asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        """Periodically refresh until terminated."""
        try:
            while self.state != SubscriptionState.TERMINATED:
                delay = self.expires * 0.8
                await asyncio.sleep(delay)
                if self.state == SubscriptionState.TERMINATED:
                    break
                await self.refresh()
        except asyncio.CancelledError:
            pass

    def _cancel_refresh(self) -> None:
        """Cancel pending refresh task."""
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
