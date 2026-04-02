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
from typing import TYPE_CHECKING, Callable, Optional, Protocol

from .._utils import logger

_log = logger.getChild("session.sub")

if TYPE_CHECKING:
    from ..client import AsyncSIPClient, SIPClient
    from ..models._message import Response


class SubscriptionState(Enum):
    """Subscription states per RFC 6665."""

    INIT = auto()
    PENDING = auto()
    ACTIVE = auto()
    TERMINATED = auto()


class _SubscriptionLike(Protocol):
    """Structural type shared by Subscription and AsyncSubscription."""

    state: SubscriptionState

    def _cancel_refresh(self) -> None: ...


# ---------------------------------------------------------------------------
# Shared pure helpers (used by both Subscription and AsyncSubscription)
# ---------------------------------------------------------------------------

#: Fraction of ``expires`` at which auto-refresh is scheduled (80%).
SUBSCRIPTION_REFRESH_MARGIN: float = 0.8


def _apply_notify_state(
    sub: _SubscriptionLike,
    subscription_state: str,
) -> None:
    """Transition *sub*.state based on the Subscription-State header value.

    Mutates ``sub.state`` and cancels the refresh timer when terminated.
    Works for both :class:`Subscription` and :class:`AsyncSubscription`.
    """
    if "terminated" in subscription_state.lower():
        sub.state = SubscriptionState.TERMINATED
        _log.info("Subscription terminated by NOTIFY")
        sub._cancel_refresh()
    elif "active" in subscription_state.lower():
        sub.state = SubscriptionState.ACTIVE
    elif "pending" in subscription_state.lower():
        sub.state = SubscriptionState.PENDING


def _update_subscription_from_response(
    sub: _SubscriptionLike, r: Response | None
) -> bool:
    """Update *sub*.state from a SUBSCRIBE response status code.

    Returns ``True`` when a refresh should be scheduled (200/202),
    ``False`` when the subscription terminated.
    """
    if r and r.status_code in (200, 202):
        sub.state = (
            SubscriptionState.ACTIVE
            if r.status_code == 200
            else SubscriptionState.PENDING
        )
        return True
    sub.state = SubscriptionState.TERMINATED
    _log.warning("Subscription failed, status=%s", r.status_code if r else "None")
    return False


@dataclass
class Subscription:
    """Manages a SIP event subscription.

    Handles SUBSCRIBE requests, auto-refresh before expiry,
    and tracks NOTIFY state.
    """

    client: SIPClient
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

        _log.info(
            "Subscribing to %s event=%s expires=%d", self.uri, self.event, self.expires
        )
        r = self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=self.expires,
        )

        if _update_subscription_from_response(self, r):
            self._schedule_refresh()

        return r

    def unsubscribe(self) -> Response | None:
        """Send SUBSCRIBE with Expires: 0 to unsubscribe."""
        _log.info("Unsubscribing from %s event=%s", self.uri, self.event)
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
        _log.debug(
            "NOTIFY received, state=%s body_len=%d", subscription_state, len(body)
        )
        self.last_notify_body = body
        _apply_notify_state(self, subscription_state)

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
        delay = self.expires * SUBSCRIPTION_REFRESH_MARGIN
        _log.debug("Scheduling refresh in %.0fs", delay)
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

    client: AsyncSIPClient
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

        _log.info(
            "Async subscribing to %s event=%s expires=%d",
            self.uri,
            self.event,
            self.expires,
        )
        r = await self.client.subscribe(
            uri=self.uri,
            event=self.event,
            expires=self.expires,
        )

        if _update_subscription_from_response(self, r):
            self._schedule_refresh()

        return r

    async def unsubscribe(self) -> Response | None:
        """Send SUBSCRIBE with Expires: 0 to unsubscribe."""
        _log.info("Async unsubscribing from %s event=%s", self.uri, self.event)
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
        _log.debug(
            "NOTIFY received, state=%s body_len=%d", subscription_state, len(body)
        )
        self.last_notify_body = body
        _apply_notify_state(self, subscription_state)

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
                delay = self.expires * SUBSCRIPTION_REFRESH_MARGIN
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


@dataclass
class ReferSubscription:
    """Tracks the implicit subscription created by a REFER (RFC 3515).

    When a REFER is accepted (200/202), the transferee sends NOTIFY
    messages with ``Event: refer`` and a ``message/sipfrag`` body that
    contains the status of the transfer attempt (e.g. ``SIP/2.0 100
    Trying``, ``SIP/2.0 200 OK``).

    This class accumulates sipfrag updates and signals when the transfer
    has reached a final outcome.

    Example::

        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        sub.update("SIP/2.0 100 Trying\\r\\n")   # provisional — not done
        sub.update("SIP/2.0 200 OK\\r\\n")        # final — transfer succeeded
        assert sub.is_complete
        assert sub.final_status == 200
    """

    refer_to: str
    state: SubscriptionState = field(default=SubscriptionState.ACTIVE)
    sipfrag_history: list[str] = field(default_factory=list)
    final_status: int | None = None

    def update(self, sipfrag: str, subscription_state: str = "") -> bool:
        """Process a sipfrag body from a NOTIFY.

        Args:
            sipfrag: Body of the NOTIFY (e.g. ``SIP/2.0 200 OK\\r\\n``).
            subscription_state: Value of the Subscription-State header.

        Returns:
            True if the transfer is complete (final sipfrag or terminated).
        """
        self.sipfrag_history.append(sipfrag)
        _log.debug("ReferSubscription sipfrag: %r", sipfrag[:80])

        if "terminated" in subscription_state.lower():
            self.state = SubscriptionState.TERMINATED
            _log.info("REFER subscription terminated")
            return True

        # Parse status code from "SIP/2.0 <code> <reason>"
        parts = sipfrag.split()
        if len(parts) >= 2:
            try:
                code = int(parts[1])
                if code >= 200:
                    self.final_status = code
                    self.state = SubscriptionState.TERMINATED
                    _log.info("REFER complete: sipfrag status %d", code)
                    return True
            except ValueError:
                pass

        return False

    @property
    def is_complete(self) -> bool:
        """True when the transfer has reached a final outcome."""
        return self.state == SubscriptionState.TERMINATED

    @property
    def succeeded(self) -> bool:
        """True if transfer completed with a 2xx final status."""
        return self.final_status is not None and 200 <= self.final_status < 300

    def __repr__(self) -> str:
        return (
            f"<ReferSubscription(refer_to={self.refer_to!r}, "
            f"state={self.state.name}, final_status={self.final_status})>"
        )
