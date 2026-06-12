# RFC 3261: SIP transactions/dialogs and INVITE provisional/final response flow.
# RFC 3264 + RFC 8866: SDP offer/answer carried in INVITE/2xx or optional 183.
# RFC 3550/3551 + RFC 4733: RTP/AVP media and telephone-event negotiated by SDP.

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Protocol, Self

from sipx.sip.auth import (
    build_digest_authorization,
    digest_challenge_for_response,
    parse_digest_challenge,
)
from sipx.sip.capabilities import SipCapabilities
from sipx.sip.dialog import Dialog
from sipx.sip.identifiers import new_branch, new_call_id, new_tag
from sipx.sip.message import (
    DEFAULT_MAX_MESSAGE_SIZE,
    SipMessage,
    SipRequest,
    SipResponse,
)
from sipx.sip.requests import (
    create_ack_request,
    create_bye_request,
    create_info_request,
    create_invite_request,
    create_request,
    create_response_for_request,
)
from sipx.sip.register import RegisterClientFlow, RegisterClientState
from sipx.sip.transaction import (
    InviteClientTransaction,
    InviteServerTransaction,
    NonInviteClientTransaction,
)
from sipx.sip.transport import (
    SipUdpEndpoint,
    SipUdpError,
    SipWireEvent,
    UdpAddress,
    sip_wire_event_name,
)
from sipx.sip.uri import SipUri
from sipx.sdp import (
    SdpNegotiationError,
    SessionDescription,
    create_audio_answer,
    parse_sdp,
)


class SipCallError(RuntimeError):
    pass


class SipRegisterError(RuntimeError):
    pass


class SipCallState(StrEnum):
    EARLY = "early"
    CONFIRMED = "confirmed"
    TERMINATED = "terminated"
    FAILED = "failed"

    @property
    def is_established(self) -> bool:
        return self is SipCallState.CONFIRMED


@dataclass(frozen=True, slots=True)
class SipRetransmissionPolicy:
    initial_interval: float = 0.5
    max_interval: float = 4.0
    max_attempts: int = 6

    def __post_init__(self) -> None:
        if self.initial_interval <= 0:
            raise ValueError("initial_interval must be positive")
        if self.max_interval <= 0:
            raise ValueError("max_interval must be positive")
        if self.max_attempts < 0:
            raise ValueError("max_attempts must be non-negative")

    def intervals(self) -> tuple[float, ...]:
        interval = self.initial_interval
        values: list[float] = []
        for _ in range(self.max_attempts):
            values.append(interval)
            interval = min(interval * 2, self.max_interval)
        return tuple(values)


@dataclass(frozen=True, slots=True)
class SipProvisionalResponse:
    """Configured INVITE provisional response.

    SIP RFC 3261 allows zero or more `1xx` responses before one final response.
    `100 Trying` is transaction progress only; it does not create an early dialog
    and this runtime sends it without To tag, Contact, or SDP body. Other `1xx`
    responses use the local To tag and may carry explicit body bytes. A `183`
    can request the negotiated SDP answer body via `include_sdp=True`.
    """

    status_code: int
    reason: str
    body: bytes = b""
    content_type: str | None = None
    include_sdp: bool = False

    def __post_init__(self) -> None:
        if not 100 <= self.status_code < 200:
            raise ValueError("provisional status_code must be between 100 and 199")
        if not self.reason:
            raise ValueError("provisional reason must not be empty")
        if self.status_code == 100 and (
            self.body or self.content_type is not None or self.include_sdp
        ):
            raise ValueError("100 Trying must not include body, content type, or SDP")
        if self.body and self.content_type is None:
            raise ValueError("provisional body requires content_type")
        if self.include_sdp and self.body:
            raise ValueError("include_sdp cannot be combined with explicit body")
        if self.include_sdp and self.content_type not in {None, "application/sdp"}:
            raise ValueError("include_sdp requires application/sdp content type")

    @classmethod
    def trying(cls) -> SipProvisionalResponse:
        return cls(status_code=100, reason="Trying")

    @classmethod
    def ringing(cls) -> SipProvisionalResponse:
        return cls(status_code=180, reason="Ringing")

    @classmethod
    def session_progress(cls, *, include_sdp: bool = False) -> SipProvisionalResponse:
        return cls(
            status_code=183,
            reason="Session Progress",
            content_type="application/sdp" if include_sdp else None,
            include_sdp=include_sdp,
        )


EventHooks = dict[str, list[Callable[..., None]]]
LAB_ONLY_EVENTS = frozenset({"sdp", "retransmission"})


@dataclass(slots=True)
class SipCall:
    call_id: str
    dialog: Dialog
    remote: UdpAddress
    request_uri: SipUri
    state: SipCallState = SipCallState.CONFIRMED
    local_sdp: SessionDescription | None = None
    remote_sdp: SessionDescription | None = None

    @property
    def is_established(self) -> bool:
        return self.state is SipCallState.CONFIRMED

    def summary(self, *, started: float | None = None):
        from sipx.summary import call_summary

        return call_summary(self, started=started)


@dataclass(slots=True)
class SipInviteAttempt:
    call_id: str
    request: SipRequest
    remote: UdpAddress
    transaction: InviteClientTransaction


@dataclass(slots=True)
class SipIncomingInvite:
    call_id: str
    request: SipRequest
    remote: UdpAddress
    transaction: InviteServerTransaction


