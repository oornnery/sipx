from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from sipx.core.capabilities import BackendCapability
from sipx.core.timeline import Timeline
from sipx.sip.dialog import Dialog
from sipx.sip.message import DEFAULT_MAX_MESSAGE_SIZE, SipRequest, SipResponse
from sipx.sip.requests import (
    create_ack_request,
    create_bye_request,
    create_invite_request,
    create_response_for_request,
)
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


class NativeSipCallState(StrEnum):
    EARLY = "early"
    CONFIRMED = "confirmed"
    TERMINATED = "terminated"
    FAILED = "failed"


@dataclass(slots=True)
class NativeSipCall:
    call_id: str
    dialog: Dialog
    remote: UdpAddress
    request_uri: SipUri
    state: NativeSipCallState = NativeSipCallState.CONFIRMED


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
    ) -> None:
        if mode not in {"strict", "lab"}:
            raise ValueError("mode must be strict or lab")
        self.mode = mode
        self.timeline = timeline
        self.actor_id = actor_id
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
                self._record_call("confirmed", call_id=call_id, data={"role": "uac"})
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
                data={"status_code": response.status_code, "reason": response.reason},
            )
            raise NativeSipCallError(
                f"INVITE failed with {response.status_code} {response.reason}"
            )

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

        if provisional_status is not None:
            provisional = create_response_for_request(
                request=request,
                status_code=provisional_status,
                reason=provisional_reason,
                to_tag=local_tag,
                contact=contact,
            )
            transaction.send_response(provisional)
            await self.send_response(provisional, event.remote)

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
        await self.send_response(final, event.remote)

        await self._receive_matching(
            timeout=timeout,
            predicate=lambda item: _request_matches(
                item,
                method="ACK",
                call_id=call_id,
            ),
        )
        dialog = Dialog.from_uas_invite_request(request, local_tag=local_tag)
        dialog.confirm()
        self._record_call("confirmed", call_id=call_id, data={"role": "uas"})
        return NativeSipCall(
            call_id=call_id,
            dialog=dialog,
            remote=event.remote,
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
        await self.send_request(request, call.remote)
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
