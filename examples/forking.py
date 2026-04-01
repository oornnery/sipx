"""
INVITE forking demo (RFC 3261 §19.3) — offline loopback test.

A proxy can fork an INVITE to multiple branches and the UAC may receive
200 OK from more than one of them (each with a unique To-tag representing
a different dialog).

sipx collects all 200s during a short fork-collection window (200ms),
returns the first one to the caller, and automatically ACK+BYEs the extras.

This example simulates the scenario using a MockTransport so it works
without any real network.

Run:
    uv run python examples/forking.py
"""

from __future__ import annotations

from sipx.client._base import ForkTracker, _extract_tag
from sipx.models._message import Response


def demo_fork_tracker() -> None:
    print("=== ForkTracker demo ===\n")

    def make_200(to_tag: str) -> Response:
        return Response(
            status_code=200,
            reason_phrase="OK",
            headers={
                "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
                "From": "<sip:alice@pbx.local>;tag=caller",
                "To": f"<sip:bob@pbx.local>;tag={to_tag}",
                "Call-ID": "fork-demo@127.0.0.1",
                "CSeq": "1 INVITE",
                "Content-Length": "0",
            },
        )

    ft = ForkTracker()

    # Branch 1 arrives first
    r1 = make_200("branch-a")
    ft.add(r1)
    print(f"Branch A 200 OK (To-tag: {_extract_tag(r1.headers['To'])})")

    # Branch 2 arrives 50ms later (different proxy branch)
    r2 = make_200("branch-b")
    ft.add(r2)
    print(f"Branch B 200 OK (To-tag: {_extract_tag(r2.headers['To'])})")

    # Duplicate branch A re-transmitted — should be ignored
    ft.add(make_200("branch-a"))

    print(f"\nTotal unique dialogs: {len(ft.responses)}")
    print(f"Best (returned to caller): To={ft.best.headers['To']}")  # type: ignore[union-attr]
    print(f"Extra legs to terminate:  {len(ft.extra)}")
    for extra in ft.extra:
        print(f"  -> ACK+BYE for To={extra.headers['To']}")

    print("\nIn real usage, sipx auto-ACKs+BYEs the extra legs.")
    print(
        "The caller receives the best (first) 200 OK and calls client.ack() normally."
    )


if __name__ == "__main__":
    demo_fork_tracker()
