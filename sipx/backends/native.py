from __future__ import annotations

from typing import Any

from sipx.core.capabilities import BackendCapability
from sipx.core.timeline import Timeline
from sipx.sip.message import DEFAULT_MAX_MESSAGE_SIZE, SipRequest, SipResponse
from sipx.sip.transport import (
    SipUdpEndpoint,
    SipUdpError,
    SipWireEvent,
    UdpAddress,
    sip_wire_event_name,
)


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

    def _record_event(self, event: SipWireEvent) -> None:
        self._record(sip_wire_event_name(event), data=_event_data(event))

    def _record(self, name: str, *, data: dict[str, Any]) -> None:
        if self.timeline is None:
            return
        self.timeline.record(
            "sip",
            name,
            actor_id=self.actor_id,
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
