"""Dialog state machine per RFC 3261 §12.

Manages dialog lifecycle: creation from INVITE, state transitions
(Early → Confirmed → Terminated), dialog matching, and route set management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sipx.exceptions import DialogError
from sipx.models import Request, Response


class DialogState(StrEnum):
    """Dialog lifecycle states per RFC 3261 §12."""

    EARLY = "Early"
    CONFIRMED = "Confirmed"
    TERMINATED = "Terminated"


# Valid state transitions per RFC 3261 §12.
_VALID_TRANSITIONS: dict[DialogState, frozenset[DialogState]] = {
    DialogState.EARLY: frozenset({DialogState.CONFIRMED, DialogState.TERMINATED}),
    DialogState.CONFIRMED: frozenset({DialogState.TERMINATED}),
    DialogState.TERMINATED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class DialogId:
    """Dialog identifier per RFC 3261 §12: Call-ID + local tag + remote tag."""

    call_id: str
    local_tag: str
    remote_tag: str


def _extract_tag(header_value: str, header_name: str) -> str | None:
    """Extract the tag parameter from a From/To header value."""
    for part in header_value.split(";")[1:]:
        name, sep, value = part.strip().partition("=")
        if name.lower() == "tag" and sep:
            return value.strip()
    return None


def _require_header(
    message: Request | Response, name: str
) -> str:
    """Get a required header value or raise DialogError."""
    value = message.headers.get(name)
    if value is None:
        raise DialogError(
            f"missing required header: {name}",
            rfc_ref="RFC 3261 §12",
        )
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _require_tag(header_value: str, header_name: str) -> str:
    """Extract tag from header or raise DialogError."""
    tag = _extract_tag(header_value, header_name)
    if not tag:
        raise DialogError(
            f"missing tag in {header_name} header",
            rfc_ref="RFC 3261 §12",
        )
    return tag


def _extract_route_set(message: Request | Response) -> list[str]:
    """Extract Record-Route URIs from a message for route set management.

    Per RFC 3261 §12.1.2, the UAC route set is the Record-Route values
    from the response, in reverse order.
    """
    rr = message.headers.get("Record-Route")
    if rr is None:
        return []
    if isinstance(rr, str):
        return [rr]
    return list(rr)


@dataclass(slots=True)
class Dialog:
    """SIP dialog state machine per RFC 3261 §12.

    Tracks dialog identity, state, sequence numbers, and route set.
    Raises DialogError on invalid state transitions.
    """

    dialog_id: DialogId
    local_uri: str
    remote_uri: str
    remote_target: str
    local_cseq: int
    remote_cseq: int | None = None
    route_set: list[str] = field(default_factory=list)
    _state: DialogState = DialogState.EARLY
    _secure: bool = False

    @property
    def state(self) -> str:
        """Current dialog state as a string."""
        return self._state.value

    @property
    def call_id(self) -> str:
        """Dialog Call-ID."""
        return self.dialog_id.call_id

    @property
    def local_tag(self) -> str:
        """Local tag (From tag for UAC, To tag for UAS)."""
        return self.dialog_id.local_tag

    @property
    def remote_tag(self) -> str:
        """Remote tag (To tag for UAC, From tag for UAS)."""
        return self.dialog_id.remote_tag

    @property
    def is_secure(self) -> bool:
        """Whether the dialog uses SIPS."""
        return self._secure

    @classmethod
    def from_invite(
        cls,
        request: Request,
        response: Response,
    ) -> Dialog:
        """Create a UAC dialog from an INVITE request and its response.

        Per RFC 3261 §12.1.2, a dialog is created when a UAC receives
        a 1xx or 2xx response to an INVITE that contains a To tag.

        Args:
            request: The INVITE request.
            response: The 1xx or 2xx response.

        Returns:
            A new Dialog in Early or Confirmed state.

        Raises:
            DialogError: If the request/response cannot create a dialog.
        """
        if request.method != "INVITE":
            raise DialogError(
                "dialog creation requires INVITE request",
                rfc_ref="RFC 3261 §12.1",
            )
        if not 100 <= response.status_code < 300:
            raise DialogError(
                f"response {response.status_code} cannot create a dialog",
                rfc_ref="RFC 3261 §12.1",
            )

        call_id = _require_header(request, "Call-ID")
        from_header = _require_header(request, "From")
        to_header = _require_header(response, "To")
        local_tag = _require_tag(from_header, "From")
        remote_tag = _require_tag(to_header, "To")

        # Route set: Record-Route from response in reverse order (§12.1.2).
        record_routes = _extract_route_set(response)
        route_set = list(reversed(record_routes))

        # Remote target from Contact header (§12.1.2).
        contact = _require_header(response, "Contact")

        state = (
            DialogState.CONFIRMED
            if response.status_code >= 200
            else DialogState.EARLY
        )

        # CSeq from request.
        cseq_value = _require_header(request, "CSeq")
        cseq_num = _parse_cseq_number(cseq_value)

        return cls(
            dialog_id=DialogId(
                call_id=call_id,
                local_tag=local_tag,
                remote_tag=remote_tag,
            ),
            local_uri=from_header,
            remote_uri=to_header,
            remote_target=contact,
            local_cseq=cseq_num,
            route_set=route_set,
            _state=state,
            _secure=request.uri.startswith("sips:"),
        )

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        local_tag: str,
    ) -> Dialog:
        """Create a UAS dialog from an incoming INVITE request.

        Per RFC 3261 §12.1.1, a UAS creates a dialog when it decides
        to accept an INVITE.

        Args:
            request: The incoming INVITE request.
            local_tag: The tag the UAS will place in the To header.

        Returns:
            A new Dialog in Early state.

        Raises:
            DialogError: If the request cannot create a dialog.
        """
        if request.method != "INVITE":
            raise DialogError(
                "dialog creation requires INVITE request",
                rfc_ref="RFC 3261 §12.1",
            )
        if not local_tag:
            raise DialogError(
                "local_tag is required for UAS dialog creation",
                rfc_ref="RFC 3261 §12.1.1",
            )

        call_id = _require_header(request, "Call-ID")
        from_header = _require_header(request, "From")
        to_header = _require_header(request, "To")
        remote_tag = _require_tag(from_header, "From")

        # Route set: Record-Route from request in order (§12.1.1).
        route_set = _extract_route_set(request)

        # Remote target from Contact header (§12.1.1).
        contact = _require_header(request, "Contact")

        # CSeq from request.
        cseq_value = _require_header(request, "CSeq")
        cseq_num = _parse_cseq_number(cseq_value)

        local_uri = _ensure_tag(to_header, local_tag)

        return cls(
            dialog_id=DialogId(
                call_id=call_id,
                local_tag=local_tag,
                remote_tag=remote_tag,
            ),
            local_uri=local_uri,
            remote_uri=from_header,
            remote_target=contact,
            local_cseq=0,
            remote_cseq=cseq_num,
            route_set=route_set,
            _state=DialogState.EARLY,
            _secure=request.uri.startswith("sips:"),
        )

    def update(self, response: Response) -> None:
        """Update dialog state from a response.

        Handles state transitions and target refresh per RFC 3261 §12.2.

        Args:
            response: A response within this dialog.

        Raises:
            DialogError: If the transition is invalid or dialog doesn't match.
        """
        self._assert_matches(response)

        status = response.status_code

        # Target refresh: update remote target from Contact (§12.2.2).
        contact = response.headers.get("Contact")
        if contact and status >= 200:
            self.remote_target = (
                contact[0] if isinstance(contact, list) else contact
            )

        # Route set refresh on 2xx (§12.2.2).
        if 200 <= status < 300:
            record_routes = _extract_route_set(response)
            if record_routes:
                self.route_set = list(reversed(record_routes))

        # State transitions.
        if 100 <= status < 200:
            # 1xx: stay in Early (or no-op if already Confirmed).
            if self._state == DialogState.EARLY:
                return  # Already Early, no transition needed.
            # Confirmed dialogs ignore further 1xx (forked dialogs).
            return

        if 200 <= status < 300:
            if self._state == DialogState.EARLY:
                self._transition_to(DialogState.CONFIRMED)
            return

        if status >= 300:
            self._transition_to(DialogState.TERMINATED)

    def terminate(self) -> None:
        """Terminate the dialog (e.g., on BYE)."""
        self._transition_to(DialogState.TERMINATED)

    def matches(
        self,
        call_id: str,
        local_tag: str,
        remote_tag: str,
    ) -> bool:
        """Check if a message matches this dialog per RFC 3261 §12.2.2.

        A request within a dialog matches if Call-ID, From tag, and To tag
        all match the dialog identifiers.
        """
        return (
            self.dialog_id.call_id == call_id
            and self.dialog_id.local_tag == local_tag
            and self.dialog_id.remote_tag == remote_tag
        )

    def next_cseq(self, method: str) -> int:
        """Increment and return the next local CSeq number.

        Per RFC 3261 §12.2.1.1, CSeq must increase by 1 for each
        new request within a dialog (except ACK which reuses INVITE CSeq).
        """
        if method == "ACK":
            return self.local_cseq
        self.local_cseq += 1
        return self.local_cseq

    def _transition_to(self, target: DialogState) -> None:
        """Perform a state transition with validation."""
        valid = _VALID_TRANSITIONS.get(self._state, frozenset())
        if target not in valid:
            raise DialogError(
                f"invalid dialog state transition: "
                f"{self._state.value} → {target.value}",
                rfc_ref="RFC 3261 §12",
            )
        self._state = target

    def _assert_matches(self, response: Response) -> None:
        """Verify a response belongs to this dialog."""
        call_id = _require_header(response, "Call-ID")
        if call_id != self.dialog_id.call_id:
            raise DialogError(
                f"Call-ID mismatch: expected {self.dialog_id.call_id}, "
                f"got {call_id}",
                rfc_ref="RFC 3261 §12.2.2",
            )


def _ensure_tag(header_value: str, tag: str) -> str:
    """Ensure a header value has a tag parameter."""
    if _extract_tag(header_value, "tag"):
        return header_value
    return f"{header_value};tag={tag}"


def _parse_cseq_number(value: str) -> int:
    """Parse the sequence number from a CSeq header value."""
    number, _, _method = value.partition(" ")
    try:
        return int(number)
    except ValueError as exc:
        raise DialogError(
            f"invalid CSeq header: {value!r}",
            rfc_ref="RFC 3261 §8.1.1.5",
        ) from exc
