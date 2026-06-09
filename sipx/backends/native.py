from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from sipx.core.capabilities import BackendCapability
from sipx.core.timeline import Timeline
from sipx.sip.auth import build_digest_authorization, parse_digest_challenge
from sipx.sip.dialog import Dialog
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


class NativeSipCallError(RuntimeError):
    pass


class NativeSipRegisterError(RuntimeError):
    pass


class NativeSipCallState(StrEnum):
    EARLY = "early"
    CONFIRMED = "confirmed"
    TERMINATED = "terminated"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NativeSipRetransmissionPolicy:
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
class NativeSipLabHooks:
    before_send_message: (
        Callable[[SipMessage, UdpAddress], SipMessage | bytes | None] | None
    ) = None
    before_sdp_body: Callable[[SipMessage, bytes], bytes | None] | None = None
    after_receive_event: Callable[[SipWireEvent], SipWireEvent | None] | None = None
    retransmission_intervals: (
        Callable[[SipMessage, UdpAddress, tuple[float, ...]], tuple[float, ...] | None]
        | None
    ) = None


@dataclass(slots=True)
class NativeSipCall:
    call_id: str
    dialog: Dialog
    remote: UdpAddress
    request_uri: SipUri
    state: NativeSipCallState = NativeSipCallState.CONFIRMED
    local_sdp: SessionDescription | None = None
    remote_sdp: SessionDescription | None = None


@dataclass(slots=True)
class NativeSipInviteAttempt:
    call_id: str
    request: SipRequest
    remote: UdpAddress
    transaction: InviteClientTransaction


@dataclass(slots=True)
class NativeSipIncomingInvite:
    call_id: str
    request: SipRequest
    remote: UdpAddress
    transaction: InviteServerTransaction


@dataclass(slots=True)
class _RetransmissionHandle:
    stop: asyncio.Event
    task: asyncio.Task[None]