class _EventRecorder(Protocol):
    def record(
        self,
        category: str,
        name: str,
        *,
        actor_id: str | None = None,
        call_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> object: ...


class SipWireRuntime(ABC):
    """ABC for SIP wire send/receive runtimes."""

    @abstractmethod
    async def start(self) -> SipWireRuntime:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_request(
        self,
        request: SipRequest,
        remote: UdpAddress,
    ) -> SipWireEvent:
        raise NotImplementedError

    @abstractmethod
    async def send_response(
        self,
        response: SipResponse,
        remote: UdpAddress,
    ) -> SipWireEvent:
        raise NotImplementedError

    @abstractmethod
    async def receive_event(self, *, timeout: float | None = None) -> SipWireEvent:
        raise NotImplementedError


class SipUacRuntime(SipWireRuntime):
    """ABC for SIP user-agent client behavior."""

    @abstractmethod
    async def initiate_call(
        self,
        *,
        remote: UdpAddress,
        target: SipUri,
        caller: SipUri,
        contact: SipUri,
        call_id: str,
        branch: str,
        from_tag: str,
        ack_branch: str,
        timeout: float = 1.0,
        body: bytes = b"",
        content_type: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth_branch: str | None = None,
        cnonce: str = "sipx",
    ) -> SipCall:
        raise NotImplementedError

    @abstractmethod
    async def start_invite(
        self,
        *,
        remote: UdpAddress,
        target: SipUri,
        caller: SipUri,
        contact: SipUri,
        call_id: str,
        branch: str,
        from_tag: str,
        body: bytes = b"",
        content_type: str | None = None,
    ) -> SipInviteAttempt:
        raise NotImplementedError

    @abstractmethod
    async def cancel_invite(
        self,
        attempt: SipInviteAttempt,
        *,
        timeout: float = 1.0,
    ) -> SipResponse:
        raise NotImplementedError


class SipUasRuntime(SipWireRuntime):
    """ABC for SIP user-agent server behavior."""

    @abstractmethod
    async def receive_invite(self, *, timeout: float = 1.0) -> SipIncomingInvite:
        raise NotImplementedError

    @abstractmethod
    async def accept_call(
        self,
        *,
        local_tag: str,
        contact: SipUri | None = None,
        timeout: float = 1.0,
        provisionals: Sequence[SipProvisionalResponse] | None = None,
        final_body: bytes = b"",
        final_content_type: str | None = None,
        media_port: int | None = None,
        media_connection_address: str | None = None,
        supported_codecs: tuple[str, ...] = ("PCMU", "PCMA"),
        telephone_event: bool = True,
    ) -> SipCall:
        raise NotImplementedError

    @abstractmethod
    async def answer_cancel(
        self,
        invite: SipIncomingInvite,
        *,
        local_tag: str,
        timeout: float = 1.0,
    ) -> SipResponse:
        raise NotImplementedError

    @abstractmethod
    async def answer_bye(
        self,
        call: SipCall,
        *,
        timeout: float = 1.0,
    ) -> SipResponse:
        raise NotImplementedError


@dataclass(slots=True)
class _RetransmissionHandle:
    stop: asyncio.Event
    task: asyncio.Task[None]


class SipUserAgent(SipUacRuntime, SipUasRuntime):
    def __init__(
        self,
        *,
        local_host: str = "127.0.0.1",
        local_port: int = 0,
        mode: str = "strict",
        timeline: _EventRecorder | None = None,
        actor_id: str | None = None,
        max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
        retransmission_policy: SipRetransmissionPolicy | None = None,
        event_hooks: EventHooks | None = None,
        compact_headers: bool = False,
    ) -> None:
        if mode not in {"strict", "lab"}:
            raise ValueError("mode must be strict or lab")
        if mode != "lab" and event_hooks is not None:
            for event_name in event_hooks:
                if event_name in LAB_ONLY_EVENTS:
                    raise ValueError(f"event_hooks['{event_name}'] requires lab mode")
        self.mode = mode
        self.timeline = timeline
        self.actor_id = actor_id
        self.retransmission_policy = retransmission_policy or SipRetransmissionPolicy()
        self.endpoint = SipUdpEndpoint(
            local_host=local_host,
            local_port=local_port,
            max_message_size=max_message_size,
            compact_headers=compact_headers,
        )
        self.event_hooks: EventHooks = dict(event_hooks) if event_hooks else {}

    @property
    def local_address(self) -> UdpAddress:
        return self.endpoint.local_address

    async def start(self) -> Self:
        await self.endpoint.start()
        self._record(
            "transport_started",
            data={
                "local_host": self.local_address[0],
                "local_port": self.local_address[1],
                "mode": self.mode,
            },
        )
        return self

    async def stop(self) -> None:
        local_address = self.local_address if self.endpoint.is_started else None
        await self.endpoint.close()
        self._record(
            "transport_stopped",
            data={
                "local_host": local_address[0] if local_address else None,
                "local_port": local_address[1] if local_address else None,
                "mode": self.mode,
            },
        )

    async def __aenter__(self) -> Self:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        await self.stop()

    async def send_request(
        self, request: SipRequest, remote: UdpAddress
    ) -> SipWireEvent:
        event = self._send_message(request, remote)
        self._emit_wire_event(event)
        self._record_event(event)
        return event

    async def send_response(
        self,
        response: SipResponse,
        remote: UdpAddress,
    ) -> SipWireEvent:
        event = self._send_message(response, remote)
        self._emit_wire_event(event)
        self._record_event(event)
        return event

    async def send_raw(self, raw: bytes, remote: UdpAddress) -> SipWireEvent:
        if self.mode != "lab":
            raise SipUdpError("send_raw is only allowed in lab mode")
        event = self.endpoint.send_raw(raw, remote)
        self._emit_wire_event(event)
        self._record_event(event)
        return event

    async def receive_event(self, *, timeout: float | None = None) -> SipWireEvent:
        event = await self.endpoint.receive_event(timeout=timeout)
        self._apply_after_receive_hooks(event)
        self._emit_wire_event(event)
        self._record_event(event)
        return event

    async def receive_response(
        self,
        *,
        call_id: str,
        method: str,
        timeout: float,
        cseq: int | None = None,
    ) -> SipResponse:
        event = await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _response_matches(
                item,
                call_id=call_id,
                cseq_method=method.upper(),
                cseq=cseq,
            ),
        )
        response = event.message
        assert isinstance(response, SipResponse)
        return response

    async def receive_final_response(
        self,
        *,
        call_id: str,
        method: str,
        timeout: float,
        cseq: int | None = None,
    ) -> SipResponse:
        while True:
            response = await self.receive_response(
                call_id=call_id,
                method=method,
                timeout=timeout,
                cseq=cseq,
            )
            if response.status_code >= 200:
                return response

    async def request(
        self,
        method: str,
        target: SipUri | str,
        *,
        remote: UdpAddress,
        caller: SipUri | str,
        contact: SipUri | str,
        timeout: float = 1.0,
        call_id: str | None = None,
        from_tag: str | None = None,
        body: bytes = b"",
        content_type: str | None = None,
        headers: tuple[tuple[str, str], ...] = (),
        capabilities: SipCapabilities | None = None,
        username: str | None = None,
        password: str | None = None,
        cnonce: str = "sipx",
    ) -> SipResponse:
        request_method = method.upper()
        target_uri = _sip_uri(target)
        caller_uri = _sip_uri(caller)
        contact_uri = _sip_uri(contact)
        call_id = call_id or new_call_id(request_method.lower())
        from_tag = from_tag or new_tag("from")
        cseq = 1
        request = create_request(
            method=request_method,
            target=target_uri,
            caller=caller_uri,
            contact=contact_uri,
            call_id=call_id,
            branch=new_branch(request_method.lower()),
            from_tag=from_tag,
            cseq=cseq,
            body=body,
            content_type=content_type,
            headers=headers,
            capabilities=capabilities,
        )
        retransmission = await self._send_with_retransmissions(request, remote)
        try:
            response = await self.receive_final_response(
                call_id=call_id,
                method=request_method,
                timeout=timeout,
                cseq=cseq,
            )
        finally:
            await self._stop_retransmission(retransmission)
        challenge = digest_challenge_for_response(response)
        if challenge is None or username is None or password is None:
            return response
        auth_header_name, challenge_value = challenge
        cseq = 2
        retry = create_request(
            method=request_method,
            target=target_uri,
            caller=caller_uri,
            contact=contact_uri,
            call_id=call_id,
            branch=new_branch(f"{request_method.lower()}-auth"),
            from_tag=from_tag,
            cseq=cseq,
            body=body,
            content_type=content_type,
            headers=headers,
            capabilities=capabilities,
            auth_header=(
                auth_header_name,
                build_digest_authorization(
                    username=username,
                    password=password,
                    method=request_method,
                    uri=str(target_uri),
                    challenge=parse_digest_challenge(challenge_value),
                    cnonce=cnonce,
                ),
            ),
        )
        retransmission = await self._send_with_retransmissions(retry, remote)
        try:
            return await self.receive_final_response(
                call_id=call_id,
                method=request_method,
                timeout=timeout,
                cseq=cseq,
            )
        finally:
            await self._stop_retransmission(retransmission)

    async def register_account(
        self,
        *,
        remote: UdpAddress,
        registrar: SipUri,
        aor: SipUri,
        contact: SipUri,
        call_id: str,
        branch: str,
        from_tag: str,
        expires: int = 3600,
        timeout: float = 1.0,
        username: str | None = None,
        password: str | None = None,
        auth_branch: str | None = None,
        cnonce: str = "sipx",
    ) -> RegisterClientState:
        flow = RegisterClientFlow(
            registrar=registrar,
            aor=aor,
            contact=contact,
            call_id=call_id,
            from_tag=from_tag,
            expires=expires,
        )
        request = flow.create_register(branch=branch)
        transaction = NonInviteClientTransaction(request)
        retransmission = await self._send_with_retransmissions(request, remote)

        try:
            while True:
                event = await self._receive_matching(
                    timeout=timeout,
                    predicate=lambda item: _response_matches(
                        item,
                        call_id=call_id,
                        cseq_method="REGISTER",
                    ),
                )
                response = event.message
                if not isinstance(response, SipResponse):
                    continue
                transaction.receive_response(response)
                if response.status_code < 200:
                    continue
                await self._stop_retransmission(retransmission)
                state = flow.receive_response(response)
                if state is RegisterClientState.CHALLENGED:
                    if username is None or password is None:
                        raise SipRegisterError(
                            "REGISTER challenge requires credentials"
                        )
                    request = flow.create_authenticated_register(
                        branch=auth_branch or f"{branch}-auth",
                        username=username,
                        password=password,
                        cnonce=cnonce,
                    )
                    transaction = NonInviteClientTransaction(request)
                    retransmission = await self._send_with_retransmissions(
                        request, remote
                    )
                    continue
                if state in {
                    RegisterClientState.REGISTERED,
                    RegisterClientState.UNREGISTERED,
                }:
                    self._record_call(
                        "registered"
                        if state is RegisterClientState.REGISTERED
                        else "unregistered",
                        call_id=call_id,
                        data={"aor": str(aor), "registrar": str(registrar)},
                    )
                    return state
                if state is RegisterClientState.FAILED:
                    raise SipRegisterError(
                        f"REGISTER failed with {response.status_code} {response.reason}"
                    )
        finally:
            await self._stop_retransmission(retransmission)

    async def unregister_account(
        self,
        *,
        remote: UdpAddress,
        registrar: SipUri,
        aor: SipUri,
        contact: SipUri,
        call_id: str,
        branch: str,
        from_tag: str,
        timeout: float = 1.0,
        username: str | None = None,
        password: str | None = None,
        auth_branch: str | None = None,
        cnonce: str = "sipx",
    ) -> RegisterClientState:
        return await self.register_account(
            remote=remote,
            registrar=registrar,
            aor=aor,
            contact=contact,
            call_id=call_id,
            branch=branch,
            from_tag=from_tag,
            expires=0,
            timeout=timeout,
            username=username,
            password=password,
            auth_branch=auth_branch,
            cnonce=cnonce,
        )

    async def initiate_call(
        self,
        *,
        remote: UdpAddress,
        target: SipUri,
        caller: SipUri,
        contact: SipUri,
        call_id: str,
        branch: str,
        from_tag: str,
        ack_branch: str,
        timeout: float = 1.0,
        body: bytes = b"",
        content_type: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth_branch: str | None = None,
        cnonce: str = "sipx",
    ) -> SipCall:
        attempt = await self.start_invite(
            remote=remote,
            target=target,
            caller=caller,
            contact=contact,
            call_id=call_id,
            branch=branch,
            from_tag=from_tag,
            body=body,
            content_type=content_type,
        )
        request = attempt.request
        transaction = attempt.transaction
        retransmission = self._start_retransmission(request, remote)
        retransmission_stopped = False
        auth_attempted = False
        received_provisional = False
        cseq = 1

        try:
            while True:
                event = await self._receive_matching(
                    timeout=None if received_provisional else timeout,
                    predicate=lambda item: _response_matches(
                        item,
                        call_id=call_id,
                        cseq_method="INVITE",
                        cseq=cseq,
                    ),
                )
                response = event.message
                if not isinstance(response, SipResponse):
                    continue
                if not retransmission_stopped:
                    await self._stop_retransmission(retransmission)
                    retransmission_stopped = True
                transaction.receive_response(response)
                if response.status_code < 200:
                    received_provisional = True
                    continue
                if 200 <= response.status_code < 300:
                    local_sdp = _sdp_from_message(request)
                    remote_sdp = _validate_sdp_answer(local_sdp, response)
                    dialog = Dialog.from_uac_invite_response(request, response)
                    ack = create_ack_request(
                        invite=request,
                        response=response,
                        via_host=self.local_address[0],
                        branch=ack_branch,
                    )
                    await self.send_request(ack, remote)
                    self._record_call(
                        "confirmed", call_id=call_id, data={"role": "uac"}
                    )
                    return SipCall(
                        call_id=call_id,
                        dialog=dialog,
                        remote=remote,
                        request_uri=target,
                        local_sdp=local_sdp,
                        remote_sdp=remote_sdp,
                    )

                if (
                    response.status_code in {401, 407}
                    and username is not None
                    and password is not None
                    and not auth_attempted
                ):
                    challenge = _digest_challenge(response)
                    if challenge is None:
                        raise SipCallError(
                            f"INVITE {response.status_code} missing Digest challenge"
                        )
                    ack = transaction.create_ack()
                    await self.send_request(ack, remote)
                    auth_header_name, challenge_value = challenge
                    authorization = build_digest_authorization(
                        username=username,
                        password=password,
                        method="INVITE",
                        uri=str(target),
                        challenge=parse_digest_challenge(challenge_value),
                        cnonce=cnonce,
                    )
                    request = create_invite_request(
                        target=target,
                        caller=caller,
                        contact=contact,
                        call_id=call_id,
                        branch=auth_branch or f"{branch}-auth",
                        from_tag=from_tag,
                        cseq=2,
                        body=body,
                        content_type=content_type,
                    )
                    request.headers.add(auth_header_name, authorization)
                    transaction = InviteClientTransaction(request)
                    retransmission = await self._send_with_retransmissions(
                        request, remote
                    )
                    retransmission_stopped = False
                    auth_attempted = True
                    received_provisional = False
                    cseq = 2
                    self._record_call(
                        "auth_challenged",
                        call_id=call_id,
                        data={"status_code": response.status_code},
                    )
                    continue

                ack = transaction.create_ack()
                await self.send_request(ack, remote)
                self._record_call(
                    "failed",
                    call_id=call_id,
                    data={
                        "status_code": response.status_code,
                        "reason": response.reason,
                    },
                )
                raise SipCallError(
                    f"INVITE failed with {response.status_code} {response.reason}"
                )
        finally:
            if not retransmission_stopped:
                await self._stop_retransmission(retransmission)

    async def start_invite(
        self,
        *,
        remote: UdpAddress,
        target: SipUri,
        caller: SipUri,
        contact: SipUri,
        call_id: str,
        branch: str,
        from_tag: str,
        body: bytes = b"",
        content_type: str | None = None,
    ) -> SipInviteAttempt:
        request = create_invite_request(
            target=target,
            caller=caller,
            contact=contact,
            call_id=call_id,
            branch=branch,
            from_tag=from_tag,
            body=body,
            content_type=content_type,
        )
        transaction = InviteClientTransaction(request)
        await self.send_request(request, remote)
        self._record_call("invite_sent", call_id=call_id, data={"target": str(target)})
        return SipInviteAttempt(
            call_id=call_id,
            request=request,
            remote=remote,
            transaction=transaction,
        )

    async def cancel_invite(
        self,
        attempt: SipInviteAttempt,
        *,
        timeout: float = 1.0,
    ) -> SipResponse:
        cancel = attempt.transaction.create_cancel()
        retransmission = await self._send_with_retransmissions(cancel, attempt.remote)
        try:
            await self._receive_matching(
                timeout=timeout,
                predicate=lambda item: _response_matches(
                    item,
                    call_id=attempt.call_id,
                    cseq_method="CANCEL",
                ),
            )
        finally:
            await self._stop_retransmission(retransmission)
        event = await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _response_matches(
                item,
                call_id=attempt.call_id,
                cseq_method="INVITE",
            ),
        )
        response = event.message
        if not isinstance(response, SipResponse):
            raise SipCallError("expected INVITE final response after CANCEL")
        attempt.transaction.receive_response(response)
        if response.status_code != 487:
            raise SipCallError(f"expected 487 after CANCEL, got {response.status_code}")
        ack = attempt.transaction.create_ack()
        await self.send_request(ack, attempt.remote)
        self._record_call("cancelled", call_id=attempt.call_id, data={"role": "uac"})
        return response

    async def receive_invite(self, *, timeout: float = 1.0) -> SipIncomingInvite:
        event = await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _request_matches(item, method="INVITE"),
        )
        request = event.message
        if not isinstance(request, SipRequest):
            raise SipCallError("expected INVITE request")
        call_id = _required_header(request, "Call-ID")
        transaction = InviteServerTransaction(request)
        self._record_call("invite_received", call_id=call_id, data={"role": "uas"})
        return SipIncomingInvite(
            call_id=call_id,
            request=request,
            remote=event.remote,
            transaction=transaction,
        )

    async def answer_cancel(
        self,
        invite: SipIncomingInvite,
        *,
        local_tag: str,
        timeout: float = 1.0,
    ) -> SipResponse:
        event = await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _request_matches(
                item,
                method="CANCEL",
                call_id=invite.call_id,
            ),
        )
        cancel = event.message
        if not isinstance(cancel, SipRequest):
            raise SipCallError("expected CANCEL request")
        cancel_response = create_response_for_request(
            request=cancel,
            status_code=200,
            reason="OK",
            to_tag=local_tag,
        )
        await self.send_response(cancel_response, event.remote)

        final = create_response_for_request(
            request=invite.request,
            status_code=487,
            reason="Request Terminated",
            to_tag=local_tag,
        )
        invite.transaction.send_response(final)
        retransmission = await self._send_with_retransmissions(final, invite.remote)
        try:
            ack_event = await self._receive_matching(
                timeout=timeout,
                predicate=lambda item: _request_matches(
                    item,
                    method="ACK",
                    call_id=invite.call_id,
                ),
            )
            ack = ack_event.message
            if isinstance(ack, SipRequest):
                invite.transaction.receive_ack(ack)
        finally:
            await self._stop_retransmission(retransmission)
        self._record_call("cancelled", call_id=invite.call_id, data={"role": "uas"})
        return final

    async def accept_call(
        self,
        *,
        local_tag: str,
        contact: SipUri | None = None,
        timeout: float = 1.0,
        provisionals: Sequence[SipProvisionalResponse] | None = None,
        final_body: bytes = b"",
        final_content_type: str | None = None,
        media_port: int | None = None,
        media_connection_address: str | None = None,
        supported_codecs: tuple[str, ...] = ("PCMU", "PCMA"),
        telephone_event: bool = True,
    ) -> SipCall:
        incoming = await self.receive_invite(timeout=timeout)
        event_remote = incoming.remote
        request = incoming.request
        call_id = incoming.call_id
        transaction = incoming.transaction
        local_sdp = _answer_sdp_for_invite(
            request,
            contact=contact,
            local_address=self.local_address,
            media_port=media_port,
            media_connection_address=media_connection_address,
            supported_codecs=supported_codecs,
            telephone_event=telephone_event,
        )
        remote_sdp = _sdp_from_message(request)

        for configured in _coerce_provisionals(provisionals):
            provisional = _create_invite_provisional_response(
                request=request,
                configured=configured,
                local_tag=local_tag,
                contact=contact,
                local_sdp=local_sdp,
            )
            transaction.send_response(provisional)
            await self.send_response(provisional, event_remote)

        body = final_body
        content_type = final_content_type
        if body == b"" and content_type is None and local_sdp is not None:
            body = local_sdp.to_sdp().encode("utf-8")
            content_type = "application/sdp"

        final = create_response_for_request(
            request=request,
            status_code=200,
            reason="OK",
            to_tag=local_tag,
            contact=contact,
            body=body,
            content_type=content_type,
        )
        transaction.send_response(final)
        retransmission = await self._send_with_retransmissions(final, event_remote)

        try:
            await self._receive_matching(
                timeout=timeout,
                predicate=lambda item: _request_matches(
                    item,
                    method="ACK",
                    call_id=call_id,
                ),
            )
        finally:
            await self._stop_retransmission(retransmission)
        dialog = Dialog.from_uas_invite_request(request, local_tag=local_tag)
        dialog.confirm()
        self._record_call("confirmed", call_id=call_id, data={"role": "uas"})
        return SipCall(
            call_id=call_id,
            dialog=dialog,
            remote=event_remote,
            request_uri=_uri_from_name_addr(_required_header(request, "From")),
            local_sdp=local_sdp,
            remote_sdp=remote_sdp,
        )

    async def hangup_call(
        self,
        call: SipCall,
        *,
        branch: str,
        timeout: float = 1.0,
        username: str | None = None,
        password: str | None = None,
        auth_branch: str | None = None,
        cnonce: str = "sipx",
    ) -> SipResponse:
        if call.state is SipCallState.TERMINATED:
            raise SipCallError("call is already terminated")
        request = create_bye_request(
            dialog=call.dialog,
            request_uri=call.request_uri,
            via_host=self.local_address[0],
            branch=branch,
        )
        transaction = NonInviteClientTransaction(request)
        retransmission = await self._send_with_retransmissions(request, call.remote)
        auth_attempted = False

        while True:
            cseq = _cseq_number(_required_header(request, "CSeq"))
            try:
                event = await self._receive_matching(
                    timeout=timeout,
                    predicate=lambda item: _response_matches(
                        item,
                        call_id=call.call_id,
                        cseq_method="BYE",
                        cseq=cseq,
                    ),
                )
                response = event.message
                if not isinstance(response, SipResponse):
                    raise SipCallError("expected BYE response")
            finally:
                await self._stop_retransmission(retransmission)
            transaction.receive_response(response)
            if 200 <= response.status_code < 300:
                call.dialog.terminate()
                call.state = SipCallState.TERMINATED
                self._record_call(
                    "terminated", call_id=call.call_id, data={"role": "uac"}
                )
                return response

            if (
                response.status_code in {401, 407}
                and username is not None
                and password is not None
                and not auth_attempted
            ):
                challenge = _digest_challenge(response)
                if challenge is None:
                    raise SipCallError(
                        f"BYE {response.status_code} missing Digest challenge"
                    )
                auth_header_name, challenge_value = challenge
                authorization = build_digest_authorization(
                    username=username,
                    password=password,
                    method="BYE",
                    uri=str(call.request_uri),
                    challenge=parse_digest_challenge(challenge_value),
                    cnonce=cnonce,
                )
                request = create_bye_request(
                    dialog=call.dialog,
                    request_uri=call.request_uri,
                    via_host=self.local_address[0],
                    branch=auth_branch or f"{branch}-auth",
                )
                request.headers.add(auth_header_name, authorization)
                transaction = NonInviteClientTransaction(request)
                retransmission = await self._send_with_retransmissions(
                    request, call.remote
                )
                auth_attempted = True
                self._record_call(
                    "auth_challenged",
                    call_id=call.call_id,
                    data={"status_code": response.status_code, "method": "BYE"},
                )
                continue

            call.state = SipCallState.FAILED
            self._record_call(
                "failed",
                call_id=call.call_id,
                data={"status_code": response.status_code, "reason": response.reason},
            )
            raise SipCallError(
                f"BYE failed with {response.status_code} {response.reason}"
            )

    async def send_info(
        self,
        call: SipCall,
        *,
        body: bytes,
        content_type: str,
        branch: str,
        timeout: float = 1.0,
    ) -> SipResponse:
        if call.state is not SipCallState.CONFIRMED:
            raise SipCallError("INFO requires a confirmed call")
        request = create_info_request(
            dialog=call.dialog,
            request_uri=call.request_uri,
            via_host=self.local_address[0],
            branch=branch,
            body=body,
            content_type=content_type,
        )
        cseq = _cseq_number(_required_header(request, "CSeq"))
        transaction = NonInviteClientTransaction(request)
        retransmission = await self._send_with_retransmissions(request, call.remote)
        try:
            event = await self._receive_matching(
                timeout=timeout,
                predicate=lambda item: _response_matches(
                    item,
                    call_id=call.call_id,
                    cseq_method="INFO",
                    cseq=cseq,
                ),
            )
            response = event.message
            if not isinstance(response, SipResponse):
                raise SipCallError("expected INFO response")
        finally:
            await self._stop_retransmission(retransmission)
        transaction.receive_response(response)
        if 200 <= response.status_code < 300:
            self._record_call(
                "info_sent",
                call_id=call.call_id,
                data={"content_type": content_type},
            )
            return response
        self._record_call(
            "failed",
            call_id=call.call_id,
            data={"status_code": response.status_code, "reason": response.reason},
        )
        raise SipCallError(f"INFO failed with {response.status_code} {response.reason}")

    async def send_dtmf_info(
        self,
        call: SipCall,
        digits: str,
        *,
        duration_ms: int = 160,
        timeout: float = 1.0,
    ) -> tuple[SipResponse, ...]:
        if not digits:
            raise ValueError("digits are required")
        if duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        responses: list[SipResponse] = []
        for digit in digits:
            _validate_dtmf_digit(digit)
            body = f"Signal={digit}\r\nDuration={duration_ms}\r\n".encode("ascii")
            response = await self.send_info(
                call,
                body=body,
                content_type="application/dtmf-relay",
                branch=f"z9hG4bK-info-{digit}-{time.monotonic_ns()}",
                timeout=timeout,
            )
            responses.append(response)
            self._record_call(
                "dtmf_sent",
                call_id=call.call_id,
                data={"digit": digit, "transport": "sip-info"},
            )
        return tuple(responses)

    async def answer_bye(
        self,
        call: SipCall,
        *,
        timeout: float = 1.0,
    ) -> SipResponse:
        event = await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _request_matches(
                item,
                method="BYE",
                call_id=call.call_id,
            ),
        )
        request = event.message
        if not isinstance(request, SipRequest):
            raise SipCallError("expected BYE request")
        response = create_response_for_request(
            request=request,
            status_code=200,
            reason="OK",
        )
        await self.send_response(response, event.remote)
        call.dialog.terminate()
        call.state = SipCallState.TERMINATED
        self._record_call("terminated", call_id=call.call_id, data={"role": "uas"})
        return response

    async def _receive_matching(
        self,
        *,
        timeout: float | None,
        predicate: Callable[[SipWireEvent], bool],
    ) -> SipWireEvent:
        if timeout is None:
            while True:
                event = await self.receive_event(timeout=None)
                if predicate(event):
                    return event
        assert timeout is not None
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SipUdpError("timed out waiting for matching SIP message")
            event = await self.receive_event(timeout=remaining)
            if predicate(event):
                return event

    def _record_event(self, event: SipWireEvent) -> None:
        self._record(sip_wire_event_name(event), data=_event_data(event))

    def _emit_wire_event(self, event: SipWireEvent) -> None:
        for hook in self.event_hooks.get("wire", []):
            hook(event)
        if isinstance(event.message, SipRequest):
            for hook in self.event_hooks.get("request", []):
                hook(event.message, event.remote)
        elif isinstance(event.message, SipResponse):
            for hook in self.event_hooks.get("response", []):
                hook(event.message, event.remote)

    def _send_message(self, message: SipMessage, remote: UdpAddress) -> SipWireEvent:
        outbound = self._apply_before_send_hooks(message, remote)
        return self.endpoint.send_message(outbound, remote)

    def _apply_before_send_hooks(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> SipMessage:
        outbound = _copy_message(message)
        for hook in self.event_hooks.get("request", []):
            hook(outbound, remote)
        if _is_sdp(outbound):
            for hook in self.event_hooks.get("sdp", []):
                hook(outbound, outbound.body)
        return outbound

    def _apply_after_receive_hooks(self, event: SipWireEvent) -> None:
        if isinstance(event.message, SipResponse):
            for hook in self.event_hooks.get("response", []):
                hook(event.message, event.remote)

    async def _send_with_retransmissions(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> _RetransmissionHandle | None:
        event = self._send_message(message, remote)
        self._emit_wire_event(event)
        self._record_event(event)
        return self._start_retransmission(message, remote)

    def _start_retransmission(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> _RetransmissionHandle | None:
        intervals = self._retransmission_intervals(message, remote)
        if not intervals:
            return None
        stop = asyncio.Event()
        task = asyncio.create_task(
            self._retransmit_until_stopped(message, remote, stop, intervals)
        )
        return _RetransmissionHandle(stop=stop, task=task)

    def _retransmission_intervals(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> tuple[float, ...]:
        intervals = list(self.retransmission_policy.intervals())
        for hook in self.event_hooks.get("retransmission", []):
            hook(message, remote, intervals)
        if any(interval <= 0 for interval in intervals):
            raise ValueError("retransmission intervals must be positive")
        return tuple(intervals)

    async def _stop_retransmission(
        self,
        handle: _RetransmissionHandle | None,
    ) -> None:
        if handle is None:
            return
        handle.stop.set()
        await handle.task

    async def _retransmit_until_stopped(
        self,
        message: SipMessage,
        remote: UdpAddress,
        stop: asyncio.Event,
        intervals: tuple[float, ...],
    ) -> None:
        for attempt, interval in enumerate(intervals, start=1):
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            event = self._send_message(message, remote)
            self._emit_wire_event(event)
            self._record_event(event)
            self._record(
                "retransmitted",
                data={
                    "attempt": attempt,
                    "remote_host": remote[0],
                    "remote_port": remote[1],
                    "message_type": _message_type(message),
                },
            )

    def _record_call(self, name: str, *, call_id: str, data: dict[str, Any]) -> None:
        self._record(name, category="call", call_id=call_id, data=data)

    def _record(
        self,
        name: str,
        *,
        data: dict[str, Any],
        category: str = "sip",
        call_id: str | None = None,
    ) -> None:
        if self.timeline is None:
            return
        self.timeline.record(
            category,
            name,
            actor_id=self.actor_id,
            call_id=call_id,
            data=data,
        )


def _event_data(event: SipWireEvent) -> dict[str, Any]:
    data: dict[str, Any] = {
        "direction": event.direction.value,
        "remote_host": event.remote[0],
        "remote_port": event.remote[1],
        "bytes": len(event.raw),
    }
    if event.error is not None:
        data["error"] = event.error
    if isinstance(event.message, SipRequest):
        data.update(
            {
                "message_type": "request",
                "method": event.message.method,
                "uri": str(event.message.uri),
            }
        )
    elif isinstance(event.message, SipResponse):
        data.update(
            {
                "message_type": "response",
                "status_code": event.message.status_code,
                "reason": event.message.reason,
            }
        )
    elif event.message is not None:
        data["message_type"] = type(event.message).__name__
    return data


def _message_type(message: SipMessage) -> str:
    if isinstance(message, SipRequest):
        return message.method
    if isinstance(message, SipResponse):
        return str(message.status_code)
    return type(message).__name__


def _copy_message(message: SipMessage) -> SipMessage:
    if isinstance(message, SipRequest):
        return SipRequest(
            method=message.method,
            uri=message.uri,
            headers=message.headers.copy(),
            body=message.body,
            version=message.version,
        )
    return SipResponse(
        status_code=message.status_code,
        reason=message.reason,
        headers=message.headers.copy(),
        body=message.body,
        version=message.version,
    )


def _is_sdp(message: SipMessage) -> bool:
    content_type = message.headers.get("Content-Type") or ""
    return (
        bool(message.body)
        and content_type.split(";", maxsplit=1)[0].strip().lower() == "application/sdp"
    )


def _sdp_from_message(message: SipMessage) -> SessionDescription | None:
    if not _is_sdp(message):
        return None
    try:
        return parse_sdp(message.body)
    except ValueError as exc:
        raise SipCallError(f"invalid SDP body: {exc}") from exc


def _validate_sdp_answer(
    offer: SessionDescription | None,
    response: SipResponse,
) -> SessionDescription | None:
    if offer is None:
        return _sdp_from_message(response)
    answer = _sdp_from_message(response)
    if answer is None:
        raise SipCallError("INVITE 200 OK missing SDP answer")
    if answer.audio is None:
        raise SipCallError("SDP answer has no audio media")
    if answer.audio.port <= 0:
        raise SipCallError("SDP answer rejected audio media")
    offered = _media_codec_names(offer)
    answered = _media_codec_names(answer)
    if offered and not offered.intersection(answered):
        raise SipCallError("SDP answer has no common audio codec")
    return answer


def _coerce_provisionals(
    provisionals: Sequence[SipProvisionalResponse] | None,
) -> tuple[SipProvisionalResponse, ...]:
    if provisionals is None:
        return (SipProvisionalResponse.ringing(),)
    return tuple(provisionals)


def _create_invite_provisional_response(
    *,
    request: SipRequest,
    configured: SipProvisionalResponse,
    local_tag: str,
    contact: SipUri | None,
    local_sdp: SessionDescription | None,
) -> SipResponse:
    if configured.include_sdp:
        if local_sdp is None:
            raise SipCallError("provisional SDP requested but INVITE has no SDP offer")
        body = local_sdp.to_sdp().encode("utf-8")
        content_type = configured.content_type or "application/sdp"
    else:
        body = configured.body
        content_type = configured.content_type
    if configured.status_code == 100:
        to_tag = None
        response_contact = None
    else:
        to_tag = local_tag
        response_contact = contact
    return create_response_for_request(
        request=request,
        status_code=configured.status_code,
        reason=configured.reason,
        to_tag=to_tag,
        contact=response_contact,
        body=body,
        content_type=content_type,
    )


def _answer_sdp_for_invite(
    request: SipRequest,
    *,
    contact: SipUri | None,
    local_address: UdpAddress,
    media_port: int | None,
    media_connection_address: str | None,
    supported_codecs: tuple[str, ...],
    telephone_event: bool,
) -> SessionDescription | None:
    offer = _sdp_from_message(request)
    if offer is None:
        return None
    port = media_port or contact_port(contact) or local_address[1]
    try:
        return create_audio_answer(
            offer,
            connection_address=media_connection_address
            or (contact.host if contact is not None else local_address[0]),
            port=port,
            supported_codecs=supported_codecs,
            telephone_event=telephone_event,
        )
    except SdpNegotiationError as exc:
        raise SipCallError(f"SDP negotiation failed: {exc}") from exc


def contact_port(contact: SipUri | None) -> int | None:
    if contact is None:
        return None
    return contact.port


def _media_codec_names(sdp: SessionDescription) -> set[str]:
    if sdp.audio is None:
        return set()
    return {
        codec.name.upper()
        for codec in sdp.audio.codecs.values()
        if codec.name.upper() != "TELEPHONE-EVENT"
    }


def _request_matches(
    event: SipWireEvent,
    *,
    method: str,
    call_id: str | None = None,
) -> bool:
    message = event.message
    if not isinstance(message, SipRequest) or message.method != method:
        return False
    return call_id is None or message.headers.get("Call-ID") == call_id


def _response_matches(
    event: SipWireEvent,
    *,
    call_id: str,
    cseq_method: str,
    cseq: int | None = None,
) -> bool:
    message = event.message
    if not isinstance(message, SipResponse):
        return False
    cseq_header = message.headers.get("CSeq") or ""
    return (
        message.headers.get("Call-ID") == call_id
        and _cseq_method(cseq_header) == cseq_method
        and (cseq is None or _cseq_number(cseq_header) == cseq)
    )


def _digest_challenge(response: SipResponse) -> tuple[str, str] | None:
    if response.status_code == 401:
        value = response.headers.get("WWW-Authenticate")
        return ("Authorization", value) if value is not None else None
    if response.status_code == 407:
        value = response.headers.get("Proxy-Authenticate")
        return ("Proxy-Authorization", value) if value is not None else None
    return None


def _required_header(message: SipRequest | SipResponse, name: str) -> str:
    value = message.headers.get(name)
    if value is None:
        raise SipCallError(f"missing required SIP header: {name}")
    return value


def _cseq_number(value: str) -> int | None:
    number, _separator, _method = value.partition(" ")
    try:
        return int(number)
    except ValueError:
        return None


def _cseq_method(value: str) -> str:
    _number, _separator, method = value.partition(" ")
    return method.strip().upper()


def _uri_from_name_addr(value: str) -> SipUri:
    start = value.find("<")
    end = value.find(">")
    if start >= 0 and end > start:
        return SipUri.parse(value[start + 1 : end])
    return SipUri.parse(value.split(";", maxsplit=1)[0].strip())


def _sip_uri(value: SipUri | str) -> SipUri:
    return value if isinstance(value, SipUri) else SipUri.parse(value)


def _validate_dtmf_digit(digit: str) -> None:
    if digit not in "0123456789ABCDabcd*#":
        raise ValueError(f"unsupported DTMF digit: {digit!r}")
