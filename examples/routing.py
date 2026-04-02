#!/usr/bin/env python3
"""
sipx — Route / Record-Route Processing (RFC 3261 Section 16)

Shows how route sets are built from Record-Route headers in responses
and applied to subsequent requests (ACK, BYE).

No network required — exercises routing logic in-memory.
"""

from sipx import Request, Response, RouteSet
from rich.console import Console

console = Console()


def main():
    console.print("[bold]sipx — Route / Record-Route Processing[/bold]\n")

    # --- 1. Build route set from response ---
    console.print("[bold]1. Extract RouteSet from Record-Route[/bold]")

    response = Response(
        status_code=200,
        reason_phrase="OK",
        headers={
            "Via": "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK776",
            "From": "<sip:alice@atlanta.com>;tag=1928301774",
            "To": "<sip:bob@biloxi.com>;tag=a6c85cf",
            "Call-ID": "a84b4c76e66710@pc33.atlanta.com",
            "CSeq": "314159 INVITE",
            "Record-Route": "<sip:proxy1.example.com;lr>, <sip:proxy2.example.com;lr>",
            "Contact": "<sip:bob@10.0.0.2:5060>",
        },
    )

    route_set = RouteSet.from_response(response)
    console.print(f"  Routes ({len(route_set.routes)}):")
    for i, route in enumerate(route_set.routes):
        console.print(f"    [{i}] {route}")
    console.print(f"  Is loose routing: {route_set.is_loose}")
    console.print(f"  Is empty: {route_set.is_empty}")

    # --- 2. Apply route set to a BYE request ---
    console.print("\n[bold]2. Apply RouteSet to BYE Request[/bold]")

    bye = Request(
        method="BYE",
        uri="sip:bob@biloxi.com",
        headers={
            "Via": "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bKbye1",
            "From": "<sip:alice@atlanta.com>;tag=1928301774",
            "To": "<sip:bob@biloxi.com>;tag=a6c85cf",
            "Call-ID": "a84b4c76e66710@pc33.atlanta.com",
            "CSeq": "1 BYE",
        },
    )

    console.print(f"  Before: URI={bye.uri}")
    console.print(f"          Route={bye.headers.get('Route', '(none)')}")

    route_set.apply(bye)

    console.print(f"  After:  URI={bye.uri}")
    console.print(f"          Route={bye.headers.get('Route', '(none)')}")

    # --- 3. Strict routing (no ;lr) ---
    console.print("\n[bold]3. Strict Routing (no ;lr parameter)[/bold]")

    strict_response = Response(
        status_code=200,
        headers={
            "Record-Route": "<sip:proxy-strict.example.com>",
            "Via": "SIP/2.0/UDP x;branch=z9hG4bK1",
            "From": "<sip:a@x>;tag=t1",
            "To": "<sip:b@x>;tag=t2",
            "Call-ID": "strict-test@x",
            "CSeq": "1 INVITE",
        },
    )

    strict_rs = RouteSet.from_response(strict_response)
    console.print(f"  Is loose: {strict_rs.is_loose}")

    ack = Request(
        method="ACK",
        uri="sip:bob@biloxi.com",
        headers={
            "Via": "SIP/2.0/UDP x;branch=z9hG4bK2",
            "From": "<sip:a@x>;tag=t1",
            "To": "<sip:b@x>;tag=t2",
            "Call-ID": "strict-test@x",
            "CSeq": "1 ACK",
        },
    )

    console.print(f"  Before: URI={ack.uri}")
    strict_rs.apply(ack)
    console.print(f"  After:  URI={ack.uri} (replaced with first route)")
    console.print(f"          Route={ack.headers.get('Route', '(none)')}")

    # --- 4. Empty route set ---
    console.print("\n[bold]4. No Record-Route (direct path)[/bold]")

    direct_response = Response(
        status_code=200,
        headers={
            "Via": "SIP/2.0/UDP x;branch=z9hG4bK3",
            "From": "<sip:a@x>;tag=t3",
            "To": "<sip:b@x>;tag=t4",
            "Call-ID": "direct@x",
            "CSeq": "1 INVITE",
        },
    )

    empty_rs = RouteSet.from_response(direct_response)
    console.print(f"  Routes: {len(empty_rs.routes)} (direct path, no proxies)")

    console.print("\n[bold green]Routing demo complete.[/bold green]")


if __name__ == "__main__":
    main()