class NativeSipBackend:
    capabilities = frozenset(
        {
            BackendCapability.SIP_WIRE,
            BackendCapability.TIMELINE,
        }
    )

    def __init__(
        self,
        *,
        local_host: str = "127.0.0.1",
        local_port: int = 0,
        mode: str = "strict",
        timeline: Timeline | None = None,
        actor_id: str | None = None,
        max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
        retransmission_policy: NativeSipRetransmissionPolicy | None = None,
        lab_hooks: NativeSipLabHooks | None = None,
        wire_event_handler: Callable[[SipWireEvent], None] | None = None,
    ) -> None:
        if mode not in {"strict", "lab"}:
            raise ValueError("mode must be strict or lab")
        if mode != "lab" and lab_hooks is not None:
            raise ValueError("lab_hooks require lab mode")
        self.mode = mode
        self.timeline = timeline
        self.actor_id = actor_id
        self.retransmission_policy = (
            retransmission_policy or NativeSipRetransmissionPolicy()
        )
        self.endpoint = SipUdpEndpoint(
            local_host=local_host,
            local_port=local_port,
            max_message_size=max_message_size,
        )
        self.lab_hooks = lab_hooks
        self.wire_event_handler = wire_event_handler

    @property
    def local_address(self) -> UdpAddress:
        return self.endpoint.local_address

    def supports(self, capability: BackendCapability | str) -> bool:
        return BackendCapability(capability) in self.capabilities

    async def start(self) -> NativeSipBackend:
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

    async def __aenter__(self) -> NativeSipBackend:
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
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise SipUdpError("timed out waiting for SIP datagram")
            event = await self.endpoint.receive_event(timeout=remaining)
            event = self._apply_after_receive_hook(event)
            if event is None:
                continue
            self._emit_wire_event(event)
            self._record_event(event)
            return event

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
                        raise NativeSipRegisterError(
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
                    raise NativeSipRegisterError(
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
    ) -> NativeSipCall:
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
        cseq = 1

        try:
            while True:
                event = await self._receive_matching(
                    timeout=timeout,
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
                    return NativeSipCall(
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
                        raise NativeSipCallError(
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
                raise NativeSipCallError(
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
    ) -> NativeSipInviteAttempt:
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
        return NativeSipInviteAttempt(
            call_id=call_id,
            request=request,
            remote=remote,
            transaction=transaction,
        )

    async def cancel_invite(
        self,
        attempt: NativeSipInviteAttempt,
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
            raise NativeSipCallError("expected INVITE final response after CANCEL")
        attempt.transaction.receive_response(response)
        if response.status_code != 487:
            raise NativeSipCallError(
                f"expected 487 after CANCEL, got {response.status_code}"
            )
        ack = attempt.transaction.create_ack()
        await self.send_request(ack, attempt.remote)
        self._record_call("cancelled", call_id=attempt.call_id, data={"role": "uac"})
        return response

    async def receive_invite(self, *, timeout: float = 1.0) -> NativeSipIncomingInvite:
        event = await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _request_matches(item, method="INVITE"),
        )
        request = event.message
        if not isinstance(request, SipRequest):
            raise NativeSipCallError("expected INVITE request")
        call_id = _required_header(request, "Call-ID")
        transaction = InviteServerTransaction(request)
        self._record_call("invite_received", call_id=call_id, data={"role": "uas"})
        return NativeSipIncomingInvite(
            call_id=call_id,
            request=request,
            remote=event.remote,
            transaction=transaction,
        )

    async def answer_cancel(
        self,
        invite: NativeSipIncomingInvite,
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
            raise NativeSipCallError("expected CANCEL request")
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
        provisional_status: int | None = 180,
        provisional_reason: str = "Ringing",
        final_body: bytes = b"",
        final_content_type: str | None = None,
        media_port: int | None = None,
        supported_codecs: tuple[str, ...] = ("PCMU", "PCMA"),
        telephone_event: bool = True,
    ) -> NativeSipCall:
        incoming = await self.receive_invite(timeout=timeout)
        event_remote = incoming.remote
        request = incoming.request
        call_id = incoming.call_id
        transaction = incoming.transaction

        if provisional_status is not None:
            provisional = create_response_for_request(
                request=request,
                status_code=provisional_status,
                reason=provisional_reason,
                to_tag=local_tag,
                contact=contact,
            )
            transaction.send_response(provisional)
            await self.send_response(provisional, event_remote)

        local_sdp = _answer_sdp_for_invite(
            request,
            contact=contact,
            local_address=self.local_address,
            media_port=media_port,
            supported_codecs=supported_codecs,
            telephone_event=telephone_event,
        )
        remote_sdp = _sdp_from_message(request)
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
        return NativeSipCall(
            call_id=call_id,
            dialog=dialog,
            remote=event_remote,
            request_uri=_uri_from_name_addr(_required_header(request, "From")),
            local_sdp=local_sdp,
            remote_sdp=remote_sdp,
        )

    async def hangup_call(
        self,
        call: NativeSipCall,
        *,
        branch: str,
        timeout: float = 1.0,
        username: str | None = None,
        password: str | None = None,
        auth_branch: str | None = None,
        cnonce: str = "sipx",
    ) -> SipResponse:
        if call.state is NativeSipCallState.TERMINATED:
            raise NativeSipCallError("call is already terminated")
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
                    raise NativeSipCallError("expected BYE response")
            finally:
                await self._stop_retransmission(retransmission)
            transaction.receive_response(response)
            if 200 <= response.status_code < 300:
                call.dialog.terminate()
                call.state = NativeSipCallState.TERMINATED
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
                    raise NativeSipCallError(
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

            call.state = NativeSipCallState.FAILED
            self._record_call(
                "failed",
                call_id=call.call_id,
                data={"status_code": response.status_code, "reason": response.reason},
            )
            raise NativeSipCallError(
                f"BYE failed with {response.status_code} {response.reason}"
            )

    async def send_info(
        self,
        call: NativeSipCall,
        *,
        body: bytes,
        content_type: str,
        branch: str,
        timeout: float = 1.0,
    ) -> SipResponse:
        if call.state is not NativeSipCallState.CONFIRMED:
            raise NativeSipCallError("INFO requires a confirmed call")
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
                raise NativeSipCallError("expected INFO response")
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
        raise NativeSipCallError(
            f"INFO failed with {response.status_code} {response.reason}"
        )

    async def send_dtmf_info(
        self,
        call: NativeSipCall,
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
        call: NativeSipCall,
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
            raise NativeSipCallError("expected BYE request")
        response = create_response_for_request(
            request=request,
            status_code=200,
            reason="OK",
        )
        await self.send_response(response, event.remote)
        call.dialog.terminate()
        call.state = NativeSipCallState.TERMINATED
        self._record_call("terminated", call_id=call.call_id, data={"role": "uas"})
        return response

    async def _receive_matching(
        self,
        *,
        timeout: float,
        predicate: Callable[[SipWireEvent], bool],
    ) -> SipWireEvent:
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
        if self.wire_event_handler is not None:
            self.wire_event_handler(event)

    def _send_message(self, message: SipMessage, remote: UdpAddress) -> SipWireEvent:
        outbound = self._apply_before_send_hooks(message, remote)
        if isinstance(outbound, bytes):
            return self.endpoint.send_raw(outbound, remote)
        return self.endpoint.send_message(outbound, remote)

    def _apply_before_send_hooks(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> SipMessage | bytes:
        hooks = self.lab_hooks
        if hooks is None:
            return message

        outbound: SipMessage | bytes = _copy_message(message)
        if hooks.before_send_message is not None:
            hooked = hooks.before_send_message(outbound, remote)
            if hooked is not None:
                outbound = hooked
        if isinstance(outbound, bytes):
            return outbound

        if hooks.before_sdp_body is not None and _is_sdp(outbound):
            body = hooks.before_sdp_body(outbound, outbound.body)
            if body is not None:
                outbound.body = body
        return outbound

    def _apply_after_receive_hook(
        self,
        event: SipWireEvent,
    ) -> SipWireEvent | None:
        hooks = self.lab_hooks
        if hooks is None or hooks.after_receive_event is None:
            return event
        return hooks.after_receive_event(event)

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
        intervals = self.retransmission_policy.intervals()
        hooks = self.lab_hooks
        if hooks is not None and hooks.retransmission_intervals is not None:
            hooked = hooks.retransmission_intervals(message, remote, intervals)
            if hooked is not None:
                intervals = hooked
        if any(interval <= 0 for interval in intervals):
            raise ValueError("retransmission intervals must be positive")
        return intervals

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
        raise NativeSipCallError(f"invalid SDP body: {exc}") from exc


def _validate_sdp_answer(
    offer: SessionDescription | None,
    response: SipResponse,
) -> SessionDescription | None:
    if offer is None:
        return _sdp_from_message(response)
    answer = _sdp_from_message(response)
    if answer is None:
        raise NativeSipCallError("INVITE 200 OK missing SDP answer")
    if answer.audio is None:
        raise NativeSipCallError("SDP answer has no audio media")
    if answer.audio.port <= 0:
        raise NativeSipCallError("SDP answer rejected audio media")
    offered = _media_codec_names(offer)
    answered = _media_codec_names(answer)
    if offered and not offered.intersection(answered):
        raise NativeSipCallError("SDP answer has no common audio codec")
    return answer


def _answer_sdp_for_invite(
    request: SipRequest,
    *,
    contact: SipUri | None,
    local_address: UdpAddress,
    media_port: int | None,
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
            connection_address=(
                contact.host if contact is not None else local_address[0]
            ),
            port=port,
            supported_codecs=supported_codecs,
            telephone_event=telephone_event,
        )
    except SdpNegotiationError as exc:
        raise NativeSipCallError(f"SDP negotiation failed: {exc}") from exc


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
        raise NativeSipCallError(f"missing required SIP header: {name}")
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


def _validate_dtmf_digit(digit: str) -> None:
    if digit not in "0123456789ABCDabcd*#":
        raise ValueError(f"unsupported DTMF digit: {digit!r}")
