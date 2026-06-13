"""SIP transaction state machines (sans-I/O).

Client and server INVITE/non-INVITE transactions that track state from
provisional through final responses, match responses to requests by Via
branch and CSeq, and build ACK/CANCEL for INVITE clients.

References:
    RFC 3261 §17 - Transactions
    RFC 3261 §17.1 - Client Transaction
    RFC 3261 §17.2 - Server Transaction
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sipx.sip.headers import HeaderMap
from sipx.sip.message import SipRequest, SipResponse


class SipTransactionError(ValueError):
    pass


class ClientTransactionState(StrEnum):
    TRYING = "trying"
    CALLING = "calling"
    PROCEEDING = "proceeding"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class ServerTransactionState(StrEnum):
    PROCEEDING = "proceeding"
    COMPLETED = "completed"
    CONFIRMED = "confirmed"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class TransactionEvent:
    state: ClientTransactionState | ServerTransactionState
    name: str
    status_code: int | None = None


class InviteClientTransaction:
    def __init__(self, request: SipRequest) -> None:
        if request.method != "INVITE":
            raise SipTransactionError("InviteClientTransaction requires INVITE")
        self.request = request
        self.branch = _branch_id(_required_header(request, "Via"))
        self.state = ClientTransactionState.CALLING
        self.responses: list[SipResponse] = []
        self.events: list[TransactionEvent] = [
            TransactionEvent(state=self.state, name="request_sent")
        ]

    @property
    def final_response(self) -> SipResponse | None:
        for response in reversed(self.responses):
            if response.status_code >= 200:
                return response
        return None

    def receive_response(self, response: SipResponse) -> ClientTransactionState:
        self.responses.append(response)
        if 100 <= response.status_code < 200:
            self.state = ClientTransactionState.PROCEEDING
            event_name = "provisional_response"
        elif 200 <= response.status_code < 300:
            self.state = ClientTransactionState.TERMINATED
            event_name = "success_response"
        elif 300 <= response.status_code < 700:
            self.state = ClientTransactionState.COMPLETED
            event_name = "failure_response"
        else:
            raise SipTransactionError(
                f"invalid SIP response code: {response.status_code}"
            )

        self.events.append(
            TransactionEvent(
                state=self.state,
                name=event_name,
                status_code=response.status_code,
            )
        )
        return self.state

    def create_ack(self) -> SipRequest:
        final = self.final_response
        if final is None:
            raise SipTransactionError("cannot create ACK before final response")
        ack = _related_request(self.request, "ACK", to_header=final.headers.get("To"))
        self.state = ClientTransactionState.TERMINATED
        self.events.append(TransactionEvent(state=self.state, name="ack_created"))
        return ack

    def create_cancel(self) -> SipRequest:
        if self.final_response is not None:
            raise SipTransactionError("cannot CANCEL after final response")
        cancel = _related_request(self.request, "CANCEL")
        self.events.append(TransactionEvent(state=self.state, name="cancel_created"))
        return cancel


class NonInviteClientTransaction:
    def __init__(self, request: SipRequest) -> None:
        if request.method == "INVITE":
            raise SipTransactionError("NonInviteClientTransaction rejects INVITE")
        self.request = request
        self.branch = _branch_id(_required_header(request, "Via"))
        self.state = ClientTransactionState.TRYING
        self.responses: list[SipResponse] = []
        self.events: list[TransactionEvent] = [
            TransactionEvent(state=self.state, name="request_sent")
        ]

    @property
    def final_response(self) -> SipResponse | None:
        for response in reversed(self.responses):
            if response.status_code >= 200:
                return response
        return None

    def receive_response(self, response: SipResponse) -> ClientTransactionState:
        self.responses.append(response)
        if 100 <= response.status_code < 200:
            self.state = ClientTransactionState.PROCEEDING
            event_name = "provisional_response"
        elif 200 <= response.status_code < 700:
            self.state = ClientTransactionState.COMPLETED
            event_name = "final_response"
        else:
            raise SipTransactionError(
                f"invalid SIP response code: {response.status_code}"
            )
        self.events.append(
            TransactionEvent(
                state=self.state,
                name=event_name,
                status_code=response.status_code,
            )
        )
        return self.state

    def terminate(self) -> None:
        self.state = ClientTransactionState.TERMINATED
        self.events.append(TransactionEvent(state=self.state, name="terminated"))


class InviteServerTransaction:
    def __init__(self, request: SipRequest) -> None:
        if request.method != "INVITE":
            raise SipTransactionError("InviteServerTransaction requires INVITE")
        self.request = request
        self.branch = _branch_id(_required_header(request, "Via"))
        self.request_cseq = _cseq_number(_required_header(request, "CSeq"))
        self.state = ServerTransactionState.PROCEEDING
        self.responses: list[SipResponse] = []
        self.events: list[TransactionEvent] = [
            TransactionEvent(state=self.state, name="request_received")
        ]

    @property
    def final_response(self) -> SipResponse | None:
        for response in reversed(self.responses):
            if response.status_code >= 200:
                return response
        return None

    def send_response(self, response: SipResponse) -> ServerTransactionState:
        _validate_response_matches_request(
            response,
            branch=self.branch,
            cseq_number=self.request_cseq,
            cseq_method="INVITE",
        )
        self.responses.append(response)
        if 100 <= response.status_code < 200:
            self.state = ServerTransactionState.PROCEEDING
            event_name = "provisional_response"
        elif 200 <= response.status_code < 300:
            self.state = ServerTransactionState.TERMINATED
            event_name = "success_response"
        elif 300 <= response.status_code < 700:
            self.state = ServerTransactionState.COMPLETED
            event_name = "failure_response"
        else:
            raise SipTransactionError(
                f"invalid SIP response code: {response.status_code}"
            )
        self.events.append(
            TransactionEvent(
                state=self.state,
                name=event_name,
                status_code=response.status_code,
            )
        )
        return self.state

    def receive_ack(self, request: SipRequest) -> ServerTransactionState:
        if request.method != "ACK":
            raise SipTransactionError("INVITE server transaction requires ACK")
        if self.state is not ServerTransactionState.COMPLETED:
            raise SipTransactionError(
                "ACK is only transaction-scoped after failure final"
            )
        if _branch_id(_required_header(request, "Via")) != self.branch:
            raise SipTransactionError("ACK branch does not match transaction")
        cseq_number, cseq_method = _cseq_parts(_required_header(request, "CSeq"))
        if cseq_number != self.request_cseq or cseq_method != "ACK":
            raise SipTransactionError("ACK CSeq does not match transaction")
        self.state = ServerTransactionState.CONFIRMED
        self.events.append(TransactionEvent(state=self.state, name="ack_received"))
        return self.state

    def terminate(self) -> None:
        self.state = ServerTransactionState.TERMINATED
        self.events.append(TransactionEvent(state=self.state, name="terminated"))


def _related_request(
    request: SipRequest,
    method: str,
    *,
    to_header: str | None = None,
) -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", _required_header(request, "Via"))
    headers.add("From", _required_header(request, "From"))
    headers.add("To", to_header or _required_header(request, "To"))
    headers.add("Call-ID", _required_header(request, "Call-ID"))
    headers.add("CSeq", f"{_cseq_number(_required_header(request, 'CSeq'))} {method}")
    headers.add("Max-Forwards", request.headers.get("Max-Forwards", "70") or "70")
    return SipRequest(method=method, uri=request.uri, headers=headers)


def _required_header(message: SipRequest | SipResponse, name: str) -> str:
    value = message.headers.get(name)
    if value is None:
        raise SipTransactionError(f"missing required SIP header: {name}")
    return value


def _branch_id(via: str) -> str:
    for part in via.split(";")[1:]:
        name, separator, value = part.strip().partition("=")
        if name.lower() == "branch" and separator:
            return value
    raise SipTransactionError("Via header missing branch parameter")


def _cseq_number(value: str) -> int:
    number, _method = _cseq_parts(value)
    return number


def _cseq_parts(value: str) -> tuple[int, str]:
    number, _, method = value.partition(" ")
    try:
        parsed = int(number)
    except ValueError as exc:
        raise SipTransactionError(f"invalid CSeq header: {value!r}") from exc
    return parsed, method.strip().upper()


def _validate_response_matches_request(
    response: SipResponse,
    *,
    branch: str,
    cseq_number: int,
    cseq_method: str,
) -> None:
    if _branch_id(_required_header(response, "Via")) != branch:
        raise SipTransactionError("response branch does not match transaction")
    response_cseq_number, response_cseq_method = _cseq_parts(
        _required_header(response, "CSeq")
    )
    if response_cseq_number != cseq_number or response_cseq_method != cseq_method:
        raise SipTransactionError("response CSeq does not match transaction")
