"""RFC 3265/6665 SIP-Specific Event Notification (SUBSCRIBE/NOTIFY).

This module implements the event notification framework for SIP.
SubscriptionDialog manages subscription lifecycle: creation from
SUBSCRIBE, state transitions (active, pending, terminated), and
NOTIFY handling.

References:
    RFC 6665 - An Event Notification Framework for SIP
               (obsoletes RFC 3265)
    RFC 3261 §12 - Dialogs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sipx.exceptions import ProtocolError
from sipx.models import Request, Response
from sipx.protocol.dialog import Dialog, DialogId, _require_header
from sipx.protocol.transaction import ClientTransaction


class SubscriptionState(StrEnum):
    """Subscription states per RFC 6665 §4.1.3."""

    ACTIVE = "active"
    PENDING = "pending"
    TERMINATED = "terminated"


# Valid subscription state transitions per RFC 6665 §4.1.3.
_VALID_SUBSCRIPTION_TRANSITIONS: dict[
    SubscriptionState, frozenset[SubscriptionState]
] = {
    SubscriptionState.PENDING: frozenset(
        {SubscriptionState.ACTIVE, SubscriptionState.TERMINATED}
    ),
    SubscriptionState.ACTIVE: frozenset(
        {SubscriptionState.TERMINATED, SubscriptionState.PENDING}
    ),
    SubscriptionState.TERMINATED: frozenset(),
}


def _parse_subscription_state(value: str) -> SubscriptionState:
    """Parse a Subscription-State header value into a SubscriptionState.

    The header may contain parameters after a semicolon (e.g.
    ``active;expires=3600``). Only the state token is used.

    Args:
        value: Raw Subscription-State header value.

    Returns:
        The parsed SubscriptionState.

    Raises:
        ProtocolError: If the state token is not recognized.
    """
    token = value.split(";")[0].strip().lower()
    try:
        return SubscriptionState(token)
    except ValueError:
        raise ProtocolError(
            f"invalid Subscription-State: {value!r}",
            rfc_ref="RFC 6665 §4.1.3",
        )


def _parse_expires(value: str | list[str] | None) -> int | None:
    """Parse an Expires header value into seconds, or None."""
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else ""
    try:
        return int(value)
    except ValueError:
        return None


def _extract_tag_from_header(header_value: str) -> str | None:
    """Extract the tag parameter from a From/To header value."""
    for part in header_value.split(";")[1:]:
        name, sep, value = part.strip().partition("=")
        if name.lower() == "tag" and sep:
            return value.strip()
    return None


def _parse_cseq(value: str | list[str]) -> int:
    """Parse the sequence number from a CSeq header value."""
    if isinstance(value, list):
        value = value[0] if value else "1"
    number, _, _method = value.partition(" ")
    try:
        return int(number)
    except ValueError:
        return 1


@dataclass(slots=True)
class SubscriptionDialog(Dialog):
    """SIP subscription dialog per RFC 6665.

    Extends Dialog with subscription-specific state: event package,
    subscription state, and expiry tracking. Integrates with
    ClientTransaction for SUBSCRIBE request/response handling.

    Attributes:
        event: The event package name (e.g. ``presence``).
        expires: Subscription duration in seconds.
    """

    event: str = ""
    expires: int = 3600
    _subscription_state: SubscriptionState = SubscriptionState.PENDING
    _transaction: ClientTransaction | None = field(default=None, repr=False)
    _notify_count: int = 0

    @property
    def state(self) -> str:
        """Current subscription state as a string."""
        return self._subscription_state.value

    @property
    def dialog_state(self) -> str:
        """Underlying SIP dialog state (Early/Confirmed/Terminated)."""
        return self._state.value

    @property
    def transaction(self) -> ClientTransaction | None:
        """The client transaction associated with the initial SUBSCRIBE."""
        return self._transaction

    @property
    def notify_count(self) -> int:
        """Number of NOTIFY requests processed."""
        return self._notify_count

    @property
    def is_terminated(self) -> bool:
        """Whether the subscription has been terminated."""
        return self._subscription_state == SubscriptionState.TERMINATED

    @classmethod
    def from_subscribe(
        cls,
        request: Request,
        response: Response,
        *,
        transaction: ClientTransaction | None = None,
    ) -> SubscriptionDialog:
        """Create a SubscriptionDialog from a SUBSCRIBE request/response pair.

        Per RFC 6665 §4.1.1, a subscription is created when a SUBSCRIBE
        request receives a 2xx response. A 202 Accepted response creates
        a pending subscription; a 200 OK creates an active subscription.

        Args:
            request: The SUBSCRIBE request.
            response: The 2xx response to the SUBSCRIBE.
            transaction: Optional client transaction for the SUBSCRIBE.

        Returns:
            A new SubscriptionDialog.

        Raises:
            ProtocolError: If the request is not SUBSCRIBE, the response
                is not 2xx, or required headers are missing.
        """
        if request.method != "SUBSCRIBE":
            raise ProtocolError(
                "subscription creation requires SUBSCRIBE request",
                rfc_ref="RFC 6665 §4.1.1",
            )
        if not 200 <= response.status_code < 300:
            raise ProtocolError(
                f"response {response.status_code} cannot create a subscription",
                rfc_ref="RFC 6665 §4.1.1",
            )

        # Extract Event header.
        event_raw = request.headers.get("Event")
        if event_raw is None:
            raise ProtocolError(
                "SUBSCRIBE request missing Event header",
                rfc_ref="RFC 6665 §4.1.1",
            )
        event = _require_header(request, "Event")
        if isinstance(event, list):
            event = event[0] if event else ""
        # Strip event parameters (e.g. "presence;param=value" → "presence").
        event = event.split(";")[0].strip()
        if not event:
            raise ProtocolError(
                "SUBSCRIBE request missing Event header",
                rfc_ref="RFC 6665 §4.1.1",
            )

        # Extract Expires.
        expires_raw = request.headers.get("Expires")
        expires = _parse_expires(expires_raw) or 3600

        # Determine initial subscription state from response code.
        if response.status_code == 202:
            sub_state = SubscriptionState.PENDING
        else:
            sub_state = SubscriptionState.ACTIVE

        # Build dialog identity from request/response headers.
        call_id = _require_header(request, "Call-ID")
        from_header = _require_header(request, "From")
        to_header = _require_header(response, "To")

        local_tag = _extract_tag_from_header(from_header)
        remote_tag = _extract_tag_from_header(to_header)

        # Contact for remote target.
        contact = response.headers.get("Contact") or request.uri
        if isinstance(contact, list):
            contact = contact[0] if contact else request.uri

        # CSeq from request.
        cseq_value = request.headers.get("CSeq", "1 SUBSCRIBE")
        cseq_num = _parse_cseq(cseq_value)

        dialog_id = DialogId(
            call_id=call_id,
            local_tag=local_tag or "",
            remote_tag=remote_tag or "",
        )

        return cls(
            dialog_id=dialog_id,
            local_uri=from_header,
            remote_uri=to_header,
            remote_target=contact,
            local_cseq=cseq_num,
            event=event,
            expires=expires,
            _subscription_state=sub_state,
            _transaction=transaction,
            _secure=request.uri.startswith("sips:"),
        )

    def update_from_notify(self, request: Request) -> SubscriptionState:
        """Update subscription state from an incoming NOTIFY request.

        Per RFC 6665 §4.1.3, the Subscription-State header in a NOTIFY
        determines the subscription state. If the header is absent, the
        subscription remains in its current state.

        Args:
            request: The incoming NOTIFY request.

        Returns:
            The new subscription state.

        Raises:
            ProtocolError: If the request is not NOTIFY, or the
                Subscription-State header is invalid.
        """
        if request.method != "NOTIFY":
            raise ProtocolError(
                "update_from_notify requires NOTIFY request",
                rfc_ref="RFC 6665 §4.1.3",
            )

        state_header = request.headers.get("Subscription-State")
        if state_header is not None:
            if isinstance(state_header, list):
                state_header = state_header[0] if state_header else ""
            new_state = _parse_subscription_state(state_header)
            self._validate_transition(new_state)
            self._subscription_state = new_state

        self._notify_count += 1
        return self._subscription_state

    def update_from_subscribe_response(self, response: Response) -> None:
        """Update subscription from a SUBSCRIBE response.

        Handles refresh responses (2xx to a re-SUBSCRIBE) and
        termination responses (3xx-6xx).

        Args:
            response: A response to a SUBSCRIBE request.

        Raises:
            ProtocolError: If the response indicates a protocol error.
        """
        status = response.status_code

        if 200 <= status < 300:
            # Refresh accepted: update expires if present.
            expires_raw = response.headers.get("Expires")
            expires = _parse_expires(expires_raw)
            if expires is not None:
                self.expires = expires
        elif status >= 300:
            # Subscription terminated by error response.
            self._subscription_state = SubscriptionState.TERMINATED

    def terminate(self, reason: str = "timeout") -> None:
        """Terminate the subscription.

        Args:
            reason: Termination reason for logging/tracking.
        """
        self._subscription_state = SubscriptionState.TERMINATED

    def create_subscribe_request(
        self,
        expires: int | None = None,
    ) -> Request:
        """Build a SUBSCRIBE request to refresh or terminate the subscription.

        Args:
            expires: New expiry in seconds. Defaults to current expires.
                Set to 0 to unsubscribe.

        Returns:
            A new SUBSCRIBE Request within this dialog.
        """
        if expires is None:
            expires = self.expires

        cseq = self.next_cseq("SUBSCRIBE")
        headers: dict[str, str | list[str]] = {
            "Call-ID": self.dialog_id.call_id,
            "From": self.local_uri,
            "To": self.remote_uri,
            "CSeq": f"{cseq} SUBSCRIBE",
            "Event": self.event,
            "Expires": str(expires),
        }

        return Request(
            method="SUBSCRIBE",
            uri=self.remote_target,
            headers=headers,
            body=None,
        )

    def create_notify_response(
        self,
        request: Request,
        status_code: int = 200,
        reason: str = "OK",
    ) -> Response:
        """Build a response to an incoming NOTIFY request.

        Args:
            request: The NOTIFY request being responded to.
            status_code: Response status code.
            reason: Response reason phrase.

        Returns:
            A Response to the NOTIFY.
        """
        return Response(
            status_code=status_code,
            reason=reason,
            headers={},
            body=None,
            request=request,
        )

    def _validate_transition(self, target: SubscriptionState) -> None:
        """Validate a subscription state transition.

        Same-state transitions (e.g. active → active) are allowed as
        refresh notifications per RFC 6665 §4.1.3.
        """
        if target == self._subscription_state:
            return  # Same-state refresh is always valid.
        valid = _VALID_SUBSCRIPTION_TRANSITIONS.get(
            self._subscription_state, frozenset()
        )
        if target not in valid:
            raise ProtocolError(
                f"invalid subscription state transition: "
                f"{self._subscription_state.value} → {target.value}",
                rfc_ref="RFC 6665 §4.1.3",
            )
