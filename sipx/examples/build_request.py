# Build a SIP request without opening a UDP socket.

from __future__ import annotations

from dataclasses import asdict

from sipx import (
    SipCapabilities,
    SipUri,
    create_request,
    new_branch,
    new_call_id,
    new_tag,
)
from sipx.examples.common import print_json


def main() -> None:
    target = SipUri.parse("sip:service@example.com")
    caller = SipUri.parse("sip:alice@example.com")
    contact = SipUri.parse("sip:alice@192.0.2.10:5060")
    capabilities = SipCapabilities(
        accept=("application/sdp", "text/plain"),
        allow=("OPTIONS", "MESSAGE", "INVITE", "ACK", "BYE", "CANCEL"),
        supported=("replaces",),
    )
    request = create_request(
        method="OPTIONS",
        target=target,
        caller=caller,
        contact=contact,
        call_id=new_call_id("options"),
        branch=new_branch("options"),
        from_tag=new_tag("from"),
        capabilities=capabilities,
    )
    print(request.to_bytes(compact_headers=True).decode("utf-8"), end="")
    print_json(asdict(request.summary()) if hasattr(request, "summary") else {})


if __name__ == "__main__":
    main()
