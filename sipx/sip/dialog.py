"""SIP dialog identity and state (sans-I/O).

Models a dialog keyed by Call-ID plus local and remote tags, created from a
UAC INVITE response or a UAS INVITE request, and tracks the local CSeq and
early/confirmed/terminated state.

References:
    RFC 3261 §12 - Dialogs
    RFC 3261 §12.1.1 - UAS behavior (dialog creation)
    RFC 3261 §12.1.2 - UAC behavior (dialog creation)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sipx.sip.message import SipRequest, SipResponse


class SipDialogError(ValueError):
    pass


class DialogState(StrEnum):
    EARLY = "early"
    CONFIRMED = "confirmed"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class DialogId:
    call_id: str
    local_tag: str
    remote_tag: str


@dataclass(slots=True)
class Dialog:
    dialog_id: DialogId
    local_uri: str
    remote_uri: str
    local_sequence: int
    remote_sequence: int | None = None
    route_set: tuple[str, ...] = ()
    state: DialogState = DialogState.EARLY

    @classmethod
    def from_uac_invite_response(
        cls,
        request: SipRequest,
        response: SipResponse,
    ) -> Dialog:
        if request.method != "INVITE":
            raise SipDialogError("dialog creation requires INVITE request")
        if not 100 <= response.status_code < 300:
            raise SipDialogError(
                "only provisional or successful INVITE responses create dialogs"
            )

        call_id = _required_header(request, "Call-ID")
        from_header = _required_header(request, "From")
        to_header = _required_header(response, "To")
        local_tag = _required_tag(from_header, "From")
        remote_tag = _required_tag(to_header, "To")

        return cls(
            dialog_id=DialogId(
                call_id=call_id,
                local_tag=local_tag,
                remote_tag=remote_tag,
            ),
            local_uri=from_header,
            remote_uri=to_header,
            local_sequence=_cseq_number(_required_header(request, "CSeq")),
            state=DialogState.CONFIRMED
            if response.status_code >= 200
            else DialogState.EARLY,
        )

    @classmethod
    def from_uas_invite_request(
        cls,
        request: SipRequest,
        *,
        local_tag: str,
    ) -> Dialog:
        if request.method != "INVITE":
            raise SipDialogError("dialog creation requires INVITE request")
        if not local_tag:
            raise SipDialogError("local tag is required")

        call_id = _required_header(request, "Call-ID")
        from_header = _required_header(request, "From")
        to_header = _required_header(request, "To")
        remote_tag = _required_tag(from_header, "From")
        local_uri = _with_tag(to_header, local_tag)

        return cls(
            dialog_id=DialogId(
                call_id=call_id,
                local_tag=header_tag(local_uri) or local_tag,
                remote_tag=remote_tag,
            ),
            local_uri=local_uri,
            remote_uri=from_header,
            local_sequence=0,
            remote_sequence=_cseq_number(_required_header(request, "CSeq")),
            state=DialogState.EARLY,
        )

    def confirm(self) -> None:
        if self.state is not DialogState.TERMINATED:
            self.state = DialogState.CONFIRMED

    def terminate(self) -> None:
        self.state = DialogState.TERMINATED

    def next_local_cseq(self, method: str) -> str:
        self.local_sequence += 1
        return f"{self.local_sequence} {method}"


def header_tag(value: str) -> str | None:
    for part in value.split(";")[1:]:
        name, separator, item = part.strip().partition("=")
        if name.lower() == "tag" and separator:
            return item.strip()
    return None


def _required_header(message: SipRequest | SipResponse, name: str) -> str:
    value = message.headers.get(name)
    if value is None:
        raise SipDialogError(f"missing required SIP header: {name}")
    return value


def _required_tag(header_value: str, header_name: str) -> str:
    tag = header_tag(header_value)
    if not tag:
        raise SipDialogError(f"missing tag parameter in {header_name} header")
    return tag


def _with_tag(header_value: str, tag: str) -> str:
    if header_tag(header_value):
        return header_value
    return f"{header_value};tag={tag}"


def _cseq_number(value: str) -> int:
    number, _, _method = value.partition(" ")
    try:
        return int(number)
    except ValueError as exc:
        raise SipDialogError(f"invalid CSeq header: {value!r}") from exc
