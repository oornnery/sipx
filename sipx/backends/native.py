from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from sipx.core.capabilities import BackendCapability
from sipx.core.timeline import Timeline
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


@dataclass(slots=True)
class NativeSipCall:
    call_id: str
    dialog: Dialog
    remote: UdpAddress
    request_uri: SipUri
    state: NativeSipCallState = NativeSipCallState.CONFIRMED


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
    ) -> None:
        if mode not in {"strict", "lab"}:
            raise ValueError("mode must be strict or lab")
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
        event = self.endpoint.send_message(request, remote)
        self._record_event(event)
        return event

    async def send_response(
        self,
        response: SipResponse,
        remote: UdpAddress,
    ) -> SipWireEvent:
        event = self.endpoint.send_message(response, remote)
        self._record_event(event)
        return event

    async def send_raw(self, raw: bytes, remote: UdpAddress) -> SipWireEvent:
        if self.mode != "lab":
            raise SipUdpError("send_raw is only allowed in lab mode")
        event = self.endpoint.send_raw(raw, remote)
        self._record_event(event)
        return event

    async def receive_event(self, *, timeout: float | None = None) -> SipWireEvent:
        event = await self.endpoint.receive_event(timeout=timeout)
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
                await self._stop_retransmission(retransmission)
                transaction.receive_response(response)
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

        try:
            while True:
                event = await self._receive_matching(
                    timeout=timeout,
                    predicate=lambda item: _response_matches(
                        item,
                        call_id=call_id,
                        cseq_method="INVITE",
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
                    )

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

        final = create_response_for_request(
            request=request,
            status_code=200,
            reason="OK",
            to_tag=local_tag,
            contact=contact,
            body=final_body,
            content_type=final_content_type,
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
        )

    async def hangup_call(
        self,
        call: NativeSipCall,
        *,
        branch: str,
        timeout: float = 1.0,
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
        try:
            event = await self._receive_matching(
                timeout=timeout,
                predicate=lambda item: _response_matches(
                    item,
                    call_id=call.call_id,
                    cseq_method="BYE",
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
            self._record_call("terminated", call_id=call.call_id, data={"role": "uac"})
            return response
        call.state = NativeSipCallState.FAILED
        self._record_call(
            "failed",
            call_id=call.call_id,
            data={"status_code": response.status_code, "reason": response.reason},
        )
        raise NativeSipCallError(
            f"BYE failed with {response.status_code} {response.reason}"
        )

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

    async def _send_with_retransmissions(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> _RetransmissionHandle | None:
        event = self.endpoint.send_message(message, remote)
        self._record_event(event)
        return self._start_retransmission(message, remote)

    def _start_retransmission(
        self,
        message: SipMessage,
        remote: UdpAddress,
    ) -> _RetransmissionHandle | None:
        if self.retransmission_policy.max_attempts == 0:
            return None
        stop = asyncio.Event()
        task = asyncio.create_task(
            self._retransmit_until_stopped(message, remote, stop)
        )
        return _RetransmissionHandle(stop=stop, task=task)

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
    ) -> None:
        for attempt, interval in enumerate(
            self.retransmission_policy.intervals(),
            start=1,
        ):
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            event = self.endpoint.send_message(message, remote)
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
) -> bool:
    message = event.message
    if not isinstance(message, SipResponse):
        return False
    return (
        message.headers.get("Call-ID") == call_id
        and _cseq_method(message.headers.get("CSeq") or "") == cseq_method
    )


def _required_header(message: SipRequest | SipResponse, name: str) -> str:
    value = message.headers.get(name)
    if value is None:
        raise NativeSipCallError(f"missing required SIP header: {name}")
    return value


def _cseq_method(value: str) -> str:
    _number, _separator, method = value.partition(" ")
    return method.strip().upper()


def _uri_from_name_addr(value: str) -> SipUri:
    start = value.find("<")
    end = value.find(">")
    if start >= 0 and end > start:
        return SipUri.parse(value[start + 1 : end])
    return SipUri.parse(value.split(";", maxsplit=1)[0].strip())
