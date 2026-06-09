# Observe SIP wire events with decorator-style handlers.

from __future__ import annotations

from sipx import (
    HeaderMap,
    SipHandlers,
    SipRequest,
    SipResponse,
    SipUri,
    SipWireDirection,
    SipWireEvent,
)
from sipx.examples.common import print_json


def main() -> None:
    handlers = SipHandlers()
    seen: list[dict[str, object]] = []

    @handlers.on_wire_event
    def record_wire(event: SipWireEvent) -> None:
        seen.append({"direction": event.direction.value, "bytes": len(event.raw)})

    @handlers.on_request
    def record_request(request: SipRequest, remote: tuple[str, int]) -> None:
        seen.append({"request": request.method, "remote": f"{remote[0]}:{remote[1]}"})

    @handlers.on_response
    def record_response(response: SipResponse, remote: tuple[str, int]) -> None:
        seen.append(
            {"response": response.status_code, "remote": f"{remote[0]}:{remote[1]}"}
        )

    request_headers = HeaderMap()
    request_headers.add("Call-ID", "handlers-demo")
    request = SipRequest(
        method="OPTIONS",
        uri=SipUri.parse("sip:service@example.com"),
        headers=request_headers,
    )
    response_headers = HeaderMap()
    response_headers.add("Call-ID", "handlers-demo")
    response = SipResponse(status_code=200, reason="OK", headers=response_headers)

    handlers.emit(
        SipWireEvent(
            direction=SipWireDirection.TX,
            remote=("192.0.2.20", 5060),
            raw=request.to_bytes(),
            message=request,
        )
    )
    handlers.emit(
        SipWireEvent(
            direction=SipWireDirection.RX,
            remote=("192.0.2.20", 5060),
            raw=response.to_bytes(),
            message=response,
        )
    )

    print_json(seen)


if __name__ == "__main__":
    main()
